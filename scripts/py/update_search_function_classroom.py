#!/usr/bin/env python3
"""
Update search function to include classroom_subject field
"""

import os

# Try to get URL from environment
url = os.getenv("SUPABASE_URL", "https://hjkcgulxddtwlljhbocb.supabase.co")

# SQLファイルを読み込み
sql_file = "database/search_documents_with_chunks.sql"
with open(sql_file, "r") as f:
    sql = f.read()

print(f"Updating search function from {sql_file}...")
print("=" * 70)

try:
    # Supabase Python client doesn't support direct SQL execution
    # Using rpc with a custom function or direct PostgreSQL connection is required

    print("\nNote: The Supabase Python client cannot execute raw SQL directly.")
    print("Please apply this SQL update through one of these methods:")
    print()
    print("METHOD 1 - Supabase Dashboard (Recommended):")
    print(f"  1. Go to: {url.replace('/rest/v1', '')}")
    print("  2. Navigate to SQL Editor")
    print(f"  3. Copy and paste the contents of: {sql_file}")
    print("  4. Click 'Run' to execute the SQL")
    print()
    print("METHOD 2 - Direct PostgreSQL connection:")
    print("  If you have the database password:")
    print(f"  psql <DATABASE_URL> -f {sql_file}")
    print()
    print("=" * 70)
    print("\nSQL to apply:")
    print(sql)

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
