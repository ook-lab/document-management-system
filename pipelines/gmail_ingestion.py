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

from core.connectors.gmail_connector import GmailConnector
from core.connectors.google_drive import GoogleDriveConnector
from core.database.client import DatabaseClient
from pipelines.two_stage_ingestion import TwoStageIngestionPipeline


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
        self.ingestion_pipeline = TwoStageIngestionPipeline()

        logger.info(f"GmailIngestionPipeline初期化完了")
        logger.info(f"  - Gmail: {gmail_user_email}")
        logger.info(f"  - Label: {self.gmail_label}")
        logger.info(f"  - Email folder: {self.email_folder_id}")
        logger.info(f"  - Attachment folder: {self.attachment_folder_id}")

    def convert_email_to_html(
        self,
        message: Dict[str, Any],
        headers: Dict[str, str],
        parts: Dict[str, Any]
    ) -> str:
        """
        メールをHTML形式に変換（画像埋め込み）

        Args:
            message: Gmailのメッセージオブジェクト
            headers: メールヘッダー
            parts: extract_message_partsの結果

        Returns:
            完全なHTML文字列
        """
        # HTML本文がある場合はそれを使用
        if parts['text_html']:
            html_body = parts['text_html']
        elif parts['text_plain']:
            # テキストのみの場合は簡易HTML化
            text = parts['text_plain']
            html_body = f"<html><body><pre>{text}</pre></body></html>"
        else:
            html_body = "<html><body><p>本文がありません</p></body></html>"

        # BeautifulSoupで解析
        soup = BeautifulSoup(html_body, 'html.parser')

        # メールヘッダーを追加
        header_html = f"""
        <div style="border-bottom: 2px solid #ccc; padding: 10px; margin-bottom: 20px; font-family: Arial, sans-serif;">
            <p><strong>From:</strong> {headers.get('From', 'Unknown')}</p>
            <p><strong>To:</strong> {headers.get('To', 'Unknown')}</p>
            <p><strong>Subject:</strong> {headers.get('Subject', 'No Subject')}</p>
            <p><strong>Date:</strong> {headers.get('Date', 'Unknown')}</p>
        </div>
        """
        header_tag = BeautifulSoup(header_html, 'html.parser')
        soup.body.insert(0, header_tag)

        return str(soup)

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

    def process_single_email(
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

            # 4. メールを既読にマーク
            if mark_as_read:
                self.gmail.mark_as_read(message_id)

            result['success'] = True
            logger.info(f"メール処理完了: {message_id}")

        except Exception as e:
            logger.error(f"メール処理エラー ({message_id}): {e}", exc_info=True)
            result['error'] = str(e)

        return result

    def process_unread_emails(
        self,
        max_emails: int = 10,
        query: Optional[str] = None,
        mark_as_read: bool = True
    ) -> List[Dict[str, Any]]:
        """
        未読メールをまとめて処理

        Args:
            max_emails: 処理する最大件数
            query: Gmail検索クエリ（Noneの場合は「label:{self.gmail_label} is:unread」）
            mark_as_read: 処理後に既読にするか

        Returns:
            処理結果のリスト
        """
        # クエリが指定されていない場合は、設定されたラベルと未読条件を使用
        if query is None:
            query = f'label:{self.gmail_label} is:unread'

        logger.info("=" * 60)
        logger.info("未読メール処理開始")
        logger.info(f"  最大処理件数: {max_emails}")
        logger.info(f"  検索クエリ: {query}")
        logger.info("=" * 60)

        # 未読メール一覧を取得
        messages = self.gmail.list_messages(query=query, max_results=max_emails)
        logger.info(f"対象メール数: {len(messages)}件")

        results = []
        for i, msg in enumerate(messages, 1):
            logger.info(f"[{i}/{len(messages)}] 処理中...")
            result = self.process_single_email(
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

    # 未読メールを処理（最大10件）
    results = pipeline.process_unread_emails(max_emails=10, mark_as_read=True)

    # 結果を表示
    for result in results:
        print(f"Message ID: {result['message_id']}")
        print(f"  Success: {result['success']}")
        if result['email_html_file_id']:
            print(f"  Email HTML: {result['email_html_file_id']}")
        if result['attachment_file_ids']:
            print(f"  Attachments: {len(result['attachment_file_ids'])} files")
        if result['ingested_document_ids']:
            print(f"  Ingested: {len(result['ingested_document_ids'])} documents")
        if result['error']:
            print(f"  Error: {result['error']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
