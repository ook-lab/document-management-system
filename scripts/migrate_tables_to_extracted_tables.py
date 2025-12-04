"""
既存データのマイグレーション: metadata.tables → extracted_tables カラム

metadata JSON内のtablesフィールドをextracted_tablesカラムに移動するスクリプト
"""

import asyncio
import json
from loguru import logger
from core.database.client import DatabaseClient


async def migrate_tables():
    """metadata.tables を extracted_tables カラムに移行"""

    db = DatabaseClient()

    logger.info("=" * 60)
    logger.info("テーブルデータ マイグレーション開始")
    logger.info("=" * 60)

    # extracted_tables が NULL のドキュメントを取得
    query = db.client.table('documents').select('*').is_('extracted_tables', 'null')
    response = query.execute()

    if not response.data:
        logger.info("マイグレーション対象のドキュメントがありません")
        return

    total = len(response.data)
    logger.info(f"対象ドキュメント数: {total} 件")

    migrated = 0
    skipped = 0
    errors = 0

    for doc in response.data:
        doc_id = doc['id']
        file_name = doc.get('file_name', 'unknown')
        metadata = doc.get('metadata')

        try:
            # metadata が文字列の場合はパース
            if isinstance(metadata, str):
                metadata = json.loads(metadata)

            # tables フィールドの確認
            if metadata and 'tables' in metadata and metadata['tables']:
                tables = metadata['tables']

                # extracted_tables カラムに保存
                update_data = {'extracted_tables': tables}

                db.client.table('documents').update(update_data).eq('id', doc_id).execute()

                logger.info(f"[{migrated+1}/{total}] ✅ {file_name}: {len(tables)} 個の表を移行")
                migrated += 1
            else:
                logger.debug(f"[{migrated+skipped+1}/{total}] ⏭️  {file_name}: 表データなし")
                skipped += 1

        except Exception as e:
            logger.error(f"[{migrated+skipped+errors+1}/{total}] ❌ {file_name}: {e}")
            errors += 1

    logger.info("=" * 60)
    logger.info("マイグレーション完了")
    logger.info(f"  移行成功: {migrated} 件")
    logger.info(f"  スキップ: {skipped} 件")
    logger.info(f"  エラー:   {errors} 件")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(migrate_tables())
