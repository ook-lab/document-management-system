"""
家計簿自動化システム メイン処理

- Google Drive Inboxを監視
- 未処理画像をダウンロード
- Gemini OCRで処理
- 正規化してSupabaseに登録
- 処理済み画像をArchiveに移動
"""

import time
from pathlib import Path
from loguru import logger

from .config import POLL_INTERVAL, TEMP_DIR, validate_config, FOLDER_MODEL_MAP
from .drive_monitor import DriveMonitor
from .gemini_ocr import GeminiOCR
from .transaction_processor import TransactionProcessor


class KakeiboAutomation:
    """家計簿自動化メインクラス"""

    def __init__(self):
        # 設定検証
        validate_config()

        # モジュール初期化
        self.drive = DriveMonitor()
        self.ocr = GeminiOCR()
        self.processor = TransactionProcessor()

        logger.info("Kakeibo Automation initialized")

    def run_once(self):
        """1回の処理サイクル"""
        logger.info("Starting processing cycle...")

        total_processed = 0

        # 2つのInboxフォルダをそれぞれ処理
        for folder_key, folder_config in FOLDER_MODEL_MAP.items():
            folder_id = folder_config["folder_id"]
            model_name = folder_config["model"]
            description = folder_config["description"]

            logger.info(f"Checking {folder_key}: {description}")

            # フォルダから未処理ファイルを取得
            files = self.drive.list_files(folder_id)

            if not files:
                logger.info(f"  No files in {folder_key}")
                continue

            logger.info(f"  Found {len(files)} files in {folder_key}")

            for file in files:
                self._process_file(file, model_name, folder_key)
                total_processed += 1

        if total_processed == 0:
            logger.info("No files to process")
        else:
            logger.info(f"Processed {total_processed} files total")

    def run_forever(self):
        """定期実行ループ"""
        logger.info(f"Starting monitoring loop (interval: {POLL_INTERVAL}s)")

        while True:
            try:
                self.run_once()
            except Exception as e:
                logger.error(f"Error in processing cycle: {e}")

            # 次の実行まで待機
            time.sleep(POLL_INTERVAL)

    def _process_file(self, file: dict, model_name: str, folder_key: str):
        """
        1ファイルの処理

        Args:
            file: {"id": "...", "name": "...", ...}
            model_name: 使用するGeminiモデル名
            folder_key: フォルダキー（INBOX_EASY/INBOX_HARD）
        """
        file_id = file["id"]
        file_name = file["name"]

        logger.info(f"Processing: {file_name} (model: {model_name})")

        try:
            # 1. ダウンロード
            local_path = self.drive.download_file(file_id, file_name)

            # 2. OCR処理（モデル名を指定）
            ocr_result = self.ocr.process_receipt(local_path, model_name=model_name)

            # 3. エラーチェック
            if "error" in ocr_result:
                self._handle_error(file_id, file_name, ocr_result, local_path)
                return

            # 4. 正規化 & DB登録（モデル名も記録）
            process_result = self.processor.process(
                ocr_result,
                file_name,
                file_id,
                model_name=model_name,
                source_folder=folder_key
            )

            if "error" in process_result:
                self._handle_error(file_id, file_name, process_result, local_path)
                return

            # 5. 成功 → Archiveに移動
            self.drive.move_to_archive(file_id, file_name)
            logger.info(f"✅ Successfully processed: {file_name}")

        except Exception as e:
            logger.error(f"Failed to process {file_name}: {e}")
            self._handle_error(file_id, file_name, {"error": str(e)}, None)

        finally:
            # 一時ファイル削除
            self._cleanup_temp_file(file_name)

    def _handle_error(self, file_id: str, file_name: str, error_info: dict, local_path: Path = None):
        """
        エラー処理

        Args:
            file_id: Drive ファイルID
            file_name: ファイル名
            error_info: エラー情報
            local_path: ローカルパス（あれば）
        """
        error_type = error_info.get("error", "unknown")

        logger.warning(f"Error processing {file_name}: {error_type}")

        # エラーフォルダに移動
        self.drive.move_to_error(file_id, file_name)

        # 通知（将来的にメール通知など追加可能）
        logger.error(f"⚠️ File moved to error folder: {file_name} (reason: {error_type})")

    def _cleanup_temp_file(self, file_name: str):
        """一時ファイルを削除"""
        temp_file = TEMP_DIR / file_name
        if temp_file.exists():
            temp_file.unlink()
            logger.debug(f"Cleaned up temp file: {file_name}")


# ========================================
# エントリーポイント
# ========================================
def main():
    """メイン関数"""
    automation = KakeiboAutomation()

    import sys

    if "--once" in sys.argv:
        # 1回だけ実行（テスト用）
        automation.run_once()
    else:
        # 定期実行モード
        automation.run_forever()


if __name__ == "__main__":
    main()
