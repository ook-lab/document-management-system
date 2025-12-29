"""
キュー処理型ドキュメント再処理スクリプト

処理状態管理テーブル (document_reprocessing_queue) を使用した統合処理スクリプト。
重複処理を防ぎ、処理進捗を追跡し、エラー時のリトライを可能にします。

処理内容:
1. すべてのワークスペース（デフォルト）または指定されたワークスペースのドキュメントをキューに登録
2. キューから順次タスクを取得して処理
3. 完全なパイプライン（Pre-processing → Stage B → Stage H → Stage A → Chunking）で処理
4. attachment_text、構造化metadata、search_indexを生成
5. 処理状態をデータベースで管理（pending → processing → completed/failed）

対応するソースタイプ:
- classroom: Google Classroom添付ファイル付き（Drive URL経由）
- classroom_text: Google Classroomテキストのみ投稿
- text_only: 一般的なテキストドキュメント
- drive: Google Driveファイル
- email_attachment: メール添付ファイル

使い方:
    # 全ワークスペースを処理（デフォルト）
    python process_queued_documents.py --limit=100

    # ドライラン（確認のみ）
    python process_queued_documents.py --dry-run

    # 特定のワークスペースのみ処理
    python process_queued_documents.py --workspace=ema_classroom --limit=20
    python process_queued_documents.py --workspace=ikuya_classroom --limit=20

    # キューに追加のみ（処理は実行しない）
    python process_queued_documents.py --populate-only --limit=50

    # キューから処理実行
    python process_queued_documents.py --process-queue --limit=10

    # ワークスペースを保持しない（AI判定に任せる）
    python process_queued_documents.py --no-preserve-workspace
"""

import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger
import json
import sys
from datetime import datetime

from A_common.database.client import DatabaseClient
from A_common.connectors.google_drive import GoogleDriveConnector
from G_unified_pipeline import UnifiedDocumentPipeline
from pathlib import Path


class ClassroomReprocessorV2:
    """Google Classroomドキュメントの再処理（統合パイプライン版）"""

    # 動画ファイル拡張子（トークン消費が多いためスキップ対象）
    VIDEO_EXTENSIONS = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.m4v', '.mpeg', '.mpg']

    def __init__(self, worker_id: str = "reprocessor_v2"):
        self.db = DatabaseClient()
        self.worker_id = worker_id

        # 統合パイプラインを初期化
        self.pipeline = UnifiedDocumentPipeline(db_client=self.db)

        # Google Drive connector
        self.drive = GoogleDriveConnector()

        # 一時ディレクトリ
        self.temp_dir = Path("./temp")
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def populate_queue_from_workspace(
        self,
        workspace: str = 'all',
        limit: int = 100,
        reason: str = 'classroom_reprocessing',
        preserve_workspace: bool = True
    ) -> int:
        """
        指定されたworkspaceのドキュメントをキューに追加

        Args:
            workspace: 対象ワークスペース ('all' で全ワークスペース)
            limit: 追加する最大件数
            reason: 再処理の理由
            preserve_workspace: workspaceを保持するか

        Returns:
            追加した件数
        """
        logger.info(f"キューへの追加を開始: workspace={workspace}")

        # 対象ドキュメントを取得（processing_status='completed'は除外）
        if workspace == 'all':
            # 全ワークスペースを対象
            result = self.db.client.table('Rawdata_FILE_AND_MAIL').select('*').neq('processing_status', 'completed').limit(limit).execute()
        else:
            # 特定のワークスペースのみ
            result = self.db.client.table('Rawdata_FILE_AND_MAIL').select('*').eq(
                'workspace', workspace
            ).neq('processing_status', 'completed').limit(limit).execute()

        documents = result.data if result.data else []
        logger.info(f"対象ドキュメント: {len(documents)}件")

        if not documents:
            logger.info("追加するドキュメントがありません")
            return 0

        added_count = 0
        skipped_count = 0

        for doc in documents:
            doc_id = doc['id']
            file_name = doc.get('file_name', 'unknown')

            # 既にキューに登録されているかチェック
            existing = self.db.client.table('99_lg_reprocess_queue').select('id, status').eq(
                'document_id', doc_id
            ).eq('status', 'pending').execute()

            if existing.data:
                logger.debug(f"スキップ（既にキューに登録済み）: {file_name}")
                skipped_count += 1
                continue

            # キューに追加
            try:
                queue_data = {
                    'document_id': doc_id,
                    'reprocess_reason': reason,
                    'reprocess_type': 'full',
                    'priority': 0,
                    'preserve_workspace': preserve_workspace,
                    'original_file_name': file_name,
                    'original_workspace': doc.get('workspace'),
                    'original_doc_type': doc.get('doc_type'),
                    'original_source_id': doc.get('source_id'),
                    'created_by': self.worker_id
                }

                self.db.client.table('99_lg_reprocess_queue').insert(queue_data).execute()
                added_count += 1
                logger.debug(f"キューに追加: {file_name}")

            except Exception as e:
                logger.error(f"キュー追加エラー: {file_name} - {e}")

        logger.info(f"キュー追加完了: {added_count}件追加, {skipped_count}件スキップ")
        return added_count

    async def process_queue(self, limit: int = 100) -> Dict[str, int]:
        """
        キューから順次タスクを取得して処理

        Args:
            limit: 処理する最大件数

        Returns:
            処理結果の統計（成功数、失敗数など）
        """
        logger.info(f"キュー処理開始: 最大{limit}件")

        stats = {
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'total': 0
        }

        for i in range(limit):
            # 次のタスクを取得
            task = self._get_next_task()

            if not task:
                logger.info("処理するタスクがありません")
                break

            stats['total'] += 1
            queue_id = task['queue_id']
            document_id = task['document_id']
            file_name = task['file_name']
            preserve_workspace = task.get('preserve_workspace', True)

            logger.info(f"\n{'='*80}")
            logger.info(f"[{i+1}/{limit}] 処理開始: {file_name}")
            logger.info(f"Queue ID: {queue_id}")
            logger.info(f"Document ID: {document_id}")

            # ドキュメントを再処理
            success = await self._reprocess_document(
                queue_id=queue_id,
                document_id=document_id,
                file_name=file_name,
                preserve_workspace=preserve_workspace
            )

            if success:
                stats['success'] += 1
            else:
                stats['failed'] += 1

            # 進捗表示
            logger.info(f"進捗: 成功={stats['success']}, 失敗={stats['failed']}, 合計={stats['total']}")

        return stats

    def _get_next_task(self) -> Optional[Dict[str, Any]]:
        """
        次の処理対象タスクをキューから取得
        データベース関数 get_next_reprocessing_task を使用

        Returns:
            タスク情報、またはNone
        """
        try:
            response = self.db.client.rpc(
                'get_next_reprocessing_task',
                {'p_worker_id': self.worker_id}
            ).execute()

            if response.data and len(response.data) > 0:
                return response.data[0]
            return None

        except Exception as e:
            logger.error(f"次タスク取得エラー: {e}")
            return None

    async def _process_document_stages(
        self,
        file_path: Path,
        file_name: str,
        doc_type: str,
        workspace: str,
        mime_type: str,
        source_id: str,
        existing_document_id: Optional[str] = None,
        display_subject: Optional[str] = None,
        display_post_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Stage E-K の処理を実行（統合パイプライン使用）

        Args:
            file_path: ファイルパス
            file_name: ファイル名
            doc_type: ドキュメントタイプ
            workspace: ワークスペース
            mime_type: MIMEタイプ
            source_id: ソースID
            existing_document_id: 更新する既存ドキュメントID（Noneの場合は新規作成）
            display_subject: Classroom件名（Classroomドキュメントの場合）
            display_post_text: Classroom本文（Classroomドキュメントの場合）

        Returns:
            処理結果 {'success': bool, 'document_id': str, ...}
        """
        # Classroom固有フィールドをmetadataに追加
        extra_metadata = {}
        if display_subject:
            extra_metadata['display_subject'] = display_subject
        if display_post_text:
            extra_metadata['display_post_text'] = display_post_text

        # 統合パイプラインで処理
        result = await self.pipeline.process_document(
            file_path=file_path,
            file_name=file_name,
            doc_type=doc_type,
            workspace=workspace,
            mime_type=mime_type,
            source_id=source_id,
            existing_document_id=existing_document_id,
            extra_metadata=extra_metadata if extra_metadata else None
        )

        return result

    async def _reprocess_document(
        self,
        queue_id: str,
        document_id: str,
        file_name: str,
        preserve_workspace: bool = True
    ) -> bool:
        """
        単一ドキュメントを再処理し、結果をキューに記録

        Args:
            queue_id: キューID
            document_id: ドキュメントID
            file_name: ファイル名
            preserve_workspace: workspaceを保持するか

        Returns:
            成功したかどうか
        """
        try:
            # ドキュメント情報を取得
            doc = self.db.get_document_by_id(document_id)
            if not doc:
                error_msg = "ドキュメントが見つかりません"
                logger.error(error_msg)
                self._mark_task_failed(queue_id, error_msg)
                return False

            source_type = doc.get('source_type', '')

            # ============================================
            # Classroom添付ファイル付きドキュメント（classroom）の処理
            # ============================================
            if source_type == 'classroom':
                logger.info(f"📎 Classroom添付ファイル付きドキュメントを検出（{source_type}）")
                return await self._reprocess_classroom_document_with_attachment(
                    queue_id=queue_id,
                    document_id=document_id,
                    doc=doc,
                    preserve_workspace=preserve_workspace
                )

            # ============================================
            # テキストのみドキュメント（classroom_text, text_only）の処理
            # ============================================
            if source_type in ['classroom_text', 'text_only']:
                logger.info(f"📝 テキストのみドキュメントを検出（{source_type}）")
                return await self._reprocess_text_only_document(
                    queue_id=queue_id,
                    document_id=document_id,
                    doc=doc,
                    preserve_workspace=preserve_workspace
                )

            # ============================================
            # ファイルベースドキュメント（drive, email_attachment等）の処理
            # ============================================
            # ファイルIDを取得
            file_id = self._extract_file_id(doc)
            if not file_id:
                error_msg = "ファイルIDが見つかりません"
                logger.error(f"{error_msg}: {file_name}")
                logger.error(f"  source_id: {doc.get('source_id')}")
                self._mark_task_failed(queue_id, error_msg)
                return False

            logger.info(f"ファイルID: {file_id}")

            # 動画ファイルはスキップ（トークン消費が多いため）
            file_ext = '.' + file_name.lower().split('.')[-1] if '.' in file_name else ''

            if file_ext in self.VIDEO_EXTENSIONS:
                logger.info(f"🎬 動画ファイルを検出: {file_name}")
                logger.info(f"  → トークン消費削減のためスキップします")
                self._mark_task_completed(queue_id, success=True)
                return True

            # ファイルメタデータを構築
            file_meta = {
                'id': file_id,
                'name': file_name,
                'mimeType': self._guess_mime_type(file_name),
                'doc_type': doc.get('doc_type', 'other')  # doc_typeを追加（デフォルト: other）
            }

            # workspaceを決定
            workspace_to_use = doc.get('workspace', 'unknown') if preserve_workspace else 'unknown'
            logger.info(f"Workspace: {workspace_to_use} (preserve={preserve_workspace})")

            # ファイルをダウンロード
            local_path = None
            try:
                local_path = self.drive.download_file(file_id, file_name, self.temp_dir)
                logger.info(f"ダウンロード完了: {local_path}")

                # Stage E-K で処理（既存ドキュメントを更新）
                result = await self._process_document_stages(
                    file_path=Path(local_path),
                    file_name=file_name,
                    doc_type=file_meta.get('doc_type', 'other'),
                    workspace=workspace_to_use,
                    mime_type=file_meta.get('mimeType', 'application/octet-stream'),
                    source_id=file_id,
                    existing_document_id=document_id  # 既存ドキュメントを更新
                )

                if result and result.get('success'):
                    logger.success(f"✅ 再処理成功: {file_name}")
                    self._mark_task_completed(queue_id, success=True)
                    return True
                else:
                    error_msg = result.get('error', 'unknown error') if result else 'no result'
                    logger.error(f"❌ 再処理失敗: {error_msg}")
                    self._mark_task_failed(queue_id, error_msg)
                    return False

            finally:
                # 一時ファイルを削除
                if local_path and Path(local_path).exists():
                    Path(local_path).unlink()
                    logger.debug(f"一時ファイル削除: {local_path}")

        except Exception as e:
            error_msg = f"処理中にエラー: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.exception(e)
            self._mark_task_failed(queue_id, error_msg, error_details={'exception': str(e)})
            return False

    def _mark_task_completed(self, queue_id: str, success: bool):
        """タスクを完了としてマーク"""
        try:
            self.db.client.rpc(
                'mark_reprocessing_task_completed',
                {
                    'p_queue_id': queue_id,
                    'p_success': success
                }
            ).execute()
        except Exception as e:
            logger.error(f"タスク完了マークエラー: {e}")

    def _mark_task_failed(
        self,
        queue_id: str,
        error_message: str,
        error_details: Optional[Dict] = None
    ):
        """タスクを失敗としてマーク"""
        try:
            self.db.client.rpc(
                'mark_reprocessing_task_completed',
                {
                    'p_queue_id': queue_id,
                    'p_success': False,
                    'p_error_message': error_message,
                    'p_error_details': json.dumps(error_details) if error_details else None
                }
            ).execute()
        except Exception as e:
            logger.error(f"タスク失敗マークエラー: {e}")

    async def _reprocess_text_only_document(
        self,
        queue_id: str,
        document_id: str,
        doc: Dict[str, Any],
        preserve_workspace: bool = True
    ) -> bool:
        """
        テキストのみのドキュメント（classroom_text）を再処理

        Args:
            queue_id: キューID
            document_id: ドキュメントID
            doc: ドキュメントデータ
            preserve_workspace: workspaceを保持するか

        Returns:
            成功したかどうか
        """
        from A_common.config.yaml_loader import get_classification_yaml_string

        file_name = doc.get('file_name', 'text_only')
        source_type = doc.get('source_type', '')

        # 各ソースから個別にデータを取得（結合しない）
        display_subject = doc.get('display_subject', '')
        display_post_text = doc.get('display_post_text', '')
        attachment_text = doc.get('attachment_text', '')

        # Classroom投稿（添付ファイルなし）の場合の検証
        if source_type == 'classroom_text':
            if not (display_subject or display_post_text):
                error_msg = "display_subjectもdisplay_post_textも空です"
                logger.error(f"{error_msg}: {file_name}")
                self._mark_task_failed(queue_id, error_msg)
                return False
            total_length = len(display_subject) + len(display_post_text)
            logger.info(f"📝 Classroomフィールド: 件名={len(display_subject)}文字, 本文={len(display_post_text)}文字")
        else:
            # text_only など、通常のテキストドキュメントの場合
            if not attachment_text:
                error_msg = "attachment_textが空です"
                logger.error(f"{error_msg}: {file_name}")
                self._mark_task_failed(queue_id, error_msg)
                return False
            total_length = len(attachment_text)
            logger.info(f"📝 添付ファイルテキスト: {total_length}文字")

        logger.info(f"テキスト総量: {total_length}文字")

        try:
            # Stage H (構造化) を使用（統合パイプラインから取得）
            stageH_extractor = self.pipeline.stage_h
            yaml_string = get_classification_yaml_string()

            # workspaceを決定
            workspace_to_use = doc.get('workspace', 'unknown') if preserve_workspace else 'unknown'

            # テキストを結合
            text_parts = []
            if display_subject:
                text_parts.append(f"【件名】\n{display_subject}")
            if display_post_text:
                text_parts.append(f"【本文】\n{display_post_text}")
            if attachment_text:
                text_parts.append(f"【添付ファイル】\n{attachment_text}")
            combined_text = '\n\n'.join(text_parts)

            # ============================================
            # Stage H: Claude構造化（メタデータ抽出）
            # ============================================
            logger.info("[Stage H] Claude構造化開始...")

            # Stage Iに渡すdoc_typeとworkspaceの情報を準備
            stagei_result_for_stageh = {
                'doc_type': doc.get('doc_type', 'unknown'),
                'workspace': doc.get('workspace', 'unknown')
            }

            stageh_result = stageH_extractor.process(
                file_name=file_name,
                doc_type=doc.get('doc_type', 'unknown'),
                workspace=doc.get('workspace', 'unknown'),
                combined_text=text_content,
                prompt=yaml_string,
                model='claude-haiku-4-5-20251001'
            )

            # Stage Hの結果をチェック
            if not stageh_result or not isinstance(stageh_result, dict):
                error_msg = "Stage H失敗: 構造化結果が不正です"
                logger.error(f"[Stage H失敗] {error_msg}")
                await self._mark_as_failed(queue_id, error_msg)
                return

            # Stage Hの結果を取得
            document_date = stageh_result.get('document_date')
            tags = stageh_result.get('tags', [])
            stageh_metadata = stageh_result.get('metadata', {})

            # フォールバック結果をエラーとして検出
            if stageh_metadata.get('extraction_failed'):
                error_msg = "Stage H失敗: JSON抽出に失敗しました（フォールバック結果）"
                logger.error(f"[Stage H失敗] {error_msg}")
                await self._mark_as_failed(queue_id, error_msg)
                return

            logger.info(f"[Stage H] 完了: metadata_fields={len(stageh_metadata)}")

            # ============================================
            # Stage I: 統合・要約（現在はStage Hの結果のみ使用）
            # ============================================
            logger.info("[Stage I] Stage Hの結果を使用...")

            summary = ''
            relevant_date = None

            # Note: 統合パイプラインへの完全移行のため、Stage Hの結果を直接使用
            # 将来的にはpipeline.stage_i.processを使用する予定
            summary = stageh_result.get('summary', '')
            relevant_date = stageh_result.get('document_date')

            logger.info(f"[Stage I] 完了: summary={summary[:50] if summary else ''}...")

            # 結果の統合
            doc_type = doc.get('doc_type', 'unknown')  # 元のdoc_typeを保持（変更しない）
            metadata = stageh_metadata

            logger.info(f"[処理完了] doc_type={doc_type}")

            # ============================================
            # チャンク化処理（新規追加）
            # ============================================
            logger.info("[チャンク化] 開始...")

            # 既存チャンクを削除（再処理の場合）
            try:
                delete_result = self.db.client.table('10_ix_search_index').delete().eq('document_id', document_id).execute()
                deleted_count = len(delete_result.data) if delete_result.data else 0
                logger.info(f"  既存チャンク削除: {deleted_count}個")
            except Exception as e:
                logger.warning(f"  既存チャンク削除エラー（継続）: {e}")

            # チャンクデータ準備（すべてのメタデータを含める）
            document_data = {
                'file_name': file_name,
                'summary': summary,
                'document_date': document_date,
                'tags': tags,
                'doc_type': doc.get('doc_type'),
                'display_subject': display_subject,
                'display_post_text': display_post_text,
                'display_sender': doc.get('display_sender'),
                'display_type': doc.get('display_type'),
                'display_sent_at': doc.get('display_sent_at'),
                'classroom_sender_email': doc.get('classroom_sender_email'),
                'attachment_text': attachment_text,  # classroom_textの場合はNone
                'persons': metadata.get('persons', []) if isinstance(metadata, dict) else [],
                'organizations': metadata.get('organizations', []) if isinstance(metadata, dict) else [],
                'people': metadata.get('people', []) if isinstance(metadata, dict) else []
            }

            # メタデータチャンク生成
            from A_common.processing.metadata_chunker import MetadataChunker
            metadata_chunker = MetadataChunker()
            metadata_chunks = metadata_chunker.create_metadata_chunks(document_data)

            current_chunk_index = 0
            for meta_chunk in metadata_chunks:
                meta_text = meta_chunk.get('chunk_text', '')
                meta_type = meta_chunk.get('chunk_type', 'metadata')
                meta_weight = meta_chunk.get('search_weight', 1.0)

                if not meta_text:
                    continue

                # Embedding生成
                meta_embedding = self.pipeline.llm_client.generate_embedding(meta_text)

                # search_indexに保存
                meta_doc = {
                    'document_id': document_id,
                    'chunk_index': current_chunk_index,
                    'chunk_content': meta_text,
                    'chunk_size': len(meta_text),
                    'chunk_type': meta_type,
                    'embedding': meta_embedding,
                    'search_weight': meta_weight
                }

                try:
                    self.db.client.table('10_ix_search_index').insert(meta_doc).execute()
                    current_chunk_index += 1
                except Exception as e:
                    logger.error(f"  チャンク保存エラー: {e}")

            logger.info(f"[チャンク化] メタデータチャンク完了: {current_chunk_index}個")

            # ============================================
            # 本文チャンク化（attachment_text）
            # ============================================
            attachment_text = document_record.get('attachment_text', '')
            if attachment_text and len(attachment_text.strip()) > 50:
                logger.info(f"[チャンク化] 本文チャンク作成開始: {len(attachment_text)}文字")

                # 小チャンク作成（150文字ずつ、オーバーラップ30文字）
                from A_common.utils.chunking import TextChunker
                chunker = TextChunker(chunk_size=150, chunk_overlap=30)
                small_chunks = chunker.split_text(attachment_text)

                logger.info(f"[チャンク化] 小チャンク数: {len(small_chunks)}個")

                # 小チャンクをembedding化して保存
                for i, chunk_dict in enumerate(small_chunks):
                    chunk_text = chunk_dict['chunk_text']
                    if not chunk_text.strip():
                        continue

                    try:
                        # Embedding生成
                        chunk_embedding = self.pipeline.llm_client.generate_embedding(chunk_text)

                        # search_indexに保存
                        chunk_doc = {
                            'document_id': document_id,
                            'chunk_index': current_chunk_index,
                            'chunk_content': chunk_text,
                            'chunk_size': len(chunk_text),
                            'chunk_type': 'content_small',
                            'embedding': chunk_embedding,
                            'search_weight': 1.0
                        }

                        self.db.client.table('10_ix_search_index').insert(chunk_doc).execute()
                        current_chunk_index += 1
                    except Exception as e:
                        logger.error(f"  小チャンク保存エラー: {e}")

            logger.info(f"[チャンク化] 全チャンク完了: {current_chunk_index}個")

            # ============================================
            # データベース更新
            # ============================================
            update_data = {
                'summary': summary,
                'metadata': metadata,
                'processing_status': 'completed',
                'processing_stage': 'stagec_and_stagea_complete',
                'stagea_classifier_model': 'gemini-2.5-flash',
                'stageb_vision_model': None,  # テキストのみドキュメント（Stage B未使用）
                'stagec_extractor_model': 'claude-haiku-4-5-20251001',
                'text_extraction_model': None,  # テキストのみドキュメント（抽出不要）
                'relevant_date': relevant_date
            }

            if document_date:
                update_data['document_date'] = document_date
            if tags:
                update_data['tags'] = tags

            response = self.db.client.table('Rawdata_FILE_AND_MAIL').update(update_data).eq('id', document_id).execute()

            if response.data:
                logger.success(f"✅ テキストのみドキュメント再処理成功: {file_name}")
                logger.info(f"  チャンク数: {current_chunk_index}")
                self._mark_task_completed(queue_id, success=True)
                return True
            else:
                error_msg = "データベース更新失敗"
                logger.error(error_msg)
                self._mark_task_failed(queue_id, error_msg)
                return False

        except Exception as e:
            error_msg = f"テキストのみドキュメント処理エラー: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.exception(e)
            self._mark_task_failed(queue_id, error_msg, error_details={'exception': str(e)})
            return False

    async def _reprocess_classroom_document_with_attachment(
        self,
        queue_id: str,
        document_id: str,
        doc: Dict[str, Any],
        preserve_workspace: bool = True
    ) -> bool:
        """
        添付ファイル付きClassroomドキュメント（source_type='classroom'）を再処理

        処理フロー:
        1. Pre-processing: Drive URLからファイルダウンロード
        2. Stage B: テキスト抽出 + Vision処理
        3. Stage H: Claude構造化（メタデータ抽出）
        4. Stage A: Gemini統合・要約（Stage Hの結果を活用）
        5. チャンク化: subject + post_text + attachment_text
        6. Supabase保存

        Args:
            queue_id: キューID
            document_id: ドキュメントID
            doc: ドキュメントデータ
            preserve_workspace: workspaceを保持するか

        Returns:
            成功したかどうか
        """
        from A_common.config.yaml_loader import get_classification_yaml_string

        file_name = doc.get('file_name', 'classroom_attachment')
        display_subject = doc.get('display_subject', '')
        display_post_text = doc.get('display_post_text', '')

        # 動画ファイルはスキップ（トークン消費が多いため）
        # ただし、投稿本文がある場合はそれを検索インデックスに登録
        file_ext = '.' + file_name.lower().split('.')[-1] if '.' in file_name else ''

        if file_ext in self.VIDEO_EXTENSIONS:
            logger.info(f"🎬 動画ファイルを検出: {file_name}")
            logger.info(f"  → 動画ファイル自体はスキップしますが、投稿本文は処理します")

            # 投稿本文がある場合は、テキストのみドキュメントとして処理
            if display_subject or display_post_text:
                logger.info(f"  📝 投稿本文を検出: 件名={len(display_subject)}文字, 本文={len(display_post_text)}文字")
                return await self._process_video_post_text_only(
                    queue_id=queue_id,
                    document_id=document_id,
                    doc=doc,
                    file_name=file_name,
                    display_subject=display_subject,
                    display_post_text=display_post_text,
                    preserve_workspace=preserve_workspace
                )
            else:
                logger.info(f"  → 投稿本文もないため完全にスキップします")
                self._mark_task_completed(queue_id, success=True)
                return True

        # metadata から Google Drive ファイルID/URLを取得
        metadata = doc.get('metadata')
        if metadata is None:
            metadata = {}
        elif isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except:
                metadata = {}

        # ファイルIDを複数のソースから取得（優先順位順）
        # ★修正: source_idを最優先（GASでコピーされたファイルID、サービスアカウントに権限付与済み）
        file_id = None
        source_description = ""

        # 1. source_id（コピー後のファイルID、サービスアカウントがアクセス可能）
        source_id = doc.get('source_id')
        if source_id and not source_id.isdigit():
            file_id = source_id
            source_description = f"source_id: {file_id}"

        # 2. metadata.drive_url からの抽出（URL形式）
        if not file_id:
            drive_url = metadata.get('drive_url')
            if drive_url:
                file_id = self._extract_file_id_from_url(drive_url)
                source_description = f"Drive URL: {drive_url}"

        # 3. metadata.original_classroom_id（元のファイルID、権限がない可能性あり）
        if not file_id:
            original_classroom_id = metadata.get('original_classroom_id')
            if original_classroom_id and not original_classroom_id.isdigit():
                file_id = original_classroom_id
                source_description = f"original_classroom_id: {file_id}"

        if not file_id:
            error_msg = "ファイルIDが見つかりません（drive_url, original_classroom_id, source_id のいずれも無効）"
            logger.error(f"{error_msg}: {file_name}")
            self._mark_task_failed(queue_id, error_msg)
            return False

        logger.info(f"📎 Classroom添付ファイルを検出")
        logger.info(f"  件名: {display_subject[:50] if display_subject else '(なし)'}...")
        logger.info(f"  ファイルソース: {source_description}")
        logger.info(f"  ファイルID: {file_id}")

        # ファイルをダウンロード
        local_path = None
        try:
            # workspaceを決定
            workspace_to_use = doc.get('workspace', 'unknown') if preserve_workspace else 'unknown'
            logger.info(f"  Workspace: {workspace_to_use} (preserve={preserve_workspace})")

            # ファイルをダウンロード
            local_path = self.drive.download_file(file_id, file_name, self.temp_dir)
            logger.info(f"ダウンロード完了: {local_path}")

            # Stage E-K で処理（既存ドキュメントを更新）
            result = await self._process_document_stages(
                file_path=Path(local_path),
                file_name=file_name,
                doc_type=doc.get('doc_type', 'classroom_document'),
                workspace=workspace_to_use,
                mime_type=self._guess_mime_type(file_name),
                source_id=file_id,
                existing_document_id=document_id,  # 既存ドキュメントを更新
                display_subject=display_subject,
                display_post_text=display_post_text
            )

            if result and result.get('success'):
                logger.success(f"✅ Classroom添付ファイルドキュメント再処理成功: {file_name}")
                logger.info(f"  チャンク数: {result.get('chunks_count', 0)}")
                self._mark_task_completed(queue_id, success=True)
                return True
            else:
                error_msg = result.get('error', 'unknown error') if result else 'no result'
                logger.error(f"❌ 再処理失敗: {error_msg}")
                self._mark_task_failed(queue_id, error_msg)
                return False

        except Exception as e:
            error_msg = f"Classroom添付ファイルドキュメント処理エラー: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.exception(e)
            self._mark_task_failed(queue_id, error_msg, error_details={'exception': str(e)})
            return False

        finally:
            # 一時ファイルを削除
            if local_path and Path(local_path).exists():
                Path(local_path).unlink()
                logger.debug(f"一時ファイル削除: {local_path}")

    async def _process_video_post_text_only(
        self,
        queue_id: str,
        document_id: str,
        doc: Dict[str, Any],
        file_name: str,
        display_subject: str,
        display_post_text: str,
        preserve_workspace: bool = True
    ) -> bool:
        """
        動画ファイル付き投稿の本文のみを処理（動画自体はスキップ）

        Args:
            queue_id: キューID
            document_id: ドキュメントID
            doc: ドキュメントデータ
            file_name: ファイル名
            display_subject: 投稿件名
            display_post_text: 投稿本文
            preserve_workspace: workspaceを保持するか

        Returns:
            成功したかどうか
        """
        from A_common.config.yaml_loader import get_classification_yaml_string

        logger.info(f"📝 動画投稿の本文処理開始: {file_name}")
        logger.info(f"  件名: {display_subject[:50] if display_subject else '(なし)'}...")
        logger.info(f"  本文: {display_post_text[:50] if display_post_text else '(なし)'}...")

        try:
            # Stage H (構造化) を使用（統合パイプラインから取得）
            stageH_extractor = self.pipeline.stage_h
            yaml_string = get_classification_yaml_string()

            # workspaceを決定
            workspace_to_use = doc.get('workspace', 'unknown') if preserve_workspace else 'unknown'

            # テキストを結合
            text_parts = []
            if display_subject:
                text_parts.append(f"【件名】\n{display_subject}")
            if display_post_text:
                text_parts.append(f"【本文】\n{display_post_text}")
            # 動画ファイルであることを明記
            text_parts.append(f"【動画ファイル】\n{file_name}")
            combined_text = '\n\n'.join(text_parts)

            # ============================================
            # Stage H: Claude構造化（メタデータ抽出）
            # ============================================
            logger.info("[Stage H] Claude構造化開始...")

            stagea_result_for_stagec = {
                'doc_type': doc.get('doc_type', 'unknown'),
                'workspace': doc.get('workspace', 'unknown')
            }

            stagec_result = stageH_extractor.process(
                file_name=file_name,
                doc_type=doc.get('doc_type', 'unknown'),
                workspace=doc.get('workspace', 'unknown'),
                combined_text=text_content,
                prompt=yaml_string,
                model='claude-haiku-4-5-20251001'
            )

            # Stage Hの結果をチェック
            if not stagec_result or not isinstance(stagec_result, dict):
                error_msg = "Stage H失敗: 構造化結果が不正です"
                logger.error(f"[Stage H失敗] {error_msg}")
                await self._mark_as_failed(document_id, error_msg)
                return

            # Stage Hの結果を取得
            document_date = stagec_result.get('document_date')
            tags = stagec_result.get('tags', [])
            stagec_metadata = stagec_result.get('metadata', {})

            # フォールバック結果をエラーとして検出
            if stagec_metadata.get('extraction_failed'):
                error_msg = "Stage H失敗: JSON抽出に失敗しました（フォールバック結果）"
                logger.error(f"[Stage H失敗] {error_msg}")
                await self._mark_as_failed(document_id, error_msg)
                return

            logger.info(f"[Stage H] 完了: metadata_fields={len(stagec_metadata)}")

            # ============================================
            # Stage I: 統合・要約（現在はStage Hの結果のみ使用）
            # ============================================
            logger.info("[Stage I] Stage Hの結果を使用...")

            summary = ''
            relevant_date = None

            # Note: 統合パイプラインへの完全移行のため、Stage Hの結果を直接使用
            # 将来的にはpipeline.stage_i.processを使用する予定
            summary = stagec_result.get('summary', '')
            relevant_date = stagec_result.get('document_date')

            logger.info(f"[Stage I] 完了: summary={summary[:50] if summary else ''}...")

            # 結果の統合
            doc_type = doc.get('doc_type', 'unknown')
            metadata = stagec_metadata

            logger.info(f"[処理完了] doc_type={doc_type}")

            # ============================================
            # チャンク化処理
            # ============================================
            logger.info("[チャンク化] 開始...")

            # 既存チャンクを削除（再処理の場合）
            try:
                delete_result = self.db.client.table('10_ix_search_index').delete().eq('document_id', document_id).execute()
                deleted_count = len(delete_result.data) if delete_result.data else 0
                logger.info(f"  既存チャンク削除: {deleted_count}個")
            except Exception as e:
                logger.warning(f"  既存チャンク削除エラー（継続）: {e}")

            # チャンクデータ準備（すべてのメタデータを含める）
            document_data = {
                'file_name': file_name,
                'summary': summary,
                'document_date': document_date,
                'tags': tags,
                'doc_type': doc.get('doc_type'),
                'display_subject': display_subject,
                'display_post_text': display_post_text,
                'display_sender': doc.get('display_sender'),
                'display_type': doc.get('display_type'),
                'display_sent_at': doc.get('display_sent_at'),
                'classroom_sender_email': doc.get('classroom_sender_email'),
                'attachment_text': None,  # 動画ファイルは処理しない
                'persons': metadata.get('persons', []) if isinstance(metadata, dict) else [],
                'organizations': metadata.get('organizations', []) if isinstance(metadata, dict) else [],
                'people': metadata.get('people', []) if isinstance(metadata, dict) else []
            }

            # メタデータチャンク生成
            from A_common.processing.metadata_chunker import MetadataChunker
            metadata_chunker = MetadataChunker()
            metadata_chunks = metadata_chunker.create_metadata_chunks(document_data)

            current_chunk_index = 0
            for meta_chunk in metadata_chunks:
                meta_text = meta_chunk.get('chunk_text', '')
                meta_type = meta_chunk.get('chunk_type', 'metadata')
                meta_weight = meta_chunk.get('search_weight', 1.0)

                if not meta_text:
                    continue

                # Embedding生成
                meta_embedding = self.pipeline.llm_client.generate_embedding(meta_text)

                # search_indexに保存
                meta_doc = {
                    'document_id': document_id,
                    'chunk_index': current_chunk_index,
                    'chunk_content': meta_text,
                    'chunk_size': len(meta_text),
                    'chunk_type': meta_type,
                    'embedding': meta_embedding,
                    'search_weight': meta_weight
                }

                try:
                    self.db.client.table('10_ix_search_index').insert(meta_doc).execute()
                    current_chunk_index += 1
                except Exception as e:
                    logger.error(f"  チャンク保存エラー: {e}")

            logger.info(f"[チャンク化] メタデータチャンク完了: {current_chunk_index}個")

            # ============================================
            # 本文チャンク化（attachment_text）
            # ============================================
            attachment_text = document_record.get('attachment_text', '')
            if attachment_text and len(attachment_text.strip()) > 50:
                logger.info(f"[チャンク化] 本文チャンク作成開始: {len(attachment_text)}文字")

                # 小チャンク作成（150文字ずつ、オーバーラップ30文字）
                from A_common.utils.chunking import TextChunker
                chunker = TextChunker(chunk_size=150, chunk_overlap=30)
                small_chunks = chunker.split_text(attachment_text)

                logger.info(f"[チャンク化] 小チャンク数: {len(small_chunks)}個")

                # 小チャンクをembedding化して保存
                for i, chunk_dict in enumerate(small_chunks):
                    chunk_text = chunk_dict['chunk_text']
                    if not chunk_text.strip():
                        continue

                    try:
                        # Embedding生成
                        chunk_embedding = self.pipeline.llm_client.generate_embedding(chunk_text)

                        # search_indexに保存
                        chunk_doc = {
                            'document_id': document_id,
                            'chunk_index': current_chunk_index,
                            'chunk_content': chunk_text,
                            'chunk_size': len(chunk_text),
                            'chunk_type': 'content_small',
                            'embedding': chunk_embedding,
                            'search_weight': 1.0
                        }

                        self.db.client.table('10_ix_search_index').insert(chunk_doc).execute()
                        current_chunk_index += 1
                    except Exception as e:
                        logger.error(f"  小チャンク保存エラー: {e}")

            logger.info(f"[チャンク化] 全チャンク完了: {current_chunk_index}個")

            # ============================================
            # データベース更新
            # ============================================
            update_data = {
                'summary': summary,
                'metadata': metadata,
                'processing_status': 'completed',
                'processing_stage': 'stagec_and_stagea_complete',
                'stagea_classifier_model': 'gemini-2.5-flash',
                'stageb_vision_model': None,  # 動画スキップ（Stage B未使用）
                'stagec_extractor_model': 'claude-haiku-4-5-20251001',
                'text_extraction_model': None,  # 動画スキップ（抽出不要）
                'relevant_date': relevant_date,
                'attachment_text': f"【動画ファイル】{file_name}"  # 動画ファイル情報を記録
            }

            if document_date:
                update_data['document_date'] = document_date
            if tags:
                update_data['tags'] = tags

            response = self.db.client.table('Rawdata_FILE_AND_MAIL').update(update_data).eq('id', document_id).execute()

            if response.data:
                logger.success(f"✅ 動画投稿本文処理成功: {file_name}")
                logger.info(f"  チャンク数: {current_chunk_index}")
                self._mark_task_completed(queue_id, success=True)
                return True
            else:
                error_msg = "データベース更新失敗"
                logger.error(error_msg)
                self._mark_task_failed(queue_id, error_msg)
                return False

        except Exception as e:
            error_msg = f"動画投稿本文処理エラー: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.exception(e)
            self._mark_task_failed(queue_id, error_msg, error_details={'exception': str(e)})
            return False

    def _extract_file_id(self, doc: Dict[str, Any]) -> str:
        """ドキュメントからGoogle Drive ファイルIDを抽出"""
        # ★修正: source_idを最優先（GASでコピーされたファイルID、サービスアカウントに権限付与済み）

        # 1. source_id（コピー後のファイルID、サービスアカウントがアクセス可能）
        source_id = doc.get('source_id', '')
        if source_id and not source_id.isdigit():
            return source_id

        # 2. metadata->original_file_id（元のファイルID、権限がない可能性あり）
        metadata = doc.get('metadata')
        if metadata is None:
            metadata = {}
        elif isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except:
                metadata = {}

        if metadata.get('original_file_id'):
            return metadata['original_file_id']

        return ''

    def _extract_file_id_from_url(self, url: str) -> Optional[str]:
        """
        Google Drive URLからファイルIDを抽出

        Args:
            url: Google Drive URL

        Returns:
            ファイルID、またはNone

        Examples:
            https://drive.google.com/file/d/1ABC123/view -> 1ABC123
            https://drive.google.com/open?id=1ABC123 -> 1ABC123
        """
        if not url:
            return None

        import re

        # パターン1: /file/d/{file_id}/
        match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
        if match:
            return match.group(1)

        # パターン2: ?id={file_id}
        match = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url)
        if match:
            return match.group(1)

        # パターン3: /d/{file_id}/
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
        if match:
            return match.group(1)

        return None

    def _guess_mime_type(self, file_name: str) -> str:
        """ファイル名から MIME タイプを推測"""
        ext = file_name.lower().split('.')[-1] if '.' in file_name else ''

        mime_map = {
            'pdf': 'application/pdf',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'xls': 'application/vnd.ms-excel',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        }

        return mime_map.get(ext, 'application/octet-stream')

    def get_queue_stats(self) -> Dict[str, int]:
        """キューの統計情報を取得"""
        try:
            # 各ステータスの件数を集計
            stats = {}
            statuses = ['pending', 'processing', 'completed', 'failed', 'skipped']

            for status in statuses:
                result = self.db.client.table('99_lg_reprocess_queue').select(
                    '*', count='exact'
                ).eq('status', status).execute()
                stats[status] = result.count if result.count else 0

            stats['total'] = sum(stats.values())

            return stats

        except Exception as e:
            logger.error(f"統計取得エラー: {e}")
            return {}

    def print_queue_stats(self):
        """キューの統計情報を表示"""
        stats = self.get_queue_stats()

        logger.info("\n" + "="*80)
        logger.info("キュー統計")
        logger.info("="*80)
        logger.info(f"待機中 (pending):   {stats.get('pending', 0):>5}件")
        logger.info(f"処理中 (processing): {stats.get('processing', 0):>5}件")
        logger.info(f"完了   (completed):  {stats.get('completed', 0):>5}件")
        logger.info(f"失敗   (failed):     {stats.get('failed', 0):>5}件")
        logger.info(f"スキップ (skipped):  {stats.get('skipped', 0):>5}件")
        logger.info("-" * 80)
        logger.info(f"合計:                {stats.get('total', 0):>5}件")
        logger.info("="*80 + "\n")

    async def run(
        self,
        limit: int = 100,
        dry_run: bool = False,
        populate_only: bool = False,
        process_queue_only: bool = False,
        preserve_workspace: bool = True,
        workspace: str = 'all',
        auto_yes: bool = False
    ):
        """
        再処理を実行

        Args:
            limit: 処理する最大件数
            dry_run: Trueの場合、実際の処理は行わず確認のみ
            populate_only: Trueの場合、キュー追加のみ（処理は実行しない）
            process_queue_only: Trueの場合、キュー処理のみ（新規追加しない）
            preserve_workspace: Trueの場合、既存のworkspaceを保持
        """
        logger.info("\n" + "="*80)
        logger.info("Google Classroom ドキュメント再処理スクリプト v2")
        logger.info("="*80)

        if dry_run:
            logger.warning("🔍 DRY RUN モード: 実際の処理は行いません")

        # キューの現在の状態を表示
        self.print_queue_stats()

        # キューへの追加
        if not process_queue_only:
            logger.info(f"\n📥 キューへの追加を開始...")
            logger.info(f"  対象ワークスペース: {workspace}")
            logger.info(f"  最大件数: {limit}")
            logger.info(f"  Workspace保持: {preserve_workspace}")

            if not dry_run:
                added = self.populate_queue_from_workspace(
                    workspace=workspace,
                    limit=limit,
                    preserve_workspace=preserve_workspace
                )
                logger.info(f"✅ {added}件をキューに追加しました")

                # 更新後の統計を表示
                self.print_queue_stats()

        # キューから処理
        if not populate_only:
            if dry_run:
                logger.info(f"\n🔍 DRY RUN: {limit}件の処理をシミュレート")
            else:
                logger.info(f"\n⚙️  キューからの処理を開始...")

                # 確認（auto_yesが無効な場合のみ確認）
                if not auto_yes:
                    print("\n処理を開始しますか？ (y/N): ", end='')
                    response = input().strip().lower()
                    if response != 'y':
                        logger.info("処理をキャンセルしました")
                        return

                # 処理実行
                stats = await self.process_queue(limit=limit)

                # 最終結果
                logger.info("\n" + "="*80)
                logger.info("再処理完了")
                logger.info("="*80)
                logger.info(f"成功: {stats['success']}件")
                logger.info(f"失敗: {stats['failed']}件")
                logger.info(f"合計: {stats['total']}件")
                logger.info("="*80)

                # 最終的なキューの状態を表示
                self.print_queue_stats()


async def main():
    """メイン処理"""
    # コマンドライン引数のパース
    dry_run = '--dry-run' in sys.argv or '-n' in sys.argv
    populate_only = '--populate-only' in sys.argv
    process_queue_only = '--process-queue' in sys.argv
    preserve_workspace = '--no-preserve-workspace' not in sys.argv
    auto_yes = '--no' not in sys.argv  # デフォルトで自動承認（--noで確認プロンプト表示）
    limit = 100
    workspace = 'all'  # デフォルト: 全ワークスペース

    # --limit オプションの処理
    for arg in sys.argv:
        if arg.startswith('--limit='):
            try:
                limit = int(arg.split('=')[1])
            except:
                pass
        elif arg.startswith('--workspace='):
            workspace = arg.split('=')[1]

    reprocessor = ClassroomReprocessorV2()
    await reprocessor.run(
        limit=limit,
        dry_run=dry_run,
        populate_only=populate_only,
        process_queue_only=process_queue_only,
        preserve_workspace=preserve_workspace,
        workspace=workspace,
        auto_yes=auto_yes
    )


if __name__ == "__main__":
    asyncio.run(main())
