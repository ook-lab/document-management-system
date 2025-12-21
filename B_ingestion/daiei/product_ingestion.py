"""
ダイエーネットスーパー 商品データ取得パイプライン

商品データを取得してSupabaseに保存します。

処理フロー:
1. ログインして配達日時を選択
2. カテゴリーページの商品データを取得
3. JANコードで既存商品をチェック
4. Supabaseに保存（新規 or 更新）
"""

import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Any

# プロジェクトルートをパスに追加
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir))

# .envファイルを読み込む
from dotenv import load_dotenv
load_dotenv(root_dir / ".env")

from B_ingestion.common.base_product_ingestion import BaseProductIngestionPipeline
from B_ingestion.daiei.daiei_scraper_playwright import DaieiScraperPlaywright

# ロガー設定
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class DaieiProductIngestionPipeline(BaseProductIngestionPipeline):
    """ダイエー商品データ取得パイプライン（共通基盤クラス継承）"""

    def __init__(self, login_id: str, password: str, headless: bool = True):
        """
        Args:
            login_id: ダイエーログインID
            password: パスワード
            headless: ヘッドレスモードで実行するか
        """
        super().__init__(organization_name="ダイエーネットスーパー", headless=headless)
        self.login_id = login_id
        self.password = password

        logger.info("DaieiProductIngestionPipeline初期化完了（Service Role使用）")

    async def start(self) -> bool:
        """
        スクレイパーを起動してログイン（ダイエー固有）

        Returns:
            成功したらTrue
        """
        try:
            self.scraper = DaieiScraperPlaywright()
            await self.scraper.start(headless=self.headless)

            # ログイン
            success = await self.scraper.login(self.login_id, self.password)
            if not success:
                logger.error("❌ ログイン失敗")
                await self.scraper.close()
                return False

            # 配達日時選択
            success = await self.scraper.select_delivery_slot()
            if not success:
                logger.error("❌ 配達日時選択失敗")
                await self.scraper.close()
                return False

            logger.info("✅ スクレイパー起動・ログイン・配達日時選択完了")
            return True

        except Exception as e:
            logger.error(f"スクレイパー起動エラー: {e}", exc_info=True)
            return False

    async def close(self):
        """スクレイパーを終了"""
        if self.scraper:
            await self.scraper.close()


async def main():
    """テスト実行用のメイン関数"""
    logger.info("ダイエー商品データ取得パイプライン開始")

    login_id = os.getenv("DAIEI_LOGIN_ID")
    password = os.getenv("DAIEI_PASSWORD")

    if not login_id or not password:
        logger.error("❌ 環境変数 DAIEI_LOGIN_ID と DAIEI_PASSWORD を設定してください")
        return

    pipeline = DaieiProductIngestionPipeline(
        login_id=login_id,
        password=password,
        headless=False
    )

    try:
        # スクレイパー起動
        success = await pipeline.start()
        if not success:
            logger.error("❌ スクレイパー起動失敗")
            return

        logger.info("✅ テスト完了")

    finally:
        await pipeline.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
