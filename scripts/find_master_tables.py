"""
マスターテーブルを探す
"""
import sys
import io
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

# Fix Windows encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

db = create_client(SUPABASE_URL, SUPABASE_KEY)

# 可能性のあるテーブル名パターン
possible_tables = [
    # エイリアステーブルの可能性
    "MASTER_Product_classify",
    "MASTER_Aliases",
    "aliases",
    "ocr_aliases",
    "product_aliases",

    # 商品辞書の可能性
    "MASTER_Product_dict",
    "MASTER_Products",
    "product_dict",
    "products",

    # シチュエーションの可能性
    "MASTER_Situations",
    "situations",
    "MASTER_Purpose",
    "purpose",

    # カテゴリの可能性
    "MASTER_Categories",
    "categories",
    "expense_categories",
    "v_expense_category_rules"
]

print("=== マスターテーブル探索 ===\n")
found_tables = []

for table in possible_tables:
    try:
        result = db.table(table).select("*").limit(1).execute()
        print(f"✓ 見つかりました: {table}")

        # カラム情報を表示
        if result.data:
            columns = list(result.data[0].keys())
            print(f"  カラム: {', '.join(columns[:10])}")

        found_tables.append(table)
        print()
    except Exception as e:
        # 存在しないテーブルはスキップ
        pass

print("\n=== 見つかったマスターテーブル ===")
for table in found_tables:
    print(f"  - {table}")
