#!/usr/bin/env python3
"""
残りの複合カテゴリーを一括処理するスクリプト
"""
import os
from supabase import create_client
import json
from collections import defaultdict
from uuid import uuid4
import time
import google.generativeai as genai

# Supabase setup
supabase = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_KEY')
)

# Gemini setup
genai.configure(api_key=os.getenv('GOOGLE_AI_API_KEY'))
model = genai.GenerativeModel('gemini-2.5-flash')

# 残りの処理対象カテゴリー（商品数順）
REMAINING_COMPOUNDS = [
    {
        'large': '食料品',
        'medium': 'カレールー・スープ',
        'parts': ['カレールー', 'スープ'],
        'step': 7
    },
    {
        'large': '食料品',
        'medium': '豆腐・大豆製品',
        'parts': ['豆腐', '大豆製品'],
        'step': 8
    },
    {
        'large': '食料品',
        'medium': '乳製品・卵・大豆製品',
        'parts': ['乳製品', '卵', '大豆製品'],
        'step': 9
    },
    {
        'large': '食料品',
        'medium': '豆腐・納豆・漬物',
        'parts': ['豆腐', '納豆', '漬物'],
        'step': 10
    },
    {
        'large': '食料品',
        'medium': 'パン・シリアル',
        'parts': ['パン', 'シリアル'],
        'step': 11
    }
]

def process_compound_category(config):
    """単一の複合カテゴリーを処理"""
    large = config['large']
    compound_medium = config['medium']
    parts = config['parts']
    step = config['step']

    print("=" * 100)
    print(f"ステップ{step}: {large}>{compound_medium} を処理中...")
    print("=" * 100)

    # 1. Get all categories
    all_categories = []
    offset = 0
    while True:
        result = supabase.table('MASTER_Categories_product').select('*').range(offset, offset + 999).execute()
        if not result.data:
            break
        all_categories.extend(result.data)
        offset += 1000

    category_by_key = {cat['name']: cat for cat in all_categories}
    print(f"カテゴリー総数: {len(all_categories)}")

    # 2. Get target category IDs
    target_category_ids = [
        cat['id'] for cat in all_categories
        if cat['large_category'] == large and cat['medium_category'] == compound_medium
    ]
    print(f"対象カテゴリー数: {len(target_category_ids)}")

    # 3. Get products
    all_products = []
    for cat_id in target_category_ids:
        offset = 0
        while True:
            result = supabase.table('Rawdata_NETSUPER_items')\
                .select('id, product_name, general_name, keywords, small_category, category_id')\
                .eq('category_id', cat_id)\
                .range(offset, offset + 999)\
                .execute()
            if not result.data:
                break
            all_products.extend(result.data)
            offset += 1000

    print(f"対象商品数: {len(all_products)}")
    print(f"分類先: {parts}")

    # Check existing parts
    existing_parts = []
    for part in parts:
        for cat in all_categories:
            if cat['large_category'] == large and cat['medium_category'] == part:
                existing_parts.append(part)
                break
    print(f"既存の中分類: {existing_parts if existing_parts else 'なし'}")

    # 4. Classify with AI
    print("\n商品分類を開始...")
    batch_size = 20
    product_classifications = {}

    for i in range(0, len(all_products), batch_size):
        batch = all_products[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(all_products) + batch_size - 1) // batch_size
        print(f"  バッチ {batch_num}/{total_batches} を処理中... ({len(batch)}商品)")

        product_list = []
        for idx, product in enumerate(batch):
            product_list.append({
                'index': idx,
                'name': product['product_name'],
                'general_name': product.get('general_name', ''),
                'keywords': product.get('keywords', ''),
                'small_category': product.get('small_category', '')
            })

        # Create prompt based on number of parts
        if len(parts) == 2:
            prompt = f'''以下の商品を「{parts[0]}」と「{parts[1]}」のどちらに分類すべきか判定してください。

【商品リスト】
{json.dumps(product_list, ensure_ascii=False, indent=2)}

各商品のindexに対して、分類先を返してください。JSON形式で返してください：
{{
  "0": "{parts[0]}",
  "1": "{parts[1]}",
  ...
}}'''
        else:  # 3分割
            prompt = f'''以下の商品を「{parts[0]}」「{parts[1]}」「{parts[2]}」のいずれかに分類してください。

【商品リスト】
{json.dumps(product_list, ensure_ascii=False, indent=2)}

各商品のindexに対して、分類先を返してください。JSON形式で返してください：
{{
  "0": "{parts[0]}",
  "1": "{parts[1]}",
  "2": "{parts[2]}",
  ...
}}'''

        try:
            response = model.generate_content(prompt)
            result_text = response.text.strip()

            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()

            classifications = json.loads(result_text)

            for idx_str, category in classifications.items():
                idx = int(idx_str)
                product_id = batch[idx]['id']
                product_classifications[product_id] = category

            print(f"    完了 ({len(classifications)}件分類)")
        except Exception as e:
            print(f"    エラー: {e}")
            # Fallback to first part
            for idx, product in enumerate(batch):
                product_classifications[product['id']] = parts[0]

        time.sleep(6)

    print(f"\n分類完了: {len(product_classifications)}商品")

    # Statistics
    stats = defaultdict(int)
    for category in product_classifications.values():
        stats[category] += 1
    print("\n分類結果:")
    for category, count in stats.items():
        print(f"  {category}: {count}件")

    # Save classification results
    classification_results = {
        'compound_category': f'{large}>{compound_medium}',
        'parts': parts,
        'classifications': product_classifications,
        'statistics': dict(stats)
    }

    with open(f'_runtime/data/classification/classification_results_step{step}.json', 'w', encoding='utf-8') as f:
        json.dump(classification_results, f, ensure_ascii=False, indent=2)
    print(f"\n分類結果を classification_results_step{step}.json に保存しました")

    # 5. Determine new categories needed
    category_migrations = defaultdict(list)
    new_categories_needed = set()

    for product in all_products:
        product_id = product['id']
        small_cat = product.get('small_category', '')
        new_medium = product_classifications.get(product_id, parts[0])
        new_key = f"{large}>{new_medium}>{small_cat}"

        if new_key not in category_by_key:
            new_categories_needed.add(new_key)

        category_migrations[new_key].append(product_id)

    print(f"\n新規作成が必要なカテゴリー: {len(new_categories_needed)}件")

    # 6. Create new categories
    for new_key in new_categories_needed:
        parts_split = new_key.split('>')
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

    # 7. Migrate products
    print(f"\n商品を新しいカテゴリーに移行中...")
    update_count = 0
    for new_key, product_ids in category_migrations.items():
        new_category_id = category_by_key[new_key]['id']
        for product_id in product_ids:
            supabase.table('Rawdata_NETSUPER_items') \
                .update({'category_id': new_category_id}) \
                .eq('id', product_id) \
                .execute()
            update_count += 1

    print(f"商品更新完了: {update_count}件")

    print("\n" + "=" * 100)
    print("処理完了")
    print("=" * 100)
    print(f"元の中分類: {large}>{compound_medium}")
    for category, count in stats.items():
        print(f"  → {category}: {count}件")
    print(f"新規カテゴリー作成: {len(new_categories_needed)}件")
    print(f"商品更新: {update_count}件")
    print()

    return {
        'step': step,
        'compound_category': f'{large}>{compound_medium}',
        'product_count': len(all_products),
        'new_categories': len(new_categories_needed),
        'stats': dict(stats)
    }

def main():
    """全ての残りカテゴリーを処理"""
    results = []

    for config in REMAINING_COMPOUNDS:
        result = process_compound_category(config)
        results.append(result)

    # Final summary
    print("\n" + "=" * 100)
    print("全処理完了サマリー")
    print("=" * 100)
    total_products = sum(r['product_count'] for r in results)
    total_new_categories = sum(r['new_categories'] for r in results)

    for result in results:
        print(f"\nステップ{result['step']}: {result['compound_category']}")
        print(f"  商品数: {result['product_count']}件")
        for category, count in result['stats'].items():
            print(f"    → {category}: {count}件")
        print(f"  新規カテゴリー: {result['new_categories']}件")

    print(f"\n総計:")
    print(f"  処理商品数: {total_products}件")
    print(f"  新規カテゴリー作成: {total_new_categories}件")

if __name__ == '__main__':
    main()
