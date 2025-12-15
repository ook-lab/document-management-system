#!/usr/bin/env python3
"""
全テーブルの詳細分析スクリプト
- データ件数
- 主要カラム
- 役割の推測
"""
import os
import sys

def load_env():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key] = value

load_env()

from supabase import create_client

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    print("エラー: SUPABASE_URLまたはSUPABASE_KEYが設定されていません")
    sys.exit(1)

client = create_client(supabase_url, supabase_key)

print("=" * 80)
print("全テーブル詳細分析")
print("=" * 80)

# 確認するテーブル
tables = [
    'attachments',
    'corrections',
    'small_chunks',
    'correction_history',
    'documents_legacy',
    'document_chunks_legacy',
    'emails',
    'hypothetical_questions',
    'document_reprocessing_queue',
    'source_documents',
    'process_logs',
    'search_index'
]

for table in tables:
    print(f"\n{'=' * 80}")
    print(f"📊 テーブル: {table}")
    print("=" * 80)

    try:
        # データ件数取得
        count_response = client.table(table).select("*", count='exact').limit(0).execute()
        count = count_response.count if hasattr(count_response, 'count') else '?'

        print(f"データ件数: {count}")

        # サンプルデータ取得（1件）
        sample = client.table(table).select("*").limit(1).execute()

        if sample.data and len(sample.data) > 0:
            print(f"\n主要カラム:")
            for key in sample.data[0].keys():
                value = sample.data[0][key]
                # 値が長すぎる場合は省略
                if isinstance(value, str) and len(value) > 50:
                    value = value[:50] + "..."
                print(f"  - {key}: {type(value).__name__}")
        else:
            print("\nデータなし（スキーマのみ存在）")

    except Exception as e:
        print(f"❌ エラー: {e}")

print("\n" + "=" * 80)
print("分析完了")
print("=" * 80)
