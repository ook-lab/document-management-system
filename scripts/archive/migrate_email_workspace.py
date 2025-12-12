"""
既存のメールデータのworkspaceを更新するマイグレーションスクリプト

workspace = 'personal' → metadataのgmail_labelから正しいworkspaceを設定
"""
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from core.database.client import DatabaseClient
from config.workspaces import get_workspace_from_gmail_label
from loguru import logger


def migrate_email_workspaces():
    """既存のメールドキュメントのworkspaceを更新"""
    db = DatabaseClient()

    logger.info("=" * 60)
    logger.info("メールworkspaceマイグレーション開始")
    logger.info("=" * 60)

    # file_type = 'email' のドキュメントを取得
    result = db.client.table('documents').select(
        'id, workspace, metadata'
    ).eq('file_type', 'email').execute()

    emails = result.data
    logger.info(f"対象メール数: {len(emails)}件")

    update_count = 0
    skip_count = 0

    for email in emails:
        email_id = email['id']
        current_workspace = email.get('workspace')
        metadata = email.get('metadata', {})

        # metadataが辞書でない場合はスキップ
        if not isinstance(metadata, dict):
            logger.warning(f"  ⚠️ メタデータが辞書ではありません: {email_id}")
            skip_count += 1
            continue

        gmail_label = metadata.get('gmail_label')

        # gmail_labelがない場合はスキップ
        if not gmail_label:
            logger.warning(f"  ⚠️ gmail_labelがありません: {email_id}")
            skip_count += 1
            continue

        # gmail_labelから正しいworkspaceを判定
        correct_workspace = get_workspace_from_gmail_label(gmail_label)

        # すでに正しいworkspaceの場合はスキップ
        if current_workspace == correct_workspace:
            logger.debug(f"  ✓ すでに正しいworkspace: {email_id} ({correct_workspace})")
            skip_count += 1
            continue

        # workspaceを更新
        try:
            db.client.table('documents').update({
                'workspace': correct_workspace
            }).eq('id', email_id).execute()

            logger.info(f"  ✅ 更新: {email_id}")
            logger.info(f"     {current_workspace} → {correct_workspace}")
            logger.info(f"     gmail_label: {gmail_label}")
            update_count += 1

        except Exception as e:
            logger.error(f"  ❌ 更新失敗: {email_id} - {e}")

    logger.info("=" * 60)
    logger.info("マイグレーション完了")
    logger.info(f"  更新: {update_count}件")
    logger.info(f"  スキップ: {skip_count}件")
    logger.info("=" * 60)


if __name__ == "__main__":
    migrate_email_workspaces()
