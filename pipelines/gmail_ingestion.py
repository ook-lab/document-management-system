"""
Gmail統合パイプライン

Gmail → Google Drive → Supabase の流れでメールを処理

処理フロー:
1. Gmail APIで未読メール取得
2. 添付ファイル → Driveに保存
3. メール本文(HTML) → Driveに保存
4. DriveのファイルIDを使ってSupabaseに登録
5. メールを既読にマーク

設定方法: docs/GMAIL_INTEGRATION_SETUP.md を参照
"""
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger
from bs4 import BeautifulSoup
import base64

# プロジェクトルートをパスに追加
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# .envファイルを読み込む
from dotenv import load_dotenv
load_dotenv(root_dir / ".env")

from core.connectors.gmail_connector import GmailConnector
from core.connectors.google_drive import GoogleDriveConnector
from core.database.client import DatabaseClient
from pipelines.two_stage_ingestion import TwoStageIngestionPipeline
from core.processors.email_vision import EmailVisionProcessor
from core.ai.stage2_extractor import Stage2Extractor
from core.ai.llm_client import LLMClient
from core.utils.chunking import chunk_document
from config.workspaces import get_workspace_from_gmail_label


class GmailIngestionPipeline:
    """Gmail統合パイプライン"""

    def __init__(
        self,
        gmail_user_email: str,
        email_folder_id: Optional[str] = None,
        attachment_folder_id: Optional[str] = None,
        gmail_label: Optional[str] = None
    ):
        """
        Args:
            gmail_user_email: Gmailのメールアドレス（例: ookubo.y@workspace-o.com）
            email_folder_id: メール本文(HTML)保存先のDriveフォルダID（Noneの場合は環境変数から取得）
            attachment_folder_id: 添付ファイル保存先のDriveフォルダID（Noneの場合は環境変数から取得）
            gmail_label: 読み取り対象のGmailラベル（Noneの場合は環境変数から取得、デフォルト: TEST）
        """
        self.gmail_user_email = gmail_user_email
        self.email_folder_id = email_folder_id or os.getenv("GMAIL_EMAIL_FOLDER_ID")
        self.attachment_folder_id = attachment_folder_id or os.getenv("GMAIL_ATTACHMENT_FOLDER_ID")
        self.gmail_label = gmail_label or os.getenv("GMAIL_LABEL", "TEST")

        # コネクタの初期化
        self.gmail = GmailConnector(user_email=gmail_user_email)
        self.drive = GoogleDriveConnector()
        self.db = DatabaseClient()
        self.llm_client = LLMClient()
        self.ingestion_pipeline = TwoStageIngestionPipeline()
        self.email_vision_processor = EmailVisionProcessor()
        self.stage2_extractor = Stage2Extractor(llm_client=self.llm_client)

        logger.info(f"GmailIngestionPipeline初期化完了")
        logger.info(f"  - Gmail: {gmail_user_email}")
        logger.info(f"  - Label: {self.gmail_label}")
        logger.info(f"  - Email folder: {self.email_folder_id}")
        logger.info(f"  - Attachment folder: {self.attachment_folder_id}")

    def _embed_images_as_base64(self, soup) -> None:
        """
        HTMLの画像URLをBase64エンコードして埋め込む

        Args:
            soup: BeautifulSoupオブジェクト（直接編集される）
        """
        import base64
        import requests
        from urllib.parse import urlparse

        img_tags = soup.find_all('img')
        if not img_tags:
            return

        logger.info(f"画像を Base64 エンコード中: {len(img_tags)} 枚")

        success_count = 0
        skip_count = 0
        error_count = 0

        for img in img_tags:
            src = img.get('src', '')

            # すでにBase64の場合はスキップ
            if src.startswith('data:'):
                skip_count += 1
                continue

            # CID画像はスキップ（添付ファイルからの取得が必要）
            if src.startswith('cid:'):
                logger.debug(f"CID画像をスキップ: {src}")
                skip_count += 1
                continue

            # HTTP/HTTPS画像のみ処理
            if not (src.startswith('http://') or src.startswith('https://')):
                skip_count += 1
                continue

            try:
                # 画像をダウンロード（タイムアウト10秒、最大1MB）
                response = requests.get(
                    src,
                    timeout=10,
                    headers={'User-Agent': 'Mozilla/5.0'},
                    stream=True
                )
                response.raise_for_status()

                # Content-Lengthチェック（1MB制限）
                content_length = response.headers.get('Content-Length')
                if content_length and int(content_length) > 1024 * 1024:
                    logger.warning(f"画像が大きすぎるためスキップ: {src} ({content_length} bytes)")
                    skip_count += 1
                    continue

                # 画像データを取得
                image_data = b''
                total_size = 0
                for chunk in response.iter_content(chunk_size=8192):
                    total_size += len(chunk)
                    if total_size > 1024 * 1024:  # 1MB超えたら中断
                        logger.warning(f"画像が大きすぎるためスキップ: {src}")
                        skip_count += 1
                        break
                    image_data += chunk
                else:
                    # MIMEタイプを取得
                    content_type = response.headers.get('Content-Type', 'image/jpeg')
                    if ';' in content_type:
                        content_type = content_type.split(';')[0].strip()

                    # Base64エンコード
                    base64_data = base64.b64encode(image_data).decode('utf-8')
                    data_uri = f"data:{content_type};base64,{base64_data}"

                    # src属性を置き換え
                    img['src'] = data_uri
                    success_count += 1
                    logger.debug(f"✓ Base64化成功: {src[:50]}... ({len(image_data)} bytes)")

            except requests.exceptions.Timeout:
                logger.warning(f"画像ダウンロードタイムアウト: {src}")
                error_count += 1
            except requests.exceptions.RequestException as e:
                logger.warning(f"画像ダウンロード失敗: {src} - {e}")
                error_count += 1
            except Exception as e:
                logger.error(f"画像処理エラー: {src} - {e}")
                error_count += 1

        logger.info(f"Base64エンコード完了: 成功={success_count}, スキップ={skip_count}, エラー={error_count}")

    def convert_email_to_html(
        self,
        message: Dict[str, Any],
        headers: Dict[str, str],
        parts: Dict[str, Any]
    ) -> str:
        """
        メールをHTML形式に変換（画像Base64埋め込み）

        Args:
            message: Gmailのメッセージオブジェクト
            headers: メールヘッダー
            parts: extract_message_partsの結果

        Returns:
            完全なHTML文字列
        """
        import html as html_module

        # メールヘッダーを作成（HTMLエスケープ）
        from_escaped = html_module.escape(headers.get('From', 'Unknown'))
        to_escaped = html_module.escape(headers.get('To', 'Unknown'))
        subject_escaped = html_module.escape(headers.get('Subject', 'No Subject'))
        date_escaped = html_module.escape(headers.get('Date', 'Unknown'))

        header_html = f"""
        <div class="email-header" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 20px;
                    margin-bottom: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <h2 style="margin: 0 0 15px 0; font-size: 20px; font-weight: 600;">
                {subject_escaped}
            </h2>
            <div style="font-size: 14px; opacity: 0.95;">
                <p style="margin: 5px 0;"><strong>From:</strong> {from_escaped}</p>
                <p style="margin: 5px 0;"><strong>To:</strong> {to_escaped}</p>
                <p style="margin: 5px 0;"><strong>Date:</strong> {date_escaped}</p>
            </div>
        </div>
        """

        # HTML本文がある場合
        if parts['text_html']:
            logger.info("HTML版を使用")

            # BeautifulSoupで元のHTMLを解析
            from bs4 import BeautifulSoup
            original_soup = BeautifulSoup(parts['text_html'], 'html.parser')

            # 古いmeta charsetタグをすべて削除（UTF-8に統一するため）
            for meta in original_soup.find_all('meta'):
                if meta.get('http-equiv') == 'Content-Type' or meta.get('charset'):
                    meta.decompose()

            # headタグ内のstyleやscriptを抽出
            head_content = ''
            if original_soup.head:
                # headからtitleとmeta以外を抽出（style, script等）
                for child in original_soup.head.children:
                    if child.name in ['style', 'script', 'link']:
                        head_content += str(child) + '\n'

            # 画像をBase64エンコードして埋め込む（body抽出の前に実行）
            self._embed_images_as_base64(original_soup)

            # body部分の中身を抽出（Base64化後）
            if original_soup.body:
                # body内の全要素を文字列化
                email_body_content = ''.join(str(child) for child in original_soup.body.children)
            else:
                # bodyタグがない場合は全体を使用
                email_body_content = parts['text_html']

            # 画像が正しく埋め込まれたか確認
            base64_images = original_soup.find_all('img', src=lambda x: x and x.startswith('data:'))
            external_images = original_soup.find_all('img', src=lambda x: x and (x.startswith('http://') or x.startswith('https://')))

            image_notice = ""
            if base64_images and not external_images:
                # すべての画像がBase64化された
                image_notice = """
        <div class="image-notice" style="background: #d4edda; border-left: 4px solid #28a745; padding: 15px; margin: 20px; border-radius: 4px;">
            <p style="margin: 0; color: #155724;">
                <strong>✅ 画像埋め込み完了：</strong><br>
                すべての画像をBase64形式で埋め込みました。Google Driveのプレビューでも正しく表示されます。
            </p>
        </div>
        """
            elif external_images:
                # まだ外部画像が残っている
                image_notice = f"""
        <div class="image-notice" style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px; border-radius: 4px;">
            <p style="margin: 0; color: #856404;">
                <strong>⚠️ 画像表示について：</strong><br>
                一部の画像（{len(external_images)}枚）がBase64化できませんでした（大きすぎる、またはダウンロードエラー）。<br>
                すべての画像を表示するには、このファイルを<strong>ダウンロード</strong>してブラウザで開いてください。
            </p>
        </div>
        """

            final_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{subject_escaped}</title>
    {head_content}
    <style>
        body {{
            font-family: 'Helvetica Neue', Arial, 'Hiragino Kaku Gothic ProN', 'Hiragino Sans', Meiryo, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .email-container {{
            max-width: 900px;
            margin: 0 auto;
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .email-body-wrapper {{
            padding: 20px;
            overflow-x: auto;
        }}
        /* 画像のスタイル */
        img {{
            max-width: 100%;
            height: auto;
        }}
        img[src^="cid:"] {{
            border: 2px dashed #ccc;
            background-color: #f9f9f9;
            padding: 10px;
        }}
    </style>
</head>
<body>
    <div class="email-container">
        {header_html}
        {image_notice}
        <div class="email-body-wrapper">
            {email_body_content}
        </div>
    </div>
</body>
</html>"""
            return final_html

        elif parts['text_plain']:
            logger.info("プレーンテキスト版をHTML化")
            # テキストのみの場合は見やすくHTML化
            import re

            text = parts['text_plain']

            # 先にHTMLエスケープ
            text_escaped = html_module.escape(text)

            # その後でURLをリンクに変換
            text_html = re.sub(
                r'(https?://[^\s]+)',
                r'<a href="\1" target="_blank">\1</a>',
                text_escaped
            )

            # 改行を<br>に変換
            text_html = text_html.replace('\n', '<br>\n')

            final_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{subject_escaped}</title>
    <style>
        body {{
            font-family: 'Helvetica Neue', Arial, 'Hiragino Kaku Gothic ProN', 'Hiragino Sans', Meiryo, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .email-container {{
            max-width: 900px;
            margin: 0 auto;
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .email-body {{
            padding: 30px;
            line-height: 1.8;
            color: #333;
        }}
        a {{
            color: #0066cc;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="email-container">
        {header_html}
        <div class="email-body">
            {text_html}
        </div>
    </div>
</body>
</html>"""
            return final_html

        else:
            return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>No Content</title>
</head>
<body>
    <div class="email-container">
        {header_html}
        <div class="email-body">
            <p>本文がありません</p>
        </div>
    </div>
</body>
</html>"""

    def save_email_to_drive(
        self,
        message_id: str,
        subject: str,
        html_content: str
    ) -> Optional[str]:
        """
        メール本文をHTMLファイルとしてDriveに保存

        Args:
            message_id: メッセージID
            subject: 件名
            html_content: HTML本文

        Returns:
            DriveのファイルID、失敗時はNone
        """
        # 安全なファイル名を生成
        safe_subject = "".join(c for c in subject if c.isalnum() or c in (' ', '-', '_')).strip()
        if not safe_subject:
            safe_subject = "no_subject"

        # タイムスタンプ付きファイル名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"{timestamp}_{safe_subject}_{message_id[:8]}.html"

        # Driveにアップロード（メール本文用フォルダ）
        file_id = self.drive.upload_file(
            file_content=html_content,
            file_name=file_name,
            mime_type='text/html',
            folder_id=self.email_folder_id
        )

        if file_id:
            logger.info(f"メール本文をDriveに保存: {file_name}")
        else:
            logger.error(f"メール本文の保存に失敗: {file_name}")

        return file_id

    def save_attachment_to_drive(
        self,
        message_id: str,
        attachment_info: Dict[str, Any]
    ) -> Optional[str]:
        """
        添付ファイルをDriveに保存

        Args:
            message_id: メッセージID
            attachment_info: 添付ファイル情報

        Returns:
            DriveのファイルID、失敗時はNone
        """
        attachment_id = attachment_info['attachmentId']
        filename = attachment_info['filename']
        mime_type = attachment_info['mimeType']

        # 添付ファイルのデータを取得
        file_data = self.gmail.get_attachment(message_id, attachment_id)
        if not file_data:
            logger.error(f"添付ファイル取得失敗: {filename}")
            return None

        # Driveにアップロード（添付ファイル用フォルダ）
        file_id = self.drive.upload_file(
            file_content=file_data,
            file_name=filename,
            mime_type=mime_type,
            folder_id=self.attachment_folder_id
        )

        if file_id:
            logger.info(f"添付ファイルをDriveに保存: {filename}")
        else:
            logger.error(f"添付ファイルの保存に失敗: {filename}")

        return file_id

    async def process_single_email(
        self,
        message_id: str,
        mark_as_read: bool = True
    ) -> Dict[str, Any]:
        """
        1件のメールを処理

        Args:
            message_id: メッセージID
            mark_as_read: 処理後に既読にするか

        Returns:
            処理結果の辞書
        """
        result = {
            'message_id': message_id,
            'success': False,
            'email_html_file_id': None,
            'attachment_file_ids': [],
            'ingested_document_ids': [],
            'error': None
        }

        try:
            # メール詳細を取得
            logger.info(f"メール処理開始: {message_id}")
            message = self.gmail.get_message(message_id)
            if not message:
                result['error'] = "メール取得失敗"
                return result

            # ヘッダーとパートを解析
            headers = self.gmail.parse_message_headers(message)
            parts = self.gmail.extract_message_parts(message)

            subject = headers.get('Subject', 'No Subject')
            logger.info(f"  件名: {subject}")
            logger.info(f"  添付ファイル数: {len(parts['attachments'])}")

            # 1. メール本文をHTMLに変換してDriveに保存
            html_content = self.convert_email_to_html(message, headers, parts)
            email_file_id = self.save_email_to_drive(message_id, subject, html_content)

            if email_file_id:
                result['email_html_file_id'] = email_file_id

            # 2. 添付ファイルをDriveに保存
            for attachment in parts['attachments']:
                file_id = self.save_attachment_to_drive(message_id, attachment)
                if file_id:
                    result['attachment_file_ids'].append(file_id)

            # 3. 添付ファイルをSupabaseに登録（Two-Stage Ingestion）
            for file_id in result['attachment_file_ids']:
                try:
                    # ファイル情報を取得
                    file_info = self.drive.service.files().get(
                        fileId=file_id,
                        fields='name, mimeType, size'
                    ).execute()

                    # PDFのみ処理（必要に応じて他の形式も追加）
                    if file_info['mimeType'] == 'application/pdf':
                        logger.info(f"  PDFをIngestion開始: {file_info['name']}")
                        doc_id = await self.ingestion_pipeline.process_file(
                            source_id=file_id,
                            source_type='gmail_attachment',
                            file_name=file_info['name']
                        )
                        if doc_id:
                            result['ingested_document_ids'].append(doc_id)

                except Exception as e:
                    logger.error(f"  添付ファイルのIngestion失敗: {e}")

            # 4. メール本文をVision処理してSupabaseに登録
            try:
                logger.info(f"  メール本文のVision処理開始")

                # メタデータを準備
                email_metadata = {
                    'from': headers.get('From', ''),
                    'to': headers.get('To', ''),
                    'subject': subject,
                    'date': headers.get('Date', '')
                }

                # HTMLメールをVision処理
                vision_result = await self.email_vision_processor.extract_email_content(
                    html_content=html_content,
                    email_metadata=email_metadata
                )

                logger.info(f"  Vision処理完了: {len(vision_result.get('extracted_text', ''))} 文字抽出")

                # Stage 2: リッチ化処理（Gemini 2.5 Flash使用）
                logger.info(f"  メール本文のStage 2処理開始（リッチ化）")

                # Gmailラベルからworkspaceを判定
                workspace = get_workspace_from_gmail_label(self.gmail_label)

                # Stage 1結果を構築（Visionの結果を疑似的にStage 1として扱う）
                stage1_result = {
                    "doc_type": "email",  # メールとして分類
                    "workspace": workspace,
                    "confidence": 1.0
                }

                # メール全文を構築（Stage 2に渡す）
                full_text_for_stage2 = f"""送信者: {email_metadata['from']}
受信者: {email_metadata['to']}
件名: {email_metadata['subject']}
日時: {email_metadata['date']}

{vision_result.get('extracted_text', '')}
"""

                # Stage 2でメタデータ抽出、タグ付け、構造化
                stage2_result = self.stage2_extractor.extract_metadata(
                    full_text=full_text_for_stage2,
                    file_name=f"{subject}_{message_id[:8]}.html",
                    stage1_result=stage1_result,
                    workspace=workspace,
                    tier="email_stage2_extraction"  # メール専用のGemini 2.5 Flash使用
                )

                logger.info(f"  Stage 2処理完了: doc_type={stage2_result.get('doc_type')}, tags={stage2_result.get('tags', [])}")

                # メール内容をSupabaseに直接保存
                # メールテキストを整形（Stage 2の結果を使用）
                email_text_content = f"""メール情報:
送信者: {email_metadata['from']}
受信者: {email_metadata['to']}
件名: {email_metadata['subject']}
日時: {email_metadata['date']}

要約:
{stage2_result.get('summary', vision_result.get('summary', ''))}

本文:
{vision_result.get('extracted_text', '')}

重要な情報:
{chr(10).join('- ' + info for info in vision_result.get('key_information', []))}
"""

                # Embeddingを生成
                embedding = self.llm_client.generate_embedding(email_text_content)

                # Supabaseに保存（workspaceベースのスキーマ + Stage 2結果）
                import hashlib
                content_hash = hashlib.sha256(email_text_content.encode('utf-8')).hexdigest()

                # Stage 2のメタデータをマージ
                stage2_metadata = stage2_result.get('metadata', {})
                merged_metadata = {
                    'from': email_metadata['from'],
                    'to': email_metadata['to'],
                    'subject': email_metadata['subject'],
                    'date': email_metadata['date'],
                    'gmail_label': self.gmail_label,
                    'workspace': workspace,
                    'summary': stage2_result.get('summary', vision_result.get('summary', '')),
                    'key_information': vision_result.get('key_information', []),
                    'has_images': vision_result.get('has_images', False),
                    'links': vision_result.get('links', []),
                    **stage2_metadata  # Stage 2の構造化メタデータを追加
                }

                email_doc = {
                    'source_type': 'gmail',
                    'source_id': email_file_id,
                    'source_url': f"https://drive.google.com/file/d/{email_file_id}/view",
                    'drive_file_id': email_file_id,
                    'file_name': f"{subject}_{message_id[:8]}.html",
                    'file_type': 'email',
                    'doc_type': stage2_result.get('doc_type', 'email'),  # Stage 2の分類を使用
                    'workspace': workspace,
                    'full_text': email_text_content,
                    'summary': stage2_result.get('summary', vision_result.get('summary', '')),
                    'tags': stage2_result.get('tags', []),  # Stage 2のタグを追加
                    'document_date': stage2_result.get('document_date'),  # Stage 2の日付を追加
                    'embedding': embedding,
                    'metadata': merged_metadata,
                    'extracted_tables': stage2_result.get('tables', []),  # Stage 2のテーブルを追加
                    'content_hash': content_hash,
                    'confidence': 1.0,
                    'extraction_confidence': stage2_result.get('extraction_confidence', 1.0),
                    'total_confidence': 1.0,
                    'processing_status': 'completed',
                    'processing_stage': 'email_stage2',
                    'stage1_model': 'gemini-2.0-flash-lite',
                    'stage2_model': 'gemini-2.5-flash',
                    'chunking_strategy': 'small_large_2tier'
                }

                try:
                    email_doc_result = await self.db.insert_document('documents', email_doc)
                    logger.debug(f"  Supabase insert result type: {type(email_doc_result)}, keys: {email_doc_result.keys() if isinstance(email_doc_result, dict) else 'N/A'}")
                    if email_doc_result:
                        email_doc_id = email_doc_result.get('id')
                        result['ingested_document_ids'].append(email_doc_id)
                        logger.info(f"  メール本文のSupabase保存完了: {email_doc_id}")

                        # チャンク化処理（2階層: 小・大）
                        logger.info(f"  メール本文の2階層チャンク化開始（小・大）")
                        try:
                            extracted_text = vision_result.get('extracted_text', '')

                            # 小チャンク（検索用、300文字）
                            small_chunks = chunk_document(
                                text=extracted_text,
                                chunk_size=300,
                                chunk_overlap=50
                            )

                            if small_chunks:
                                logger.info(f"  小チャンク作成完了: {len(small_chunks)}個のチャンク")

                                # 小チャンクにembeddingを生成して保存
                                small_chunk_success_count = 0
                                for i, chunk in enumerate(small_chunks):
                                    try:
                                        chunk_text = chunk.get('chunk_text', '')
                                        chunk_embedding = self.llm_client.generate_embedding(chunk_text)

                                        chunk_doc = {
                                            'document_id': email_doc_id,
                                            'chunk_index': chunk.get('chunk_index', 0),
                                            'chunk_text': chunk_text,
                                            'chunk_size': chunk.get('chunk_size', len(chunk_text)),
                                            'chunk_type': 'small',
                                            'embedding': chunk_embedding
                                        }

                                        chunk_result = await self.db.insert_document('document_chunks', chunk_doc)
                                        if chunk_result:
                                            small_chunk_success_count += 1
                                    except Exception as chunk_insert_error:
                                        logger.error(f"  小チャンク{i+1}保存エラー: {type(chunk_insert_error).__name__}: {chunk_insert_error}")
                                        logger.debug(f"  エラー詳細: {repr(chunk_insert_error)}", exc_info=True)

                                logger.info(f"  小チャンク保存完了: {small_chunk_success_count}/{len(small_chunks)}個")
                            else:
                                logger.warning(f"  小チャンク作成失敗: テキストが短すぎる可能性")

                            # 大チャンク（回答用、全文）
                            large_doc = {
                                'document_id': email_doc_id,
                                'chunk_index': 0,
                                'chunk_text': extracted_text,
                                'chunk_size': len(extracted_text),
                                'chunk_type': 'large',
                                'embedding': embedding  # 既に生成済みの全文embedding
                            }

                            try:
                                large_chunk_result = await self.db.insert_document('document_chunks', large_doc)
                                if large_chunk_result:
                                    logger.info(f"  大チャンク保存完了")
                                else:
                                    logger.error(f"  大チャンク保存失敗")
                            except Exception as large_chunk_error:
                                logger.error(f"  大チャンク保存エラー: {type(large_chunk_error).__name__}: {large_chunk_error}")
                                logger.debug(f"  エラー詳細: {repr(large_chunk_error)}", exc_info=True)

                        except Exception as chunk_error:
                            logger.error(f"  チャンク化エラー: {chunk_error}", exc_info=True)

                except Exception as db_error:
                    logger.error(f"  Supabase保存エラー: {type(db_error).__name__}: {db_error}", exc_info=True)

            except Exception as e:
                logger.error(f"  メール本文のVision処理失敗: {e}", exc_info=True)

            # 5. メールを既読にマーク
            if mark_as_read:
                self.gmail.mark_as_read(message_id)

            result['success'] = True
            logger.info(f"メール処理完了: {message_id}")

        except Exception as e:
            logger.error(f"メール処理エラー ({message_id}): {e}", exc_info=True)
            result['error'] = str(e)

        return result

    async def process_emails(
        self,
        max_emails: int = 10,
        query: Optional[str] = None,
        mark_as_read: bool = False
    ) -> List[Dict[str, Any]]:
        """
        メールをまとめて処理

        Args:
            max_emails: 処理する最大件数
            query: Gmail検索クエリ（Noneの場合は「label:{self.gmail_label}」）
            mark_as_read: 処理後に既読にするか

        Returns:
            処理結果のリスト
        """
        # クエリが指定されていない場合は、設定されたラベルを使用（未読限定なし）
        if query is None:
            query = f'label:{self.gmail_label}'

        logger.info("=" * 60)
        logger.info("メール処理開始")
        logger.info(f"  最大処理件数: {max_emails}")
        logger.info(f"  検索クエリ: {query}")
        logger.info(f"  既読マーク: {mark_as_read}")
        logger.info("=" * 60)

        # メール一覧を取得
        messages = self.gmail.list_messages(query=query, max_results=max_emails)
        logger.info(f"対象メール数: {len(messages)}件")

        results = []
        for i, msg in enumerate(messages, 1):
            logger.info(f"[{i}/{len(messages)}] 処理中...")
            result = await self.process_single_email(
                message_id=msg['id'],
                mark_as_read=mark_as_read
            )
            results.append(result)

        # サマリー
        success_count = sum(1 for r in results if r['success'])
        logger.info("=" * 60)
        logger.info("処理完了")
        logger.info(f"  成功: {success_count}/{len(results)}")
        logger.info(f"  失敗: {len(results) - success_count}/{len(results)}")
        logger.info("=" * 60)

        return results


async def main():
    """メインエントリーポイント"""
    # 環境変数から設定を取得
    gmail_user = os.getenv("GMAIL_USER_EMAIL", "ookubo.y@workspace-o.com")

    # パイプラインの初期化
    pipeline = GmailIngestionPipeline(gmail_user_email=gmail_user)

    # ラベル「TEST」のメールを処理（最大10件、既読マークなし）
    results = await pipeline.process_emails(max_emails=10, mark_as_read=False)

    # 結果を表示
    print("\n" + "=" * 80)
    print("📧 Gmail取り込み結果")
    print("=" * 80)

    for result in results:
        print(f"\nMessage ID: {result['message_id']}")
        print(f"  Success: {result['success']}")
        if result['email_html_file_id']:
            file_id = result['email_html_file_id']
            print(f"  Email HTML ID: {file_id}")
            print(f"  📥 ダウンロードリンク:")
            print(f"     https://drive.google.com/uc?export=download&id={file_id}")
            print(f"  👁️  プレビュー:")
            print(f"     https://drive.google.com/file/d/{file_id}/view")
        if result['attachment_file_ids']:
            print(f"  Attachments: {len(result['attachment_file_ids'])} files")
        if result['ingested_document_ids']:
            print(f"  Ingested: {len(result['ingested_document_ids'])} documents")
        if result['error']:
            print(f"  ❌ Error: {result['error']}")

    print("\n" + "=" * 80)
    print("💡 ヒント: プレビューで正しく表示されない場合は、ダウンロードリンクから")
    print("   ファイルをダウンロードしてブラウザで開いてください。")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
