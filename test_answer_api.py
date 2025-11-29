"""
/api/answerエンドポイントの統合テスト
検索→回答生成の流れを確認
"""
import requests
import json

BASE_URL = "http://127.0.0.1:5001"

def test_search_and_answer():
    """検索→回答生成の統合テスト"""

    # ステップ1: 検索
    query = "運動会はいつですか？"
    print(f"=" * 80)
    print(f"クエリ: {query}")
    print(f"=" * 80)

    print("\n[ステップ1] 検索実行...")
    search_response = requests.post(
        f"{BASE_URL}/api/search",
        json={"query": query, "limit": 5}  # ✅ デフォルトの5件でテスト
    )

    search_data = search_response.json()

    if not search_data.get('success'):
        print(f"❌ 検索失敗: {search_data.get('error')}")
        return

    print(f"✅ 検索成功: {search_data['count']} 件ヒット")

    # 検索結果の確認
    for idx, doc in enumerate(search_data['results'][:3], 1):
        print(f"\n  [{idx}] {doc.get('file_name')}")
        print(f"      類似度: {doc.get('similarity', 0):.4f}")
        content_preview = doc.get('content', '')[:100] + '...' if doc.get('content') else '[空]'
        print(f"      内容プレビュー: {content_preview}")

    # ステップ2: 回答生成
    print(f"\n{'=' * 80}")
    print("[ステップ2] 回答生成...")
    print(f"{'=' * 80}\n")

    answer_response = requests.post(
        f"{BASE_URL}/api/answer",
        json={
            "query": query,
            "documents": search_data['results']
        }
    )

    answer_data = answer_response.json()

    if not answer_data.get('success'):
        print(f"❌ 回答生成失敗: {answer_data.get('error')}")
        return

    print(f"✅ 回答生成成功")
    print(f"\nモデル: {answer_data.get('provider')} / {answer_data.get('model')}")
    print(f"\n【回答】\n{answer_data.get('answer')}")

    print(f"\n{'=' * 80}")
    print("✅ 統合テスト完了")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    try:
        test_search_and_answer()
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
