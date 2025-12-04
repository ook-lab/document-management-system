from core.database.client import DatabaseClient
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

db = DatabaseClient()
resp = db.client.table('documents').select('extracted_tables').eq('file_name', '価格表(小）2025.5.1以降 (1).pdf').execute()

if resp.data:
    tables = resp.data[0]['extracted_tables']
    print(f"Number of tables: {len(tables)}")
    print("\nFirst table structure:")
    print(json.dumps(tables[0], ensure_ascii=False, indent=2))
