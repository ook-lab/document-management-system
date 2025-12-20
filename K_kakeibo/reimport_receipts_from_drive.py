"""
Google Drive から家計簿レシートを取得して統合パイプラインで処理

処理フロー:
1. Google Drive の Inbox フォルダ（Easy/Hard）から画像を取得
2. 統合パイプライン (Stage E-K) で処理
   - Stage F: 全テキスト抽出 (gemini-2.5-flash-lite)
   - Stage G: JSON構造化 (gemini-2.5-flash-lite)
   - Stage H: 税額按分・分類 (stage_h_kakeibo.py + Python)
3. 3層DB (60_rd_receipts → 60_rd_transactions → 60_rd_standardized_items) に保存
"""

import asyncio
from pathlib import Path
from typing import List, Dict
from loguru import logger

from A_common.connectors.google_drive import GoogleDriveConnector
from G_unified_pipeline import UnifiedDocumentPipeline
from K_kakeibo.config import INBOX_EASY_FOLDER_ID, INBOX_HARD_FOLDER_ID, TEMP_DIR


class ReceiptReimporter:
    """Google Drive からレシートを再取り込み"""

    def __init__(self):
        self.drive = GoogleDriveConnector()
        self.pipeline = UnifiedDocumentPipeline()
        self.temp_dir = Path(TEMP_DIR)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def list_receipt_images(self, folder_id: str) -> List[Dict]:
        """
        Google Drive フォルダから画像ファイル一覧を取得（共有ドライブ対応）

        Args:
            folder_id: Google Drive フォルダID

        Returns:
            ファイル情報のリスト
        """
        try:
            # まず全ファイルを取得してデバッグ（共有ドライブ対応）
            query_all = f"'{folder_id}' in parents and trashed=false"
            all_files = self.drive.service.files().list(
                q=query_all,
                fields="files(id, name, mimeType, createdTime, modifiedTime)",
                orderBy="createdTime desc",
                supportsAllDrives=True,  # 共有ドライブ対応
                includeItemsFromAllDrives=True,  # 共有ドライブのアイテムを含む
                corpora='allDrives'  # すべてのドライブから検索
            ).execute()

            all_file_list = all_files.get('files', [])
            logger.info(f"📋 フォルダ内の全ファイル: {len(all_file_list)}件")
            for f in all_file_list:
                logger.info(f"  - {f['name']} (MIMEタイプ: {f['mimeType']})")

            # 画像ファイルのみ取得（JPG, JPEG, PNG, HEIC）
            query = f"'{folder_id}' in parents and (mimeType='image/jpeg' or mimeType='image/png' or mimeType='image/heic') and trashed=false"
            files = self.drive.service.files().list(
                q=query,
                fields="files(id, name, mimeType, createdTime, modifiedTime)",
                orderBy="createdTime desc",
                supportsAllDrives=True,  # 共有ドライブ対応
                includeItemsFromAllDrives=True,  # 共有ドライブのアイテムを含む
                corpora='allDrives'  # すべてのドライブから検索
            ).execute()

            return files.get('files', [])

        except Exception as e:
            logger.error(f"ファイル一覧取得エラー: {e}")
            return []

    async def process_receipt_image(
        self,
        file_id: str,
        file_name: str,
        mime_type: str,
        source_folder: str
    ) -> Dict:
        """
        レシート画像を処理

        Args:
            file_id: Google Drive ファイルID
            file_name: ファイル名
            mime_type: MIMEタイプ
            source_folder: ソースフォルダ名（"inbox_easy" or "inbox_hard")

        Returns:
            処理結果
        """
        local_path = None
        try:
            logger.info(f"\n{'='*80}")
            logger.info(f"📄 処理開始: {file_name}")
            logger.info(f"  ファイルID: {file_id}")
            logger.info(f"  ソース: {source_folder}")

            # ファイルをダウンロード
            local_path = self.drive.download_file(file_id, file_name, self.temp_dir)
            logger.info(f"  ダウンロード完了: {local_path}")

            # 統合パイプラインで処理（doc_type='kakeibo' が重要！）
            result = await self.pipeline.process_document(
                file_path=Path(local_path),
                file_name=file_name,
                doc_type='kakeibo',  # source_documents_routing.yaml の kakeibo ルートを使用
                workspace='household',
                mime_type=mime_type,
                source_id=file_id,
                existing_document_id=None,
                extra_metadata={'source_folder': source_folder}
            )

            if result.get('success'):
                logger.success(f"✅ 処理成功: {file_name}")
                logger.info(f"  receipt_id: {result.get('receipt_id')}")
                logger.info(f"  transaction_ids: {len(result.get('transaction_ids', []))}件")
                return {'success': True, 'file_name': file_name, 'result': result}
            else:
                error_msg = result.get('error', 'unknown error')
                logger.error(f"❌ 処理失敗: {file_name} - {error_msg}")
                return {'success': False, 'file_name': file_name, 'error': error_msg}

        except Exception as e:
            logger.error(f"❌ 処理エラー: {file_name} - {e}")
            logger.exception(e)
            return {'success': False, 'file_name': file_name, 'error': str(e)}

        finally:
            # 一時ファイルを削除
            if local_path and Path(local_path).exists():
                Path(local_path).unlink()
                logger.debug(f"一時ファイル削除: {local_path}")

    async def reimport_all_receipts(self, limit: int = 100):
        """
        すべてのレシートを再取り込み

        Args:
            limit: 処理する最大件数（各フォルダごと）
        """
        logger.info("\n" + "="*80)
        logger.info("Google Drive からレシート再取り込み開始")
        logger.info("="*80)

        stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'easy': 0,
            'hard': 0
        }

        # Inbox Easy から取得
        if INBOX_EASY_FOLDER_ID:
            logger.info(f"\n📂 Inbox Easy フォルダから取得中...")
            easy_files = self.list_receipt_images(INBOX_EASY_FOLDER_ID)
            logger.info(f"  → {len(easy_files)}件の画像ファイルを検出")

            for i, file_info in enumerate(easy_files[:limit]):
                stats['total'] += 1
                stats['easy'] += 1

                result = await self.process_receipt_image(
                    file_id=file_info['id'],
                    file_name=file_info['name'],
                    mime_type=file_info['mimeType'],
                    source_folder='inbox_easy'
                )

                if result['success']:
                    stats['success'] += 1
                else:
                    stats['failed'] += 1

                logger.info(f"\n進捗: {i+1}/{len(easy_files[:limit])} (Easy)")
        else:
            logger.warning("INBOX_EASY_FOLDER_ID が設定されていません")

        # Inbox Hard から取得
        if INBOX_HARD_FOLDER_ID:
            logger.info(f"\n📂 Inbox Hard フォルダから取得中...")
            hard_files = self.list_receipt_images(INBOX_HARD_FOLDER_ID)
            logger.info(f"  → {len(hard_files)}件の画像ファイルを検出")

            for i, file_info in enumerate(hard_files[:limit]):
                stats['total'] += 1
                stats['hard'] += 1

                result = await self.process_receipt_image(
                    file_id=file_info['id'],
                    file_name=file_info['name'],
                    mime_type=file_info['mimeType'],
                    source_folder='inbox_hard'
                )

                if result['success']:
                    stats['success'] += 1
                else:
                    stats['failed'] += 1

                logger.info(f"\n進捗: {i+1}/{len(hard_files[:limit])} (Hard)")
        else:
            logger.warning("INBOX_HARD_FOLDER_ID が設定されていません")

        # 最終結果
        logger.info("\n" + "="*80)
        logger.info("再取り込み完了")
        logger.info("="*80)
        logger.info(f"合計:   {stats['total']}件")
        logger.info(f"成功:   {stats['success']}件")
        logger.info(f"失敗:   {stats['failed']}件")
        logger.info(f"Easy:   {stats['easy']}件")
        logger.info(f"Hard:   {stats['hard']}件")
        logger.info("="*80)


async def main():
    """メイン処理"""
    import sys

    # --limit オプションの処理
    limit = 100
    for arg in sys.argv:
        if arg.startswith('--limit='):
            try:
                limit = int(arg.split('=')[1])
            except:
                pass

    reimporter = ReceiptReimporter()
    await reimporter.reimport_all_receipts(limit=limit)


if __name__ == "__main__":
    asyncio.run(main())
