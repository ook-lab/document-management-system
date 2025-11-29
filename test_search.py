"""
ベクトル検索の診断スクリプト
DB内のEmbedding次元数とベクトル検索機能をテスト
"""

import asyncio
import os
from core.database.client import DatabaseClient
from core.ai.llm_client import LLMClient
from config.settings import settings


def print_section(title: str):
    """セクションヘッダーを出力"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


async def diagnose_vector_search():
    """ベクトル検索の診断を実行"""

    print_section("🔍 ベクトル検索診断スクリプト")
    print(f"Supabase URL: {settings.SUPABASE_URL}")
    print(f"OpenAI API Key: {'✅ 設定済み' if os.getenv('OPENAI_API_KEY') else '❌ 未設定'}")

    # クライアント初期化
    try:
        db_client = DatabaseClient()
        llm_client = LLMClient()
        print("✅ クライアント初期化成功")
    except Exception as e:
        print(f"❌ クライアント初期化失敗: {e}")
        return

    # ============================================
    # 診断1: DB生存確認（documentsテーブルの行数カウント）
    # ============================================
    print_section("診断1: DB生存確認")
    try:
        response = db_client.client.table('documents').select('id', count='exact').execute()
        total_count = response.count
        print(f"✅ documentsテーブル: {total_count} 件のレコードが存在")

        if total_count == 0:
            print("⚠️  警告: データが空です。先にデータを取り込む必要があります。")
            return
    except Exception as e:
        print(f"❌ テーブルカウント失敗: {e}")
        import traceback
        traceback.print_exc()
        return

    # ============================================
    # 診断2: 次元数チェック（最重要）
    # ============================================
    print_section("診断2: Embedding次元数チェック（最重要）")
    try:
        # 最新のレコードを1件取得（embeddingが存在するもの）
        response = db_client.client.table('documents') \
            .select('id, file_name, embedding, created_at') \
            .not_.is_('embedding', 'null') \
            .order('created_at', desc=True) \
            .limit(1) \
            .execute()

        if not response.data or len(response.data) == 0:
            print("⚠️  警告: embeddingを持つレコードが見つかりません")
            print("   データは存在しますが、embeddingが保存されていない可能性があります")
            return

        latest_doc = response.data[0]
        doc_id = latest_doc['id']
        file_name = latest_doc['file_name']
        embedding_raw = latest_doc['embedding']

        print(f"📄 最新のドキュメント:")
        print(f"   ID: {doc_id}")
        print(f"   ファイル名: {file_name}")
        print(f"   作成日時: {latest_doc['created_at']}")

        # Embeddingの次元数を確認
        # Supabaseはembeddingを文字列 "[0.1,0.2,...]" または配列で返す
        if isinstance(embedding_raw, str):
            # 文字列形式の場合、カンマの数+1が次元数
            import json
            try:
                embedding_list = json.loads(embedding_raw)
                dimension = len(embedding_list)
            except:
                # "[0.1,0.2,...]" 形式を手動でパース
                dimension = embedding_raw.count(',') + 1
        elif isinstance(embedding_raw, list):
            dimension = len(embedding_raw)
        else:
            print(f"⚠️  警告: embedding の型が不明です: {type(embedding_raw)}")
            dimension = None

        if dimension:
            print(f"\n🎯 **DB保存済みEmbeddingの次元数: {dimension}**")

            if dimension == 3072:
                print("   ❌ 問題発見: 3072次元 (text-embedding-3-large のデフォルト)")
                print("   ✅ 原因特定: 過去に `large` モデルでインジェストされたデータです")
                print("   📝 対策: データの再取り込みまたはモデル設定の統一が必要")
            elif dimension == 1536:
                print("   ✅ 正常: 1536次元 (現在の設定と一致)")
            else:
                print(f"   ⚠️  予期しない次元数: {dimension}")

    except Exception as e:
        print(f"❌ 次元数チェック失敗: {e}")
        import traceback
        traceback.print_exc()
        return

    # ============================================
    # 診断3: 現在のLLMClientで生成されるEmbedding次元数を確認
    # ============================================
    print_section("診断3: 現在のLLMClientのEmbedding生成")
    try:
        test_text = "これはテストクエリです"
        current_embedding = llm_client.generate_embedding(test_text)
        current_dimension = len(current_embedding)

        print(f"✅ 現在のLLMClient設定:")
        print(f"   テキスト: \"{test_text}\"")
        print(f"   生成されたEmbedding次元数: {current_dimension}")

        if dimension and dimension != current_dimension:
            print(f"\n❌ **次元数の不一致を検出！**")
            print(f"   DB保存済み: {dimension}次元")
            print(f"   現在の生成: {current_dimension}次元")
            print(f"   📝 これが検索で0件になる原因です")
        elif dimension and dimension == current_dimension:
            print(f"\n✅ 次元数は一致しています ({dimension}次元)")

    except Exception as e:
        print(f"❌ Embedding生成失敗: {e}")
        import traceback
        traceback.print_exc()
        return

    # ============================================
    # 診断4: 検索テスト（match_documents RPC）
    # ============================================
    print_section("診断4: ベクトル検索テスト")
    try:
        test_query = "時間割"
        print(f"検索クエリ: \"{test_query}\"")

        # Embedding生成
        query_embedding = llm_client.generate_embedding(test_query)
        print(f"クエリEmbedding次元数: {len(query_embedding)}")

        # ベクトル検索実行
        results = await db_client.search_documents(
            query=test_query,
            embedding=query_embedding,
            limit=5,
            workspace=None
        )

        print(f"\n検索結果: {len(results)} 件")

        if len(results) == 0:
            print("❌ 0件の結果が返されました")
            print("   原因候補:")
            if dimension and dimension != current_dimension:
                print("   1. ✅ Embedding次元数の不一致（上記で確認済み）")
            else:
                print("   1. match_documents RPC関数の実装に問題がある")
                print("   2. データにembeddingが正しく保存されていない")
                print("   3. Supabaseのベクトル検索設定に問題がある")
        else:
            print("✅ 検索結果が返されました:")
            for idx, result in enumerate(results[:3], 1):
                print(f"\n   結果 {idx}:")
                print(f"   - ファイル名: {result.get('file_name', 'N/A')}")
                print(f"   - doc_type: {result.get('doc_type', 'N/A')}")
                print(f"   - 類似度: {result.get('similarity', 'N/A')}")

    except Exception as e:
        print(f"❌ 検索テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return

    # ============================================
    # 診断まとめ
    # ============================================
    print_section("📊 診断まとめ")
    if dimension and dimension != current_dimension:
        print("🔴 **問題を特定しました**")
        print(f"   - DB保存データ: {dimension}次元")
        print(f"   - 現在の設定: {current_dimension}次元")
        print("\n✅ **推奨対策**:")
        print("   1. データベースの全データを再取り込み（推奨）")
        print("   2. または、config/model_tiers.py を text-embedding-3-large (3072次元) に変更")
        print("      ただし、Supabaseのカラム定義も3072次元に変更が必要")
    elif dimension == current_dimension and len(results) > 0:
        print("🟢 **検索機能は正常に動作しています**")
        print(f"   - Embedding次元数: {dimension}次元（一致）")
        print(f"   - 検索結果: {len(results)}件取得成功")
    elif dimension == current_dimension and len(results) == 0:
        print("🟡 **次元数は一致していますが、検索結果が0件です**")
        print("   - match_documents RPC関数の実装を確認してください")
        print("   - または、検索クエリに該当するデータがない可能性があります")
    else:
        print("🟡 **診断結果が不明確です**")
        print("   - 上記のエラーログを確認してください")


if __name__ == "__main__":
    asyncio.run(diagnose_vector_search())
