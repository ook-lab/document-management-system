#!/usr/bin/env python3
"""1つの複合小分類を処理"""
import os, sys
from supabase import create_client
from dotenv import load_dotenv
import google.generativeai as genai
import json
from uuid import uuid4

load_dotenv()
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
genai.configure(api_key=os.getenv('GOOGLE_AI_API_KEY'))
model = genai.GenerativeModel('gemini-2.5-flash-lite')

large = sys.argv[1]
medium = sys.argv[2]
compound_small = sys.argv[3]

print("=" * 80)
print(f"処理対象: {large}>{medium}>{compound_small}")
print("=" * 80)

# カテゴリーIDを取得
categories = []
offset = 0
while True:
    result = supabase.table('MASTER_Categories_product').select('*').range(offset, offset + 999).execute()
    if not result.data:
        break
    categories.extend(result.data)
    offset += 1000

target_cat = next((c for c in categories if c['large_category'] == large and c['medium_category'] == medium and c['small_category'] == compound_small), None)

if not target_cat:
    print("カテゴリーが見つかりません")
    exit(1)

# 商品を取得
products = supabase.table('Rawdata_NETSUPER_items').select('id, product_name').eq('category_id', target_cat['id']).execute()
print(f"商品数: {len(products.data)}件")

# Geminiで分類
parts = [p.strip() for p in compound_small.split('・')]
product_list = [f"{i+1}. {p['product_name']}" for i, p in enumerate(products.data)]
prompt = f"""以下の商品を {' または '.join([f'「{p}」' for p in parts])} に分類してください。

選択肢: {', '.join(parts)}

商品リスト:
{chr(10).join(product_list)}

回答は以下のJSON形式のみ:
{{"1": "{parts[0]}", "2": "{parts[1]}", ...}}
"""

response = model.generate_content(prompt)
response_text = response.text.strip()
if '```json' in response_text:
    response_text = response_text.split('```json')[1].split('```')[0].strip()
elif '```' in response_text:
    response_text = response_text.split('```')[1].split('```')[0].strip()

classifications = json.loads(response_text)
print("分類結果:")
for i, p in enumerate(products.data, 1):
    cat = classifications.get(str(i), parts[0])
    print(f"  {p['product_name']} → {cat}")

    # 新しいカテゴリーを作成または取得
    new_key = f"{large}>{medium}>{cat}"
    new_cat = next((c for c in categories if c['name'] == new_key), None)
    if not new_cat:
        new_id = str(uuid4())
        new_cat = {'id': new_id, 'name': new_key, 'large_category': large, 'medium_category': medium, 'small_category': cat}
        supabase.table('MASTER_Categories_product').insert(new_cat).execute()
        categories.append(new_cat)
        print(f"    新規カテゴリー作成: {new_key}")

    # 商品を移行
    supabase.table('Rawdata_NETSUPER_items').update({'category_id': new_cat['id']}).eq('id', p['id']).execute()

print(f"✅ 完了: {large}>{medium}>{compound_small} ({len(products.data)}件)")
