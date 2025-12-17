"""
Google Drive 監視・操作モジュール

- Inboxフォルダから未処理画像を取得
- ファイルのダウンロード
- 処理後のファイル移動（Archive / Error）
"""

from pathlib import Path
from typing import List, Dict
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

from loguru import logger
from .config import (
    GOOGLE_DRIVE_CREDENTIALS,
    ARCHIVE_FOLDER_ID,
    ERROR_FOLDER_ID,
    TEMP_DIR
)


class DriveMonitor:
    """Google Drive 操作クラス"""

    def __init__(self):
        self.service = self._authenticate()

    def _authenticate(self):
        """Google Drive API 認証"""
        credentials = service_account.Credentials.from_service_account_file(
            GOOGLE_DRIVE_CREDENTIALS,
            scopes=["https://www.googleapis.com/auth/drive"]
        )
        return build("drive", "v3", credentials=credentials)

    def list_files(self, folder_id: str) -> List[Dict]:
        """
        指定フォルダ内の未処理JPGファイルを取得（共有ドライブ対応）

        Args:
            folder_id: Google DriveフォルダID

        Returns:
            List[Dict]: ファイル情報のリスト
                [{"id": "...", "name": "20241027_001.jpg", ...}, ...]
        """
        query = (
            f"'{folder_id}' in parents "
            "and (mimeType contains 'image/jpeg' or mimeType contains 'image/jpg' or mimeType contains 'image/png') "
            "and trashed = false"
        )

        try:
            results = self.service.files().list(
                q=query,
                fields="files(id, name, createdTime, modifiedTime, parents)",
                orderBy="createdTime",
                supportsAllDrives=True,  # 共有ドライブ対応
                includeItemsFromAllDrives=True  # 共有ドライブのアイテムを含める
            ).execute()

            files = results.get("files", [])
            logger.info(f"Found {len(files)} files in folder {folder_id}")
            return files

        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return []

    def download_file(self, file_id: str, file_name: str) -> Path:
        """
        ファイルをダウンロード（共有ドライブ対応）

        Args:
            file_id: Google Drive のファイルID
            file_name: ファイル名

        Returns:
            Path: ダウンロードしたファイルのパス
        """
        local_path = TEMP_DIR / file_name

        try:
            request = self.service.files().get_media(
                fileId=file_id,
                supportsAllDrives=True  # 共有ドライブ対応
            )
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()

            # ファイルに書き出し
            with open(local_path, "wb") as f:
                f.write(fh.getvalue())

            logger.info(f"Downloaded: {file_name} → {local_path}")
            return local_path

        except Exception as e:
            logger.error(f"Failed to download {file_name}: {e}")
            raise

    def move_to_archive(self, file_id: str, file_name: str, source_parents: List[str] = None):
        """
        ファイルをArchiveフォルダに移動

        Args:
            file_id: Google Drive のファイルID
            file_name: ファイル名
            source_parents: 元の親フォルダIDリスト（Noneの場合は取得する）
        """
        # YYYY-MM サブフォルダを作成
        month_folder = self._get_or_create_month_folder()

        try:
            # 元の親フォルダを取得
            if source_parents is None:
                file_info = self.service.files().get(
                    fileId=file_id,
                    fields="parents",
                    supportsAllDrives=True
                ).execute()
                source_parents = file_info.get("parents", [])

            # 元のフォルダから削除 & Archiveに追加
            self.service.files().update(
                fileId=file_id,
                addParents=month_folder,
                removeParents=",".join(source_parents) if source_parents else None,
                fields="id, parents",
                supportsAllDrives=True
            ).execute()

            logger.info(f"Moved to Archive: {file_name}")

        except Exception as e:
            logger.error(f"Failed to move {file_name} to Archive: {e}")
            raise

    def move_to_error(self, file_id: str, file_name: str, source_parents: List[str] = None):
        """
        ファイルをErrorフォルダに移動

        Args:
            file_id: Google Drive のファイルID
            file_name: ファイル名
            source_parents: 元の親フォルダIDリスト（Noneの場合は取得する）
        """
        try:
            # 元の親フォルダを取得
            if source_parents is None:
                file_info = self.service.files().get(
                    fileId=file_id,
                    fields="parents",
                    supportsAllDrives=True
                ).execute()
                source_parents = file_info.get("parents", [])

            # 元のフォルダから削除 & Errorに追加
            self.service.files().update(
                fileId=file_id,
                addParents=ERROR_FOLDER_ID,
                removeParents=",".join(source_parents) if source_parents else None,
                fields="id, parents",
                supportsAllDrives=True
            ).execute()

            logger.info(f"Moved to Error: {file_name}")

        except Exception as e:
            logger.error(f"Failed to move {file_name} to Error: {e}")
            raise

    def _get_or_create_month_folder(self) -> str:
        """
        Archive配下にYYYY-MM形式のフォルダを取得/作成

        Returns:
            str: フォルダID
        """
        current_month = datetime.now().strftime("%Y-%m")

        # 既存フォルダを検索
        query = (
            f"'{ARCHIVE_FOLDER_ID}' in parents "
            f"and name = '{current_month}' "
            "and mimeType = 'application/vnd.google-apps.folder' "
            "and trashed = false"
        )

        results = self.service.files().list(
            q=query,
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()

        folders = results.get("files", [])

        if folders:
            return folders[0]["id"]

        # 存在しなければ作成
        folder_metadata = {
            "name": current_month,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [ARCHIVE_FOLDER_ID]
        }

        folder = self.service.files().create(
            body=folder_metadata,
            fields="id",
            supportsAllDrives=True
        ).execute()

        logger.info(f"Created month folder: {current_month}")
        return folder["id"]


# ========================================
# テスト実行
# ========================================
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m K_kakeibo.drive_monitor <folder_id>")
        sys.exit(1)

    folder_id = sys.argv[1]
    monitor = DriveMonitor()
    files = monitor.list_files(folder_id)

    print(f"Found {len(files)} files:")
    for file in files:
        print(f"- {file['name']} (ID: {file['id']})")
