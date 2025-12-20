"""
価格表PDFのデータベースレコードを削除して再処理を可能にする
"""
from core.database.client import DatabaseClient
from loguru import logger

def delete_price_list_document():
    """価格表PDFのレコードを削除"""
    db = DatabaseClient()

    # ファイル名で検索
    file_name = "価格表(小）2025.5.1以降 (1).pdf"

    try:
        # レコード検索
        response = db.client.table('10_rd_source_docs').select('id, file_name').eq('file_name', file_name).execute()

        if not response.data:
            logger.warning(f"❌ レコードが見つかりません: {file_name}")
            return False

        # 削除実行
        for doc in response.data:
            db.client.table('10_rd_source_docs').delete().eq('id', doc['id']).execute()
            logger.info(f"✅ 削除完了: {doc['file_name']} (ID: {doc['id']})")

        logger.info(f"🗑️  {len(response.data)} 件のレコードを削除しました")
        return True

    except Exception as e:
        logger.error(f"❌ 削除失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    delete_price_list_document()
