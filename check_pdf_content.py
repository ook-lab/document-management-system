"""
PDFの内容をデータベースから取得
"""
import os
from dotenv import load_dotenv
from supabase import create_client

# 環境変数を読み込み
load_dotenv()

# Supabase接続
supabase = create_client(
    os.environ.get('SUPABASE_URL'),
    os.environ.get('SUPABASE_KEY')
)

# ドキュメントを取得
response = supabase.table('documents').select('file_name, full_text, metadata, document_date').eq('file_name', '学年通信（29）.pdf').execute()

if response.data:
    doc = response.data[0]
    print(f"ファイル名: {doc['file_name']}")
    print(f"document_date: {doc['document_date']}")

    # metadataを確認
    import json
    metadata = doc.get('metadata', {})
    print(f"\n=== メタデータ ===")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))

    print(f"\n=== PDF全文（最初の2000文字） ===")
    full_text = doc.get('full_text', '')
    print(full_text[:2000])
    print(f"\n... (全文字数: {len(full_text)})")
else:
    print("ドキュメントが見つかりませんでした")
