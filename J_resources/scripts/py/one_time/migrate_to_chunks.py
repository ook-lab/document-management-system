"""
既存ドキュメントを小チャンクに分割する移行スクリプト

既存の29件（以上）のドキュメントを小チャンクに分割し、
各チャンクのembeddingを生成してsmall_chunksテーブルに保存する。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from typing import List, Dict
from core.database.client import DatabaseClient
from core.processing.chunk_processor import ChunkProcessor
from loguru import logger

async def main():
    print("="*80)
    print("既存ドキュメント → 小チャンク移行スクリプト")
    print("="*80)

    db = DatabaseClient()
    chunk_processor = ChunkProcessor(
        chunk_size=300,
        overlap=50,
        max_concurrent=2  # レート制限対策（同時2件まで - メモリ節約）
    )

    # 全ドキュメントを取得
    print("\n[Step 1] ドキュメント取得中...")
    result = db.client.table('10_rd_source_docs').select('id,file_name,attachment_text').execute()
    documents = result.data if result.data else []

    total = len(documents)
    print(f"対象ドキュメント数: {total} 件")

    if total == 0:
        print("ドキュメントが見つかりません")
        return

    # 既にチャンクがあるドキュメントを確認
    print("\n[Step 2] 既存チャンク確認中...")
    existing_chunks_result = db.client.table('small_chunks').select('document_id').execute()
    existing_document_ids = set()
    if existing_chunks_result.data:
        for chunk in existing_chunks_result.data:
            existing_document_ids.add(chunk['document_id'])

    print(f"既にチャンクがあるドキュメント: {len(existing_document_ids)} 件")
    documents_to_process = [doc for doc in documents if doc['id'] not in existing_document_ids]
    print(f"処理が必要なドキュメント: {len(documents_to_process)} 件")

    if len(documents_to_process) == 0:
        print("\n全てのドキュメントは既にチャンクに分割されています")
        return

    # 確認
    print(f"\n{len(documents_to_process)} 件のドキュメントをチャンクに分割します")
    print("各チャンクのembeddingを生成します（OpenAI API使用）")
    print("続行しますか？ (y/N): ", end='')
    response = input().strip().lower()
    if response != 'y':
        print("キャンセルしました")
        return

    # 各ドキュメントを処理
    print("\n[Step 3] チャンク分割 & Embedding生成中...")
    success_count = 0
    error_count = 0
    total_chunks_created = 0

    for idx, doc in enumerate(documents_to_process, 1):
        doc_id = doc['id']
        file_name = doc.get('file_name', 'unknown')
        attachment_text = doc.get('attachment_text', '')

        if not attachment_text or not attachment_text.strip():
            print(f"[{idx}/{len(documents_to_process)}] ⚠️  {file_name}: 本文が空です（スキップ）")
            error_count += 1
            continue

        print(f"[{idx}/{len(documents_to_process)}] 処理中: {file_name}")

        try:
            # チャンク処理
            result = await chunk_processor.process_document(
                document_id=doc_id,
                full_text=attachment_text,
                force_reprocess=False  # 既存チャンクがある場合はスキップ
            )

            if result["success"]:
                chunks_created = result["chunks_created"]
                chunks_failed = result["chunks_failed"]
                total_chunks_created += chunks_created

                if chunks_created > 0:
                    print(f"  ✅ 成功: {chunks_created} チャンク作成")
                    success_count += 1
                else:
                    print(f"  ⚠️  警告: チャンクが作成されませんでした")
                    error_count += 1

                if chunks_failed > 0:
                    print(f"  ⚠️  警告: {chunks_failed} チャンクのembedding生成失敗")
            else:
                print(f"  ❌ 失敗: {result.get('error', 'Unknown error')}")
                error_count += 1

        except Exception as e:
            print(f"  ❌ 例外発生: {e}")
            logger.error(f"Error processing document {doc_id}: {e}")
            error_count += 1

        # レート制限対策：少し待機
        if idx % 10 == 0:
            print(f"\n進捗: {idx}/{len(documents_to_process)} 完了 (一時停止: 5秒)")
            await asyncio.sleep(5)

    # 結果サマリー
    print("\n" + "="*80)
    print("移行完了")
    print("="*80)
    print(f"成功: {success_count} 件")
    print(f"失敗: {error_count} 件")
    print(f"作成されたチャンク総数: {total_chunks_created} 個")
    print(f"平均チャンク数/ドキュメント: {total_chunks_created / success_count if success_count > 0 else 0:.1f} 個")

    # 最終確認
    print("\n[Step 4] 最終確認...")
    all_chunks_result = db.client.table('small_chunks').select('document_id', count='exact').execute()
    total_chunks_in_db = all_chunks_result.count if all_chunks_result.count else 0
    print(f"データベース内の総チャンク数: {total_chunks_in_db} 個")

    # ドキュメントごとのチャンク数を表示
    chunks_by_doc = {}
    all_chunks = db.client.table('small_chunks').select('document_id').execute()
    if all_chunks.data:
        for chunk in all_chunks.data:
            doc_id = chunk['document_id']
            chunks_by_doc[doc_id] = chunks_by_doc.get(doc_id, 0) + 1

    print(f"\nチャンクがあるドキュメント数: {len(chunks_by_doc)} 件")
    print(f"全ドキュメント数: {total} 件")

    if len(chunks_by_doc) == total:
        print("\n✅ 全てのドキュメントがチャンクに分割されました！")
    else:
        print(f"\n⚠️  {total - len(chunks_by_doc)} 件のドキュメントにはチャンクがありません")

if __name__ == "__main__":
    asyncio.run(main())
