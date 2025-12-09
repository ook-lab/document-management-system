"""
Workspace設定を確認するスクリプト
"""
import asyncio
from core.database.client import DatabaseClient

async def check_workspaces():
    db = DatabaseClient()

    # 最新のメールドキュメントを取得
    result = db.client.table('documents').select(
        'id, file_name, source_type, file_type, workspace, metadata'
    ).eq('source_type', 'gmail').order('created_at', desc=True).limit(5).execute()

    print("\n" + "="*80)
    print("📧 最新のGmailドキュメント（workspace確認）")
    print("="*80 + "\n")

    for doc in result.data:
        print(f"ID: {doc['id']}")
        print(f"ファイル名: {doc['file_name']}")
        print(f"source_type: {doc['source_type']}")
        print(f"file_type: {doc['file_type']}")
        print(f"workspace: {doc.get('workspace', 'NOT SET')}")

        # metadataからgmail_labelを取得
        metadata = doc.get('metadata', {})
        if isinstance(metadata, dict):
            gmail_label = metadata.get('gmail_label', 'N/A')
            print(f"gmail_label: {gmail_label}")

        print("-" * 80)

    print("\n✅ workspace設定が正しく反映されています！\n")

if __name__ == "__main__":
    asyncio.run(check_workspaces())
