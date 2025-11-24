#!/usr/bin/env python3
"""
Embedding状態確認スクリプト

指定したドキュメントのembeddingとprocessing_statusを確認します。
"""
import sys
import os

# プロジェクトルートをPythonパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from supabase import create_client
from config.settings import settings


def check_embedding(file_name_pattern: str):
    """ドキュメントのembedding状態を確認"""

    # Supabaseクライアント初期化
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

    print(f"🔍 ファイル名: '{file_name_pattern}' のembedding状態を確認中...")
    print("=" * 80)

    try:
        # file_name で部分一致検索
        response = client.table('documents').select(
            'id, file_name, workspace, processing_status, embedding, doc_type, confidence'
        ).ilike('file_name', f'%{file_name_pattern}%').execute()

        if not response.data or len(response.data) == 0:
            print(f"⚠️  ファイル名に '{file_name_pattern}' を含むドキュメントが見つかりませんでした。")
            return

        print(f"✅ {len(response.data)} 件のドキュメントが見つかりました\n")

        for idx, doc in enumerate(response.data, 1):
            print(f"📄 ドキュメント #{idx}")
            print("-" * 80)
            print(f"ファイル名: {doc.get('file_name')}")
            print(f"ワークスペース: {doc.get('workspace')}")
            print(f"doc_type: {doc.get('doc_type')}")
            print(f"confidence: {doc.get('confidence')}")
            print(f"processing_status: {doc.get('processing_status')}")

            embedding = doc.get('embedding')
            if embedding:
                # embeddingが文字列の場合、次元数を確認
                if isinstance(embedding, str):
                    # "[0.1,0.2,...]" 形式の文字列から次元数を推定
                    dim = embedding.count(',') + 1 if ',' in embedding else 1
                    print(f"embedding: ✅ 存在 (次元数: ~{dim})")
                else:
                    print(f"embedding: ✅ 存在 (型: {type(embedding)})")
            else:
                print(f"embedding: ❌ NULL")

            print()

    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


def main():
    """メインエントリーポイント"""
    if len(sys.argv) < 2:
        print("使用方法: python scripts/check_embedding.py <ファイル名パターン>")
        print("例: python scripts/check_embedding.py '学年通信 (28)'")
        sys.exit(1)

    file_name_pattern = sys.argv[1]
    check_embedding(file_name_pattern)


if __name__ == "__main__":
    main()
