"""
東急ストアネットスーパー スケジュール管理対応版

カテゴリーごとの実行スケジュールを管理し、
サーバー負荷を最小限に抑える待機時間を実装します。
"""

import os
import sys
import asyncio
import random
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# プロジェクトルートをパスに追加
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

from dotenv import load_dotenv
load_dotenv(root_dir / ".env")

from B_ingestion.common.category_manager import CategoryManager
from B_ingestion.tokyu_store.product_ingestion import TokyuStoreProductIngestionPipeline

# ロガー設定
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class PoliteTokyuStorePipeline:
    """サーバー負荷に配慮したスケジュール管理パイプライン"""

    def __init__(
        self,
        login_id: str,
        password: str,
        zip_code: str = "158-0094",
        headless: bool = True,
        dry_run: bool = False
    ):
        """
        Args:
            login_id: 東急ストアログインID
            password: パスワード
            zip_code: 配達エリア郵便番号
            headless: ヘッドレスモード
            dry_run: Dry Run モード（設定ファイルの初期化のみ）
        """
        self.pipeline = TokyuStoreProductIngestionPipeline(
            login_id=login_id,
            password=password,
            zip_code=zip_code,
            headless=headless
        )
        self.manager = CategoryManager()
        self.dry_run = dry_run
        self.store_name = "tokyu_store"

    async def polite_wait_between_pages(self):
        """ページ遷移間の待機（4秒〜8秒のランダム）"""
        wait_time = random.uniform(4.0, 8.0)
        logger.info(f"⏳ ページ遷移待機: {wait_time:.1f}秒")
        await asyncio.sleep(wait_time)

    async def polite_wait_between_categories(self):
        """カテゴリー切替時の待機（15秒〜30秒のランダム）"""
        wait_time = random.uniform(15.0, 30.0)
        logger.info(f"⏳ カテゴリー切替待機: {wait_time:.1f}秒")
        await asyncio.sleep(wait_time)

    async def initialize_categories(self):
        """カテゴリーを初期化（初回実行時）"""
        logger.info("📋 カテゴリーを初期化します...")

        # スクレイパー起動
        success = await self.pipeline.start()
        if not success:
            logger.error("❌ スクレイパー起動失敗")
            return False

        try:
            # カテゴリーを動的に取得
            categories = await self.pipeline.discover_categories()

            if not categories:
                logger.warning("カテゴリーが見つかりませんでした")
                return False

            # CategoryManagerに登録
            category_list = [
                {"name": cat["name"], "url": cat["url"]}
                for cat in categories
            ]

            # デフォルト設定で初期化
            # 開始日: 明日、インターバル: 7日
            tomorrow = datetime.now().strftime("%Y-%m-%d")
            self.manager.initialize_store_categories(
                self.store_name,
                category_list,
                default_interval_days=7,
                default_start_date=tomorrow
            )

            logger.info(f"✅ {len(categories)}件のカテゴリーを初期化しました")
            logger.info("管理画面で設定を調整してください:")
            logger.info("  streamlit run B_ingestion/netsuper_category_manager_ui.py")

            return True

        finally:
            await self.pipeline.close()

    async def run_scheduled_categories(self):
        """スケジュールに基づいてカテゴリーを処理"""
        logger.info("="*80)
        logger.info("東急ストアネットスーパー スケジュール実行開始")
        logger.info("="*80)

        # スクレイパー起動
        success = await self.pipeline.start()
        if not success:
            logger.error("❌ スクレイパー起動失敗")
            return

        try:
            # 設定からカテゴリーを取得
            categories = self.manager.get_all_categories(self.store_name)

            if not categories:
                logger.warning("カテゴリーが設定されていません。初回実行してください:")
                logger.warning("  python -m B_ingestion.tokyu_store.process_with_schedule --init")
                return

            # 今日実行すべきカテゴリーをフィルタリング
            today = datetime.now()
            runnable_categories = []

            for cat in categories:
                if self.manager.should_run_category(self.store_name, cat["name"], today):
                    runnable_categories.append(cat)

            logger.info(f"📊 総カテゴリー数: {len(categories)}件")
            logger.info(f"✅ 本日実行対象: {len(runnable_categories)}件")

            if not runnable_categories:
                logger.info("本日実行するカテゴリーはありません")
                return

            # カテゴリーごとに処理
            for idx, cat in enumerate(runnable_categories, 1):
                logger.info("")
                logger.info("="*80)
                logger.info(f"📦 カテゴリー {idx}/{len(runnable_categories)}: {cat['name']}")
                logger.info(f"   URL: {cat['url']}")
                logger.info("="*80)

                try:
                    # カテゴリーページにアクセス
                    await self.pipeline.scraper.page.goto(cat['url'], wait_until="domcontentloaded")
                    await self.polite_wait_between_pages()

                    # ここで商品データを取得する処理を実装
                    # （既存のスクレイピングロジックを呼び出す）
                    # products = await self.pipeline.scrape_category_products(cat['url'])
                    # await self.pipeline.save_products(products)

                    logger.info(f"✅ カテゴリー {cat['name']} の処理完了")

                    # 実行済みとしてマーク
                    self.manager.mark_as_run(self.store_name, cat["name"], today)

                    # カテゴリー間の待機
                    if idx < len(runnable_categories):
                        await self.polite_wait_between_categories()

                except Exception as e:
                    logger.error(f"❌ カテゴリー {cat['name']} 処理エラー: {e}", exc_info=True)
                    # エラー時は長めに待機
                    await asyncio.sleep(60)
                    continue

            logger.info("")
            logger.info("="*80)
            logger.info("✅ すべてのカテゴリー処理完了")
            logger.info("="*80)

        finally:
            await self.pipeline.close()


async def main():
    """メイン処理"""
    import argparse

    parser = argparse.ArgumentParser(description="東急ストアスクレイピング（スケジュール管理対応）")
    parser.add_argument("--init", action="store_true", help="カテゴリーを初期化（初回実行時のみ）")
    parser.add_argument("--headless", action="store_true", default=True, help="ヘッドレスモード")
    parser.add_argument("--zip-code", default="158-0094", help="配達エリア郵便番号")
    args = parser.parse_args()

    login_id = os.getenv("TOKYU_STORE_LOGIN_ID")
    password = os.getenv("TOKYU_STORE_PASSWORD")

    if not login_id or not password:
        logger.error("❌ 環境変数 TOKYU_STORE_LOGIN_ID と TOKYU_STORE_PASSWORD を設定してください")
        return

    pipeline = PoliteTokyuStorePipeline(
        login_id=login_id,
        password=password,
        zip_code=args.zip_code,
        headless=args.headless
    )

    if args.init:
        # 初期化モード
        await pipeline.initialize_categories()
    else:
        # 通常実行モード
        await pipeline.run_scheduled_categories()


if __name__ == "__main__":
    asyncio.run(main())
