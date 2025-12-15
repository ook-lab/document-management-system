"""
2段階取り込みパイプライン（v4.0: ハイブリッドAI版）
Stage A/B/C実装版（Stage C: Claude詳細抽出）
"""

import os
import asyncio
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from loguru import logger
import hashlib
import json
import traceback

from A_common.connectors.google_drive import GoogleDriveConnector
from A_common.processors.pdf import PDFProcessor
from A_common.processors.office import OfficeProcessor
from D_stage_a_classifier.classifier import StageAClassifier
from F_stage_c_extractor.extractor import StageCExtractor
# from C_ai_common.embeddings.embeddings import EmbeddingClient  # 768次元 - 使用しない
from A_common.database.client import DatabaseClient
from C_ai_common.llm_client.llm_client import LLMClient
from A_common.utils.chunking import TextChunker, ParentChildChunker
from A_common.utils.synthetic_chunks import create_all_synthetic_chunks
from A_common.utils.date_extractor import DateExtractor
from A_common.processing.metadata_chunker import MetadataChunker
from A_common.config.yaml_loader import get_classification_yaml_string
from A_common.config.model_tiers import ModelTier


def flatten_metadata_to_text(metadata: Dict[str, Any]) -> str:
    """
    メタデータを検索可能なテキストに変換（再帰的に全フィールド抽出）
    activities, recruitment, organization などの構造化データを完全に展開
    """
    searchable_parts = []

    def extract_values(obj, prefix=''):
        """再帰的に辞書やリストから値を抽出"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                # メタ情報やデバッグ用フィールドはスキップ
                if key in ['extractor', 'num_pages', 'extraction_method', 'confidence']:
                    continue
                extract_values(value, f"{prefix}{key}: " if prefix or key not in ['weekly_schedule', 'text_blocks'] else '')
        elif isinstance(obj, list):
            for item in obj:
                extract_values(item, prefix)
        elif obj is not None and str(obj).strip():
            # 有効な値のみ追加
            searchable_parts.append(f"{prefix}{str(obj)}" if prefix else str(obj))

    # 除外フィールド（検索に不要、または大きすぎる）
    excluded_fields = ['weekly_schedule', 'text_blocks', 'extractor', 'num_pages']

    # 全メタデータフィールドを再帰的に抽出
    for key, value in metadata.items():
        if key not in excluded_fields:
            extract_values(value)

    # weekly_schedule の展開（従来通り）
    if 'weekly_schedule' in metadata and metadata['weekly_schedule']:
        for day_schedule in metadata['weekly_schedule']:
            if 'date' in day_schedule:
                searchable_parts.append(day_schedule['date'])
            if 'day_of_week' in day_schedule:
                searchable_parts.append(day_schedule['day_of_week'])
            if 'day' in day_schedule:
                searchable_parts.append(f"{day_schedule['day']}曜日")
            if 'events' in day_schedule and day_schedule['events']:
                searchable_parts.extend(day_schedule['events'])
            if 'note' in day_schedule and day_schedule['note']:
                searchable_parts.append(day_schedule['note'])
            if 'class_schedules' in day_schedule:
                for class_schedule in day_schedule['class_schedules']:
                    if 'class' in class_schedule:
                        searchable_parts.append(class_schedule['class'])
                    if 'subjects' in class_schedule and class_schedule['subjects']:
                        searchable_parts.extend(class_schedule['subjects'])
                    if 'periods' in class_schedule and class_schedule['periods']:
                        for period in class_schedule['periods']:
                            if 'subject' in period:
                                searchable_parts.append(period['subject'])
                            if 'time' in period:
                                searchable_parts.append(period['time'])

    # text_blocks の展開（従来通り）
    if 'text_blocks' in metadata and metadata['text_blocks']:
        for block in metadata['text_blocks']:
            if 'title' in block and block['title']:
                searchable_parts.append(block['title'])
            if 'content' in block and block['content']:
                searchable_parts.append(block['content'])

    return ' '.join(searchable_parts)

PROCESSING_STATUS = {
    "PENDING": "pending",
    "COMPLETED": "completed",
    "FAILED": "failed",
    "SKIPPED": "skipped"
}

class TwoStageIngestionPipeline:
    """2段階取り込みパイプライン"""
    
    def __init__(self, temp_dir: str = "./temp"):

        self.llm_client = LLMClient()
        self.drive = GoogleDriveConnector()
        self.db = DatabaseClient()
        self.date_extractor = DateExtractor()  # 日付抽出ユーティリティ
        self.yaml_string = get_classification_yaml_string()

        self.pdf_processor = PDFProcessor(llm_client=self.llm_client)
        self.office_processor = OfficeProcessor()

        self.stageA_classifier = StageAClassifier(llm_client=self.llm_client)
        self.stageC_extractor = StageCExtractor(llm_client=self.llm_client)
        # EmbeddingはLLMClient経由で生成（1536次元）
        # self.embeddings = EmbeddingClient()  # 削除
        
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # Stage Cは完全リレー方式（判定なし、Stage Aの結果を必ずStage Cへ）

        logger.info("TwoStageIngestionPipeline初期化完了 (完全リレー方式: Gemini→Haiku)")
    
    def _extract_text(self, local_path: str, mime_type: str) -> Dict[str, Any]:
        """ファイルタイプに応じてテキスト抽出をルーティング"""
        
        logger.debug(f"テキスト抽出開始: {local_path}, mime_type={mime_type}")
        logger.debug(f"ファイル存在確認: {Path(local_path).exists()}")
        logger.debug(f"ファイルサイズ: {Path(local_path).stat().st_size if Path(local_path).exists() else 'N/A'} bytes")
        
        mime_map = {
            "application/pdf": self.pdf_processor.extract_text,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": self.office_processor.extract_from_docx,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": self.office_processor.extract_from_xlsx,
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": self.office_processor.extract_from_pptx,
        }
        
        processor = mime_map.get(mime_type)
        if processor:
            result = processor(local_path)
            logger.debug(f"抽出結果: success={result.get('success')}, content_length={len(result.get('content', ''))}")
            return result
        
        return {"content": "", "metadata": {}, "success": False, "error_message": f"Unsupported MIME Type: {mime_type}"}

    def _get_file_type(self, mime_type: str) -> str:
        """MIME Typeからfile_typeを判定"""
        mapping = {
            "application/pdf": "pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
        }
        return mapping.get(mime_type, "other")
    
    def _should_run_stageC(self, stageA_result: Dict[str, Any], extracted_text: str) -> bool:
        """
        Stage Cを実行すべきかどうか判定（完全リレー方式）

        【アーキテクチャ】
        - Stage A (Gemini): 文書の分類と基本情報の抽出
        - Stage B (Gemini Vision): Vision処理（必要な場合）
        - Stage C (Claude Haiku): Stage Aの結果を受けて構造化・意味付け

        テキストが存在する限り、Stage Aの結果は必ずStage C（Haiku）に渡して構造化する。
        信頼度に関係なく、判定なしの完全リレー方式で動作する。
        """

        # 抽出テキストが空の場合のみスキップ
        if not extracted_text or not extracted_text.strip():
            logger.info("[Stage C] テキストが空のためスキップ")
            return False

        # テキストがある限り、文字数に関係なく無条件でStage C（構造化プロセス）へ
        doc_type = stageA_result.get('doc_type', 'other')
        logger.info(f"[Stage C] 構造化プロセスへ移行 ({doc_type}, テキスト長={len(extracted_text.strip())}文字)")
        return True

    async def process_file(
        self,
        file_meta: Dict[str, Any],
        workspace: str = "personal",
        force_reprocess: bool = False,
        source_type: str = "drive"
    ) -> Optional[Dict[str, Any]]:
        """単一ファイルを2段階で処理"""
        file_id = file_meta['id']
        file_name = file_meta['name']
        mime_type = file_meta.get('mimeType', 'application/octet-stream')
        doc_type = file_meta.get('doc_type', 'other')  # doc_typeを取得（デフォルト: other）

        # source_typeはfile_metaから取得する（指定があればそちらを優先）
        if 'source_type' in file_meta:
            source_type = file_meta['source_type']

        logger.info(f"=== 2段階処理開始: {file_name} ===")

        existing = self.db.get_document_by_source_id(file_id)
        if existing and not force_reprocess:
            logger.warning(f"既に処理済み (Source ID): {file_name}")
            return existing

        if existing and force_reprocess:
            logger.info(f"🔄 再処理モード: 既存レコードを上書きします")

        # ✅ Classroom投稿の場合、display_sent_atを取得してreference_dateとして使用
        reference_date = None
        if existing and existing.get('display_sent_at'):
            reference_date = str(existing['display_sent_at']).split('T')[0]  # YYYY-MM-DD形式に変換
            logger.info(f"[Classroom] reference_date={reference_date} (display_sent_at から取得)")
        elif 'display_sent_at' in file_meta:
            reference_date = str(file_meta['display_sent_at']).split('T')[0]
            logger.info(f"[Classroom] reference_date={reference_date} (file_meta から取得)")
        
        local_path = None
        # extraction_resultを初期化（NameError回避）
        extraction_result = {"success": False, "content": "", "metadata": {}, "error_message": "未実行"}

        try:
            # ============================================
            # ファイルダウンロード
            # ============================================
            local_path = self.drive.download_file(file_id, file_name, self.temp_dir)
            logger.debug(f"ダウンロード完了: {local_path}")

            # ============================================
            # テキスト抽出（Stage 1の前に実行）
            # ============================================
            extraction_result = self._extract_text(local_path, mime_type)

            if not extraction_result["success"]:
                logger.warning(f"テキスト抽出失敗: {file_name}")
                logger.warning(f"エラー詳細: {extraction_result.get('error_message')}")
                extracted_text = ""
            else:
                extracted_text = extraction_result["content"]

            base_metadata = extraction_result.get("metadata", {})

            # ============================================
            # Stage 1: Gemini分類（テキストを渡す）
            # ============================================
            logger.info("[Stage 1] Gemini分類開始...")
            stageA_result = await self.stageA_classifier.classify(
                file_path=Path(local_path),
                doc_types_yaml=self.yaml_string,
                mime_type=mime_type,
                text_content=extracted_text
            )

            # Stage1はdoc_typeとworkspaceを返さない（入力元で決定されるため）
            # workspaceは引数で渡された値をそのまま使用
            summary = stageA_result.get('summary', '')
            relevant_date = stageA_result.get('relevant_date')
            document_date = None  # Stage Cで設定される可能性あり（初期化必須）

            logger.info(f"[Stage A] 完了: summary={summary[:50] if summary else ''}...")

            # ============================================
            # テキスト抽出が失敗した場合でもsummaryを使用
            # ============================================
            if not extraction_result["success"]:
                logger.warning("[テキスト抽出] 失敗 → summaryをfull_textとして使用")
                extracted_text = summary

            # ============================================
            # Stage C判定・実行（テキスト抽出失敗でも実行）
            # ============================================
            if self._should_run_stageC(stageA_result, extracted_text):
                logger.info("[Stage C] Claude詳細抽出開始...")
                try:
                    stageC_result = self.stageC_extractor.extract_metadata(
                        file_name=file_name,
                        stage1_result=stageA_result,  # StageCExtractorは stage1_result を期待
                        workspace=workspace,  # 引数で渡された元のworkspaceを使用
                        reference_date=reference_date,  # ✅ Classroom投稿の場合は投稿日を渡す
                        # 添付ファイルから抽出したテキストを渡す
                        attachment_text=extracted_text if extracted_text else None,
                    )

                    # Stage Cの結果を反映（doc_typeは使わない）
                    summary = stageC_result.get('summary', summary)
                    document_date = stageC_result.get('document_date')
                    event_dates = stageC_result.get('event_dates', [])  # イベント日付配列を取得
                    tags = stageC_result.get('tags', [])
                    tables = stageC_result.get('tables', [])  # 表データを取得
                    stageC_metadata = stageC_result.get('metadata', {})

                    # metadataをマージ（Stage C優先）
                    metadata = {
                        **base_metadata,
                        **stageC_metadata,
                        'stagec_attempted': True  # 新しい命名規則
                    }
                    if tags:
                        metadata['tags'] = tags
                    if document_date:
                        metadata['document_date'] = document_date
                    if event_dates:
                        metadata['event_dates'] = event_dates  # イベント日付配列をmetadataに追加
                    if tables:
                        metadata['tables'] = tables  # 表データをmetadataに追加

                    processing_stage = 'stagea_and_stagec'  # 新しい命名規則
                    stagec_model = ModelTier.STAGEC_EXTRACTOR["model"]  # 設定ファイルから参照

                    logger.info(f"[Stage C] 完了: metadata_fields={len(stageC_metadata)}")

                except Exception as e:
                    error_msg = str(e)
                    error_traceback = traceback.format_exc()
                    # KeyError回避: エラーメッセージを安全に文字列化
                    safe_error_msg = error_msg.replace('{', '{{').replace('}', '}}')
                    safe_traceback = error_traceback.replace('{', '{{').replace('}', '}}')
                    logger.error(f"[Stage C] 処理エラー: {safe_error_msg}\n{safe_traceback}")

                    # エラー情報をmetadataに記録
                    metadata = {
                        **base_metadata,
                        'stagec_attempted': True,
                        'stagec_error': str(e),
                        'stagec_error_type': type(e).__name__,
                        'stagec_error_timestamp': datetime.now().isoformat()
                    }

                    processing_stage = 'stagec_failed'
                    stagec_model = None
            else:
                # Stage Aのみで完結
                processing_stage = 'stagea_only'
                metadata = {**base_metadata, 'stagec_attempted': False}
                stagec_model = None

            # ============================================
            # コンテンツハッシュ生成
            # ============================================
            content_hash = hashlib.sha256(extracted_text.encode('utf-8')).hexdigest() if extracted_text else None
            
            # ============================================
            # データベース保存（Null文字除去 + 重複エラーハンドリング）
            # ============================================
            # Null文字を除去
            if extracted_text:
                extracted_text = extracted_text.replace('\x00', '')
            if summary:
                summary = summary.replace('\x00', '')

            # metadata.tables から extracted_tables を抽出
            extracted_tables = None
            if 'tables' in metadata and metadata['tables']:
                extracted_tables = metadata['tables']

            # Vision処理に使用したモデル情報を取得
            vision_model = base_metadata.get('vision_model', None)  # Gemini Vision等

            # イベント日付配列を取得（Stage Cで抽出されたもの）
            event_dates_array = event_dates if 'event_dates' in locals() and event_dates else []

            # ============================================
            # すべての日付を抽出（正規表現ベース + AI結果）
            # 【重要】日付は最優先検索項目として、漏れなく抽出
            # ============================================
            all_mentioned_dates = []
            try:
                # 正規表現で本文からすべての日付を抽出
                regex_extracted_dates = self.date_extractor.extract_all_dates(
                    text=extracted_text,
                    reference_date=reference_date  # Classroom投稿日などを基準に相対日付を計算
                )

                # AIが抽出したevent_datesと統合
                all_dates_set = set(regex_extracted_dates)
                if event_dates_array:
                    all_dates_set.update(event_dates_array)

                # document_dateも追加
                if document_date:
                    all_dates_set.add(document_date)

                # display_sent_atも追加（投稿日も検索対象）
                if reference_date:
                    all_dates_set.add(reference_date)

                # リストに変換してソート
                all_mentioned_dates = sorted(list(all_dates_set))

                logger.info(f"[日付統合] 合計{len(all_mentioned_dates)}件の日付を抽出: {all_mentioned_dates[:10]}...")

            except Exception as e:
                logger.error(f"日付抽出エラー: {e}", exc_info=True)

            document_data = {
                "source_type": source_type,  # 引数またはfile_metaから取得した値を使用
                "source_id": file_id,
                "source_url": f"https://drive.google.com/file/d/{file_id}/view",
                "file_name": file_name,
                "file_type": self._get_file_type(mime_type),
                "doc_type": workspace,  # doc_typeは入力元で決定（workspaceと同じ値を使用）
                "workspace": workspace,  # 引数で渡された値を使用（入力元で決定）
                "attachment_text": extracted_text,  # 添付ファイルから抽出したテキスト（source_documentsテーブルのカラムに対応）
                "summary": summary,
                "metadata": metadata,
                # extracted_tables と event_dates は metadata 内に含まれているため、トップレベルカラムから削除
                "all_mentioned_dates": all_mentioned_dates,  # 正規表現+AI統合による全日付配列（検索最優先）
                "content_hash": content_hash,
                "processing_status": PROCESSING_STATUS["COMPLETED"],
                "processing_stage": processing_stage,
                "stagea_classifier_model": ModelTier.STAGE1_CLASSIFIER["model"],  # B1更新（小文字）
                "stagec_extractor_model": stagec_model,  # Stage C抽出モデル
                "stageb_vision_model": vision_model,  # B1更新（小文字）
                "relevant_date": relevant_date,
            }

            try:
                # upsertを使用
                # force_reprocess=True時は全フィールドを更新するが、GAS由来のフィールドは保持
                preserve_fields = ['doc_type', 'workspace', 'source_type', 'display_sender', 'classroom_sender_email', 'display_sent_at', 'display_subject', 'classroom_course_id', 'classroom_course_name'] if force_reprocess else []
                result = await self.db.upsert_document(
                    'source_documents',  # 3層アーキテクチャのテーブル名に修正
                    document_data,
                    conflict_column='source_id',
                    force_update=force_reprocess,
                    preserve_fields=preserve_fields
                )
                document_id = result.get('id')
                logger.info(f"Document保存完了（upsert, force_update={force_reprocess}）: {document_id}")

                # ============================================
                # 再処理時の既存チャンク削除
                # ============================================
                if force_reprocess and document_id:
                    logger.info(f"  🔄 再処理モード: 既存チャンクを削除します")
                    try:
                        delete_result = self.db.client.table('search_index').delete().eq('document_id', document_id).execute()
                        deleted_count = len(delete_result.data) if delete_result.data else 0
                        logger.info(f"  既存チャンク削除完了: {deleted_count}個")
                    except Exception as e:
                        logger.warning(f"  既存チャンク削除エラー（継続）: {e}")

                # ============================================
                # チャンク化処理（B2: メタデータ別ベクトル化戦略対応）
                # - メタデータチャンク（タイトル、サマリー、日付、タグ）
                # - 小チャンク検索用
                # - 大チャンク回答用
                # - 合成チャンク
                # ============================================
                if extracted_text and document_id:
                    logger.info(f"  ドキュメントのチャンク化開始（メタデータ + 小 + 合成）")
                    try:
                        # Classroom投稿本文を取得
                        display_subject = None
                        if existing and existing.get('display_subject'):
                            display_subject = existing.get('display_subject')
                        elif 'display_subject' in file_meta:
                            display_subject = file_meta.get('display_subject')

                        # チャンク化対象テキスト：Classroom投稿本文 + 添付ファイル内容
                        chunk_target_text = ""
                        if extracted_text and display_subject:
                            # 両方ある場合：投稿本文 + 添付ファイル
                            chunk_target_text = f"【投稿本文】\n{display_subject}\n\n【添付ファイル】\n{extracted_text}"
                            logger.info(f"  Classroom投稿本文を追加: {len(display_subject)}文字")
                        elif display_subject:
                            # テキストのみの投稿（添付なし）
                            chunk_target_text = f"【投稿本文】\n{display_subject}"
                            logger.info(f"  テキストのみ投稿: {len(display_subject)}文字")
                        elif extracted_text:
                            # 添付ファイルのみ
                            chunk_target_text = extracted_text
                        elif summary:
                            # サマリーのみ（フォールバック）
                            chunk_target_text = summary
                            logger.info(f"  サマリーをチャンク化: {len(summary)}文字")

                        # チャンクインデックスカウンター
                        current_chunk_index = 0
                        metadata_chunk_success_count = 0

                        # ============================================
                        # ステップ0: メタデータチャンク（B2: 重み付きチャンク）
                        # ============================================
                        logger.info(f"  メタデータチャンクの生成開始")
                        metadata_chunker = MetadataChunker()

                        # Classroom情報を取得（existing または file_meta から）
                        classroom_fields = {}
                        for field in ['display_subject', 'display_post_text', 'display_type',
                                     'display_sender', 'display_sent_at', 'classroom_sender_email']:
                            value = None
                            if existing and existing.get(field):
                                value = existing.get(field)
                            elif field in file_meta:
                                value = file_meta.get(field)
                            if value:
                                classroom_fields[field] = value

                        document_data = {
                            'file_name': file_name,
                            'summary': summary,
                            'document_date': document_date,
                            'tags': tags,
                            'event_dates': event_dates if 'event_dates' in dir() else [],
                            **classroom_fields  # Classroomフィールドを展開
                        }
                        metadata_chunks = metadata_chunker.create_metadata_chunks(document_data)

                        for meta_chunk in metadata_chunks:
                            try:
                                meta_text = meta_chunk.get('chunk_text', '')
                                meta_type = meta_chunk.get('chunk_type', 'metadata')
                                meta_weight = meta_chunk.get('search_weight', 1.0)

                                if not meta_text:
                                    continue

                                meta_embedding = self.llm_client.generate_embedding(meta_text)

                                meta_doc = {
                                    'document_id': document_id,
                                    'chunk_index': current_chunk_index,
                                    'chunk_content': meta_text,
                                    'chunk_size': len(meta_text),
                                    'chunk_type': meta_type,
                                    'search_weight': meta_weight,
                                    'embedding': meta_embedding
                                }

                                chunk_result = await self.db.insert_document('search_index', meta_doc)
                                if chunk_result:
                                    metadata_chunk_success_count += 1
                                    current_chunk_index += 1
                                    logger.debug(f"    ✅ メタデータチャンク保存: {meta_type} (weight={meta_weight})")
                            except Exception as meta_chunk_error:
                                logger.error(f"  メタデータチャンク保存エラー: {meta_chunk_error}")

                        logger.info(f"  メタデータチャンク保存完了: {metadata_chunk_success_count}個")

                        # 小チャンク化（検索用）
                        chunker = TextChunker(chunk_size=150, chunk_overlap=30)
                        small_chunks = chunker.split_text(chunk_target_text)

                        logger.info(f"  小チャンク作成完了: {len(small_chunks)}個")

                        # ステップ1: 小チャンク（検索用）を保存
                        logger.info(f"  小チャンク（検索用）の保存開始: {len(small_chunks)}個")
                        small_chunk_success_count = 0
                        for small_chunk in small_chunks:
                            try:
                                small_text = small_chunk.get('chunk_text', '')
                                small_embedding = self.llm_client.generate_embedding(small_text)

                                small_doc = {
                                    'document_id': document_id,
                                    'chunk_index': current_chunk_index,  # メタデータチャンクの後から
                                    'chunk_content': small_text,
                                    'chunk_size': small_chunk.get('chunk_size', len(small_text)),
                                    'chunk_type': 'content_small',  # B2: チャンク種別
                                    'search_weight': 1.0,  # B2: 検索重み
                                    'embedding': small_embedding
                                }

                                chunk_result = await self.db.insert_document('search_index', small_doc)
                                if chunk_result:
                                    small_chunk_success_count += 1
                                    current_chunk_index += 1
                            except Exception as chunk_insert_error:
                                logger.error(f"  小チャンク保存エラー: {type(chunk_insert_error).__name__}: {chunk_insert_error}")
                                logger.debug(f"  エラー詳細: {repr(chunk_insert_error)}", exc_info=True)

                        logger.info(f"  小チャンク保存完了: {small_chunk_success_count}/{len(small_chunks)}個")

                        # ステップ2: 合成チャンク（スケジュール・議題等）を生成・保存
                        logger.info(f"  合成チャンク（構造化データ専用）の生成開始")
                        synthetic_chunk_success_count = 0
                        synthetic_chunks = create_all_synthetic_chunks(metadata, file_name)

                        if synthetic_chunks:
                            logger.info(f"  合成チャンク生成完了: {len(synthetic_chunks)}個")
                            for synthetic in synthetic_chunks:
                                try:
                                    synthetic_text = synthetic.get('content', '')
                                    synthetic_type = synthetic.get('type', 'unknown')

                                    if not synthetic_text:
                                        continue

                                    # 合成チャンク用のembeddingを生成
                                    synthetic_embedding = self.llm_client.generate_embedding(synthetic_text)

                                    synthetic_doc = {
                                        'document_id': document_id,
                                        'chunk_index': current_chunk_index,
                                        'chunk_content': synthetic_text,
                                        'chunk_size': len(synthetic_text),
                                        'chunk_type': 'synthetic',  # B2: チャンク種別
                                        'search_weight': 1.0,  # B2: 検索重み
                                        'embedding': synthetic_embedding,
                                        'section_title': f'[合成チャンク: {synthetic_type}]'  # 識別用
                                    }

                                    chunk_result = await self.db.insert_document('search_index', synthetic_doc)
                                    if chunk_result:
                                        synthetic_chunk_success_count += 1
                                        current_chunk_index += 1
                                        logger.info(f"  ✅ 合成チャンク保存成功: {synthetic_type} ({len(synthetic_text)}文字)")
                                except Exception as chunk_insert_error:
                                    logger.error(f"  合成チャンク保存エラー: {type(chunk_insert_error).__name__}: {chunk_insert_error}")
                                    logger.debug(f"  エラー詳細: {repr(chunk_insert_error)}", exc_info=True)
                        else:
                            logger.info(f"  合成チャンク生成: 対象データなし（スキップ）")

                        # B2: メタデータチャンクを含めた合計
                        total_chunks = metadata_chunk_success_count + small_chunk_success_count + synthetic_chunk_success_count
                        logger.info(f"  チャンク保存完了（合計）: {total_chunks}個（メタ{metadata_chunk_success_count}個 + 小{small_chunk_success_count}個 + 合成{synthetic_chunk_success_count}個）")

                        # ステップ4: document の chunk_count を更新
                        try:
                            update_data = {
                                'chunk_count': total_chunks,
                                'chunking_strategy': 'metadata_small_synthetic'  # B2: メタデータ + 小 + 合成
                            }
                            response = (
                                self.db.client.table('source_documents')
                                .update(update_data)
                                .eq('id', document_id)
                                .execute()
                            )
                            logger.info(f"  Document chunk_count更新完了: {total_chunks}個")
                        except Exception as update_error:
                            logger.error(f"  Document chunk_count更新エラー: {update_error}")

                    except Exception as chunk_error:
                        logger.error(f"  チャンク化エラー: {chunk_error}", exc_info=True)
                else:
                    logger.warning(f"  チャンク化スキップ: extracted_text={bool(extracted_text)}, document_id={bool(document_id)}")

                logger.info(f"=== 処理完了: {file_name} ({doc_type}, {processing_stage}) ===")
                return {"success": True, "document_id": document_id, "doc_type": doc_type}
            except Exception as db_error:
                # 重複エラー（23505）の場合はスキップ
                error_str = str(db_error)
                if '23505' in error_str or 'duplicate' in error_str.lower():
                    logger.warning(f"重複エラー検出（スキップ）: {file_name} - {error_str}")
                    return {"status": "skipped", "reason": "duplicate"}
                else:
                    # その他のDBエラーは再スロー
                    raise
            
        except Exception as e:
            error_msg = str(e)
            error_traceback = traceback.format_exc()
            # KeyError回避: エラーメッセージを安全に文字列化
            safe_error_msg = error_msg.replace('{', '{{').replace('}', '}}')
            safe_traceback = error_traceback.replace('{', '{{').replace('}', '}}')
            logger.error(f"処理エラー: {file_name} - {safe_error_msg}\n{safe_traceback}")

            error_data = {
                "source_type": source_type,  # 引数またはfile_metaから取得した値を使用
                "source_id": file_id,
                "file_name": file_name,
                "workspace": workspace,
                "processing_status": PROCESSING_STATUS["FAILED"],
                "error_message": str(e),
                "file_type": self._get_file_type(mime_type),
            }

            try:
                # 既存レコードがある場合は上書き（force_reprocessモード対応）
                await self.db.upsert_document('source_documents', error_data, conflict_column='source_id', force_update=True)
            except Exception as db_error:
                db_error_traceback = traceback.format_exc()
                # KeyError回避: エラーメッセージを安全に文字列化
                safe_db_error = str(db_error).replace('{', '{{').replace('}', '}}')
                safe_db_traceback = db_error_traceback.replace('{', '{{').replace('}', '}}')
                logger.critical(f"DB保存失敗（エラーレコード）: {file_name} - DB Error: {safe_db_error}\n{safe_db_traceback}")

                # ファイルシステムフォールバック
                fallback_dir = Path('_runtime/logs/db_errors')
                fallback_dir.mkdir(parents=True, exist_ok=True)

                fallback_file = fallback_dir / f"db_error_{datetime.now():%Y%m%d_%H%M%S}_{file_id}.json"

                try:
                    with open(fallback_file, 'w', encoding='utf-8') as f:
                        json.dump({
                            'error_data': error_data,
                            'db_error': str(db_error),
                            'db_error_traceback': traceback.format_exc(),
                            'timestamp': datetime.now().isoformat()
                        }, f, ensure_ascii=False, indent=2)
                    logger.warning(f"エラー情報をファイルに保存: {fallback_file}")
                except Exception as file_error:
                    # KeyError回避: エラーメッセージを安全に文字列化
                    safe_file_error = str(file_error).replace('{', '{{').replace('}', '}}')
                    logger.critical(f"ファイルシステムへの保存も失敗: {safe_file_error}") 
                
            return None
            
        finally:
            if local_path and Path(local_path).exists():
                os.remove(local_path)
                logger.debug(f"一時ファイル削除: {local_path}")