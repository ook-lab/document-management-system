"""
特定のファイルを再処理（Vision補完を強制実行）
"""
import os
import asyncio
from dotenv import load_dotenv
from loguru import logger

from pipelines.two_stage_ingestion import TwoStageIngestionPipeline
from core.database.client import DatabaseClient

load_dotenv()

async def reprocess_file(file_name: str):
    """
    特定のファイルを再処理

    Args:
        file_name: ファイル名（例: "学年通信（29）.pdf"）
    """
    logger.info(f"🔄 ファイル再処理開始: {file_name}")

    # パイプライン初期化
    pipeline = TwoStageIngestionPipeline()
    db = DatabaseClient()

    # Google Driveからファイルを検索
    folder_id = os.getenv('PERSONAL_FOLDER_ID')
    files = pipeline.drive.list_files_in_folder(folder_id)

    target_file = None
    for f in files:
        if f.get('name') == file_name:
            target_file = f
            break

    if not target_file:
        logger.error(f"❌ ファイルが見つかりません: {file_name}")
        return

    logger.info(f"✅ ファイル発見: {file_name} (ID: {target_file['id']})")

    # 既存データを削除
    try:
        response = db.client.table('source_documents').select('id').eq('source_id', target_file['id']).execute()
        if response.data:
            for doc in response.data:
                db.client.table('source_documents').delete().eq('id', doc['id']).execute()
            logger.info(f"🗑️  既存データ削除: {len(response.data)} 件")
    except Exception as e:
        logger.error(f"❌ 既存データ削除失敗: {e}")

    # 再処理
    logger.info("📝 再処理開始（Vision補完を含む）...")
    result = await pipeline.process_file(target_file, workspace='family')

    if result:
        vision_used = result.get('metadata', {}).get('vision_supplemented', False)
        vision_pages = result.get('metadata', {}).get('vision_pages', 0)

        logger.info("=" * 80)
        logger.info("✅ 再処理完了")
        logger.info(f"Vision補完: {'有効' if vision_used else '無効'}")
        logger.info(f"Vision処理ページ数: {vision_pages}")
        logger.info("=" * 80)
    else:
        logger.error("❌ 再処理失敗")

if __name__ == "__main__":
    asyncio.run(reprocess_file("価格表(小）2025.5.1以降 (1).pdf"))
