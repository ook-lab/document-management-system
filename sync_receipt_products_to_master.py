"""
レシート商品を80_rd_productsに統合

レシートデータ（60_rd_standardized_items）から商品情報を取得し、
80_rd_productsテーブルに統合する。

処理内容：
1. レシート商品データを取得（商品名、税込単価、店舗名など）
2. 税込単価を計算（std_amount ÷ quantity）
3. 80_rd_productsに既存商品があるかチェック（商品名＋店舗名）
4. あれば価格を更新、なければ新規作成
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
from typing import Dict, List, Optional
from openai import OpenAI

# Windows環境でのUnicode出力設定
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# プロジェクトルートをパスに追加
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

load_dotenv(root_dir / ".env")

from A_common.database.client import DatabaseClient

# ロギング設定
try:
    from loguru import logger
    logger.remove()
    logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")
except ImportError:
    # loguruがない場合は標準のloggingを使用
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s', datefmt='%H:%M:%S')
    logger = logging.getLogger(__name__)


class ReceiptProductSync:
    """レシート商品を80_rd_productsに同期"""

    def __init__(self):
        self.db = DatabaseClient(use_service_role=True)

        # OpenAI clientの初期化（embedding生成用）
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if openai_api_key:
            self.openai_client = OpenAI(api_key=openai_api_key)
            self.embedding_enabled = True
            logger.info("OpenAI Embedding機能が有効化されました")
        else:
            self.openai_client = None
            self.embedding_enabled = False
            logger.warning("OPENAI_API_KEYが設定されていません。Embedding生成は無効です")

    def fetch_receipt_products(self) -> List[Dict]:
        """
        レシート商品データを取得

        Returns:
            商品データのリスト
        """
        logger.info("レシート商品データを取得中...")

        # 60_rd_standardized_itemsから商品データを取得
        # JOINでtransactions（数量取得用）とreceipts（店舗名取得用）も取得
        result = self.db.client.table('60_rd_standardized_items').select(
            '''
            id,
            official_name,
            std_amount,
            tax_amount,
            tax_rate,
            major_category,
            minor_category,
            receipt_id,
            transaction_id,
            60_rd_transactions!inner(quantity),
            60_rd_receipts!inner(shop_name, transaction_date)
            '''
        ).execute()

        products = []
        for item in result.data:
            # 数量を取得
            quantity = item.get('60_rd_transactions', {}).get('quantity', 1)
            if quantity == 0:
                logger.warning(f"数量が0の商品をスキップ: {item.get('official_name')}")
                continue

            # 店舗名と日付を取得
            receipt_info = item.get('60_rd_receipts', {})
            shop_name = receipt_info.get('shop_name', '不明')
            transaction_date = receipt_info.get('transaction_date')

            # 税込単価を計算（std_amount ÷ quantity）
            std_amount = item.get('std_amount', 0)
            tax_included_unit_price = std_amount / quantity if quantity > 0 else 0

            # 税抜単価を計算（参考用）
            tax_amount = item.get('tax_amount', 0)
            tax_excluded_unit_price = (std_amount - tax_amount) / quantity if quantity > 0 else 0

            products.append({
                'std_item_id': item.get('id'),
                'official_name': item.get('official_name'),
                'shop_name': shop_name,
                'quantity': quantity,
                'std_amount': std_amount,
                'tax_amount': tax_amount,
                'tax_rate': item.get('tax_rate', 10),
                'tax_included_unit_price': tax_included_unit_price,
                'tax_excluded_unit_price': tax_excluded_unit_price,
                'major_category': item.get('major_category'),
                'minor_category': item.get('minor_category'),
                'transaction_date': transaction_date,
                'receipt_id': item.get('receipt_id'),
                'transaction_id': item.get('transaction_id')
            })

        logger.info(f"取得完了: {len(products)}件の商品データ")
        return products

    def check_existing_product(self, product_name: str, shop_name: str) -> Optional[Dict]:
        """
        既存商品をチェック（商品名＋店舗名）

        Args:
            product_name: 商品名
            shop_name: 店舗名

        Returns:
            既存商品データ（なければNone）
        """
        result = self.db.client.table('80_rd_products').select('*').eq(
            'product_name', product_name
        ).eq('organization', shop_name).limit(1).execute()

        return result.data[0] if result.data else None

    def _generate_embedding(self, text: str) -> Optional[List]:
        """
        商品名からembeddingを生成

        Args:
            text: 商品名

        Returns:
            1536次元のベクトル（失敗時はNone）
        """
        if not self.embedding_enabled or not self.openai_client:
            return None

        if not text:
            return None

        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding生成エラー: {e}")
            return None

    def create_product(self, product: Dict) -> str:
        """
        新規商品を作成

        Args:
            product: 商品データ

        Returns:
            作成された商品ID
        """
        data = {
            'source_type': 'physical_store',
            'workspace': 'shopping',
            'doc_type': 'Receipt',
            'organization': product['shop_name'],
            'product_name': product['official_name'],
            'product_name_normalized': product['official_name'].strip(),
            'current_price': round(product['tax_excluded_unit_price'], 2),
            'current_price_tax_included': round(product['tax_included_unit_price'], 2),
            'price_text': f"税抜¥{product['tax_excluded_unit_price']:.0f} / 税込¥{product['tax_included_unit_price']:.0f}",
            'category': product.get('minor_category') or product.get('major_category'),
            'document_date': product.get('transaction_date'),
            'last_scraped_at': datetime.now().isoformat(),
            'metadata': {
                'source': 'receipt',
                'receipt_id': product['receipt_id'],
                'transaction_id': product['transaction_id'],
                'std_item_id': product['std_item_id'],
                'tax_rate': product['tax_rate']
            }
        }

        # Embeddingを生成（商品名から）
        embedding = self._generate_embedding(product['official_name'])
        if embedding:
            # vector型として保存するために文字列形式に変換
            embedding_str = '[' + ','.join(map(str, embedding)) + ']'
            data['embedding'] = embedding_str

        result = self.db.client.table('80_rd_products').insert(data).execute()
        return result.data[0]['id']

    def update_product_price(self, product_id: str, product: Dict):
        """
        既存商品の価格を更新

        Args:
            product_id: 商品ID
            product: 商品データ
        """
        data = {
            'current_price': round(product['tax_excluded_unit_price'], 2),
            'current_price_tax_included': round(product['tax_included_unit_price'], 2),
            'price_text': f"税抜¥{product['tax_excluded_unit_price']:.0f} / 税込¥{product['tax_included_unit_price']:.0f}",
            'document_date': product.get('transaction_date'),
            'last_scraped_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }

        # 既存商品のembeddingが無ければ生成
        existing = self.db.client.table('80_rd_products').select('embedding').eq('id', product_id).execute()
        if existing.data and not existing.data[0].get('embedding'):
            embedding = self._generate_embedding(product['official_name'])
            if embedding:
                # vector型として保存するために文字列形式に変換
                embedding_str = '[' + ','.join(map(str, embedding)) + ']'
                data['embedding'] = embedding_str

        self.db.client.table('80_rd_products').update(data).eq('id', product_id).execute()

    def sync_products(self, limit: Optional[int] = None):
        """
        レシート商品を80_rd_productsに同期

        Args:
            limit: 処理する最大件数（Noneの場合は全件）
        """
        logger.info("="*80)
        logger.info("レシート商品同期開始")
        logger.info("="*80)

        # レシート商品を取得
        products = self.fetch_receipt_products()

        if limit:
            products = products[:limit]
            logger.info(f"処理件数を{limit}件に制限")

        stats = {
            'total': len(products),
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'error': 0
        }

        # 各商品を処理
        for i, product in enumerate(products, 1):
            try:
                product_name = product['official_name']
                shop_name = product['shop_name']

                if not product_name:
                    logger.warning(f"[{i}/{stats['total']}] 商品名が空のためスキップ")
                    stats['skipped'] += 1
                    continue

                # 既存商品をチェック
                existing = self.check_existing_product(product_name, shop_name)

                if existing:
                    # 既存商品を更新
                    self.update_product_price(existing['id'], product)
                    logger.info(f"[{i}/{stats['total']}] 更新: {product_name} @ {shop_name} → ¥{product['tax_included_unit_price']:.0f}")
                    stats['updated'] += 1
                else:
                    # 新規商品を作成
                    product_id = self.create_product(product)
                    logger.info(f"[{i}/{stats['total']}] 新規: {product_name} @ {shop_name} → ¥{product['tax_included_unit_price']:.0f}")
                    stats['created'] += 1

                # 進捗表示
                if i % 50 == 0:
                    logger.info(f"進捗: {i}/{stats['total']} ({i/stats['total']*100:.1f}%)")

            except Exception as e:
                logger.error(f"[{i}/{stats['total']}] エラー: {product.get('official_name', '不明')} - {e}")
                stats['error'] += 1

        # 結果サマリー
        logger.info("="*80)
        logger.info("同期完了")
        logger.info("="*80)
        logger.info(f"処理件数: {stats['total']}件")
        logger.info(f"新規作成: {stats['created']}件")
        logger.info(f"価格更新: {stats['updated']}件")
        logger.info(f"スキップ: {stats['skipped']}件")
        logger.info(f"エラー:   {stats['error']}件")
        logger.info("="*80)


def main():
    """メイン処理"""
    import argparse

    parser = argparse.ArgumentParser(description='レシート商品を80_rd_productsに同期')
    parser.add_argument('--limit', type=int, help='処理する最大件数', default=None)
    args = parser.parse_args()

    syncer = ReceiptProductSync()
    syncer.sync_products(limit=args.limit)


if __name__ == "__main__":
    main()
