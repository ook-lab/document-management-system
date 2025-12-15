"""
日次同期スクリプト (v4.0: GitHub Actions対応版)

設計書: FINAL_UNIFIED_COMPLETE_v4.md の 7.2節 および AUTO_INBOX_COMPLETE_v3.0.md の 6.5節に準拠
目的: Google Driveからファイルを検知し、TwoStageIngestionPipelineを実行する。
"""

import os
import sys
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from loguru import logger
import argparse
import traceback
from dotenv import load_dotenv

# .envファイルを読み込む（システム環境変数よりも優先）
load_dotenv(override=True)

# パス設定
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.connectors.google_drive import GoogleDriveConnector
from pipelines.two_stage_ingestion import TwoStageIngestionPipeline

# ログ設定 (loguruを使用)
log_dir = Path('logs')
log_dir.mkdir(exist_ok=True)

logger.add(log_dir / f'daily_sync_{datetime.now():%Y%m%d}.log', rotation="10 MB", level="INFO")
logger.add(sys.stdout, level="INFO")


class DailySyncProcessor:
    """日次同期処理クラス"""

    def __init__(self, workspace_folders: Dict[str, str], full_sync: bool = False):

        self.workspace_folders = workspace_folders
        self.full_sync = full_sync
        self.drive = GoogleDriveConnector()
        self.pipeline = TwoStageIngestionPipeline()
        
    def _scan_folder(self, folder_id: str) -> List[Dict[str, Any]]:
        """
        指定されたフォルダ内の未処理ファイルをスキャンする
        
        Phase 1Aでは、InBox方式ではなく特定のフォルダをスキャンすることを想定する。
        """
        logger.info(f"[SCAN] フォルダID [{folder_id}] からファイルをスキャン中...")
        
        # Google Drive Connectorを使用してファイルリストを取得
        # 現状は、単純にフォルダ内の全ファイルを取得する
        files = self.drive.list_files_in_folder(folder_id)
        
        # 実際にはここで DB をチェックし、既に処理済みの source_id を持つファイルをフィルタする
        
        logger.info(f"[OK] {len(files)} 件のファイルを検出しました。")
        return files

    async def run_sync(self):
        """同期処理のメイン実行"""
        logger.info("=" * 60)
        logger.info("自動日次同期処理 開始 (v4.0 Hybrid AI)")
        logger.info("=" * 60)
        
        stats = {
            'total_files': 0,
            'processed_success': 0,
            'processed_failed': 0,
            'skipped': 0
        }
        
        for workspace, folder_id in self.workspace_folders.items():
            if not folder_id:
                logger.warning(f"ワークスペース [{workspace}] のフォルダIDが設定されていません。スキップします。")
                continue
                
            files_to_process = self._scan_folder(folder_id)
            
            for file_meta in files_to_process:
                stats['total_files'] += 1
                try:
                    # メインパイプラインを実行
                    result = await self.pipeline.process_file(file_meta, workspace=workspace)

                    if result and result.get('status') == 'skipped':
                        stats['skipped'] += 1
                    elif result:
                        stats['processed_success'] += 1
                    else:
                        stats['processed_failed'] += 1
                        
                except Exception as e:
                    logger.error(f"ファイル処理中に致命的なエラーが発生: {file_meta['name']} - {e}")
                    logger.error(traceback.format_exc())
                    stats['processed_failed'] += 1
        
        logger.info("=" * 60)
        logger.info("自動日次同期処理 完了サマリー")
        logger.info(f"総検出ファイル数: {stats['total_files']}")
        logger.info(f"処理成功数: {stats['processed_success']}")
        logger.info(f"スキップ数: {stats['skipped']}")
        logger.info(f"処理失敗数: {stats['processed_failed']}")
        logger.info("=" * 60)
        
        return stats


async def main():
    parser = argparse.ArgumentParser(description='自動日次同期スクリプト v4.0')
    parser.add_argument('--business-id', type=str, default=os.getenv('BUSINESS_FOLDER_ID'), help='ビジネス用フォルダID')
    parser.add_argument('--personal-id', type=str, default=os.getenv('PERSONAL_FOLDER_ID'), help='個人用フォルダID')
    parser.add_argument('--full-sync', action='store_true', help='フルスキャンモード（既存ファイルも再処理）')
    parser.add_argument('--folder-id', type=str, help='指定されたフォルダのみ処理')

    args = parser.parse_args()

    # --folder-id が指定された場合は、そのフォルダのみ処理
    if args.folder_id:
        workspace_folders = {
            'specified': args.folder_id
        }
    else:
        # 処理対象フォルダの定義 (Phase 1Aでは、PROGRESS_TRACKER.mdに基づき、ユーザーが設定した特定のフォルダを使用)
        # ユーザーが Phase 1A で使用する特定のフォルダIDを環境変数または引数で渡すことを想定
        workspace_folders = {
            'personal': args.personal_id,
            'business': args.business_id
        }

        # フォルダIDが設定されていない場合はエラー終了
        if not args.personal_id and not args.business_id:
            logger.error("処理対象のフォルダID (PERSONAL_FOLDER_ID または BUSINESS_FOLDER_ID) が設定されていません。")
            sys.exit(1)

    processor = DailySyncProcessor(workspace_folders, full_sync=args.full_sync)
    stats = await processor.run_sync()

    # 終了コード決定
    if stats['total_files'] == 0:
        logger.info("処理対象ファイルが0件でした。")
        sys.exit(3)

    failure_rate = stats['processed_failed'] / stats['total_files']

    if failure_rate >= 0.5:
        logger.error(f"失敗率が高すぎます ({failure_rate:.1%})。システムレベルの問題の可能性があります。")
        sys.exit(1)
    elif stats['processed_failed'] > 0:
        logger.warning(f"{stats['processed_failed']}件のファイル処理が失敗しました。詳細はログを確認してください。")
        sys.exit(2)
    else:
        logger.info("全ファイルの処理が正常に完了しました。")
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())