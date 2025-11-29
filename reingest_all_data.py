"""
全データ再取り込みスクリプト
ハイブリッドPDF抽出（pypdf + Gemini Vision）で全ファイルを再処理
"""
import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from loguru import logger

from pipelines.two_stage_ingestion import TwoStageIngestionPipeline
from core.database.client import DatabaseClient

# 環境変数読み込み
load_dotenv()

# 統計情報
class ProcessingStats:
    def __init__(self):
        self.total = 0
        self.success = 0
        self.skipped = 0
        self.failed = 0
        self.vision_used = 0
        self.errors = []
        self.start_time = None
        self.end_time = None

    def add_success(self, file_name, vision_used=False):
        self.success += 1
        if vision_used:
            self.vision_used += 1
        logger.info(f"✅ [{self.success}/{self.total}] 成功: {file_name}")

    def add_skipped(self, file_name):
        self.skipped += 1
        logger.info(f"⏭️  [{self.success + self.skipped + self.failed}/{self.total}] スキップ: {file_name}")

    def add_failed(self, file_name, error):
        self.failed += 1
        error_msg = str(error)
        self.errors.append((file_name, error_msg))
        logger.error(f"❌ [{self.success + self.skipped + self.failed}/{self.total}] 失敗: {file_name} - {error_msg}")

    def print_summary(self):
        """処理結果サマリーを表示"""
        duration = (self.end_time - self.start_time).total_seconds() if self.end_time and self.start_time else 0

        logger.info("=" * 80)
        logger.info("📊 全データ再取り込み完了")
        logger.info("=" * 80)
        logger.info(f"総ファイル数:     {self.total} 件")
        logger.info(f"✅ 成功:          {self.success} 件")
        logger.info(f"⏭️  スキップ:      {self.skipped} 件")
        logger.info(f"❌ 失敗:          {self.failed} 件")
        logger.info(f"🤖 Vision補完:    {self.vision_used} 件")
        logger.info(f"⏱️  処理時間:      {duration:.1f} 秒 ({duration/60:.1f} 分)")

        if self.errors:
            logger.warning("-" * 80)
            logger.warning(f"❌ エラー詳細 ({len(self.errors)} 件):")
            for file_name, error_msg in self.errors:
                logger.warning(f"   - {file_name}: {error_msg}")

        logger.info("=" * 80)


async def reingest_all_data(skip_existing: bool = True):
    """
    全データを再取り込み

    Args:
        skip_existing: 既存データをスキップするか（True: スキップ、False: 削除して再処理）
    """
    stats = ProcessingStats()
    stats.start_time = datetime.now()

    logger.info("=" * 80)
    logger.info("🚀 全データ再取り込み開始")
    logger.info("=" * 80)
    logger.info(f"スキップモード: {'ON (既存データはスキップ)' if skip_existing else 'OFF (既存データを削除して再処理)'}")
    logger.info("-" * 80)

    # パイプライン初期化
    try:
        pipeline = TwoStageIngestionPipeline()
        logger.info("✅ パイプライン初期化完了")
    except Exception as e:
        logger.critical(f"❌ パイプライン初期化失敗: {e}")
        return

    # Google Drive フォルダID取得
    folder_id = os.getenv('PERSONAL_FOLDER_ID')
    if not folder_id:
        logger.critical("❌ PERSONAL_FOLDER_ID が設定されていません")
        return

    # ファイルリスト取得
    try:
        files = pipeline.drive.list_files_in_folder(folder_id)
        stats.total = len(files)
        logger.info(f"📁 取得ファイル数: {stats.total} 件")
        logger.info("-" * 80)
    except Exception as e:
        logger.critical(f"❌ ファイルリスト取得失敗: {e}")
        return

    # PDFファイルのみフィルタ
    pdf_files = [f for f in files if f.get('mimeType') == 'application/pdf']
    stats.total = len(pdf_files)
    logger.info(f"📄 PDFファイル数: {stats.total} 件")
    logger.info("-" * 80)

    # 既存データの処理
    if not skip_existing:
        logger.warning("⚠️  既存データ削除モード: すべての既存PDFデータを削除します")
        try:
            db = DatabaseClient()
            # すべてのPDFドキュメントを削除
            response = db.client.table('documents').select('id, file_name').eq('file_type', 'pdf').execute()
            if response.data:
                for doc in response.data:
                    db.client.table('documents').delete().eq('id', doc['id']).execute()
                logger.info(f"🗑️  削除完了: {len(response.data)} 件")
        except Exception as e:
            logger.error(f"❌ 既存データ削除失敗: {e}")
            logger.warning("⚠️  処理を継続しますが、重複データが発生する可能性があります")

    # 各ファイルを処理
    for idx, file_meta in enumerate(pdf_files, 1):
        file_name = file_meta.get('name', 'Unknown')

        logger.info(f"\n[{idx}/{stats.total}] 処理開始: {file_name}")

        try:
            result = await pipeline.process_file(file_meta, workspace='family')

            if result is None:
                # スキップ（既存データ等）
                stats.add_skipped(file_name)
            else:
                # 成功
                vision_used = result.get('metadata', {}).get('vision_supplemented', False)
                stats.add_success(file_name, vision_used=vision_used)

                # Vision補完の詳細ログ
                if vision_used:
                    vision_pages = result.get('metadata', {}).get('vision_pages', 0)
                    logger.info(f"   🤖 Vision補完: {vision_pages} ページ")

        except Exception as e:
            # 失敗してもスキップして継続
            stats.add_failed(file_name, e)
            import traceback
            logger.error(traceback.format_exc())
            continue

    # 処理完了
    stats.end_time = datetime.now()
    stats.print_summary()


if __name__ == "__main__":
    # 既存データをスキップして処理（デフォルト）
    # 既存データを削除して再処理する場合は skip_existing=False に変更
    asyncio.run(reingest_all_data(skip_existing=True))
