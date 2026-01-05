#!/usr/bin/env python
"""既存のGmailメールをデータベースから削除"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')

if not supabase_url or not supabase_key:
    print("エラー: SUPABASE_URLまたはSUPABASE_KEYが設定されていません")
    sys.exit(1)

client = create_client(supabase_url, supabase_key)

# workspace='gmail' のメールを取得
result = client.table('Rawdata_FILE_AND_MAIL').select('id, title').eq('workspace', 'gmail').execute()

if not result.data:
    print("workspace='gmail' のメールが見つかりません")
    sys.exit(0)

print(f"=== {len(result.data)}件のGmailメールを削除します ===\n")

for email in result.data:
    title = email.get('title', '(タイトルなし)')
    email_id = email['id']

    # search_indexからチャンクを削除
    try:
        chunk_result = client.table('10_ix_search_index').delete().eq('document_id', email_id).execute()
        print(f"[OK] チャンク削除: {title[:50]}")
    except Exception as e:
        print(f"[WARN] チャンク削除失敗: {title[:50]} - {e}")

    # Rawdata_FILE_AND_MAILから削除
    try:
        delete_result = client.table('Rawdata_FILE_AND_MAIL').delete().eq('id', email_id).execute()
        print(f"[OK] メール削除: {title[:50]}")
        print()
    except Exception as e:
        print(f"[ERROR] メール削除失敗: {title[:50]} - {e}")

print("完了！")
print("\n次のステップ:")
print("1. Gmailで「Processed」ラベルを削除し、「DM」ラベルを追加")
print("2. python B_ingestion/gmail/gmail_ingestion.py --mail-type DM")
print("3. python process_queued_documents.py --workspace=gmail")
