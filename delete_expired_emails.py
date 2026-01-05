#!/usr/bin/env python
"""
期限切れメールを自動検出して一括削除（ベクトル検索版）

使用方法:
  # DRY RUNモード（削除せずに表示のみ）
  python delete_expired_emails.py --dry-run

  # 実際に削除
  python delete_expired_emails.py

  # 特定の猶予日数
  python delete_expired_emails.py --grace-days 7
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import json
import re

# プロジェクトのルートディレクトリをPythonパスに追加
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

import argparse
from typing import List, Dict, Any, Optional
from loguru import logger
from dotenv import load_dotenv

from A_common.database.client import DatabaseClient
from A_common.connectors.google_drive import GoogleDriveConnector
from A_common.connectors.gmail_connector import GmailConnector
from C_ai_common.llm_client.llm_client import LLMClient

load_dotenv()


# 期限関連のキーワード（ベクトル検索用）
EXPIRATION_KEYWORDS = [
    "セール 終了",
    "配送期限",
    "注文期限",
    "有効期限",
    "締切日",
    "まもなく終了",
    "本日最終日",
    "本日限定",
    "今日まで",
    "キャンペーン 終了"
]


def extract_dates_from_text(text: str, title: str = "") -> List[datetime]:
    """
    テキストから日付を抽出

    Args:
        text: 本文テキスト
        title: タイトル

    Returns:
        抽出された日付のリスト
    """
    dates = []
    now = datetime.now()

    combined_text = f"{title} {text}"

    # パターン1: YYYY年MM月DD日
    pattern1 = r'(\d{4})年(\d{1,2})月(\d{1,2})日'
    for match in re.finditer(pattern1, combined_text):
        try:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            date = datetime(year, month, day, 23, 59, 59)
            dates.append(date)
        except ValueError:
            continue

    # パターン2: MM月DD日（年なし）
    pattern2 = r'(\d{1,2})月(\d{1,2})日'
    for match in re.finditer(pattern2, combined_text):
        try:
            month = int(match.group(1))
            day = int(match.group(2))
            year = now.year
            date = datetime(year, month, day, 23, 59, 59)
            # 過去の日付の場合は翌年と判定
            if date < now:
                date = datetime(year + 1, month, day, 23, 59, 59)
            dates.append(date)
        except ValueError:
            continue

    # パターン3: MM/DD
    pattern3 = r'(\d{1,2})/(\d{1,2})'
    for match in re.finditer(pattern3, combined_text):
        try:
            month = int(match.group(1))
            day = int(match.group(2))
            year = now.year
            date = datetime(year, month, day, 23, 59, 59)
            # 過去の日付の場合は翌年と判定
            if date < now:
                date = datetime(year + 1, month, day, 23, 59, 59)
            dates.append(date)
        except ValueError:
            continue

    # パターン4: YYYY-MM-DD
    pattern4 = r'(\d{4})-(\d{1,2})-(\d{1,2})'
    for match in re.finditer(pattern4, combined_text):
        try:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            date = datetime(year, month, day, 23, 59, 59)
            dates.append(date)
        except ValueError:
            continue

    return dates


def find_expired_emails_with_search(grace_days: int = 0) -> List[Dict[str, Any]]:
    """
    ベクトル検索を使って期限切れメールを検出

    Args:
        grace_days: 猶予日数

    Returns:
        期限切れメールのリスト
    """
    logger.info("=" * 80)
    logger.info("期限切れメール検出を開始（ベクトル検索版）")
    logger.info(f"猶予日数: {grace_days}日")
    logger.info("=" * 80)

    # クライアント初期化
    db_client = DatabaseClient()
    llm_client = LLMClient()

    expired_emails = []
    seen_ids = set()  # 重複排除用
    now = datetime.now()

    # 各キーワードで検索
    for keyword in EXPIRATION_KEYWORDS:
        logger.info(f"検索キーワード: '{keyword}'")

        try:
            # Embeddingを生成
            embedding = llm_client.generate_embedding(keyword)

            # ベクトル検索を実行（DM-mail = Gmailメール）
            results = db_client.search_documents_sync(
                keyword,
                embedding,
                limit=50,
                doc_types=['DM-mail']  # DM-mail = Gmailメール
            )

            logger.info(f"  → {len(results)}件の関連メールを発見")

            # 各検索結果から日付を抽出
            for doc in results:
                doc_id = doc.get('id')

                # 既に処理済みならスキップ
                if doc_id in seen_ids:
                    continue

                title = doc.get('file_name', '') or doc.get('title', '')

                # all_chunksから本文を取得
                content = ""
                all_chunks = doc.get('all_chunks', [])
                if all_chunks:
                    chunk_contents = [chunk.get('chunk_content', '') for chunk in all_chunks]
                    content = '\n'.join(chunk_contents)
                else:
                    # フォールバック
                    content = doc.get('content', '') or doc.get('summary', '') or doc.get('attachment_text', '')

                # 日付を抽出
                dates = extract_dates_from_text(content, title)

                if not dates:
                    continue

                # 最も早い日付を期限として使用
                expiration_date = min(dates)
                grace = timedelta(days=grace_days)

                # 期限切れチェック
                if (expiration_date + grace) < now:
                    doc['expiration_date'] = expiration_date
                    doc['search_keyword'] = keyword
                    expired_emails.append(doc)
                    seen_ids.add(doc_id)

                    logger.info(f"  ✓ 期限切れ: {title[:50]} (期限: {expiration_date.strftime('%Y-%m-%d')})")

        except Exception as e:
            logger.error(f"  ✗ 検索エラー: {e}")
            continue

    # 期限日順にソート
    expired_emails.sort(key=lambda x: x.get('expiration_date', datetime.max))

    logger.info("=" * 80)
    logger.info(f"期限切れメール: {len(expired_emails)}件")
    logger.info("=" * 80)

    return expired_emails


def delete_expired_emails(grace_days: int = 0, dry_run: bool = False) -> None:
    """
    期限切れメールを削除

    Args:
        grace_days: 猶予日数
        dry_run: Trueの場合、実際には削除せずに表示のみ
    """
    # 期限切れメールを検出
    expired_emails = find_expired_emails_with_search(grace_days)

    if not expired_emails:
        logger.info("期限切れメールはありません")
        return

    if dry_run:
        logger.warning("=" * 80)
        logger.warning("⚠️ DRY RUNモード: 実際には削除しません")
        logger.warning("=" * 80)
        for email in expired_emails:
            title = email.get('file_name', '') or email.get('title', '')
            expiration = email.get('expiration_date')
            keyword = email.get('search_keyword', '')
            exp_str = expiration.strftime('%Y-%m-%d') if expiration else '不明'
            logger.info(f"  - {title[:60]} (期限: {exp_str}, キーワード: {keyword})")
        logger.info("=" * 80)
        logger.info(f"合計: {len(expired_emails)}件")
        logger.info("実際に削除するには、--dry-run フラグを外して実行してください")
        return

    # 確認プロンプト
    print(f"\n⚠️ {len(expired_emails)}件の期限切れメールを削除します。よろしいですか？ (yes/no): ", end='')
    response = input().strip().lower()
    if response not in ['yes', 'y']:
        logger.info("キャンセルしました")
        return

    # クライアントの初期化
    try:
        db_client = DatabaseClient()
        drive_connector = GoogleDriveConnector()
        user_email = os.getenv('GMAIL_USER_EMAIL', 'ookubo.y@workspace-o.com')
        gmail_connector = GmailConnector(user_email)
    except Exception as e:
        logger.error(f"❌ 初期化エラー: {e}")
        return

    success_count = 0
    fail_count = 0

    # 削除実行
    for i, email in enumerate(expired_emails, 1):
        email_id = email['id']
        title = email.get('file_name', '') or email.get('title', '') or '(タイトルなし)'
        source_id = email.get('source_id')
        metadata = email.get('metadata', {})

        logger.info("-" * 80)
        logger.info(f"[{i}/{len(expired_emails)}] 削除中: {title[:50]}")

        # metadataをパース
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except:
                metadata = {}

        try:
            # 1. Gmailのメッセージをゴミ箱に移動
            message_id = metadata.get('message_id')
            if message_id:
                try:
                    gmail_connector.trash_message(message_id)
                    logger.info(f"  ✅ Gmailゴミ箱に移動")
                except Exception as e:
                    logger.error(f"  ⚠️ Gmailゴミ箱移動エラー: {e}")
            else:
                logger.warning(f"  ⚠️ message_idがないため、Gmail削除をスキップ")

            # 2. Google DriveからHTMLファイルを削除
            if source_id:
                try:
                    drive_connector.trash_file(source_id)
                    logger.info(f"  ✅ Google Driveゴミ箱に移動")
                except Exception as e:
                    logger.error(f"  ⚠️ Google Drive削除エラー: {e}")

            # 3. データベースから削除
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
        description="期限切れメールを自動検出して一括削除（ベクトル検索版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # DRY RUNモード（削除せずに表示のみ）
  python delete_expired_emails.py --dry-run

  # 実際に削除
  python delete_expired_emails.py

  # 7日間の猶予期間を設定
  python delete_expired_emails.py --grace-days 7
        """
    )

    parser.add_argument(
        '--grace-days',
        type=int,
        default=0,
        help='猶予日数（デフォルト: 0）。期限から指定日数経過したメールを削除'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='実際には削除せず、期限切れメールの一覧のみ表示'
    )

    args = parser.parse_args()

    # 期限切れメールを削除
    delete_expired_emails(grace_days=args.grace_days, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
