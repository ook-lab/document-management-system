#!/usr/bin/env python
"""既存のGmailメールにmessage_idを手動追加"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')

if not supabase_url or not supabase_key:
    print("エラー: SUPABASE_URLまたはSUPABASE_KEYが設定されていません")
    sys.exit(1)

client = create_client(supabase_url, supabase_key)

# workspace='gmail' のメールを取得
result = client.table('Rawdata_FILE_AND_MAIL').select('id, title, metadata').eq('workspace', 'gmail').order('created_at', desc=True).limit(2).execute()

if not result.data:
    print("Gmailメールが見つかりません")
    sys.exit(1)

# 既知のmessage_idをマッピング（Gmail取り込み時のログから取得）
message_id_mapping = {
    '19b88e3f12851bc2': {
        'title_contains': 'NOLLEY',
        'message_id': '19b88e3f12851bc2',
        'thread_id': '19b88e3f12851bc2',
        'subject': ' 【NOLLEY\'S】など まもなく終了！'
    },
    '19b88e3ca132c7db': {
        'title_contains': 'MODE FOURRURE',
        'message_id': '19b88e3ca132c7db',
        'thread_id': '19b88e3ca132c7db',
        'subject': '【MODE FOURRURE、HIDEO WAKAMATSU、SPRING COURT】など GLADD大人気アイテムランキング'
    }
}

print("=== Gmailメールにmessage_idを追加 ===\n")

for email in result.data:
    title = email.get('title', '')
    email_id = email['id']
    metadata = email.get('metadata', {})
    if isinstance(metadata, str):
        metadata = json.loads(metadata)

    # タイトルから適切なmessage_idを判定
    matched_info = None
    for msg_id, info in message_id_mapping.items():
        if info['title_contains'] in title:
            matched_info = info
            break

    if not matched_info:
        print(f"[SKIP] {title[:50]} - マッチするmessage_idが見つかりません")
        continue

    # metadataにmessage_id等を追加
    metadata['message_id'] = matched_info['message_id']
    metadata['thread_id'] = matched_info['thread_id']
    metadata['subject'] = matched_info['subject']

    # データベースを更新
    try:
        update_result = client.table('Rawdata_FILE_AND_MAIL').update({
            'metadata': metadata
        }).eq('id', email_id).execute()

        if update_result.data:
            print(f"[OK] {title[:50]}")
            print(f"     → message_id: {matched_info['message_id']}")
            print(f"     → thread_id: {matched_info['thread_id']}")
            print()
        else:
            print(f"[ERROR] 更新失敗: {title[:50]}")
    except Exception as e:
        print(f"[ERROR] {title[:50]}: {e}")

print("完了！")
