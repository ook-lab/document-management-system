#!/usr/bin/env python3
"""
検索クエリテストスクリプト

コマンドライン引数で質問を受け取り、検索→回答生成を実行して結果を出力します。
"""
import sys
import os
import asyncio
import json

# プロジェクトルートをPythonパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from core.database.client import DatabaseClient
from core.ai.llm_client import LLMClient


def format_metadata(metadata: dict, indent: int = 0) -> str:
    """メタデータを見やすく整形"""
    if not metadata:
        return ""

    lines = []
    prefix = "  " * indent

    for key, value in metadata.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(format_metadata(value, indent + 1))
        elif isinstance(value, list):
            if not value:
                continue
            lines.append(f"{prefix}{key}:")
            for item in value:
                if isinstance(item, dict):
                    for sub_key, sub_value in item.items():
                        lines.append(f"{prefix}  - {sub_key}: {sub_value}")
                else:
                    lines.append(f"{prefix}  - {item}")
        else:
            lines.append(f"{prefix}{key}: {value}")

    return "\n".join(lines)


def build_context(documents: list) -> str:
    """検索結果からコンテキストを構築"""
    if not documents:
        return "関連する文書が見つかりませんでした。"

    context_parts = []
    for idx, doc in enumerate(documents, 1):
        file_name = doc.get('file_name', '無題')
        doc_type = doc.get('doc_type', '不明')
        summary = doc.get('summary', '')
        similarity = doc.get('similarity', 0)
        metadata = doc.get('metadata', {})

        # 基本情報
        context_part = f"""
【文書{idx}】
ファイル名: {file_name}
文書タイプ: {doc_type}
類似度: {similarity:.2f}"""

        # サマリー追加
        if summary:
            context_part += f"\n要約: {summary}"

        # メタデータを整形して追加
        if metadata:
            formatted_metadata = format_metadata(metadata)
            if formatted_metadata:
                context_part += f"\n\n詳細情報:\n{formatted_metadata}"

        context_parts.append(context_part)

    return "\n".join(context_parts)


async def search_and_answer(query: str, workspace: str = None, limit: int = 50):
    """検索→回答生成を実行"""

    print(f"🔍 質問: {query}")
    print("=" * 80)

    # クライアント初期化
    db_client = DatabaseClient()
    llm_client = LLMClient()

    try:
        # 1. Embeddingを生成
        print("\n📊 Embedding生成中...")
        embedding = llm_client.generate_embedding(query)
        print(f"✅ Embedding生成完了 (次元数: {len(embedding)})")

        # 2. ベクトル検索を実行
        print(f"\n🔎 ベクトル検索中... (limit={limit})")
        results = await db_client.search_documents(query, embedding, limit, workspace)
        print(f"✅ {len(results)} 件のドキュメントが見つかりました")

        if not results:
            print("\n⚠️  関連するドキュメントが見つかりませんでした。")
            return

        # 3. コンテキストを構築
        print("\n📝 コンテキスト構築中...")
        context = build_context(results)

        print("\n" + "=" * 80)
        print("📄 検索結果のコンテキスト:")
        print("=" * 80)
        print(context)

        # 4. 回答生成
        print("\n" + "=" * 80)
        print("💬 回答生成中...")
        print("=" * 80)

        prompt = f"""以下の文書情報を参考に、ユーザーの質問に日本語で回答してください。

【質問】
{query}

【参考文書】
{context}

【回答の条件】
- 参考文書の情報を基に、正確に回答してください
- 情報が不足している場合は、その旨を伝えてください
- 簡潔で分かりやすい回答を心がけてください
- 回答の最後に、参考にした文書のタイトルを列挙してください

【回答】
"""

        response = llm_client.call_model(
            tier="ui_response",
            prompt=prompt
        )

        if not response.get('success'):
            print(f"❌ 回答生成に失敗: {response.get('error')}")
            return

        print(f"\n✅ 回答生成完了 (モデル: {response.get('model')}, プロバイダー: {response.get('provider')})")
        print("\n" + "=" * 80)
        print("🤖 生成された回答:")
        print("=" * 80)
        print(response.get('content', ''))
        print("\n" + "=" * 80)

    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


def main():
    """メインエントリーポイント"""
    if len(sys.argv) < 2:
        print("使用方法: python scripts/test_search_query.py <質問>")
        print("例: python scripts/test_search_query.py '黒姫移動教室の持ち物は？'")
        sys.exit(1)

    query = sys.argv[1]
    workspace = sys.argv[2] if len(sys.argv) > 2 else None

    # 非同期関数を実行
    asyncio.run(search_and_answer(query, workspace))


if __name__ == "__main__":
    main()
