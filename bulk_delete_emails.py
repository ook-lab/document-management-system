#!/usr/bin/env python
"""
メールIDのリストを使って一括削除

使用方法:
  # コマンドライン引数
  python bulk_delete_emails.py <email_id1> <email_id2> ...

  # ファイルから読み込み
  python bulk_delete_emails.py --file email_ids.txt

  # 標準入力から受け取る
  echo "email_id1\nemail_id2" | python bulk_delete_emails.py --stdin
"""
import sys
import os
from pathlib import Path

# プロジェクトのルートディレクトリをPythonパスに追加
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

import argparse
from typing import List
from loguru import logger
from dotenv import load_dotenv

from A_common.database.client import DatabaseClient
from A_common.connectors.google_drive import GoogleDriveConnector
from A_common.connectors.gmail_connector import GmailConnector

load_dotenv()


def delete_emails(email_ids: List[str], dry_run: bool = False) -> None:
    """
    メールIDのリストを使って一括削除

    Args:
        email_ids: メールIDのリスト（UUIDまたはmessage_id）
        dry_run: Trueの場合、実際には削除せずに処理内容を表示
    """
    if not email_ids:
        logger.error("メールIDが指定されていません")
        return

    logger.info("=" * 80)
    logger.info(f"メール一括削除開始（{len(email_ids)}件）")
    if dry_run:
        logger.warning("⚠️ DRY RUNモード: 実際には削除しません")
    logger.info("=" * 80)

    # クライアントの初期化
    try:
        db_client = DatabaseClient()
        drive_connector = GoogleDriveConnector()
        user_email = os.getenv('GMAIL_USER_EMAIL', 'ookubo.y@workspace-o.com')
        gmail_connector = GmailConnector(user_email)
        logger.info(f"✅ クライアント初期化完了 (Gmail: {user_email})")
    except Exception as e:
        logger.error(f"❌ 初期化エラー: {e}")
        return

    success_count = 0
    fail_count = 0

    for i, email_id in enumerate(email_ids, 1):
        logger.info("-" * 80)
        logger.info(f"[{i}/{len(email_ids)}] 処理中: {email_id}")

        try:
            # 1. データベースからメール情報を取得
            result = db_client.client.table('Rawdata_FILE_AND_MAIL').select(
                'id, title, source_id, metadata'
            ).eq('id', email_id).execute()

            if not result.data:
                logger.error(f"  ❌ メールが見つかりません: {email_id}")
                fail_count += 1
                continue

            email = result.data[0]
            title = email.get('title', '(タイトルなし)')
            source_id = email.get('source_id')
            metadata = email.get('metadata', {})

            # metadataをパース
            if isinstance(metadata, str):
                import json
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {}

            message_id = metadata.get('message_id')

            logger.info(f"  📧 タイトル: {title[:50]}")
            logger.info(f"  🔑 Message ID: {message_id or 'なし'}")
            logger.info(f"  📁 Drive ID: {source_id or 'なし'}")

            if dry_run:
                logger.info("  ⏭️ DRY RUN: スキップ")
                success_count += 1
                continue

            # 2. Gmailのメッセージをゴミ箱に移動
            if message_id:
                try:
                    gmail_connector.trash_message(message_id)
                    logger.info(f"  ✅ Gmailゴミ箱に移動")
                except Exception as e:
                    logger.error(f"  ⚠️ Gmailゴミ箱移動エラー: {e}")
            else:
                logger.warning(f"  ⚠️ message_idがないため、Gmail削除をスキップ")

            # 3. Google DriveからHTMLファイルを削除
            if source_id:
                try:
                    drive_connector.trash_file(source_id)
                    logger.info(f"  ✅ Google Driveゴミ箱に移動")
                except Exception as e:
                    logger.error(f"  ⚠️ Google Drive削除エラー: {e}")
            else:
                logger.warning(f"  ⚠️ source_idがないため、Drive削除をスキップ")

            # 4. データベースから削除
            if db_client.delete_document(email_id):
                logger.info(f"  ✅ データベースから削除")
                success_count += 1
            else:
                logger.error(f"  ❌ データベース削除失敗")
                fail_count += 1

        except Exception as e:
            logger.error(f"  ❌ エラー: {e}")
            fail_count += 1

    logger.info("=" * 80)
    logger.info(f"✅ 完了: 成功={success_count}, 失敗={fail_count}")
    logger.info("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="メールIDのリストを使って一括削除",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # コマンドライン引数でメールIDを指定
  python bulk_delete_emails.py abc123 def456 ghi789

  # ファイルから読み込み（1行に1つのメールID）
  python bulk_delete_emails.py --file email_ids.txt

  # 標準入力から受け取る
  echo -e "abc123\\ndef456" | python bulk_delete_emails.py --stdin

  # DRY RUNモード（実際には削除しない）
  python bulk_delete_emails.py --file email_ids.txt --dry-run
        """
    )

    parser.add_argument(
        'email_ids',
        nargs='*',
        help='削除するメールIDのリスト'
    )
    parser.add_argument(
        '--file', '-f',
        type=str,
        help='メールIDのリストを含むファイル（1行に1つのID）'
    )
    parser.add_argument(
        '--stdin',
        action='store_true',
        help='標準入力からメールIDを読み込む'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='実際には削除せず、処理内容のみ表示'
    )

    args = parser.parse_args()

    # メールIDを収集
    email_ids = []

    # コマンドライン引数から
    if args.email_ids:
        email_ids.extend(args.email_ids)

    # ファイルから
    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        email_ids.append(line)
            logger.info(f"✅ ファイルから{len(email_ids)}件のメールIDを読み込みました: {args.file}")
        except Exception as e:
            logger.error(f"❌ ファイル読み込みエラー: {e}")
            return

    # 標準入力から
    if args.stdin:
        try:
            for line in sys.stdin:
                line = line.strip()
                if line and not line.startswith('#'):
                    email_ids.append(line)
            logger.info(f"✅ 標準入力から{len(email_ids)}件のメールIDを読み込みました")
        except Exception as e:
            logger.error(f"❌ 標準入力読み込みエラー: {e}")
            return

    # 重複を除去
    email_ids = list(dict.fromkeys(email_ids))

    if not email_ids:
        logger.error("❌ メールIDが指定されていません")
        parser.print_help()
        return

    # 確認プロンプト（dry-runでない場合）
    if not args.dry_run:
        print(f"\n⚠️ {len(email_ids)}件のメールを削除します。よろしいですか？ (yes/no): ", end='')
        response = input().strip().lower()
        if response not in ['yes', 'y']:
            logger.info("キャンセルしました")
            return

    # 一括削除実行
    delete_emails(email_ids, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
