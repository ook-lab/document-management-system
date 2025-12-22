#!/usr/bin/env python3
"""
マイグレーションスクリプト実行ツール
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

# プロジェクトルートを取得
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 環境変数をロード
load_dotenv()

def run_migration(migration_file: str):
    """
    指定されたマイグレーションファイルを実行

    Args:
        migration_file: マイグレーションファイルのパス
    """
    # Supabase接続
    url = os.getenv("SUPABASE_URL")
    # SERVICE_ROLE_KEYを使用（DDL実行には管理者権限が必要）
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

    if not url or not key:
        print("ERROR: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not found in environment")
        sys.exit(1)

    db = create_client(url, key)

    # マイグレーションファイルを読み込み
    migration_path = Path(migration_file)
    if not migration_path.exists():
        print(f"ERROR: Migration file not found: {migration_file}")
        sys.exit(1)

    print(f"Reading migration file: {migration_path}")
    with open(migration_path, 'r', encoding='utf-8') as f:
        sql = f.read()

    print(f"Executing migration...")
    print("-" * 80)
    print(sql)
    print("-" * 80)

    try:
        # PostgreSQL関数を使ってSQLを実行
        result = db.rpc('exec_sql', {'sql': sql}).execute()
        print("✅ Migration executed successfully!")
        return True
    except Exception as e:
        # rpc関数がない場合は、postgrestの機能を使って実行を試みる
        print(f"⚠️ RPC method failed: {e}")
        print("Trying alternative method...")

        try:
            # 各SQLステートメントを個別に実行
            statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]

            for stmt in statements:
                if stmt:
                    print(f"Executing: {stmt[:100]}...")
                    # postgrestでは直接SQLを実行できないため、psycopg2を使用
                    import psycopg2

                    # 接続文字列を構築（Supabase URLから）
                    # 注: これは推奨される方法ではありません。本番環境ではSupabase CLIを使用してください
                    print("ERROR: Direct SQL execution requires psycopg2 or Supabase CLI")
                    print("Please run this SQL manually in Supabase SQL Editor:")
                    print("-" * 80)
                    print(sql)
                    print("-" * 80)
                    sys.exit(1)

        except Exception as e2:
            print(f"❌ Migration failed: {e2}")
            print("\nPlease run this SQL manually in Supabase SQL Editor:")
            print("-" * 80)
            print(sql)
            print("-" * 80)
            return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_migration.py <migration_file>")
        print("\nExample:")
        print("  python database/run_migration.py database/migrations/add_tax_subtotal_columns.sql")
        sys.exit(1)

    migration_file = sys.argv[1]
    run_migration(migration_file)
