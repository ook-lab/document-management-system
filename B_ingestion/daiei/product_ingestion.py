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
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, date

# プロジェクトルートをパスに追加
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir))

# .envファイルを読み込む
from dotenv import load_dotenv
load_dotenv(root_dir / ".env")

from A_common.database.client import DatabaseClient
from B_ingestion.daiei.daiei_scraper_playwright import DaieiScraperPlaywright

# ロガー設定
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class DaieiProductIngestionPipeline:
    """ダイエー商品データ取得パイプライン"""

    def __init__(self, login_id: str, password: str, headless: bool = True):
        """
        Args:
            login_id: ダイエーログインID
            password: パスワード
            headless: ヘッドレスモードで実行するか
        """
        self.login_id = login_id
        self.password = password
        self.headless = headless
        self.scraper: Optional[DaieiScraperPlaywright] = None
        # Service Role Keyを使用（RLSをバイパス）
        self.db = DatabaseClient(use_service_role=True)

        logger.info("DaieiProductIngestionPipeline初期化完了（Service Role使用）")

    async def start(self) -> bool:
        """
        スクレイパーを起動してログイン

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

    async def check_existing_products(self, jan_codes: List[str]) -> set:
        """
        Supabaseで既存の商品（JANコード）をチェック

        Args:
            jan_codes: チェックするJANコードのリスト

        Returns:
            既に存在するJANコードのセット
        """
        try:
            # Noneや空文字列を除外
            valid_jan_codes = [jan for jan in jan_codes if jan]

            if not valid_jan_codes:
                return set()

            # 80_rd_products テーブルで既存のJANコードを取得
            result = self.db.client.table('80_rd_products').select(
                'jan_code'
            ).in_('jan_code', valid_jan_codes).execute()

            # JANコードを抽出
            existing_codes = set()
            if result.data:
                for doc in result.data:
                    jan_code = doc.get('jan_code')
                    if jan_code:
                        existing_codes.add(jan_code)

            logger.info(f"既存の商品: {len(existing_codes)}件")
            return existing_codes

        except Exception as e:
            logger.error(f"Supabase検索エラー: {e}", exc_info=True)
            return set()

    def _prepare_product_data(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """
        商品データをSupabase保存用に整形

        Args:
            product: スクレイパーから取得した商品データ

        Returns:
            Supabase保存用のデータ
        """
        today = date.today()

        # 価格の処理
        price = product.get("price")
        price_float = None
        if price is not None:
            try:
                price_float = float(price)
            except (ValueError, TypeError):
                logger.warning(f"価格の変換失敗: {price}")

        # 商品名の正規化（全角スペース→半角、連続スペース削除）
        product_name = product.get("product_name", "")
        product_name_normalized = " ".join(product_name.replace("　", " ").split())

        data = {
            # 基本情報
            "source_type": "online_shop",
            "workspace": "shopping",
            "doc_type": "online shop",
            "organization": "ダイエーネットスーパー",

            # 商品基本情報
            "product_name": product_name,
            "product_name_normalized": product_name_normalized,
            "jan_code": product.get("jan_code"),

            # 価格
            "current_price": price_float,
            "current_price_tax_included": price_float,  # 税込み価格
            "price_text": str(price) if price else None,

            # 分類
            "category": product.get("category"),
            "manufacturer": product.get("manufacturer"),

            # 商品詳細
            "image_url": product.get("image_url"),

            # 在庫・販売状況
            "in_stock": product.get("in_stock", True),
            "is_available": product.get("is_available", True),

            # メタデータ
            "metadata": json.dumps(product.get("raw_data", {}), ensure_ascii=False),

            # 日付
            "document_date": today.isoformat(),
            "last_scraped_at": datetime.now().isoformat(),

            # 表示用
            "display_subject": f"{product_name} - ダイエー",
            "display_sender": "ダイエーネットスーパー",

            # タイムスタンプ
            "updated_at": datetime.now().isoformat()
        }

        return data

    async def process_category_page(
        self,
        category_url: str,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        1カテゴリーの1ページを処理

        Args:
            category_url: カテゴリーの完全URL
            page: ページ番号

        Returns:
            処理結果の辞書
        """
        logger.info(f"ページ {page} を処理中...")

        # 商品データとページネーション情報を取得
        products, pagination_info = await self.scraper.fetch_products_page(category_url, page)

        # ページネーション情報をログ出力
        if page == 1 and pagination_info:
            logger.info(f"ページネーション情報: {pagination_info}")

        if not products:
            logger.warning("商品が見つかりませんでした")
            return {
                "success": True,
                "total_products": 0,
                "new_products": 0,
                "updated_products": 0,
                "pagination_info": pagination_info
            }

        # JANコードで既存商品をチェック
        jan_codes = [p.get("jan_code") for p in products if p.get("jan_code")]
        existing_jan_codes = await self.check_existing_products(jan_codes)

        # データベースに保存
        new_count = 0
        updated_count = 0

        for product in products:
            try:
                product_data = self._prepare_product_data(product)
                jan_code = product.get("jan_code")

                if jan_code and jan_code in existing_jan_codes:
                    # 既存商品の更新
                    result = self.db.client.table('80_rd_products').update(
                        product_data
                    ).eq('jan_code', jan_code).execute()

                    if result.data:
                        updated_count += 1
                        logger.debug(f"商品更新: {product.get('product_name')}")
                else:
                    # 新規商品の追加
                    product_data["created_at"] = datetime.now().isoformat()
                    result = self.db.client.table('80_rd_products').insert(
                        product_data
                    ).execute()

                    if result.data:
                        new_count += 1
                        logger.debug(f"商品追加: {product.get('product_name')}")

            except Exception as e:
                logger.error(f"商品保存エラー: {e}", exc_info=True)
                continue

        logger.info(f"✅ 処理完了: 合計{len(products)}件（新規{new_count}件、更新{updated_count}件）")

        return {
            "success": True,
            "total_products": len(products),
            "new_products": new_count,
            "updated_products": updated_count,
            "pagination_info": pagination_info
        }

    async def process_category_all_pages(
        self,
        category_url: str,
        category_name: str,
        max_pages: int = 100
    ) -> Dict[str, Any]:
        """
        1カテゴリーの全ページを処理

        Args:
            category_url: カテゴリーの完全URL
            category_name: カテゴリー名
            max_pages: 最大ページ数

        Returns:
            処理結果の辞書
        """
        logger.info(f"カテゴリー '{category_name}' の全ページ処理開始")

        total_new = 0
        total_updated = 0
        total_products = 0
        page = 1
        total_pages_from_pagination = None

        while page <= max_pages:
            result = await self.process_category_page(category_url, page)

            # 初回のページネーション情報を取得
            if page == 1 and result.get("pagination_info"):
                pagination = result["pagination_info"]
                total_pages_from_pagination = pagination.get("totalPages")
                if total_pages_from_pagination:
                    logger.info(f"📄 検出された総ページ数: {total_pages_from_pagination}")
                    # 総ページ数がmax_pagesより少ない場合、max_pagesを更新
                    if total_pages_from_pagination < max_pages:
                        max_pages = total_pages_from_pagination
                        logger.info(f"✅ 処理ページ数を {total_pages_from_pagination} に制限")

            if not result["success"] or result["total_products"] == 0:
                logger.info(f"ページ {page} で商品なし、カテゴリー処理終了")
                break

            total_products += result["total_products"]
            total_new += result["new_products"]
            total_updated += result["updated_products"]

            # ページネーション情報に基づく終了判定
            if total_pages_from_pagination and page >= total_pages_from_pagination:
                logger.info(f"✅ 全{total_pages_from_pagination}ページの処理完了")
                break

            page += 1

        logger.info(f"✅ カテゴリー '{category_name}' 完了")
        logger.info(f"   合計: {total_products}件（新規{total_new}件、更新{total_updated}件）")

        return {
            "success": True,
            "category_url": category_url,
            "category_name": category_name,
            "total_products": total_products,
            "new_products": total_new,
            "updated_products": total_updated,
            "pages_processed": page - 1,
            "total_pages": total_pages_from_pagination
        }


async def main():
    """テスト実行用のメイン関数"""
    logger.info("ダイエー商品データ取得パイプライン開始")

    login_id = os.getenv("DAIEI_LOGIN_ID")
    password = os.getenv("DAIEI_PASSWORD")

    if not login_id or not password:
        logger.error("❌ 環境変数 DAIEI_LOGIN_ID と DAIEI_PASSWORD を設定してください")
        return

    async with DaieiScraperPlaywright() as scraper:
        # ログイン
        success = await scraper.login(login_id, password)
        if not success:
            logger.error("❌ ログイン失敗")
            return

        # 配達日時選択
        success = await scraper.select_delivery_slot()
        if not success:
            logger.error("❌ 配達日時選択失敗")
            return

        # テスト: カテゴリーページにアクセス
        # TODO: 実際のカテゴリーURLを指定
        test_category_url = "https://netsuper.daiei.co.jp/0000/category/test"
        products, pagination = await scraper.fetch_products_page(test_category_url, 1)

        logger.info(f"✅ テスト完了: {len(products)}件の商品を取得")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
