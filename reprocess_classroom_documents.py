"""
Google Classroom ドキュメントの再処理スクリプト

既存の TwoStageIngestionPipeline を使用して、
Google Classroomから取り込まれたドキュメントを完全に再処理します。

処理内容:
1. workspace='ikuya_classroom' のドキュメントを取得
2. original_file_id を使ってGoogle Driveからファイルを取得
3. 既存の2段階パイプライン（Gemini分類 + Claude抽出）で処理
4. full_text、構造化metadata、embedding を生成
5. workspace を IKUYA_SCHOOL に修正
"""

import asyncio
from typing import List, Dict, Any
from loguru import logger
import json

from core.database.client import DatabaseClient
from pipelines.two_stage_ingestion import TwoStageIngestionPipeline
class ClassroomReprocessor:
    """Google Classroomドキュメントの再処理"""

    def __init__(self):
        self.db = DatabaseClient()
        self.pipeline = TwoStageIngestionPipeline()

    def get_classroom_documents(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        再処理対象のGoogle Classroomドキュメントを取得

        Args:
            limit: 取得件数の上限

        Returns:
            ドキュメントのリスト
        """
        logger.info("Google Classroomドキュメントを取得中...")

        result = self.db.client.table('documents').select('*').eq(
            'workspace', 'ikuya_classroom'
        ).limit(limit).execute()

        documents = result.data if result.data else []
        logger.info(f"{len(documents)}件のドキュメントを取得しました")

        return documents

    def extract_file_id(self, doc: Dict[str, Any]) -> str:
        """
        ドキュメントからGoogle Drive ファイルIDを抽出

        Args:
            doc: ドキュメント辞書

        Returns:
            ファイルID、見つからない場合は空文字列
        """
        # 1. drive_file_id を優先
        if doc.get('drive_file_id'):
            return doc['drive_file_id']

        # 2. metadata->original_file_id を確認
        metadata = doc.get('metadata', {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except:
                metadata = {}

        if metadata.get('original_file_id'):
            return metadata['original_file_id']

        # 3. source_id を確認（ただしこれはClassroom投稿IDの可能性）
        # source_idが長い数字の場合はClassroom IDなので使わない
        source_id = doc.get('source_id', '')
        if source_id and not source_id.isdigit():
            return source_id

        return ''

    async def reprocess_document(self, doc: Dict[str, Any], preserve_workspace: bool = True) -> bool:
        """
        単一ドキュメントを再処理

        Args:
            doc: ドキュメント辞書
            preserve_workspace: Trueの場合、既存のworkspaceを保持

        Returns:
            成功したかどうか
        """
        doc_id = doc['id']
        file_name = doc['file_name']
        existing_workspace = doc.get('workspace', 'unknown')

        logger.info(f"\n{'='*80}")
        logger.info(f"再処理開始: {file_name}")
        logger.info(f"Document ID: {doc_id}")
        logger.info(f"既存のworkspace: {existing_workspace}")

        # ファイルIDを取得
        file_id = self.extract_file_id(doc)

        if not file_id:
            logger.error(f"ファイルIDが見つかりません: {file_name}")
            logger.error(f"  drive_file_id: {doc.get('drive_file_id')}")
            logger.error(f"  source_id: {doc.get('source_id')}")
            logger.error(f"  metadata: {doc.get('metadata')}")
            return False

        logger.info(f"使用するファイルID: {file_id}")

        # ファイルメタデータを構築（TwoStageIngestionPipeline.process_file用）
        file_meta = {
            'id': file_id,
            'name': file_name,
            'mimeType': self._guess_mime_type(file_name)
        }

        # workspaceを決定
        if preserve_workspace:
            workspace_to_use = existing_workspace
            logger.info(f"既存のworkspaceを保持: {workspace_to_use}")
        else:
            workspace_to_use = "unknown"
            logger.info(f"workspaceをStage1に判定させます")

        try:
            # 既存のパイプラインで処理
            result = await self.pipeline.process_file(
                file_meta=file_meta,
                workspace=workspace_to_use
            )

            if result and result.get('success'):
                logger.success(f"✅ 再処理成功: {file_name}")

                # 古いレコードを削除（新しいレコードが作成されるため）
                logger.info(f"古いレコードを削除: {doc_id}")
                self.db.client.table('documents').delete().eq('id', doc_id).execute()

                return True
            else:
                logger.error(f"❌ 再処理失敗: {file_name}")
                return False

        except Exception as e:
            logger.error(f"❌ 再処理中にエラー: {file_name}")
            logger.error(f"エラー詳細: {str(e)}")
            logger.exception(e)
            return False

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

    async def run(self, limit: int = 100, dry_run: bool = False, preserve_workspace: bool = True):
        """
        再処理を実行

        Args:
            limit: 処理する最大件数
            dry_run: Trueの場合、実際の処理は行わず確認のみ
            preserve_workspace: Trueの場合、既存のworkspaceを保持
        """
        logger.info("\n" + "="*80)
        logger.info("Google Classroom ドキュメント再処理スクリプト")
        logger.info("="*80)

        if dry_run:
            logger.warning("🔍 DRY RUN モード: 実際の処理は行いません")

        # 対象ドキュメントを取得
        documents = self.get_classroom_documents(limit)

        if not documents:
            logger.info("再処理対象のドキュメントがありません")
            return

        logger.info(f"\n処理予定: {len(documents)}件")
        if preserve_workspace:
            logger.info(f"Workspace: 既存の値を保持（ikuya_classroom のまま）")
        else:
            logger.info(f"Workspace: Stage1 AIに判定させる")

        # 確認
        if not dry_run:
            print("\n処理を開始しますか？ (y/N): ", end='')
            response = input().strip().lower()
            if response != 'y':
                logger.info("処理をキャンセルしました")
                return

        # 統計
        success_count = 0
        failed_count = 0

        # 各ドキュメントを処理
        for idx, doc in enumerate(documents, 1):
            logger.info(f"\n[{idx}/{len(documents)}] 処理中...")

            if dry_run:
                file_id = self.extract_file_id(doc)
                logger.info(f"  ファイル: {doc['file_name']}")
                logger.info(f"  ファイルID: {file_id or 'NOT FOUND'}")
                logger.info(f"  現在のworkspace: {doc.get('workspace')}")
                logger.info(f"  現在のdoc_type: {doc.get('doc_type')}")
                if preserve_workspace:
                    logger.info(f"  → workspace: {doc.get('workspace')} (保持)")
                else:
                    logger.info(f"  → workspace: Stage1が判定")
                continue

            # 実際の再処理
            success = await self.reprocess_document(doc, preserve_workspace=preserve_workspace)

            if success:
                success_count += 1
            else:
                failed_count += 1

            # 進捗表示
            logger.info(f"進捗: 成功={success_count}, 失敗={failed_count}")

        # 最終結果
        logger.info("\n" + "="*80)
        logger.info("再処理完了")
        logger.info(f"成功: {success_count}件")
        logger.info(f"失敗: {failed_count}件")
        logger.info(f"合計: {len(documents)}件")
        logger.info("="*80)


async def main():
    """メイン処理"""
    import sys

    # コマンドライン引数のパース
    dry_run = '--dry-run' in sys.argv or '-n' in sys.argv
    preserve_workspace = '--preserve-workspace' not in sys.argv  # デフォルトTrue
    limit = 100

    # --limit オプションの処理
    for arg in sys.argv:
        if arg.startswith('--limit='):
            try:
                limit = int(arg.split('=')[1])
            except:
                pass

    reprocessor = ClassroomReprocessor()
    await reprocessor.run(limit=limit, dry_run=dry_run, preserve_workspace=preserve_workspace)


if __name__ == "__main__":
    asyncio.run(main())
