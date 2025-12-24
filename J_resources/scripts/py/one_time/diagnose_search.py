"""
検索が0件になる原因を診断するスクリプト
データベースの状態を詳しく調査します
"""
import asyncio
from dotenv import load_dotenv
from core.database.client import DatabaseClient
from core.ai.llm_client import LLMClient

# 環境変数読み込み
load_dotenv()


def check_database_status():
    """データベースの状態を診断"""
    db = DatabaseClient()

    print("=" * 80)
    print("📊 データベース診断開始")
    print("=" * 80)

    # 1. 全ドキュメント数
    try:
        all_docs = db.client.table('Rawdata_FILE_AND_MAIL').select('id, file_name, processing_status, workspace').execute()
        total_count = len(all_docs.data) if all_docs.data else 0
        print(f"\n1️⃣  全ドキュメント数: {total_count} 件")

        if total_count > 0:
            # processing_status別の集計
            status_counts = {}
            for doc in all_docs.data:
                status = doc.get('processing_status', 'unknown')
                status_counts[status] = status_counts.get(status, 0) + 1

            print(f"\n   processing_status別:")
            for status, count in status_counts.items():
                print(f"   - {status}: {count} 件")

            # workspace別の集計
            workspace_counts = {}
            for doc in all_docs.data:
                workspace = doc.get('workspace', 'NULL')
                workspace_counts[workspace] = workspace_counts.get(workspace, 0) + 1

            print(f"\n   workspace別:")
            for workspace, count in workspace_counts.items():
                print(f"   - {workspace}: {count} 件")

    except Exception as e:
        print(f"❌ エラー: {e}")

    # 2. embeddingが設定されているドキュメント数
    try:
        embedded_docs = db.client.table('Rawdata_FILE_AND_MAIL').select('id, file_name').not_.is_('embedding', 'null').execute()
        embedded_count = len(embedded_docs.data) if embedded_docs.data else 0
        print(f"\n2️⃣  embeddingあり: {embedded_count} 件")

        if embedded_count == 0:
            print("   ⚠️  WARNING: embeddingが設定されているドキュメントが0件です！")
            print("   → ベクトル検索は実行できません")

    except Exception as e:
        print(f"❌ エラー: {e}")

    # 3. 検索可能なドキュメント（embedding + completed）
    try:
        searchable_docs = (
            db.client.table('Rawdata_FILE_AND_MAIL')
            .select('id, file_name, workspace, doc_type')
            .not_.is_('embedding', 'null')
            .eq('processing_status', 'completed')
            .execute()
        )
        searchable_count = len(searchable_docs.data) if searchable_docs.data else 0
        print(f"\n3️⃣  検索可能（embedding + completed）: {searchable_count} 件")

        if searchable_count == 0:
            print("   ❌ CRITICAL: 検索可能なドキュメントが0件です！")
            print("   → 検索結果が0件になる原因はこれです")
        else:
            print(f"\n   検索可能なドキュメント（最初の5件）:")
            for doc in searchable_docs.data[:5]:
                print(f"   - {doc.get('file_name')} (workspace: {doc.get('workspace')}, type: {doc.get('doc_type')})")

    except Exception as e:
        print(f"❌ エラー: {e}")

    print("\n" + "=" * 80)


async def test_search():
    """実際に検索を実行してテスト"""
    db = DatabaseClient()
    llm = LLMClient()

    print("\n" + "=" * 80)
    print("🔍 検索テスト開始")
    print("=" * 80)

    test_query = "テスト"

    try:
        # Embedding生成
        print(f"\nクエリ: '{test_query}'")
        print("Embedding生成中...")
        embedding = llm.generate_embedding(test_query)
        print(f"✅ Embedding生成完了 (次元: {len(embedding)})")

        # 検索実行（workspace指定なし）
        print("\n検索実行中（workspace指定なし）...")
        results = await db.search_documents(
            query=test_query,
            embedding=embedding,
            limit=50,
            workspace=None
        )

        print(f"✅ 検索結果: {len(results)} 件")

        if len(results) == 0:
            print("   ❌ 検索結果が0件です")
            print("   → データベース診断結果を確認してください")
        else:
            print(f"\n   検索結果（最初の3件）:")
            for idx, result in enumerate(results[:3], 1):
                print(f"\n   [{idx}] {result.get('file_name')}")
                print(f"       類似度: {result.get('similarity', 0):.4f}")
                print(f"       workspace: {result.get('workspace')}")
                print(f"       doc_type: {result.get('doc_type')}")

    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)


if __name__ == "__main__":
    # Step 1: データベース診断
    check_database_status()

    # Step 2: 検索テスト
    asyncio.run(test_search())
