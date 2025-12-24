"""
display_sender と display_subject カラムを削除するマイグレーション
psycopg2を使用してPostgreSQLに直接接続
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import logging

# 環境変数読み込み
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_supabase_connection_string():
    """Supabase接続文字列を取得"""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

    if not supabase_url:
        raise ValueError("SUPABASE_URL not found in environment variables")

    # Supabase URLからプロジェクト参照を抽出
    # 例: https://hjkcgulxddtwlljhbocb.supabase.co -> hjkcgulxddtwlljhbocb
    project_ref = supabase_url.split("//")[1].split(".")[0]

    # PostgreSQL接続文字列を構築
    # Supabaseのデフォルトパスワードは環境変数から取得する必要がある
    db_password = os.getenv("SUPABASE_DB_PASSWORD")

    if not db_password:
        logger.warning("SUPABASE_DB_PASSWORD not found. Please set it in .env file")
        logger.info("You can find the password in Supabase Dashboard -> Project Settings -> Database -> Connection String")
        logger.info("\nAlternatively, run the SQL migration manually in Supabase Dashboard:")
        logger.info("  1. Go to SQL Editor in Supabase Dashboard")
        logger.info("  2. Copy and paste the contents of:")
        logger.info("     database/migrations/drop_redundant_display_columns_from_products.sql")
        logger.info("  3. Click 'Run'")
        return None

    conn_string = f"postgresql://postgres:{db_password}@db.{project_ref}.supabase.co:5432/postgres"
    return conn_string


def main():
    """マイグレーション実行"""
    logger.info("=" * 80)
    logger.info("カラム削除マイグレーション開始")
    logger.info("=" * 80)

    # 接続文字列取得
    conn_string = get_supabase_connection_string()

    if not conn_string:
        logger.error("\n手動でSupabase Dashboardから実行してください:")
        logger.error("SQL Editor -> 以下のSQLを実行")
        logger.error("-" * 80)
        with open(Path(__file__).parent / "drop_redundant_display_columns_from_products.sql", "r") as f:
            logger.error(f.read())
        logger.error("-" * 80)
        return

    try:
        import psycopg2
    except ImportError:
        logger.error("psycopg2 がインストールされていません")
        logger.error("インストールコマンド: pip install psycopg2-binary")
        logger.info("\nまたは、Supabase Dashboardから手動で実行してください:")
        logger.info("  1. Supabase Dashboard -> SQL Editor")
        logger.info("  2. 以下のファイルの内容を実行:")
        logger.info("     database/migrations/drop_redundant_display_columns_from_products.sql")
        return

    try:
        # データベース接続
        logger.info("[1] データベースに接続中...")
        conn = psycopg2.connect(conn_string)
        cursor = conn.cursor()
        logger.info("✓ 接続成功")

        # 削除前のカラム確認
        logger.info("\n[2] 削除前のカラム確認...")
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'Rawdata_NETSUPER_items'
              AND column_name IN ('display_sender', 'display_subject')
            ORDER BY column_name;
        """)
        columns_before = cursor.fetchall()
        logger.info(f"削除前: {len(columns_before)} カラムが存在")
        for col in columns_before:
            logger.info(f"  - {col[0]}")

        # カラム削除
        logger.info("\n[3] カラム削除実行...")

        cursor.execute('ALTER TABLE "Rawdata_NETSUPER_items" DROP COLUMN IF EXISTS display_sender;')
        logger.info("✓ display_sender カラムを削除しました")

        cursor.execute('ALTER TABLE "Rawdata_NETSUPER_items" DROP COLUMN IF EXISTS display_subject;')
        logger.info("✓ display_subject カラムを削除しました")

        conn.commit()
        logger.info("✓ コミット完了")

        # 削除後のカラム確認
        logger.info("\n[4] 削除後のカラム確認...")
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'Rawdata_NETSUPER_items'
              AND column_name IN ('display_sender', 'display_subject')
            ORDER BY column_name;
        """)
        columns_after = cursor.fetchall()

        if len(columns_after) == 0:
            logger.info("✓ 削除成功: display_sender と display_subject は存在しません")
        else:
            logger.warning(f"⚠️  まだ {len(columns_after)} カラムが残っています:")
            for col in columns_after:
                logger.warning(f"  - {col[0]}")

        # クリーンアップ
        cursor.close()
        conn.close()

        logger.info("\n" + "=" * 80)
        logger.info("マイグレーション完了")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ エラーが発生しました: {e}")
        logger.error("\n手動で実行してください:")
        logger.error("Supabase Dashboard -> SQL Editor -> 以下を実行")
        logger.error("-" * 80)
        logger.error("ALTER TABLE \"Rawdata_NETSUPER_items\" DROP COLUMN IF EXISTS display_sender;")
        logger.error("ALTER TABLE \"Rawdata_NETSUPER_items\" DROP COLUMN IF EXISTS display_subject;")
        logger.error("-" * 80)


if __name__ == "__main__":
    main()
