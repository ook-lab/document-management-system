#!/usr/bin/env python3
"""
複合小分類（・を含む）をGemini APIで単一小分類に分解
"""
import os
import json
import time
from supabase import create_client
from dotenv import load_dotenv
import google.generativeai as genai
from collections import defaultdict

# Load environment variables
load_dotenv()

# Supabase setup
supabase = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_KEY')
)

# Gemini setup
genai.configure(api_key=os.getenv('GOOGLE_AI_API_KEY'))
model = genai.GenerativeModel('gemini-2.5-flash-lite')

def get_compound_small_categories():
    """複合小分類（・を含む）のカテゴリーと商品を取得"""
    print("複合小分類のカテゴリーを取得中...")

    # 全カテゴリーを取得
    all_categories = []
    offset = 0
    while True:
        result = supabase.table('MASTER_Categories_product')\
            .select('id, large_category, medium_category, small_category')\
            .range(offset, offset + 999)\
            .execute()
        if not result.data:
            break
        all_categories.extend(result.data)
        offset += 1000

    # 複合小分類のカテゴリーIDを収集
    compound_categories = []
    for cat in all_categories:
        small = cat.get('small_category', '')
        if '・' in small:
            compound_categories.append(cat)

    print(f"複合小分類のカテゴリー数: {len(compound_categories)}個")

    # 各カテゴリーの商品を取得
    all_products = []
    for cat in compound_categories:
        offset = 0
        while True:
            result = supabase.table('Rawdata_NETSUPER_items')\
                .select('id, product_name, general_name, keywords, small_category, category_id')\
                .eq('category_id', cat['id'])\
                .range(offset, offset + 999)\
                .execute()
            if not result.data:
                break

            for product in result.data:
                product['large_category'] = cat['large_category']
                product['medium_category'] = cat['medium_category']
                product['compound_small'] = cat['small_category']
                all_products.append(product)

            offset += 1000

    print(f"複合小分類に含まれる商品総数: {len(all_products)}件")
    return all_products

def classify_products_batch(products, compound_small_category):
    """
    商品バッチを分類
    compound_small_category: 例 "スパイス・香辛料"
    """
    parts = [p.strip() for p in compound_small_category.split('・')]

    # プロンプト作成
    product_list = []
    for i, p in enumerate(products, 1):
        product_list.append(f"{i}. {p['product_name']}")

    prompt = f"""あなたは日本のスーパーマーケットの商品分類の専門家です。

以下の商品は、現在「{compound_small_category}」という複合カテゴリーに分類されています。
これらの商品を以下のいずれかの単一カテゴリーに分類してください：

選択肢: {', '.join(parts)}

商品リスト:
{chr(10).join(product_list)}

各商品について、最も適切なカテゴリーを1つ選択してください。

回答は必ず以下のJSON形式で出力してください（他の説明は不要）:
{{
  "1": "カテゴリー名",
  "2": "カテゴリー名",
  ...
}}

例:
{{
  "1": "{parts[0]}",
  "2": "{parts[1]}"
}}
"""

    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()

        # JSONを抽出（```json ``` で囲まれている場合に対応）
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0].strip()
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0].strip()

        classifications = json.loads(response_text)

        # 結果をproduct_idベースに変換
        result = {}
        for i, product in enumerate(products, 1):
            category = classifications.get(str(i), parts[0])  # デフォルトは最初の選択肢
            result[product['id']] = category

        return result

    except Exception as e:
        print(f"  ⚠️  分類エラー: {e}")
        # エラー時はデフォルト（最初の選択肢）を返す
        return {p['id']: parts[0] for p in products}

def main():
    """メイン処理 - 中分類ごとに処理"""
    import sys

    # コマンドライン引数で中分類を指定（オプション）
    target_medium = sys.argv[1] if len(sys.argv) > 1 else None

    print("=" * 100)
    print("複合小分類の分解処理を開始")
    print("=" * 100)

    # 1. 複合小分類の商品を取得
    all_products = get_compound_small_categories()

    if not all_products:
        print("処理対象の商品がありません")
        return

    # 2. 中分類ごとにグループ化
    grouped_by_medium = defaultdict(list)
    for product in all_products:
        medium_key = f"{product['large_category']}>{product['medium_category']}"
        grouped_by_medium[medium_key].append(product)

    # 中分類のリストを表示
    print(f"\n中分類の種類: {len(grouped_by_medium)}種類")
    for i, (medium_key, products) in enumerate(sorted(grouped_by_medium.items(), key=lambda x: len(x[1]), reverse=True), 1):
        print(f"{i}. {medium_key} ({len(products)}件)")

    # 特定の中分類が指定されている場合はそれだけ処理
    if target_medium:
        medium_to_process = {k: v for k, v in grouped_by_medium.items() if target_medium in k}
        if not medium_to_process:
            print(f"\n指定された中分類 '{target_medium}' が見つかりません")
            return
        grouped_by_medium = medium_to_process
        print(f"\n指定された中分類のみ処理します: {list(medium_to_process.keys())}")

    # 3. 各中分類を1つずつ処理
    for medium_idx, (medium_key, medium_products) in enumerate(sorted(grouped_by_medium.items(), key=lambda x: len(x[1]), reverse=True), 1):
        print(f"\n{'='*100}")
        print(f"[{medium_idx}/{len(grouped_by_medium)}] 中分類: {medium_key} ({len(medium_products)}件)")
        print(f"{'='*100}")

        # この中分類内の複合小分類ごとにグループ化
        grouped_by_compound = defaultdict(list)
        for product in medium_products:
            compound_key = f"{product['compound_small']}"
            grouped_by_compound[compound_key].append(product)

        # 複合小分類ごとに処理
        all_classifications = {}
        processed_count = 0

        for compound_small, products in sorted(grouped_by_compound.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"\n  処理中: {medium_key}>{compound_small} ({len(products)}件)")

            # バッチサイズ50で処理
            batch_size = 50
            for i in range(0, len(products), batch_size):
                batch = products[i:i+batch_size]
                print(f"    バッチ {i//batch_size + 1}/{(len(products)-1)//batch_size + 1} ({len(batch)}件)...")

                classifications = classify_products_batch(batch, compound_small)
                all_classifications.update(classifications)

                processed_count += len(batch)
                print(f"    進捗: {processed_count}/{len(medium_products)}件完了")

                # レート制限対策
                time.sleep(2)

        # 4. この中分類の結果を保存
        safe_medium_name = medium_key.replace('>', '_').replace('/', '_')
        output_file = f'classification_results_small_{safe_medium_name}.json'
        result_data = {
            'medium_category': medium_key,
            'total_products': len(medium_products),
            'total_compound_small_categories': len(grouped_by_compound),
            'classifications': all_classifications
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)

        # 統計情報
        stats = defaultdict(int)
        for category in all_classifications.values():
            stats[category] += 1

        print(f"\n  {'='*80}")
        print(f"  中分類 {medium_key} の処理完了")
        print(f"  {'='*80}")
        print(f"  結果を {output_file} に保存しました")
        print(f"  総商品数: {len(medium_products)}件")
        print(f"  複合小分類の種類: {len(grouped_by_compound)}種類")
        print(f"  分類結果の内訳:")
        for category, count in sorted(stats.items(), key=lambda x: x[1], reverse=True):
            print(f"    {category}: {count}件")
        print()

    print(f"\n{'='*100}")
    print("全中分類の処理完了")
    print(f"{'='*100}")

if __name__ == '__main__':
    main()
