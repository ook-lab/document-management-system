"""
既存データをチャンク分割形式に移行するスクリプト

実行方法:
    python scripts/migrate_to_chunks.py

機能:
    - 既存の documents テーブルから full_text を読み込み
    - チャンクに分割してembeddingを生成
    - document_chunks テーブルに保存
"""
import asyncio
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.database.client import DatabaseClient
from core.ai.embeddings import EmbeddingClient
from core.utils.chunking import chunk_document
from loguru import logger

# ログ設定
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}", level="INFO")


class ChunkMigration:
    """既存データのチャンク移行クラス"""

    def __init__(self):
        self.db_client = DatabaseClient()
        self.embedding_client = EmbeddingClient()

    async def migrate_all_documents(self, batch_size: int = 10, skip_existing: bool = True):
        """
        全文書をチャンク形式に移行

        Args:
            batch_size: 一度に処理する文書数
            skip_existing: 既にチャンクが存在する文書をスキップするか
        """
        logger.info("==================== チャンク移行開始 ====================")

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

            # 既にチャンクが存在する場合はスキップ
            if skip_existing:
                existing_chunks = self.db_client.get_document_chunks(doc_id)
                if existing_chunks:
                    logger.info(f"  ⏭️  スキップ: 既に {len(existing_chunks)} チャンクが存在します")
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
        1つの文書をチャンク形式に移行

        Args:
            doc: 文書レコード

        Returns:
            成功したかどうか
        """
        doc_id = doc.get('id')
        full_text = doc.get('full_text')

        if not full_text or not full_text.strip():
            logger.warning(f"  ⚠️  full_text が空です（doc_id: {doc_id}）")
            return False

        try:
            # ステップ1: チャンク分割
            logger.info(f"  📄 テキスト長: {len(full_text)} 文字")
            chunks = chunk_document(full_text, chunk_size=800, chunk_overlap=100)

            if not chunks:
                logger.warning(f"  ⚠️  チャンク分割結果が空です")
                return False

            logger.info(f"  ✂️  チャンク分割: {len(chunks)} チャンク")

            # ステップ2: 各チャンクのembedding生成
            logger.info(f"  🔢 Embedding生成中...")
            embeddings = []

            for chunk in chunks:
                chunk_text = chunk["chunk_text"]
                try:
                    embedding = self.embedding_client.generate_embedding(chunk_text)
                    embeddings.append(embedding)
                except Exception as e:
                    logger.error(f"  ❌ Embedding生成エラー (chunk {chunk['chunk_index']}): {e}")
                    # エラーが発生した場合はゼロベクトルを使用
                    embeddings.append([0.0] * 768)

            logger.info(f"  ✅ Embedding生成完了: {len(embeddings)} 件")

            # ステップ3: データベースに保存
            success = await self.db_client.insert_document_chunks(
                document_id=doc_id,
                chunks=chunks,
                embeddings=embeddings
            )

            if not success:
                logger.error(f"  ❌ チャンク保存失敗")
                return False

            # ステップ4: 文書のチャンク統計を更新
            await self.db_client.update_document_chunk_count(
                document_id=doc_id,
                chunk_count=len(chunks),
                strategy="overlap"
            )

            return True

        except Exception as e:
            logger.error(f"  ❌ 移行エラー: {e}")
            import traceback
            traceback.print_exc()
            return False


async def main():
    """メイン処理"""
    migration = ChunkMigration()
    await migration.migrate_all_documents(batch_size=10, skip_existing=True)


if __name__ == "__main__":
    asyncio.run(main())
