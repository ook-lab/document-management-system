#!/usr/bin/env python3
"""
複合小分類の分類結果をデータベースに反映するスクリプト
"""
import os
from supabase import create_client
import json
import glob
from collections import defaultdict
from uuid import uuid4
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Supabase setup
supabase = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_KEY')
)

def apply_small_classification(json_file):
    """1つのJSONファイルの分類結果をデータベースに適用"""
    print("=" * 100)
    print(f"ファイル: {json_file}")
    print("=" * 100)

    # 1. Load classification results
    with open(json_file, 'r', encoding='utf-8') as f:
        results = json.load(f)

    medium_category = results.get('medium_category', '')
    product_classifications = results['classifications']
    print(f"中分類: {medium_category}")
    print(f"分類済み商品数: {len(product_classifications)}件")

    # 2. Get all categories
    all_categories = []
    offset = 0
    while True:
        result = supabase.table('MASTER_Categories_product').select('*').range(offset, offset + 999).execute()
        if not result.data:
            break
        all_categories.extend(result.data)
        offset += 1000

    category_by_key = {cat['name']: cat for cat in all_categories}
    print(f"カテゴリー総数: {len(all_categories)}件")

    # 3. Get products to update
    all_products = []
    for product_id in product_classifications.keys():
        result = supabase.table('Rawdata_NETSUPER_items')\
            .select('id, product_name, small_category, category_id')\
            .eq('id', product_id)\
            .execute()
        if result.data:
            all_products.extend(result.data)

    print(f"対象商品数: {len(all_products)}件")

    # 4. Determine new categories needed
    category_migrations = defaultdict(list)
    new_categories_needed = set()

    for product in all_products:
        product_id = product['id']

        # Get category info from current category_id
        current_cat_id = product.get('category_id')
        if current_cat_id and current_cat_id in [c['id'] for c in all_categories]:
            current_cat = next((c for c in all_categories if c['id'] == current_cat_id), None)
            if current_cat:
                large_cat = current_cat['large_category']
                medium_cat = current_cat['medium_category']
            else:
                # Fallback: parse from medium_category in results
                parts = medium_category.split('>')
                large_cat = parts[0] if len(parts) > 0 else ''
                medium_cat = parts[1] if len(parts) > 1 else ''
        else:
            # Fallback: parse from medium_category in results
            parts = medium_category.split('>')
            large_cat = parts[0] if len(parts) > 0 else ''
            medium_cat = parts[1] if len(parts) > 1 else ''

        new_small = product_classifications.get(product_id, '')
        new_key = f"{large_cat}>{medium_cat}>{new_small}"

        if new_key not in category_by_key:
            new_categories_needed.add(new_key)

        category_migrations[new_key].append(product_id)

    print(f"\n新規作成が必要なカテゴリー: {len(new_categories_needed)}件")

    # 5. Create new categories
    for new_key in new_categories_needed:
        parts_split = new_key.split('>')
        if len(parts_split) != 3:
            print(f"  警告: 不正なカテゴリーキー: {new_key}")
            continue

        new_id = str(uuid4())
        new_category = {
            'id': new_id,
            'name': new_key,
            'large_category': parts_split[0],
            'medium_category': parts_split[1],
            'small_category': parts_split[2]
        }
        supabase.table('MASTER_Categories_product').insert(new_category).execute()
        category_by_key[new_key] = {'id': new_id}
        print(f"  作成: {new_key}")

    # 6. Migrate products
    print(f"\n商品を新しいカテゴリーに移行中...")
    update_count = 0
    for new_key, product_ids in category_migrations.items():
        if new_key not in category_by_key:
            print(f"  警告: カテゴリーが見つかりません: {new_key}")
            continue

        new_category_id = category_by_key[new_key]['id']
        for product_id in product_ids:
            supabase.table('Rawdata_NETSUPER_items') \
                .update({'category_id': new_category_id}) \
                .eq('id', product_id) \
                .execute()
            update_count += 1

            if update_count % 50 == 0:
                print(f"  進捗: {update_count}件更新完了...")

    print(f"商品更新完了: {update_count}件")

    # Statistics
    stats = defaultdict(int)
    for category in product_classifications.values():
        stats[category] += 1

    print("\n" + "=" * 100)
    print("処理完了")
    print("=" * 100)
    print(f"中分類: {medium_category}")
    for category, count in sorted(stats.items(), key=lambda x: x[1], reverse=True):
        print(f"  → {category}: {count}件")
    print(f"新規カテゴリー作成: {len(new_categories_needed)}件")
    print(f"商品更新: {update_count}件")
    print()

    return {
        'file': json_file,
        'medium_category': medium_category,
        'product_count': len(all_products),
        'new_categories': len(new_categories_needed),
        'updated_products': update_count,
        'stats': dict(stats)
    }

def main():
    """全てのJSONファイルを処理"""
    # JSONファイルを検索
    json_files = glob.glob('classification_results_small_*.json')
    # classification_results_small_categories.jsonは除外
    json_files = [f for f in json_files if f != 'classification_results_small_categories.json']

    print(f"処理対象ファイル数: {len(json_files)}件\n")

    results = []
    for json_file in sorted(json_files):
        try:
            result = apply_small_classification(json_file)
            results.append(result)
        except Exception as e:
            print(f"エラー: {json_file} - {e}")
            continue

    # Final summary
    print("\n" + "=" * 100)
    print("全処理完了サマリー")
    print("=" * 100)
    total_products = sum(r['updated_products'] for r in results)
    total_new_categories = sum(r['new_categories'] for r in results)

    for result in results:
        print(f"\n{result['medium_category']}")
        print(f"  商品数: {result['product_count']}件")
        for category, count in result['stats'].items():
            print(f"    → {category}: {count}件")
        print(f"  新規カテゴリー: {result['new_categories']}件")
        print(f"  更新商品: {result['updated_products']}件")

    print(f"\n総計:")
    print(f"  処理ファイル数: {len(results)}件")
    print(f"  更新商品数: {total_products}件")
    print(f"  新規カテゴリー作成: {total_new_categories}件")

if __name__ == '__main__':
    main()
