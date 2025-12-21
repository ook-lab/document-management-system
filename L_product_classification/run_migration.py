"""
データベースマイグレーション実行スクリプト
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from A_common.database.client import DatabaseClient
from loguru import logger


def run_migration():
    """マイグレーションを実行"""
    db = DatabaseClient(use_service_role=True)

    # SQLファイルを読み込み
    sql_file = root_dir / "database" / "migrations" / "create_product_classification_system.sql"

    logger.info(f"Reading SQL file: {sql_file}")
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # セミコロンで分割して個別に実行
    # DO $$ ブロックは分割しないように注意
    statements = []
    current_statement = []
    in_do_block = False

    for line in sql_content.split('\n'):
        stripped = line.strip()

        # コメント行はスキップ
        if stripped.startswith('--'):
            continue

        # DO $$ ブロックの開始
        if 'DO $$' in line or 'DO$$' in line:
            in_do_block = True

        current_statement.append(line)

        # DO $$ ブロックの終了
        if in_do_block and '$$;' in line:
            in_do_block = False
            statements.append('\n'.join(current_statement))
            current_statement = []
        # 通常の文の終了
        elif not in_do_block and stripped.endswith(';'):
            statements.append('\n'.join(current_statement))
            current_statement = []

    # 実行
    success_count = 0
    for i, statement in enumerate(statements, 1):
        stmt = statement.strip()
        if not stmt or stmt == ';':
            continue

        try:
            logger.info(f"Executing statement {i}/{len(statements)}")
            logger.debug(f"SQL: {stmt[:100]}...")

            # Supabase REST APIではなくrpc()を使うか、直接SQLを実行
            # ここでは簡易的にエラーをキャッチして続行
            result = db.client.rpc('exec_sql', {'sql': stmt}).execute()
            success_count += 1
            logger.success(f"Statement {i} executed successfully")

        except Exception as e:
            # テーブルやカラムが既に存在する場合のエラーは無視
            error_msg = str(e).lower()
            if 'already exists' in error_msg or 'duplicate' in error_msg:
                logger.warning(f"Statement {i} skipped (already exists): {e}")
                success_count += 1
            else:
                logger.error(f"Statement {i} failed: {e}")
                # 致命的なエラーの場合は中断
                if 'syntax error' in error_msg:
                    raise

    logger.success(f"Migration completed: {success_count}/{len(statements)} statements executed")


if __name__ == "__main__":
    try:
        run_migration()
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)
