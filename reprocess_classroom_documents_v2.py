"""
Google Classroom ドキュメントの再処理スクリプト v2

処理状態管理テーブル (document_reprocessing_queue) を使用した改良版。
重複処理を防ぎ、処理進捗を追跡し、エラー時のリトライを可能にします。

処理内容:
1. すべてのワークスペース（デフォルト）または指定されたワークスペースのドキュメントをキューに登録
2. キューから順次タスクを取得して処理
3. 既存の2段階パイプライン（Gemini分類 + Claude抽出）で処理
4. full_text、構造化metadataを生成
5. 処理状態をデータベースで管理（pending → processing → completed/failed）

使い方:
    # 全ワークスペースを処理（デフォルト）
    python reprocess_classroom_documents_v2.py --limit=100

    # ドライラン（確認のみ）
    python reprocess_classroom_documents_v2.py --dry-run

    # 特定のワークスペースのみ処理
    python reprocess_classroom_documents_v2.py --workspace=ema_classroom --limit=20
    python reprocess_classroom_documents_v2.py --workspace=ikuya_classroom --limit=20

    # キューに追加のみ（処理は実行しない）
    python reprocess_classroom_documents_v2.py --populate-only --limit=50

    # キューから処理実行
    python reprocess_classroom_documents_v2.py --process-queue --limit=10

    # ワークスペースを保持しない（Stage1 AIに判定させる）
    python reprocess_classroom_documents_v2.py --no-preserve-workspace
"""

import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger
import json
import sys
from datetime import datetime

from core.database.client import DatabaseClient
from pipelines.two_stage_ingestion import TwoStageIngestionPipeline


class ClassroomReprocessorV2:
    """Google Classroomドキュメントの再処理（処理状態管理テーブル対応版）"""

    def __init__(self, worker_id: str = "reprocessor_v2"):
        self.db = DatabaseClient()
        self.pipeline = TwoStageIngestionPipeline()
        self.worker_id = worker_id

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

        # 対象ドキュメントを取得
        if workspace == 'all':
            # 全ワークスペースを対象
            result = self.db.client.table('documents').select('*').limit(limit).execute()
        else:
            # 特定のワークスペースのみ
            result = self.db.client.table('documents').select('*').eq(
                'workspace', workspace
            ).limit(limit).execute()

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
            existing = self.db.client.table('document_reprocessing_queue').select('id, status').eq(
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

                self.db.client.table('document_reprocessing_queue').insert(queue_data).execute()
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

            # パイプラインで処理
            result = await self.pipeline.process_file(
                file_meta=file_meta,
                workspace=workspace_to_use,
                force_reprocess=True
            )

            if result and result.get('success'):
                logger.success(f"✅ 再処理成功: {file_name}")
                self._mark_task_completed(queue_id, success=True)
                return True

            elif result and result.get('error') and 'duplicate key' in str(result.get('error')):
                # 重複エラーの場合、古いレコードを削除して再試行
                logger.warning(f"重複検出、古いレコードを削除して再試行")
                self.db.client.table('documents').delete().eq('id', document_id).execute()

                # 再試行
                result = await self.pipeline.process_file(
                    file_meta=file_meta,
                    workspace=workspace_to_use,
                    force_reprocess=True
                )

                if result and result.get('success'):
                    logger.success(f"✅ 再処理成功（再試行）: {file_name}")
                    self._mark_task_completed(queue_id, success=True)
                    return True
                else:
                    error_msg = f"再試行も失敗: {result.get('error', 'unknown')}"
                    logger.error(f"❌ {error_msg}")
                    self._mark_task_failed(queue_id, error_msg)
                    return False
            else:
                error_msg = result.get('error', 'unknown error') if result else 'no result'
                logger.error(f"❌ 再処理失敗: {error_msg}")
                self._mark_task_failed(queue_id, error_msg)
                return False

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
        from core.ai.stage1_classifier import Stage1Classifier
        from core.ai.stage2_extractor import Stage2Extractor
        from config.yaml_loader import get_classification_yaml_string

        file_name = doc.get('file_name', 'text_only')
        full_text = doc.get('full_text', '')

        if not full_text:
            error_msg = "full_textが空です"
            logger.error(f"{error_msg}: {file_name}")
            self._mark_task_failed(queue_id, error_msg)
            return False

        logger.info(f"テキスト長: {len(full_text)}文字")

        try:
            # Stage 1とStage 2のクライアントを初期化
            stage1_classifier = Stage1Classifier(llm_client=self.pipeline.llm_client)
            stage2_extractor = Stage2Extractor(llm_client=self.pipeline.llm_client)
            yaml_string = get_classification_yaml_string()

            # workspaceを決定
            workspace_to_use = doc.get('workspace', 'unknown') if preserve_workspace else 'unknown'

            # ============================================
            # Stage 1: Gemini分類
            # ============================================
            logger.info("[Stage 1] Gemini分類開始...")
            # テキストのみドキュメントの場合、file_pathは不要
            # mime_typeをtext/plainに設定し、text_contentを渡す
            from pathlib import Path as PathLib
            stage1_result = await stage1_classifier.classify(
                file_path=PathLib("dummy"),  # ダミーパス（使用されない）
                doc_types_yaml=yaml_string,
                mime_type="text/plain",  # PDFではないことを示す
                text_content=full_text
            )

            # Stage1はdoc_typeとworkspaceを返さない（入力元で決定されるため）
            stage1_doc_type = doc.get('doc_type', 'unknown')  # 元のdoc_typeを保持
            summary = stage1_result.get('summary', '')
            relevant_date = stage1_result.get('relevant_date')

            logger.info(f"[Stage 1] 完了: summary={summary[:50]}...")

            # ============================================
            # Stage 2: Claude詳細抽出
            # ============================================
            logger.info("[Stage 2] Claude詳細抽出開始...")
            stage2_result = stage2_extractor.extract_metadata(
                full_text=full_text,
                file_name=file_name,
                stage1_result=stage1_result,
                workspace=doc.get('workspace', 'unknown')  # 元のworkspaceを使用
            )

            # Stage 2の結果を反映
            doc_type = stage2_result.get('doc_type', stage1_doc_type)
            summary = stage2_result.get('summary', summary)
            document_date = stage2_result.get('document_date')
            tags = stage2_result.get('tags', [])
            metadata = stage2_result.get('metadata', {})

            logger.info(f"[Stage 2] 完了: doc_type={doc_type}")

            # ============================================
            # データベース更新
            # ============================================
            update_data = {
                # doc_type と workspace は入力元の反映なので更新しない（破壊行為になる）
                # 'doc_type': doc_type,
                # 'workspace': workspace_to_use,
                'summary': summary,
                'metadata': metadata,
                'processing_status': 'completed',
                'processing_stage': 'stage1_and_stage2',
                'stage1_model': 'gemini-2.5-flash',
                'stage2_model': 'claude-haiku-4-5-20251001',
                'relevant_date': relevant_date
            }

            response = self.db.client.table('documents').update(update_data).eq('id', document_id).execute()

            if response.data:
                logger.success(f"✅ テキストのみドキュメント再処理成功: {file_name}")
                logger.info(f"  Stage1: {stage1_doc_type}")
                logger.info(f"  Stage2: {doc_type}")
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

    def _extract_file_id(self, doc: Dict[str, Any]) -> str:
        """ドキュメントからGoogle Drive ファイルIDを抽出"""
        # 1. metadata->original_file_id を確認
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

        # 3. source_id を確認（数字だけの場合はClassroom IDなので使わない）
        source_id = doc.get('source_id', '')
        if source_id and not source_id.isdigit():
            return source_id

        return ''

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
                result = self.db.client.table('document_reprocessing_queue').select(
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
        workspace: str = 'all'
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

                # 確認
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
        workspace=workspace
    )


if __name__ == "__main__":
    asyncio.run(main())
