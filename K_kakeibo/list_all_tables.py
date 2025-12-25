"""
すべてのテーブルを探す（ブルートフォース）
"""
import sys
import io
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

# Fix Windows encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

db = create_client(SUPABASE_URL, SUPABASE_KEY)

# よくあるテーブル名のプレフィックス/パターン
prefixes = ["", "MASTER_", "ms_", "ag_", "lg_", "Rawdata_", "v_"]
base_names = [
    "aliases", "ocr_aliases", "product_aliases",
    "products", "product_dict", "product_classify",
    "situations", "purpose", "purposes",
    "categories", "expense_categories", "category_rules",
    "items", "shops", "receipts"
]

possible_tables = []
for prefix in prefixes:
    for base in base_names:
        possible_tables.append(f"{prefix}{base}")

# 追加で数字プレフィックス付き
for i in [60, 70, 80, 90, 99]:
    for base in base_names:
        possible_tables.append(f"{i}_ms_{base}")
        possible_tables.append(f"{i}_ag_{base}")

print("=== データベーステーブル探索 ===\n")
found_tables = {}

for table in set(possible_tables):
    try:
        result = db.table(table).select("*").limit(1).execute()
        # 件数を確認
        count_result = db.table(table).select("*", count="exact").execute()
        found_tables[table] = count_result.count
    except:
        pass

# 結果を表示
print("見つかったテーブル:\n")
for table, count in sorted(found_tables.items()):
    print(f"  {table:40} {count:5}件")
