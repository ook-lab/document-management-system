"""
Google Drive コネクタ (サービスアカウント認証)

設計書: COMPLETE_IMPLEMENTATION_GUIDE_v3.md の 1.4節に基づき、Google Driveと通信する。
"""
import os
from typing import List, Dict, Any, Optional, Union
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload, MediaInMemoryUpload
from io import FileIO, BytesIO
from loguru import logger
from pathlib import Path

# 認証情報ファイルのパス (環境変数から取得)
CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
SCOPES = ['https://www.googleapis.com/auth/drive']

class GoogleDriveConnector:
    """Google Drive APIクライアント"""
    
    def __init__(self):
        self.service = self._authenticate()
        # logger.info("Google Driveコネクタ初期化完了")
    
    def _authenticate(self):
        """サービスアカウント認証の実行（環境変数を優先、Streamlit Secretsは補助）"""
        # 優先順位1: 環境変数 GOOGLE_APPLICATION_CREDENTIALS
        if CREDENTIALS_PATH and os.path.exists(CREDENTIALS_PATH):
            try:
                creds = service_account.Credentials.from_service_account_file(
                    CREDENTIALS_PATH, scopes=SCOPES
                )
                logger.info(f"環境変数から認証成功: {CREDENTIALS_PATH}")
                return build('drive', 'v3', credentials=creds)
            except Exception as e:
                logger.warning(f"環境変数からの認証失敗、Streamlit Secretsにフォールバック: {e}")

        # 優先順位2: Streamlit Secrets (デプロイ環境用)
        try:
            import streamlit as st
            if hasattr(st, 'secrets') and 'gcp_service_account' in st.secrets:
                creds_dict = dict(st.secrets["gcp_service_account"])
                creds = service_account.Credentials.from_service_account_info(
                    creds_dict, scopes=SCOPES
                )
                logger.info("Streamlit Secretsから認証成功")
                return build('drive', 'v3', credentials=creds)
        except ImportError:
            # Streamlitがインストールされていない場合はスキップ
            pass
        except Exception as e:
            logger.warning(f"Streamlit Secretsからの認証失敗: {e}")

        # どちらも失敗した場合
        raise FileNotFoundError(
            f"認証情報が見つかりません。以下のいずれかを設定してください:\n"
            f"1. 環境変数 GOOGLE_APPLICATION_CREDENTIALS (現在: {CREDENTIALS_PATH})\n"
            f"2. Streamlit Secrets の gcp_service_account"
        )

    def list_files_in_folder(self, folder_id: str, mime_type_filter: str = None) -> List[Dict[str, Any]]:
        """
        指定されたフォルダ内のファイルを一覧表示
        
        Args:
            folder_id: 親フォルダのID
            mime_type_filter: MIMEタイプによるフィルタリング（オプション）
            
        Returns:
            ファイルメタデータのリスト
        """
        # フォルダを除外するクエリを構築
        query = f"'{folder_id}' in parents and trashed=false"
        
        # デフォルトでフォルダを除外
        if mime_type_filter is None:
            query += " and mimeType != 'application/vnd.google-apps.folder'"
        else:
            query += f" and {mime_type_filter}"
        
        try:
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='nextPageToken, files(id, name, mimeType, size)',
            ).execute()
            
            return results.get('files', [])
        except Exception as e:
            print(f"Error listing files: {e}")
            return []

    def download_file(self, file_id: str, file_name: str, dest_dir: Union[str, Path]) -> Optional[str]:
        """
        Google Driveからファイルをダウンロードし、一時パスを返す

        Args:
            file_id: ファイルのID
            file_name: ファイル名
            dest_dir: 保存先ディレクトリ

        Returns:
            ダウンロードされたファイルへのローカルパス（失敗時はNone）
        """
        try:
            logger.info(f"ファイルダウンロード開始: {file_name} (ID: {file_id})")

            dest_path = Path(dest_dir) / file_name
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # DriveのMIMEタイプをチェックし、Google Docs形式の場合はエクスポート
            file_metadata = self.service.files().get(fileId=file_id, fields='mimeType').execute()
            mime_type = file_metadata['mimeType']
            logger.info(f"ファイルMIMEタイプ: {mime_type}")

            request = None
            if mime_type == 'application/vnd.google-apps.document':
                # Google Docs -> DOCXとしてエクスポート
                request = self.service.files().export(fileId=file_id, mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
                dest_path = dest_path.with_suffix('.docx')
            elif mime_type == 'application/vnd.google-apps.spreadsheet':
                # Google Sheets -> XLSXとしてエクスポート
                request = self.service.files().export(fileId=file_id, mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                dest_path = dest_path.with_suffix('.xlsx')
            elif mime_type == 'application/vnd.google-apps.presentation':
                # Google Slides -> PPTXとしてエクスポート
                request = self.service.files().export(fileId=file_id, mimeType='application/vnd.openxmlformats-officedocument.presentationml.presentation')
                dest_path = dest_path.with_suffix('.pptx')
            else:
                # 通常のファイル (PDF, DOCXなど) はダウンロード
                request = self.service.files().get_media(fileId=file_id)

            with open(dest_path, 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                    if status:
                        logger.debug(f"ダウンロード進捗: {int(status.progress() * 100)}%")

            logger.info(f"ファイルダウンロード完了: {dest_path} ({dest_path.stat().st_size} bytes)")
            return str(dest_path)

        except Exception as e:
            logger.error(f"ファイルダウンロードエラー ({file_name}): {e}", exc_info=True)
            return None

    def get_inbox_folder_id(self) -> Optional[str]:
        """
        環境変数からInBoxフォルダIDを取得

        Returns:
            InBoxフォルダID、設定されていない場合はNone
        """
        inbox_folder_id = os.getenv("INBOX_FOLDER_ID")
        if not inbox_folder_id:
            logger.warning("INBOX_FOLDER_ID が環境変数に設定されていません")
        return inbox_folder_id

    def get_archive_folder_id(self) -> Optional[str]:
        """
        環境変数からArchiveフォルダIDを取得

        Returns:
            ArchiveフォルダID、設定されていない場合はNone
        """
        archive_folder_id = os.getenv("ARCHIVE_FOLDER_ID")
        if not archive_folder_id:
            logger.warning("ARCHIVE_FOLDER_ID が環境変数に設定されていません")
        return archive_folder_id

    def list_inbox_files(
        self,
        folder_id: str,
        processed_file_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        InBoxフォルダ内の新規ファイルを取得

        Args:
            folder_id: InBoxフォルダのID
            processed_file_ids: 既に処理済みのファイルIDリスト

        Returns:
            未処理のファイルメタデータリスト
        """
        try:
            # フォルダ内の全ファイルを取得（PDFのみ）
            all_files = self.list_files_in_folder(
                folder_id,
                mime_type_filter="mimeType='application/pdf'"
            )

            # 未処理のファイルのみをフィルタリング
            new_files = [
                file for file in all_files
                if file['id'] not in processed_file_ids
            ]

            logger.info(f"InBox内の全ファイル数: {len(all_files)}, 新規ファイル数: {len(new_files)}")
            return new_files

        except Exception as e:
            logger.error(f"InBoxファイルリスト取得エラー: {e}")
            return []

    def move_file(self, file_id: str, new_folder_id: str) -> bool:
        """
        ファイルを別のフォルダに移動

        Args:
            file_id: 移動するファイルのID
            new_folder_id: 移動先フォルダのID

        Returns:
            成功した場合True、失敗した場合False
        """
        try:
            # 現在の親フォルダを取得
            file = self.service.files().get(
                fileId=file_id,
                fields='parents'
            ).execute()

            previous_parents = ",".join(file.get('parents', []))

            # ファイルを新しいフォルダに移動（古い親を削除し、新しい親を追加）
            self.service.files().update(
                fileId=file_id,
                addParents=new_folder_id,
                removeParents=previous_parents,
                fields='id, parents'
            ).execute()

            logger.info(f"ファイル移動成功: {file_id} -> {new_folder_id}")
            return True

        except Exception as e:
            logger.error(f"ファイル移動エラー ({file_id}): {e}")
            return False

    def upload_file(
        self,
        file_content: Union[bytes, str],
        file_name: str,
        mime_type: str,
        folder_id: Optional[str] = None
    ) -> Optional[str]:
        """
        ファイルをGoogle Driveにアップロード（共有ドライブ対応）

        Args:
            file_content: ファイルの内容（バイトまたは文字列）
            file_name: ファイル名
            mime_type: MIMEタイプ（例: 'text/html', 'application/pdf'）
            folder_id: 保存先フォルダID（Noneの場合はルート）

        Returns:
            アップロードされたファイルのID、失敗時はNone
        """
        try:
            # ファイルメタデータ
            file_metadata = {'name': file_name}
            if folder_id:
                file_metadata['parents'] = [folder_id]

            # 文字列の場合はバイトに変換
            if isinstance(file_content, str):
                file_content = file_content.encode('utf-8')

            # メモリ上のデータからアップロード
            media = MediaInMemoryUpload(
                file_content,
                mimetype=mime_type,
                resumable=True
            )

            # 共有ドライブ対応: supportsAllDrives=True を追加
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink',
                supportsAllDrives=True
            ).execute()

            logger.info(f"ファイルアップロード成功: {file_name} (ID: {file['id']})")
            return file['id']

        except Exception as e:
            logger.error(f"ファイルアップロードエラー ({file_name}): {e}")
            return None

    def upload_file_from_path(
        self,
        file_path: Union[str, Path],
        folder_id: Optional[str] = None,
        mime_type: Optional[str] = None
    ) -> Optional[str]:
        """
        ローカルファイルをGoogle Driveにアップロード（共有ドライブ対応）

        Args:
            file_path: ローカルファイルのパス
            folder_id: 保存先フォルダID（Noneの場合はルート）
            mime_type: MIMEタイプ（Noneの場合は自動判定）

        Returns:
            アップロードされたファイルのID、失敗時はNone
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                logger.error(f"ファイルが見つかりません: {file_path}")
                return None

            # ファイルメタデータ
            file_metadata = {'name': file_path.name}
            if folder_id:
                file_metadata['parents'] = [folder_id]

            # MIMEタイプの自動判定
            if mime_type is None:
                import mimetypes
                mime_type, _ = mimetypes.guess_type(str(file_path))
                mime_type = mime_type or 'application/octet-stream'

            # ファイルからアップロード
            media = MediaFileUpload(
                str(file_path),
                mimetype=mime_type,
                resumable=True
            )

            # 共有ドライブ対応: supportsAllDrives=True を追加
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink',
                supportsAllDrives=True
            ).execute()

            logger.info(f"ファイルアップロード成功: {file_path.name} (ID: {file['id']})")
            return file['id']

        except Exception as e:
            logger.error(f"ファイルアップロードエラー ({file_path}): {e}")
            return None