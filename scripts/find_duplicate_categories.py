#!/usr/bin/env python3
"""
中分類と小分類（カテゴリ）が同じ名前になっている項目を検出
"""
import sys
from pathlib import Path
import csv
from collections import Counter

root_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(root_dir))

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def find_duplicate_categories():
    """中分類と小分類（カテゴリ）が同じ項目を検出"""

    csv_path = root_dir / 'netsuper_classification_list.csv'
    logger.info(f"Reading CSV file: {csv_path}")

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    logger.info(f"Total products: {len(rows)}")
    logger.info(f"Columns: {list(rows[0].keys())}")

    # 中分類と小分類（カテゴリ）が同じ項目を抽出
    same_cat = []
    for row in rows:
        if row['中分類'] == row['小分類（カテゴリ）']:
            same_cat.append(row)

    logger.info(f"\n中分類＝小分類（カテゴリ）の項目数: {len(same_cat)}")

    if len(same_cat) > 0:
        logger.info(f"\n最初の50件を表示:")
        logger.info("=" * 120)
        for idx, row in enumerate(same_cat[:50]):
            logger.info(f"{idx+1}. {row['商品名']}")
            logger.info(f"   中分類: {row['中分類']}")
            logger.info(f"   小分類（カテゴリ）: {row['小分類（カテゴリ）']}")
            logger.info(f"   小分類（商品）: {row['小分類（商品）']}")
            logger.info("")

        # CSV出力
        output_path = root_dir / 'duplicate_categories.csv'
        with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
            if same_cat:
                writer = csv.DictWriter(f, fieldnames=same_cat[0].keys())
                writer.writeheader()
                writer.writerows(same_cat)
        logger.info(f"\n重複項目を {output_path} に出力しました")

        # 中分類ごとの集計
        logger.info("\n中分類ごとの重複件数:")
        logger.info("=" * 60)
        category_counts = Counter(row['中分類'] for row in same_cat)
        for category, count in category_counts.most_common():
            logger.info(f"  {category}: {count}件")
    else:
        logger.info("\n✅ 中分類＝小分類（カテゴリ）の項目は見つかりませんでした")

if __name__ == "__main__":
    try:
        find_duplicate_categories()
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
