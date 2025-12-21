"""
共通商品取り込みパイプライン基盤クラス
全ネットスーパースクリプトで共有する処理を定義
"""

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Dict, List, Optional, Set
from uuid import UUID
import uuid

from A_common.database.client import DatabaseClient
from C_ai_common.llm_client.llm_client import LLMClient
from loguru import logger


class BaseProductIngestionPipeline(ABC):
    """商品取り込みの共通基盤クラス"""

    def __init__(self, organization_name: str, headless: bool = True):
        """
        初期化

        Args:
            organization_name: 組織名（東急ストア、楽天西友、ダイエー）
            headless: ブラウザのヘッドレスモード
        """
        self.organization_name = organization_name
        self.headless = headless
        self.db = DatabaseClient(use_service_role=True)
        self.llm_client = LLMClient()
        self.scraper = None

    @abstractmethod
    async def start(self) -> bool:
        """
        スクレイパーの起動とログイン
        各ストア固有の実装が必要
        """
        pass

    @abstractmethod
    async def close(self):
        """スクレイパーのクリーンアップ"""
        pass

    async def check_existing_products(self, jan_codes: List[str]) -> Set[str]:
        """
        既存商品のチェック（JANコードで重複排除）

        Args:
            jan_codes: チェックするJANコードリスト

        Returns:
            既存のJANコードのセット
        """
        if not jan_codes:
            return set()

        # 空文字・Noneを除外
        valid_jan_codes = [code for code in jan_codes if code]

        if not valid_jan_codes:
            return set()

        result = self.db.client.table('80_rd_products').select(
            'jan_code'
        ).in_('jan_code', valid_jan_codes).execute()

        return {row['jan_code'] for row in result.data if row.get('jan_code')}

    def _prepare_product_data(
        self,
        product: Dict,
        category_name: Optional[str] = None,
        general_name: Optional[str] = None,
        category_id: Optional[UUID] = None,
        confidence: Optional[float] = None
    ) -> Dict:
        """
        商品データの正規化と準備

        Args:
            product: スクレイパーから取得した生データ
            category_name: カテゴリ名（スクレイパー取得値）
            general_name: 一般名詞（分類済みの場合）
            category_id: カテゴリID（分類済みの場合）
            confidence: 分類信頼度

        Returns:
            データベース挿入用の正規化済みデータ
        """
        today = date.today()

        # 商品名の正規化
        product_name = product.get("product_name", "")
        product_name_normalized = " ".join(product_name.replace("　", " ").split())

        # 価格のパース
        price_text = product.get("price", "")
        try:
            current_price = float(price_text.replace(",", "").replace("円", "").replace("¥", "").strip())
        except (ValueError, AttributeError):
            current_price = None

        # メタデータ
        metadata = {
            "raw_data": product,
            "scraping_timestamp": datetime.now().isoformat()
        }

        # データ構築
        data = {
            # 基本情報
            "source_type": "online_shop",
            "workspace": "shopping",
            "doc_type": "online shop",
            "organization": self.organization_name,

            # 商品情報
            "product_name": product_name,
            "product_name_normalized": product_name_normalized,
            "jan_code": product.get("jan_code"),

            # 価格情報
            "current_price": current_price,
            "current_price_tax_included": current_price,
            "price_text": price_text,

            # 分類情報
            "category": category_name,
            "general_name": general_name,
            "category_id": str(category_id) if category_id else None,
            "classification_confidence": confidence,
            "needs_approval": general_name is None,  # 未分類の場合は承認待ち

            # その他
            "manufacturer": product.get("manufacturer"),
            "image_url": product.get("image_url"),
            "in_stock": product.get("in_stock", True),
            "is_available": product.get("is_available", True),

            # メタデータ
            "metadata": metadata,
            "document_date": today.isoformat(),
            "last_scraped_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        return data

    async def process_category_page(
        self,
        category_url: str,
        page: int = 1,
        category_name: Optional[str] = None
    ) -> Dict:
        """
        カテゴリページの処理（共通ロジック）

        Args:
            category_url: カテゴリURL
            page: ページ番号
            category_name: カテゴリ名

        Returns:
            処理結果
        """
        if not self.scraper:
            raise RuntimeError("Scraper not initialized. Call start() first.")

        logger.info(f"ページ {page} を処理中...")

        # スクレイパー固有の実装を呼び出し（タプル返却）
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

        # 商品データの正規化と保存
        jan_codes = [p.get("jan_code") for p in products if p.get("jan_code")]
        existing_jan_codes = await self.check_existing_products(jan_codes)

        insert_count = 0
        update_count = 0

        for product in products:
            # 商品データ準備（分類は後で実施）
            product_data = self._prepare_product_data(product, category_name)
            jan_code = product.get("jan_code")

            try:
                if jan_code and jan_code in existing_jan_codes:
                    # 既存商品を更新
                    self.db.client.table('80_rd_products').update(
                        product_data
                    ).eq('jan_code', jan_code).execute()
                    update_count += 1
                else:
                    # 新規商品を挿入
                    product_data["created_at"] = datetime.now().isoformat()
                    self.db.client.table('80_rd_products').insert(
                        product_data
                    ).execute()
                    insert_count += 1

            except Exception as e:
                logger.error(f"Failed to save product {product_name}: {e}")

        logger.info(f"✅ 処理完了: 合計{len(products)}件（新規{insert_count}件、更新{update_count}件）")

        return {
            "success": True,
            "total_products": len(products),
            "new_products": insert_count,
            "updated_products": update_count,
            "pagination_info": pagination_info
        }

    async def process_category_all_pages(
        self,
        category_url: str,
        category_name: Optional[str] = None,
        max_pages: int = 100
    ) -> Dict:
        """
        カテゴリの全ページを処理

        Args:
            category_url: カテゴリURL
            category_name: カテゴリ名
            max_pages: 最大ページ数

        Returns:
            処理結果
        """
        logger.info(f"カテゴリー '{category_name}' の全ページ処理開始")

        page = 1
        total_products = 0
        total_new = 0
        total_updated = 0
        total_pages_from_pagination = None

        while page <= max_pages:
            result = await self.process_category_page(category_url, page, category_name)

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

            if not result.get("success") or result.get("total_products", 0) == 0:
                logger.info(f"ページ {page} で商品なし、カテゴリー処理終了")
                break

            total_products += result.get("total_products", 0)
            total_new += result.get("new_products", 0)
            total_updated += result.get("updated_products", 0)

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
