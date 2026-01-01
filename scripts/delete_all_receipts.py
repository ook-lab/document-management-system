"""
全レシートデータを削除
⚠️ 警告: この操作は取り消せません
"""
import sys
import io
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

# Fix Windows encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

db = create_client(SUPABASE_URL, SUPABASE_KEY)

print("=" * 60)
print("⚠️  全レシートデータ削除スクリプト")
print("=" * 60)
print()

# 現在のデータ件数を確認
receipts = db.table("Rawdata_RECEIPT_shops").select("*", count="exact").execute()
items = db.table("Rawdata_RECEIPT_items").select("*", count="exact").execute()
logs = db.table("99_lg_image_proc_log").select("*", count="exact").execute()

print(f"削除対象:")
print(f"  - レシート: {receipts.count}件")
print(f"  - 商品明細: {items.count}件")
print(f"  - 処理ログ: {logs.count}件")
print()

# 確認
confirm = input("本当に全データを削除しますか？ (yes/no): ")

if confirm.lower() != "yes":
    print("キャンセルしました")
    sys.exit(0)

print("\n削除を開始します...")

# 1. 商品明細を削除（子テーブル）
print("\n[1/3] 商品明細を削除中...")
try:
    # workspace = 'household' のみ削除（安全のため）
    result = db.table("Rawdata_RECEIPT_items").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    print(f"✓ 商品明細を削除しました")
except Exception as e:
    print(f"✗ エラー: {e}")
    sys.exit(1)

# 2. レシート情報を削除（親テーブル）
print("\n[2/3] レシート情報を削除中...")
try:
    result = db.table("Rawdata_RECEIPT_shops").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    print(f"✓ レシート情報を削除しました")
except Exception as e:
    print(f"✗ エラー: {e}")
    sys.exit(1)

# 3. 処理ログを削除
print("\n[3/3] 処理ログを削除中...")
try:
    result = db.table("99_lg_image_proc_log").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    print(f"✓ 処理ログを削除しました")
except Exception as e:
    print(f"✗ エラー: {e}")
    sys.exit(1)

# 削除後の件数を確認
receipts_after = db.table("Rawdata_RECEIPT_shops").select("*", count="exact").execute()
items_after = db.table("Rawdata_RECEIPT_items").select("*", count="exact").execute()
logs_after = db.table("99_lg_image_proc_log").select("*", count="exact").execute()

print("\n" + "=" * 60)
print("✓ 削除完了")
print("=" * 60)
print(f"削除後の件数:")
print(f"  - レシート: {receipts_after.count}件")
print(f"  - 商品明細: {items_after.count}件")
print(f"  - 処理ログ: {logs_after.count}件")
print()
print("レシート画像をINBOXに戻して、全件取り込みを開始してください。")
