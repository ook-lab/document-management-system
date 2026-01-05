#!/usr/bin/env python3
"""
中分類と小分類が同じ名称の商品を、Gemini2.5flash-liteで適切な小分類に振り分ける
"""

import pandas as pd
import json
import os
import time
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Gemini API設定
genai.configure(api_key=os.getenv('GOOGLE_AI_API_KEY'))
model = genai.GenerativeModel('gemini-2.5-flash-lite')

def get_available_small_categories(df, medium_category):
    """指定された中分類で利用可能な小分類を取得（同名のものを除く）"""
    medium_df = df[df['中分類'] == medium_category]
    available = medium_df[medium_df['小分類（カテゴリ）'] != medium_category]['小分類（カテゴリ）'].unique().tolist()
    # 空文字列やNaNを除外
    available = [cat for cat in available if pd.notna(cat) and cat.strip() != '']
    return sorted(available)

def classify_with_gemini(products_batch, medium_category, available_small_categories):
    """Geminiで商品を分類"""

    # 商品リストを整形
    products_text = ""
    for i, product in enumerate(products_batch, 1):
        products_text += f"{i}. {product['商品名']} (一般名詞: {product['一般名詞']})\n"

    # 利用可能な小分類リスト
    categories_text = "\n".join([f"- {cat}" for cat in available_small_categories])

    # プロンプト
    prompt = f"""以下の商品は、現在「中分類: {medium_category}」「小分類: {medium_category}」と分類されています。
これは中分類と小分類が同じ名前になってしまっているため、適切ではありません。

この中分類内で利用可能な小分類は以下の通りです：
{categories_text}

各商品について、上記の利用可能な小分類の中から最も適切なものを選んで分類してください。
どうしても適切な小分類がない場合のみ、新しい小分類名を提案してください。

商品リスト：
{products_text}

以下のJSON形式で回答してください：
{{
  "classifications": [
    {{
      "商品名": "商品名",
      "推奨小分類": "選択した小分類名",
      "理由": "選択理由（簡潔に）",
      "新規作成": false
    }},
    ...
  ]
}}

必ず有効なJSONフォーマットで回答してください。"""

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                max_output_tokens=8000,
            )
        )

        result_text = response.text.strip()

        # JSONを抽出
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()

        result = json.loads(result_text)
        return result['classifications']

    except Exception as e:
        print(f"エラー: {e}")
        print(f"レスポンス: {response.text if 'response' in locals() else 'なし'}")
        return None

def main():
    # CSVを読み込み
    print("CSVファイルを読み込んでいます...")
    df = pd.read_csv('netsuper_classification_list.csv')

    # 中分類と小分類が同じ商品を抽出
    same_category_df = df[df['中分類'] == df['小分類（カテゴリ）']].copy()

    print(f"\n中分類と小分類が同じ商品: {len(same_category_df)}件")
    print(same_category_df['中分類'].value_counts())

    # 結果を保存するリスト
    all_results = []

    # 中分類ごとに処理
    for medium_category in same_category_df['中分類'].unique():
        if pd.isna(medium_category) or medium_category.strip() == '':
            continue

        print(f"\n\n{'='*60}")
        print(f"処理中: {medium_category}")
        print(f"{'='*60}")

        # この中分類の同名商品を取得
        category_products = same_category_df[same_category_df['中分類'] == medium_category]

        # 利用可能な小分類を取得
        available_small_cats = get_available_small_categories(df, medium_category)

        print(f"同名商品数: {len(category_products)}件")
        print(f"利用可能な小分類: {len(available_small_cats)}個")
        if available_small_cats:
            print(f"  {', '.join(available_small_cats[:10])}")
            if len(available_small_cats) > 10:
                print(f"  ... 他 {len(available_small_cats) - 10}個")
        else:
            print("  ※利用可能な小分類がありません。新規作成が必要です。")

        # バッチ処理（1回に20商品ずつ）
        batch_size = 20
        products_list = category_products.to_dict('records')

        for i in range(0, len(products_list), batch_size):
            batch = products_list[i:i+batch_size]
            print(f"\n  バッチ {i//batch_size + 1}/{(len(products_list)-1)//batch_size + 1} ({len(batch)}件)")

            # Geminiで分類（レート制限回避のため待機）
            time.sleep(6)  # 1分間に10リクエストまでなので6秒待機
            classifications = classify_with_gemini(batch, medium_category, available_small_cats)

            if classifications:
                for j, classification in enumerate(classifications):
                    product = batch[j]
                    result = {
                        '商品名': product['商品名'],
                        '一般名詞': product['一般名詞'],
                        '大分類': product['大分類'],
                        '現在の中分類': medium_category,
                        '現在の小分類': medium_category,
                        '推奨小分類': classification['推奨小分類'],
                        '理由': classification.get('理由', ''),
                        '新規作成': classification.get('新規作成', False)
                    }
                    all_results.append(result)
                    print(f"    {j+1}. {product['商品名'][:40]}... → {classification['推奨小分類']}")

    # 結果をJSONで保存
    output_file = 'temp/fix_same_category_results.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"\n\n{'='*60}")
    print(f"分類結果を {output_file} に保存しました")
    print(f"総処理件数: {len(all_results)}件")

    # 新規作成が必要な小分類を集計
    new_categories = {}
    for result in all_results:
        if result['新規作成']:
            medium = result['現在の中分類']
            small = result['推奨小分類']
            key = f"{medium} > {small}"
            if key not in new_categories:
                new_categories[key] = []
            new_categories[key].append(result['商品名'])

    if new_categories:
        print(f"\n新規作成が必要な小分類:")
        for cat, products in new_categories.items():
            print(f"  {cat}: {len(products)}件")

    # 推奨小分類の集計
    print(f"\n推奨小分類の集計:")
    small_cat_counts = {}
    for result in all_results:
        key = f"{result['現在の中分類']} > {result['推奨小分類']}"
        small_cat_counts[key] = small_cat_counts.get(key, 0) + 1

    for cat, count in sorted(small_cat_counts.items(), key=lambda x: x[1], reverse=True)[:20]:
        print(f"  {cat}: {count}件")

if __name__ == "__main__":
    # ⚠️ 安全ガード：誤実行防止
    import sys
    print("\n" + "="*70)
    print("⚠️  警告: このスクリプトは高額なAPI料金が発生します")
    print("⚠️  処理内容: 中分類=小分類の商品を20件バッチでGemini分類")
    print("⚠️  max_output_tokens: 8000トークン/バッチ")
    print("⚠️  推定コスト: 商品数により変動（100件で約50-100円）")
    print("="*70)
    confirm = input("\n本当に実行しますか？ (YES と大文字で入力): ")
    if confirm != "YES":
        print("❌ 実行を中止しました")
        sys.exit(0)
    print("\n✅ 実行を開始します...\n")

    main()
