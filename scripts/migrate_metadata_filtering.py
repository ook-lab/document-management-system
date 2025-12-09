"""
既存データにメタデータフィルタリング用のカラムを追加するスクリプト

実行方法:
    python scripts/migrate_metadata_filtering.py

機能:
    - 既存の documents テーブルから metadata と document_date を読み込み
    - year, month, amount, event_dates, grade_level, school_name を抽出
    - documents テーブルを更新
"""
import asyncio
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.database.client import DatabaseClient
from core.utils.metadata_extractor import MetadataExtractor
from loguru import logger

# ログ設定
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}", level="INFO")


class MetadataFilteringMigration:
    """メタデータフィルタリング用カラムの移行クラス"""

    def __init__(self):
        self.db_client = DatabaseClient()

    async def migrate_all_documents(self, batch_size: int = 10, skip_existing: bool = True):
        """
        全文書にメタデータフィルタリング用カラムを追加

        Args:
            batch_size: 一度に処理する文書数
            skip_existing: 既にyearが設定されている文書をスキップするか
        """
        logger.info("==================== メタデータフィルタリング移行開始 ====================")

        # 処理対象の文書を取得
        documents = self.db_client.get_documents_for_review(limit=1000)

        if not documents:
            logger.warning("処理対象の文書が見つかりませんでした")
            return

        logger.info(f"処理対象: {len(documents)} 件の文書")

        success_count = 0
        skip_count = 0
        error_count = 0

        for i, doc in enumerate(documents, 1):
            doc_id = doc.get('id')
            file_name = doc.get('file_name', 'Unknown')

            logger.info(f"\n[{i}/{len(documents)}] 処理中: {file_name}")

            # 既にyearが設定されている場合はスキップ
            if skip_existing and doc.get('year') is not None:
                logger.info(f"  ⏭️  スキップ: 既に year={doc.get('year')} が設定されています")
                skip_count += 1
                continue

            # 移行実行
            success = await self.migrate_document(doc)

            if success:
                success_count += 1
                logger.info(f"  ✅ 移行成功")
            else:
                error_count += 1
                logger.error(f"  ❌ 移行失敗")

            # 進捗表示
            if i % 10 == 0:
                logger.info(f"\n--- 進捗: {i}/{len(documents)} 完了 (成功: {success_count}, スキップ: {skip_count}, エラー: {error_count}) ---\n")

        logger.info("\n==================== 移行完了 ====================")
        logger.info(f"成功: {success_count} 件")
        logger.info(f"スキップ: {skip_count} 件")
        logger.info(f"エラー: {error_count} 件")

    async def migrate_document(self, doc: dict) -> bool:
        """
        1つの文書にメタデータフィルタリング用カラムを追加

        Args:
            doc: 文書レコード

        Returns:
            成功したかどうか
        """
        doc_id = doc.get('id')
        metadata = doc.get('metadata', {})
        document_date = doc.get('document_date')

        try:
            # メタデータから抽出
            filtering_metadata = MetadataExtractor.extract_filtering_metadata(
                metadata=metadata,
                document_date=document_date
            )

            # ログ出力
            extracted_info = []
            if filtering_metadata.get("year"):
                extracted_info.append(f"年={filtering_metadata['year']}")
            if filtering_metadata.get("month"):
                extracted_info.append(f"月={filtering_metadata['month']}")
            if filtering_metadata.get("grade_level"):
                extracted_info.append(f"学年={filtering_metadata['grade_level']}")
            if filtering_metadata.get("school_name"):
                extracted_info.append(f"学校={filtering_metadata['school_name']}")

            info_str = ", ".join(extracted_info) if extracted_info else "なし"
            logger.info(f"  📊 抽出情報: {info_str}")

            # データベースを更新
            update_data = {}

            for key, value in filtering_metadata.items():
                if value is not None:
                    update_data[key] = value

            if not update_data:
                logger.warning(f"  ⚠️  更新するデータがありません")
                return False

            response = (
                self.db_client.client.table('documents')
                .update(update_data)
                .eq('id', doc_id)
                .execute()
            )

            if response.data:
                return True
            else:
                logger.error(f"  ❌ 更新失敗")
                return False

        except Exception as e:
            logger.error(f"  ❌ 移行エラー: {e}")
            import traceback
            traceback.print_exc()
            return False


async def main():
    """メイン処理"""
    migration = MetadataFilteringMigration()
    await migration.migrate_all_documents(batch_size=10, skip_existing=True)


if __name__ == "__main__":
    asyncio.run(main())
