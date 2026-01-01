#!/usr/bin/env python3
"""
CSVファイルからデータベースへ分類情報を反映 (JANコードベース)
"""
import sys
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv

root_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(root_dir))

from A_common.database.client import DatabaseClient
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def sync_csv_to_database():
    """CSVファイルからデータベースへ分類情報を同期"""

    # CSVファイルを読み込み
    csv_path = root_dir / 'netsuper_classification_list.csv'
    logger.info(f"Reading CSV file: {csv_path}")
    df = pd.read_csv(csv_path)

    logger.info(f"Total products in CSV: {len(df)}")

    # データベースクライアント初期化 (service_role_keyを使用)
    db = DatabaseClient(use_service_role=True)

    # データベースから全商品を取得してマッピングを作成
    logger.info("Fetching all products from database...")
    all_products = []
    page_size = 1000
    offset = 0

    while True:
        result = db.client.table('Rawdata_NETSUPER_items')\
            .select('id', 'product_name', 'jan_code')\
            .range(offset, offset + page_size - 1)\
            .execute()

        if not result.data:
            break

        all_products.extend(result.data)
        offset += page_size
        logger.info(f"  Fetched {len(all_products)} products...")

        if len(result.data) < page_size:
            break

    logger.info(f"Total products in database: {len(all_products)}")

    # JANコードと商品名でマッピングを作成
    jan_to_id = {}
    name_to_ids = {}

    for p in all_products:
        if p.get('jan_code'):
            jan_to_id[p['jan_code']] = p['id']

        name = p.get('product_name', '')
        if name not in name_to_ids:
            name_to_ids[name] = []
        name_to_ids[name].append(p['id'])

    logger.info(f"Created mappings: {len(jan_to_id)} JANs, {len(name_to_ids)} names")

    # 更新カウンター
    updated = 0
    errors = 0
    not_found = 0

    # 商品ごとに分類情報を更新
    logger.info("Starting database update...")

    for idx, row in df.iterrows():
        product_name = row['商品名']
        jan_code = row.get('JANコード', '')

        # 更新データ
        # keywordsフィールドは配列型なので、文字列を配列に変換
        keywords_str = row.get('キーワード', '')
        keywords_list = []
        if pd.notna(keywords_str) and keywords_str:
            # カンマや改行で分割
            keywords_list = [kw.strip() for kw in str(keywords_str).replace('\n', ',').split(',') if kw.strip()]

        update_data = {
            'general_name': row.get('一般名詞', '') if pd.notna(row.get('一般名詞')) else '',
            'small_category': row.get('小分類（カテゴリ）', '') if pd.notna(row.get('小分類（カテゴリ）')) else '',
            'keywords': keywords_list
        }

        # 商品IDを特定
        product_id = None

        # JANコードで検索
        if pd.notna(jan_code) and jan_code and jan_code in jan_to_id:
            product_id = jan_to_id[jan_code]
        # 商品名で検索 (ユニークな場合のみ)
        elif product_name in name_to_ids and len(name_to_ids[product_name]) == 1:
            product_id = name_to_ids[product_name][0]

        if not product_id:
            not_found += 1
            if not_found <= 10:
                logger.warning(f"Product not found: {product_name}")
            continue

        try:
            # IDで更新
            result = db.client.table('Rawdata_NETSUPER_items')\
                .update(update_data)\
                .eq('id', product_id)\
                .execute()

            if result.data:
                updated += 1
            else:
                errors += 1

            if (idx + 1) % 100 == 0:
                logger.info(f"Progress: {idx + 1}/{len(df)} ({updated} updated, {not_found} not found)")

        except Exception as e:
            errors += 1
            if errors <= 10:
                logger.error(f"Error updating product '{product_name}': {e}")

    logger.info("=" * 80)
    logger.info(f"Sync completed")
    logger.info(f"Total products: {len(df)}")
    logger.info(f"Updated: {updated}")
    logger.info(f"Not found: {not_found}")
    logger.info(f"Errors: {errors}")
    logger.info("=" * 80)

if __name__ == "__main__":
    try:
        sync_csv_to_database()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
