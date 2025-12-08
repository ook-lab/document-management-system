"""
Google Classroom関連のレコードをSupabaseから削除
"""
from core.database.client import DatabaseClient
from loguru import logger

def delete_classroom_records():
    """workspace='ikuya_classroom' のレコードを全削除"""
    db = DatabaseClient()

    logger.info("workspace='ikuya_classroom' のレコードを削除します...")

    try:
        # 削除前に件数確認
        result = db.client.table('documents').select('id').eq('workspace', 'ikuya_classroom').execute()
        count = len(result.data) if result.data else 0

        logger.info(f"削除対象: {count}件")

        if count == 0:
            logger.info("削除対象のレコードがありません")
            return

        # 確認
        print(f"\n{count}件のレコードを削除します。よろしいですか？ (y/N): ", end='')
        response = input().strip().lower()

        if response != 'y':
            logger.info("削除をキャンセルしました")
            return

        # 削除実行
        db.client.table('documents').delete().eq('workspace', 'ikuya_classroom').execute()

        logger.success(f"✅ {count}件のレコードを削除しました")

    except Exception as e:
        logger.error(f"削除エラー: {e}")
        raise

if __name__ == "__main__":
    delete_classroom_records()
