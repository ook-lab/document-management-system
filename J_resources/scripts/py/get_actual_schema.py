"""
Supabaseの実際のsource_documentsテーブル構造を取得
"""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')

client = create_client(supabase_url, supabase_key)

# PostgreSQLのシステムカタログから列情報を取得
query = """
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'source_documents'
ORDER BY ordinal_position;
"""

try:
    # RPC経由でクエリを実行
    # Supabaseではsql()関数が使えない可能性があるため、
    # 直接テーブルから1行取得してカラム名を確認
    response = client.table('source_documents').select('*').limit(1).execute()

    if response.data:
        columns = list(response.data[0].keys())
        print(f"\n✅ source_documentsテーブルのカラム一覧（{len(columns)}個）:")
        print("=" * 80)
        for col in sorted(columns):
            print(f"  - {col}")
    else:
        print("データが存在しません")

except Exception as e:
    print(f"❌ エラー: {e}")
