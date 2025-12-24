"""
全ドキュメントのembeddingを再生成
embeddingカラムが削除された後の復旧用スクリプト
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from core.database.client import DatabaseClient
from core.ai.llm_client import LLMClient
from loguru import logger

async def main():
    print("="*80)
    print("全ドキュメント embedding 再生成スクリプト")
    print("="*80)

    db = DatabaseClient()
    llm_client = LLMClient()

    # 全ドキュメントを取得
    print("\n[Step 1] ドキュメント取得中...")
    result = db.client.table('Rawdata_FILE_AND_MAIL').select('id,file_name,attachment_text,summary').execute()
    documents = result.data if result.data else []

    total = len(documents)
    print(f"対象ドキュメント数: {total} 件")

    if total == 0:
        print("ドキュメントが見つかりません")
        return

    # 確認
    print(f"\n{total}件のドキュメントのembeddingを再生成します")
    print("続行しますか？ (y/N): ", end='')
    response = input().strip().lower()
    if response != 'y':
        print("キャンセルしました")
        return

    # 各ドキュメントのembeddingを生成
    print("\n[Step 2] Embedding生成中...")
    success_count = 0
    error_count = 0

    for idx, doc in enumerate(documents, 1):
        doc_id = doc['id']
        file_name = doc.get('file_name', 'unknown')
        attachment_text = doc.get('attachment_text', '')
        summary = doc.get('summary', '')

        # テキストを結合
        text_to_embed = attachment_text if attachment_text else summary
        if not text_to_embed:
            print(f"[{idx}/{total}] スキップ: {file_name} (テキストなし)")
            error_count += 1
            continue

        try:
            # Embeddingを生成
            embedding = llm_client.generate_embedding(text_to_embed)

            # PostgreSQL vector形式に変換
            embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'

            # データベースを更新
            db.client.table('Rawdata_FILE_AND_MAIL').update({
                'embedding': embedding_str
            }).eq('id', doc_id).execute()

            print(f"[{idx}/{total}] OK: {file_name}")
            success_count += 1

        except Exception as e:
            print(f"[{idx}/{total}] ERROR: {file_name} - {e}")
            error_count += 1
            logger.error(f"Embedding生成エラー: {doc_id} - {e}")

    print("\n" + "="*80)
    print("完了")
    print("="*80)
    print(f"成功: {success_count} 件")
    print(f"失敗: {error_count} 件")
    print(f"合計: {total} 件")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main())
