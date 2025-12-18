"""
チラシ処理パイプライン

flyer_documentsテーブルの processing_status='pending' のチラシを処理

処理フロー:
1. Pre-processing: 画像ファイルダウンロード
2. Stage B (Gemini Vision):
   - Step 1: OCR + レイアウト解析
   - Step 2: 商品情報の構造化抽出
3. Stage C (Haiku): 構造化データの最終整理
4. Stage A (Gemini): 要約生成
5. チャンク化・ベクトル化: search_indexに保存

使い方:
    # 全てのpendingチラシを処理（デフォルト10件）
    python process_queued_flyers.py

    # 処理件数を指定
    python process_queued_flyers.py --limit=50

    # 特定の店舗のみ処理
    python process_queued_flyers.py --store="フーディアム 武蔵小杉"

    # ドライラン（確認のみ）
    python process_queued_flyers.py --dry-run
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger
import hashlib

# プロジェクトルートをパスに追加
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

from A_common.database.client import DatabaseClient
from A_common.connectors.google_drive import GoogleDriveConnector
from C_ai_common.llm_client.llm_client import LLMClient
from E_stage_b_vision.flyer_vision_processor import FlyerVisionProcessor
from F_stage_c_extractor.extractor import StageCExtractor
from D_stage_a_classifier.classifier import StageAClassifier
from A_common.processing.metadata_chunker import MetadataChunker


class FlyerProcessor:
    """チラシ処理パイプライン"""

    def __init__(self, temp_dir: str = "./temp"):
        """
        Args:
            temp_dir: 一時ファイル保存ディレクトリ
        """
        self.db = DatabaseClient()
        self.drive = GoogleDriveConnector()
        self.llm_client = LLMClient()

        self.vision_processor = FlyerVisionProcessor(llm_client=self.llm_client)
        self.stagec_extractor = StageCExtractor(llm_client=self.llm_client)
        self.stagea_classifier = StageAClassifier(llm_client=self.llm_client)

        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        logger.info("FlyerProcessor初期化完了")

    def get_pending_flyers(
        self,
        limit: int = 10,
        store_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        処理待ちのチラシを取得

        Args:
            limit: 取得件数
            store_name: 店舗名（指定された場合のみ）

        Returns:
            チラシ情報のリスト
        """
        try:
            query = self.db.client.table('flyer_documents').select('*').eq(
                'processing_status', 'pending'
            )

            if store_name:
                query = query.eq('organization', store_name)

            result = query.limit(limit).execute()

            if result.data:
                logger.info(f"処理待ちチラシ: {len(result.data)}件")
                return result.data

            return []

        except Exception as e:
            logger.error(f"チラシ取得エラー: {e}")
            return []

    async def process_single_flyer(
        self,
        flyer_doc: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        1件のチラシを処理

        Args:
            flyer_doc: チラシドキュメント情報

        Returns:
            処理結果
        """
        flyer_doc_id = flyer_doc['id']
        file_name = flyer_doc.get('file_name', '不明')
        source_id = flyer_doc.get('source_id')  # Google Drive ID
        organization = flyer_doc.get('organization', '不明')

        logger.info(f"\n{'='*80}")
        logger.info(f"チラシ処理開始: {file_name}")
        logger.info(f"  店舗: {organization}")
        logger.info(f"  ID: {flyer_doc_id}")
        logger.info(f"{'='*80}")

        result = {
            'flyer_doc_id': flyer_doc_id,
            'file_name': file_name,
            'success': False,
            'products_count': 0,
            'chunks_count': 0,
            'error': None
        }

        local_path = None

        try:
            # ステータスを 'processing' に更新
            self._update_status(flyer_doc_id, 'processing')

            # ============================================
            # Pre-processing: ファイルダウンロード
            # ============================================
            logger.info("[Pre-processing] 画像ダウンロード中...")
            local_path = self.drive.download_file(source_id, file_name, self.temp_dir)

            if not local_path or not Path(local_path).exists():
                raise Exception("画像ダウンロード失敗")

            logger.info(f"  ダウンロード完了: {local_path}")

            # ============================================
            # Stage B: Gemini Vision（2段階処理）
            # ============================================
            logger.info("[Stage B] Gemini Vision処理開始...")

            flyer_metadata = {
                'organization': organization,
                'flyer_title': flyer_doc.get('flyer_title'),
                'flyer_period': flyer_doc.get('flyer_period'),
                'page_number': flyer_doc.get('page_number')
            }

            vision_result = await self.vision_processor.process_flyer_image(
                image_path=Path(local_path),
                flyer_metadata=flyer_metadata
            )

            if not vision_result.get('success'):
                raise Exception(f"Vision処理失敗: {vision_result.get('error')}")

            step1_result = vision_result['step1_result']
            step2_result = vision_result['step2_result']

            full_text = step1_result.get('full_text', '')
            products = step2_result.get('products', [])

            logger.info(f"[Stage B完了] テキスト: {len(full_text)}文字, 商品: {len(products)}件")

            # ============================================
            # Stage C: Haiku構造化
            # ============================================
            logger.info("[Stage C] Haiku構造化開始...")

            stagec_result = self.stagec_extractor.extract_metadata(
                file_name=file_name,
                stage1_result={
                    'doc_type': 'physical shop',
                    'workspace': 'shopping'
                },
                workspace='shopping',
                attachment_text=full_text
            )

            document_date = stagec_result.get('document_date')
            tags = stagec_result.get('tags', [])
            stagec_metadata = stagec_result.get('metadata', {})

            logger.info(f"[Stage C完了] metadata_fields={len(stagec_metadata)}")

            # ============================================
            # 商品情報をflyer_productsテーブルに保存
            # ============================================
            logger.info("[商品保存] flyer_productsテーブルに保存中...")

            saved_products = await self._save_products(
                flyer_doc_id=flyer_doc_id,
                products=products,
                page_number=flyer_doc.get('page_number', 1)
            )

            result['products_count'] = saved_products
            logger.info(f"  保存完了: {saved_products}件")

            # ============================================
            # Stage A: Gemini要約
            # ============================================
            logger.info("[Stage A] Gemini要約開始...")

            summary = ''
            try:
                stageA_result = await self.stagea_classifier.classify(
                    file_path=Path(local_path),
                    doc_types_yaml="",  # チラシは分類不要
                    mime_type="image/jpeg",
                    text_content=full_text,
                    stagec_result=stagec_result
                )

                summary = stageA_result.get('summary', '')
                logger.info(f"[Stage A完了] summary={summary[:50] if summary else ''}...")

            except Exception as e:
                logger.error(f"[Stage A] エラー: {e}")
                summary = stagec_result.get('summary', '')

            # ============================================
            # flyer_documentsテーブルを更新
            # ============================================
            logger.info("[更新] flyer_documentsテーブルを更新中...")

            update_data = {
                'attachment_text': full_text,
                'summary': summary,
                'metadata': {
                    **stagec_metadata,
                    'step1_ocr': step1_result,
                    'extraction_notes': step2_result.get('extraction_notes')
                },
                'tags': tags,
                'document_date': document_date,
                'processing_status': 'completed',
                'processing_stage': 'products_extracted',
                'stageb_vision_model': 'gemini-2.0-flash-exp',
                'stagec_extractor_model': 'claude-haiku-4-5-20251001',
                'stagea_classifier_model': 'gemini-2.5-flash'
            }

            self.db.client.table('flyer_documents').update(update_data).eq(
                'id', flyer_doc_id
            ).execute()

            # ============================================
            # チャンク化・ベクトル化
            # ============================================
            logger.info("[チャンク化] search_indexに保存中...")

            # 既存チャンク削除
            try:
                delete_result = self.db.client.table('search_index').delete().eq(
                    'document_id', flyer_doc_id
                ).execute()
                deleted_count = len(delete_result.data) if delete_result.data else 0
                logger.info(f"  既存チャンク削除: {deleted_count}個")
            except Exception as e:
                logger.warning(f"  既存チャンク削除エラー（継続）: {e}")

            # メタデータチャンク生成
            metadata_chunker = MetadataChunker()

            document_data = {
                'file_name': file_name,
                'summary': summary,
                'document_date': document_date,
                'tags': tags,
                'doc_type': 'physical shop',
                'display_subject': flyer_doc.get('flyer_title'),
                'display_sender': organization,
                'display_sent_at': flyer_doc.get('created_at'),
                'persons': stagec_metadata.get('persons', []),
                'organizations': [organization],
                'attachment_text': full_text
            }

            metadata_chunks = metadata_chunker.create_metadata_chunks(document_data)

            current_chunk_index = 0
            for meta_chunk in metadata_chunks:
                meta_text = meta_chunk.get('chunk_text', '')
                meta_type = meta_chunk.get('chunk_type', 'metadata')
                meta_weight = meta_chunk.get('search_weight', 1.0)

                if not meta_text:
                    continue

                # Embedding生成
                meta_embedding = self.llm_client.generate_embedding(meta_text)

                # search_indexに保存
                meta_doc = {
                    'document_id': flyer_doc_id,
                    'chunk_index': current_chunk_index,
                    'chunk_content': meta_text,
                    'chunk_size': len(meta_text),
                    'chunk_type': meta_type,
                    'embedding': meta_embedding,
                    'search_weight': meta_weight
                }

                try:
                    await self.db.insert_document('search_index', meta_doc)
                    current_chunk_index += 1
                except Exception as e:
                    logger.error(f"  チャンク保存エラー: {e}")

            result['chunks_count'] = current_chunk_index
            logger.info(f"  チャンク保存完了: {current_chunk_index}個")

            # チャンク数を更新
            self.db.client.table('flyer_documents').update({
                'chunk_count': current_chunk_index
            }).eq('id', flyer_doc_id).execute()

            result['success'] = True
            logger.success(f"✅ チラシ処理完了: {file_name}")
            logger.info(f"  商品: {saved_products}件, チャンク: {current_chunk_index}個")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ チラシ処理エラー: {error_msg}", exc_info=True)

            self._update_status(
                flyer_doc_id,
                'failed',
                error=error_msg
            )
            result['error'] = error_msg

        finally:
            # 一時ファイル削除
            if local_path and Path(local_path).exists():
                Path(local_path).unlink()
                logger.debug(f"一時ファイル削除: {local_path}")

        return result

    async def _save_products(
        self,
        flyer_doc_id: str,
        products: List[Dict[str, Any]],
        page_number: int
    ) -> int:
        """
        商品情報をflyer_productsテーブルに保存

        Args:
            flyer_doc_id: チラシドキュメントID
            products: 商品リスト
            page_number: ページ番号

        Returns:
            保存成功件数
        """
        success_count = 0

        for product in products:
            try:
                # 商品名の正規化（検索用）
                product_name = product.get('product_name', '')
                product_name_normalized = product_name.lower().strip()

                product_data = {
                    'flyer_document_id': flyer_doc_id,
                    'product_name': product_name,
                    'product_name_normalized': product_name_normalized,
                    'price': product.get('price'),
                    'original_price': product.get('original_price'),
                    'discount_rate': product.get('discount_rate'),
                    'price_unit': product.get('price_unit', '円'),
                    'price_text': product.get('price_text'),
                    'category': product.get('category', 'その他'),
                    'subcategory': product.get('subcategory'),
                    'brand': product.get('brand'),
                    'quantity': product.get('quantity'),
                    'origin': product.get('origin'),
                    'is_special_offer': product.get('is_special_offer', False),
                    'offer_type': product.get('offer_type'),
                    'page_number': page_number,
                    'extracted_text': product.get('extracted_text'),
                    'confidence': product.get('confidence', 0.5),
                    'metadata': {
                        'extraction_date': datetime.now().isoformat(),
                        'extraction_model': 'gemini-2.0-flash-exp'
                    }
                }

                result = await self.db.insert_document('flyer_products', product_data)
                if result:
                    success_count += 1

            except Exception as e:
                logger.error(f"商品保存エラー: {e}")
                logger.debug(f"商品データ: {product}")

        return success_count

    def _update_status(
        self,
        flyer_doc_id: str,
        status: str,
        error: str = None
    ):
        """
        チラシの処理ステータスを更新

        Args:
            flyer_doc_id: チラシドキュメントID
            status: ステータス（processing, completed, failed）
            error: エラーメッセージ
        """
        try:
            update_data = {
                'processing_status': status,
                'updated_at': datetime.now().isoformat()
            }

            if error:
                update_data['processing_error'] = error

            self.db.client.table('flyer_documents').update(update_data).eq(
                'id', flyer_doc_id
            ).execute()

        except Exception as e:
            logger.error(f"ステータス更新エラー: {e}")

    async def process_pending_flyers(
        self,
        limit: int = 10,
        store_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        処理待ちのチラシを一括処理

        Args:
            limit: 処理件数
            store_name: 店舗名（指定された場合のみ）

        Returns:
            処理結果のサマリー
        """
        logger.info("=" * 80)
        logger.info("チラシ処理パイプライン開始")
        logger.info("=" * 80)

        # 処理待ちチラシを取得
        pending_flyers = self.get_pending_flyers(limit, store_name)

        if not pending_flyers:
            logger.info("処理待ちのチラシはありません")
            return {'total': 0, 'success': 0, 'failed': 0}

        logger.info(f"処理対象: {len(pending_flyers)}件")

        results = []
        for i, flyer in enumerate(pending_flyers, 1):
            logger.info(f"\n[{i}/{len(pending_flyers)}] 処理中...")
            result = await self.process_single_flyer(flyer)
            results.append(result)

        # サマリー
        success_count = sum(1 for r in results if r['success'])
        failed_count = len(results) - success_count
        total_products = sum(r.get('products_count', 0) for r in results)
        total_chunks = sum(r.get('chunks_count', 0) for r in results)

        logger.info("\n" + "=" * 80)
        logger.info("処理完了")
        logger.info(f"  成功: {success_count}/{len(results)}")
        logger.info(f"  失敗: {failed_count}/{len(results)}")
        logger.info(f"  抽出商品数: {total_products}件")
        logger.info(f"  生成チャンク数: {total_chunks}個")
        logger.info("=" * 80)

        return {
            'total': len(results),
            'success': success_count,
            'failed': failed_count,
            'total_products': total_products,
            'total_chunks': total_chunks,
            'results': results
        }


async def main():
    """メインエントリーポイント"""
    # コマンドライン引数のパース
    dry_run = '--dry-run' in sys.argv
    limit = 10
    store_name = None

    for arg in sys.argv:
        if arg.startswith('--limit='):
            try:
                limit = int(arg.split('=')[1])
            except:
                pass
        elif arg.startswith('--store='):
            store_name = arg.split('=')[1]

    processor = FlyerProcessor()

    if dry_run:
        logger.info("🔍 DRY RUN モード: 実際の処理は行いません")
        pending = processor.get_pending_flyers(limit, store_name)
        logger.info(f"処理対象: {len(pending)}件")
        for flyer in pending:
            logger.info(f"  - {flyer.get('organization')}: {flyer.get('file_name')}")
        return

    result = await processor.process_pending_flyers(limit, store_name)

    # 結果を表示
    print("\n" + "=" * 80)
    print("🛒 チラシ処理結果")
    print("=" * 80)
    print(f"処理件数: {result['total']}")
    print(f"成功: {result['success']}")
    print(f"失敗: {result['failed']}")
    print(f"抽出商品数: {result['total_products']}")
    print(f"生成チャンク数: {result['total_chunks']}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
