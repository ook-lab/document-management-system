"""
シンプル版ドキュメント処理スクリプト

キューテーブルを使わず、Rawdata_FILE_AND_MAIL.processing_status で直接管理

処理内容:
1. processing_status='pending' のドキュメントを取得
2. 統合パイプライン（Stage E-K）で処理
3. 成功: processing_status='completed'
4. 失敗: processing_status='failed'

使い方:
    # 全ワークスペースを処理
    python process_queued_documents_v3.py --limit=100

    # 特定のワークスペースのみ
    python process_queued_documents_v3.py --workspace=ema_classroom --limit=20

    # pendingにリセット（再処理用）
    python process_queued_documents_v3.py --reset-to-pending --workspace=all
"""

import asyncio
from typing import List, Dict, Any, Optional
import sys
from datetime import datetime
from pathlib import Path

from A_common.database.client import DatabaseClient
from A_common.connectors.google_drive import GoogleDriveConnector
from G_unified_pipeline import UnifiedDocumentPipeline


class DocumentProcessor:
    """ドキュメント処理（シンプル版）"""

    VIDEO_EXTENSIONS = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.m4v', '.mpeg', '.mpg']

    def __init__(self):
        self.db = DatabaseClient()
        self.pipeline = UnifiedDocumentPipeline(db_client=self.db)
        self.drive = GoogleDriveConnector()
        self.temp_dir = Path("./temp")
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def get_pending_documents(self, workspace: str = 'all', limit: int = 100) -> List[Dict[str, Any]]:
        """
        processing_status='pending' のドキュメントを取得

        Args:
            workspace: 対象ワークスペース ('all' で全ワークスペース)
            limit: 取得する最大件数

        Returns:
            ドキュメントリスト
        """
        query = self.db.client.table('Rawdata_FILE_AND_MAIL').select('*').eq('processing_status', 'pending')

        if workspace != 'all':
            query = query.eq('workspace', workspace)

        result = query.limit(limit).execute()
        return result.data if result.data else []

    def mark_as_processing(self, document_id: str):
        """処理中にマーク"""
        try:
            self.db.client.table('Rawdata_FILE_AND_MAIL').update({
                'processing_status': 'processing'
            }).eq('id', document_id).execute()
        except Exception as e:
            print("ERROR:", f"処理中マークエラー: {e}")

    def mark_as_completed(self, document_id: str):
        """完了にマーク"""
        try:
            self.db.client.table('Rawdata_FILE_AND_MAIL').update({
                'processing_status': 'completed'
            }).eq('id', document_id).execute()
        except Exception as e:
            print("ERROR:", f"完了マークエラー: {e}")

    def mark_as_failed(self, document_id: str, error_message: str = ""):
        """失敗にマーク"""
        try:
            update_data = {'processing_status': 'failed'}

            # エラーメッセージをメタデータに保存
            if error_message:
                # 既存のメタデータを取得
                doc_result = self.db.client.table('Rawdata_FILE_AND_MAIL').select('metadata').eq('id', document_id).execute()
                if doc_result.data and len(doc_result.data) > 0:
                    metadata = doc_result.data[0].get('metadata', {}) or {}
                else:
                    metadata = {}

                metadata['last_error'] = error_message
                metadata['last_error_time'] = datetime.now().isoformat()
                update_data['metadata'] = metadata

            self.db.client.table('Rawdata_FILE_AND_MAIL').update(update_data).eq('id', document_id).execute()
        except Exception as e:
            print("ERROR:", f"失敗マークエラー: {e}")

    async def process_document(
        self,
        doc: Dict[str, Any],
        preserve_workspace: bool = True
    ) -> bool:
        """
        ドキュメントを処理

        Args:
            doc: ドキュメントデータ
            preserve_workspace: workspaceを保持するか

        Returns:
            成功したかどうか
        """
        document_id = doc['id']
        file_name = doc.get('file_name', 'unknown')
        source_type = doc.get('source_type', '')

        try:
            # 処理中にマーク
            self.mark_as_processing(document_id)

            # source_idの有無で判断（source_typeには依存しない）
            drive_file_id = doc.get('source_id')

            if drive_file_id:
                # 添付ファイルあり（Drive File IDが存在）
                result = await self._process_with_attachment(doc, preserve_workspace)
            else:
                # テキストのみ（添付ファイルなし）
                result = await self._process_text_only(doc, preserve_workspace)

            # 結果がboolの場合（後方互換性）
            if isinstance(result, bool):
                success = result
                error_msg = "処理失敗（詳細なし）" if not success else None
            else:
                # 結果がdictの場合（詳細エラー付き）
                success = result.get('success', False)
                error_msg = result.get('error', "不明なエラー") if not success else None

            # ステータス更新
            if success:
                self.mark_as_completed(document_id)
                print(f"✅ 処理成功: {file_name}")
            else:
                self.mark_as_failed(document_id, error_msg)
                print("ERROR:", f"❌ 処理失敗: {file_name} - {error_msg}")

            return success

        except Exception as e:
            error_msg = f"処理中にエラー: {str(e)}"
            print("ERROR:", f"❌ {error_msg}")
            self.mark_as_failed(document_id, error_msg)
            return False

    async def _process_text_only(
        self,
        doc: Dict[str, Any],
        preserve_workspace: bool = True
    ) -> bool:
        """テキストのみドキュメントを処理（統合パイプラインのStage H-K部分のみ使用）"""
        from A_common.processing.metadata_chunker import MetadataChunker

        document_id = doc['id']
        file_name = doc.get('file_name', 'text_only')
        workspace_to_use = doc.get('workspace', 'unknown') if preserve_workspace else 'unknown'

        display_subject = doc.get('display_subject', '')
        display_post_text = doc.get('display_post_text', '')
        attachment_text = doc.get('attachment_text', '')

        # テキスト結合
        text_parts = []
        if display_subject:
            text_parts.append(f"【件名】\n{display_subject}")
        if display_post_text:
            text_parts.append(f"【本文】\n{display_post_text}")
        if attachment_text:
            text_parts.append(f"【添付ファイル】\n{attachment_text}")

        combined_text = '\n\n'.join(text_parts)

        if not combined_text.strip():
            error_msg = "テキストが空です"
            print("ERROR:", error_msg)
            return {'success': False, 'error': error_msg}

        # 統合パイプラインの Stage H-K を使用
        # config から設定を取得
        stage_h_config = self.pipeline.config.get_stage_config('stage_h', doc.get('doc_type', 'other'), workspace_to_use)

        # Stage H: 構造化
        stageh_result = self.pipeline.stage_h.process(
            file_name=file_name,
            doc_type=doc.get('doc_type', 'unknown'),
            workspace=workspace_to_use,
            combined_text=combined_text,
            prompt=stage_h_config['prompt'],
            model=stage_h_config['model']
        )

        # Stage H の結果をチェック
        if not stageh_result or not isinstance(stageh_result, dict):
            error_msg = "Stage H失敗: 構造化結果が不正です"
            print("ERROR:", error_msg)
            return {'success': False, 'error': error_msg}

        stageh_metadata = stageh_result.get('metadata', {})
        if stageh_metadata.get('extraction_failed'):
            error_msg = "Stage H失敗: JSON抽出に失敗しました"
            print("ERROR:", error_msg)
            return {'success': False, 'error': error_msg}

        document_date = stageh_result.get('document_date')
        tags = stageh_result.get('tags', [])

        # Stage I はスキップ（テキストのみなので要約不要）

        # Stage J: チャンク化
        metadata_chunker = MetadataChunker()
        document_data = {
            'file_name': file_name,
            'summary': '',
            'document_date': document_date,
            'tags': tags,
            'doc_type': doc.get('doc_type'),
            'display_subject': display_subject,
            'display_post_text': display_post_text,
            'display_sender': doc.get('display_sender'),
            'display_type': doc.get('display_type'),
            'display_sent_at': doc.get('display_sent_at'),
            'classroom_sender_email': doc.get('classroom_sender_email'),
            'attachment_text': attachment_text,
            'persons': stageh_metadata.get('persons', []) if isinstance(stageh_metadata, dict) else [],
            'organizations': stageh_metadata.get('organizations', []) if isinstance(stageh_metadata, dict) else [],
            'people': stageh_metadata.get('people', []) if isinstance(stageh_metadata, dict) else [],
            # Stage H の構造化データを追加
            'text_blocks': stageh_metadata.get('text_blocks', []) if isinstance(stageh_metadata, dict) else [],
            'structured_tables': stageh_metadata.get('structured_tables', []) if isinstance(stageh_metadata, dict) else [],
            'weekly_schedule': stageh_metadata.get('weekly_schedule', []) if isinstance(stageh_metadata, dict) else [],
            'other_text': stageh_metadata.get('other_text', []) if isinstance(stageh_metadata, dict) else []
        }

        chunks = metadata_chunker.create_metadata_chunks(document_data)

        # 既存チャンクを削除
        try:
            self.db.client.table('10_ix_search_index').delete().eq('document_id', document_id).execute()
        except Exception as e:
            print("WARNING:", f"既存チャンク削除エラー（継続）: {e}")

        # Stage K: Embedding + 保存
        stage_k_result = self.pipeline.stage_k.embed_and_save(document_id, chunks)

        if not stage_k_result.get('success'):
            error_msg = f"Stage K失敗: {stage_k_result.get('failed_count', 0)}/{len(chunks)}チャンク保存失敗"
            print("ERROR:", error_msg)
            return {'success': False, 'error': error_msg}

        # 部分的失敗もエラーとして扱う（厳格モード）
        failed_count = stage_k_result.get('failed_count', 0)
        if failed_count > 0:
            error_msg = f"Stage K部分失敗: {failed_count}/{len(chunks)}チャンク保存失敗"
            print("ERROR:", error_msg)
            return {'success': False, 'error': error_msg}

        print(f"チャンク保存完了: {stage_k_result.get('saved_count', 0)}/{len(chunks)}件")

        # ドキュメント更新
        try:
            self.db.client.table('Rawdata_FILE_AND_MAIL').update({
                'tags': tags,
                'document_date': document_date,
                'metadata': stageh_metadata
            }).eq('id', document_id).execute()
        except Exception as e:
            error_msg = f"ドキュメント更新エラー: {e}"
            print("ERROR:", error_msg)
            return {'success': False, 'error': error_msg}

        return {'success': True}

    async def _process_with_attachment(
        self,
        doc: Dict[str, Any],
        preserve_workspace: bool = True
    ) -> bool:
        """添付ファイルありドキュメントを処理"""
        document_id = doc['id']
        file_name = doc.get('file_name', 'unknown')
        drive_file_id = doc.get('source_id')

        if not drive_file_id:
            print("ERROR:", "source_id（Drive File ID）がありません")
            return False

        # ファイル拡張子チェック
        file_extension = Path(file_name).suffix.lower()
        if file_extension in self.VIDEO_EXTENSIONS:
            print(f"⏭️  動画ファイルをスキップ: {file_name}")
            return False

        # Driveからダウンロード
        try:
            self.drive.download_file(drive_file_id, file_name, str(self.temp_dir))
            local_path = self.temp_dir / file_name
        except Exception as e:
            # 404エラー（ファイルが存在しない）の場合、テキストのみ処理にフォールバック
            error_str = str(e)
            if 'File not found' in error_str or '404' in error_str:
                print("WARNING:", f"Driveにファイルが存在しません。テキストのみ処理にフォールバック: {file_name}")
                return await self._process_text_only(doc, preserve_workspace)
            else:
                print("ERROR:", f"ダウンロード失敗: {e}")
                return False

        # MIMEタイプを推測
        mime_type = doc.get('mimeType', 'application/octet-stream')

        # 統合パイプラインで処理
        try:
            workspace_to_use = doc.get('workspace', 'unknown') if preserve_workspace else 'unknown'

            result = await self.pipeline.process_document(
                file_path=Path(local_path),
                file_name=file_name,
                doc_type=doc.get('doc_type', 'other'),
                workspace=workspace_to_use,
                mime_type=mime_type,
                source_id=drive_file_id,
                existing_document_id=document_id,
                extra_metadata={
                    'display_subject': doc.get('display_subject'),
                    'display_post_text': doc.get('display_post_text'),
                    'display_sender': doc.get('display_sender'),
                    'display_type': doc.get('display_type'),
                    'display_sent_at': doc.get('display_sent_at'),
                    'classroom_sender_email': doc.get('classroom_sender_email')
                }
            )

            # 結果全体を返す（エラーメッセージを含む）
            return result

        finally:
            # 一時ファイル削除
            if local_path.exists():
                local_path.unlink()
                print("DEBUG:", f"一時ファイル削除: {local_path}")

    async def run(
        self,
        workspace: str = 'all',
        limit: int = 100,
        preserve_workspace: bool = True
    ):
        """
        処理を実行

        Args:
            workspace: 対象ワークスペース
            limit: 処理する最大件数
            preserve_workspace: workspaceを保持するか
        """
        print("="*80)
        print("ドキュメント処理スクリプト（シンプル版）")
        print("="*80)

        # pending ドキュメントを取得
        docs = self.get_pending_documents(workspace, limit)

        if not docs:
            print("処理対象のドキュメントがありません")
            return

        print(f"処理対象: {len(docs)}件")
        print("")

        # 統計
        stats = {'success': 0, 'failed': 0, 'total': len(docs)}

        # 順次処理
        for i, doc in enumerate(docs, 1):
            file_name = doc.get('file_name', 'unknown')
            print(f"\n{'='*80}")
            print(f"[{i}/{len(docs)}] 処理開始: {file_name}")
            print(f"Document ID: {doc['id']}")

            success = await self.process_document(doc, preserve_workspace)

            if success:
                stats['success'] += 1
            else:
                stats['failed'] += 1

            print(f"進捗: 成功={stats['success']}, 失敗={stats['failed']}, 残り={len(docs)-i}")

        # 最終結果
        print("\n" + "="*80)
        print("処理完了")
        print("="*80)
        print(f"✅ 成功: {stats['success']}件")
        print(f"❌ 失敗: {stats['failed']}件")
        print(f"📊 合計: {stats['total']}件")
        print("="*80)


async def main():
    """メイン関数"""
    import argparse

    parser = argparse.ArgumentParser(description='ドキュメント処理スクリプト（シンプル版）')
    parser.add_argument('--workspace', default='all', help='対象ワークスペース (デフォルト: all)')
    parser.add_argument('--limit', type=int, default=100, help='処理する最大件数 (デフォルト: 100)')
    parser.add_argument('--no-preserve-workspace', action='store_true', help='workspaceを保持しない')

    args = parser.parse_args()

    processor = DocumentProcessor()
    await processor.run(
        workspace=args.workspace,
        limit=args.limit,
        preserve_workspace=not args.no_preserve_workspace
    )


if __name__ == '__main__':
    asyncio.run(main())
