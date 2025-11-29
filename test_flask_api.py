"""
Flask API エンドポイントの検証スクリプト
フロントエンドと同じJSONペイロードでAPIをテスト
"""

import json
import sys
from app import app


def print_section(title: str):
    """セクションヘッダーを出力"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_search_api():
    """Flask /api/search エンドポイントをテスト"""

    print_section("🧪 Flask API テスト: /api/search")

    # Flaskテストクライアントを作成
    with app.test_client() as client:

        # ============================================
        # テスト1: 正常なリクエスト（フロントエンドと同じペイロード）
        # ============================================
        print_section("テスト1: 正常なリクエスト")

        test_payload = {
            "query": "時間割",
            "limit": 50
        }

        print(f"リクエストペイロード: {json.dumps(test_payload, ensure_ascii=False)}")

        try:
            response = client.post(
                '/api/search',
                data=json.dumps(test_payload),
                content_type='application/json'
            )

            print(f"ステータスコード: {response.status_code}")

            # レスポンスをパース
            response_data = response.get_json()
            print(f"レスポンス: {json.dumps(response_data, ensure_ascii=False, indent=2)}")

            # 成功判定
            if response.status_code == 200:
                if response_data.get('success'):
                    results = response_data.get('results', [])
                    count = response_data.get('count', 0)

                    print(f"\n✅ 検索成功: {count} 件の結果")

                    if count == 0:
                        print("⚠️  警告: 0件の結果が返されました")
                        print("   この問題を再現しました！")
                    else:
                        print(f"✅ {count} 件の結果が返されました")

                        # 最初の3件を詳細表示
                        for idx, doc in enumerate(results[:3], 1):
                            print(f"\n   結果 {idx}:")
                            print(f"   - ファイル名: {doc.get('file_name', 'N/A')}")
                            print(f"   - doc_type: {doc.get('doc_type', 'N/A')}")
                            print(f"   - 類似度: {doc.get('similarity', 'N/A')}")
                            print(f"   - workspace: {doc.get('workspace', 'N/A')}")
                else:
                    print(f"❌ API がエラーを返しました: {response_data.get('error', '不明')}")
            else:
                print(f"❌ HTTPエラー: {response.status_code}")

        except Exception as e:
            print(f"❌ テスト1失敗: {e}")
            import traceback
            traceback.print_exc()

        # ============================================
        # テスト2: workspace パラメータを明示的に指定
        # ============================================
        print_section("テスト2: workspace パラメータを指定")

        test_payload_with_workspace = {
            "query": "時間割",
            "limit": 50,
            "workspace": "personal"  # 明示的に指定
        }

        print(f"リクエストペイロード: {json.dumps(test_payload_with_workspace, ensure_ascii=False)}")

        try:
            response = client.post(
                '/api/search',
                data=json.dumps(test_payload_with_workspace),
                content_type='application/json'
            )

            print(f"ステータスコード: {response.status_code}")
            response_data = response.get_json()

            if response.status_code == 200 and response_data.get('success'):
                count = response_data.get('count', 0)
                print(f"検索結果: {count} 件")

                if count == 0:
                    print("⚠️  workspace='personal' では0件です")
                    print("   → データのworkspaceが 'personal' でない可能性があります")
                else:
                    print(f"✅ workspace='personal' で {count} 件取得")

        except Exception as e:
            print(f"❌ テスト2失敗: {e}")
            import traceback
            traceback.print_exc()

        # ============================================
        # テスト3: 空のクエリ（エラーハンドリングテスト）
        # ============================================
        print_section("テスト3: 空のクエリ")

        empty_payload = {
            "query": "",
            "limit": 50
        }

        try:
            response = client.post(
                '/api/search',
                data=json.dumps(empty_payload),
                content_type='application/json'
            )

            print(f"ステータスコード: {response.status_code}")
            response_data = response.get_json()

            if response.status_code == 400:
                print(f"✅ 期待通りのエラー: {response_data.get('error', '')}")
            else:
                print(f"⚠️  予期しないステータスコード: {response.status_code}")

        except Exception as e:
            print(f"❌ テスト3失敗: {e}")

        # ============================================
        # テスト4: workspace を None で明示的に指定
        # ============================================
        print_section("テスト4: workspace=None を明示指定")

        test_payload_none = {
            "query": "時間割",
            "limit": 50,
            "workspace": None
        }

        print(f"リクエストペイロード: {json.dumps(test_payload_none, ensure_ascii=False)}")

        try:
            response = client.post(
                '/api/search',
                data=json.dumps(test_payload_none),
                content_type='application/json'
            )

            print(f"ステータスコード: {response.status_code}")
            response_data = response.get_json()

            if response.status_code == 200 and response_data.get('success'):
                count = response_data.get('count', 0)
                print(f"検索結果: {count} 件")

                if count > 0:
                    print(f"✅ workspace=None で {count} 件取得（診断スクリプトと一致）")
                else:
                    print("⚠️  workspace=None でも0件です")

        except Exception as e:
            print(f"❌ テスト4失敗: {e}")
            import traceback
            traceback.print_exc()

    # ============================================
    # まとめ
    # ============================================
    print_section("📊 テストまとめ")
    print("上記の結果から、以下を確認してください:")
    print("1. テスト1で0件の場合 → APIレベルで問題あり（要調査）")
    print("2. テスト1で結果が返る場合 → フロントエンドの表示ロジックに問題")
    print("3. テスト2とテスト4の結果を比較 → workspace フィルタの影響を確認")


if __name__ == "__main__":
    test_search_api()
