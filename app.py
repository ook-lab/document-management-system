"""
Flask Web Application
質問・回答システムのWebインターフェース
"""
import os
import asyncio
from typing import Dict, List, Any
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

from core.database.client import DatabaseClient
from core.ai.llm_client import LLMClient

app = Flask(__name__)
CORS(app)

# クライアントの初期化
db_client = DatabaseClient()
llm_client = LLMClient()


@app.route('/')
def index():
    """メインページ"""
    return render_template('index.html')


@app.route('/api/search', methods=['POST'])
def search_documents():
    """
    ベクトル検索API
    ユーザーの質問から関連文書を検索
    """
    try:
        data = request.get_json()
        query = data.get('query', '')
        limit = data.get('limit', 20)  # デフォルトを5から20に増やして検索精度を向上
        workspace = data.get('workspace')

        if not query:
            return jsonify({'success': False, 'error': 'クエリが空です'}), 400

        # Embeddingを生成
        embedding = llm_client.generate_embedding(query)

        # ベクトル検索を実行（非同期関数を同期的に実行）
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(
            db_client.search_documents(query, embedding, limit, workspace)
        )
        loop.close()

        return jsonify({
            'success': True,
            'results': results,
            'count': len(results)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/answer', methods=['POST'])
def generate_answer():
    """
    回答生成API
    検索結果を元にGPT-4で自然な回答を生成
    """
    try:
        data = request.get_json()
        query = data.get('query', '')
        documents = data.get('documents', [])

        if not query:
            return jsonify({'success': False, 'error': 'クエリが空です'}), 400

        # ドキュメントコンテキストを構築
        context = _build_context(documents)

        # プロンプトを作成
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

        # GPT-4で回答生成
        response = llm_client.call_model(
            tier="ui_response",
            prompt=prompt
        )

        if not response.get('success'):
            return jsonify({
                'success': False,
                'error': response.get('error', '回答生成に失敗しました')
            }), 500

        return jsonify({
            'success': True,
            'answer': response.get('content', ''),
            'model': response.get('model', ''),
            'provider': response.get('provider', '')
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def _format_metadata(metadata: Dict[str, Any], indent: int = 0) -> str:
    """
    メタデータを見やすく整形

    Args:
        metadata: メタデータ辞書
        indent: インデントレベル

    Returns:
        整形された文字列
    """
    if not metadata:
        return ""

    lines = []
    prefix = "  " * indent

    for key, value in metadata.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(_format_metadata(value, indent + 1))
        elif isinstance(value, list):
            if not value:
                continue
            lines.append(f"{prefix}{key}:")
            for item in value:
                if isinstance(item, dict):
                    # 辞書のリストの場合、各アイテムを整形
                    for sub_key, sub_value in item.items():
                        lines.append(f"{prefix}  - {sub_key}: {sub_value}")
                else:
                    lines.append(f"{prefix}  - {item}")
        else:
            lines.append(f"{prefix}{key}: {value}")

    return "\n".join(lines)


def _build_context(documents: List[Dict[str, Any]]) -> str:
    """
    検索結果からコンテキストを構築

    Args:
        documents: 検索結果のリスト

    Returns:
        フォーマットされたコンテキスト文字列
    """
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
            formatted_metadata = _format_metadata(metadata)
            if formatted_metadata:
                context_part += f"\n\n詳細情報:\n{formatted_metadata}"

        context_parts.append(context_part)

    return "\n".join(context_parts)


@app.route('/api/health', methods=['GET'])
def health_check():
    """ヘルスチェックエンドポイント"""
    return jsonify({
        'status': 'ok',
        'message': 'Document Q&A System is running'
    })


if __name__ == '__main__':
    # 開発環境での実行
    app.run(host='localhost', port=5000, debug=True)
