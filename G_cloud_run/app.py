"""
Flask Web Application
質問・回答システムのWebインターフェース
"""
import os
from typing import Dict, List, Any
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# クライアントの遅延初期化（Cloud Run起動高速化）
db_client = None
llm_client = None
query_expander = None


def get_clients():
    """クライアントを初回アクセス時に初期化（遅延読み込み）"""
    global db_client, llm_client, query_expander

    if db_client is None:
        print("[INFO] クライアントを初期化中...")
        # 遅延import（起動高速化）
        from A_common.database.client import DatabaseClient
        from C_ai_common.llm_client.llm_client import LLMClient
        from A_common.utils.query_expansion import QueryExpander

        db_client = DatabaseClient()
        llm_client = LLMClient()
        query_expander = QueryExpander(llm_client=llm_client)
        print("[INFO] クライアント初期化完了")

    return db_client, llm_client, query_expander


@app.route('/')
def index():
    """メインページ"""
    return render_template('index.html')


@app.route('/api/filters', methods=['GET'])
def get_filters():
    """
    フィルタオプション取得API（階層構造対応）
    workspace（親）→ doc_type（子）の階層データを返す
    """
    try:
        # クライアント取得（遅延初期化）
        db_client, _, _ = get_clients()

        # workspace別のdoc_type階層構造を取得
        hierarchy = db_client.get_workspace_hierarchy()

        # 階層構造をリスト形式に変換（フロントエンド用）
        workspace_list = []
        for workspace, doc_types in hierarchy.items():
            workspace_list.append({
                'name': workspace,
                'doc_types': doc_types
            })

        print(f"[DEBUG] フィルタ取得: {len(workspace_list)} workspaces（階層構造）")

        return jsonify({
            'success': True,
            'hierarchy': workspace_list
        })
    except Exception as e:
        print(f"[ERROR] フィルタ取得エラー: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/search', methods=['POST'])
def search_documents():
    """
    ベクトル検索API（クエリ拡張対応 + 複数フィルタ対応）
    ユーザーの質問から関連文書を検索
    """
    try:
        # クライアント取得（遅延初期化）
        db_client, llm_client, query_expander = get_clients()

        data = request.get_json()
        query = data.get('query', '')
        # リランク機能のため、フロントエンドの指定を尊重（最大50件まで）
        requested_limit = data.get('limit', 3)
        limit = min(requested_limit, 50)  # 50件取得→高精度な5件にリランク可能

        # ✅ 配列で受け取る（後方互換性のため単一値もサポート）
        workspaces = data.get('workspaces', [])
        doc_types = data.get('doc_types', [])

        # 後方互換性: 単一のworkspaceパラメータもサポート
        if not workspaces and data.get('workspace'):
            workspaces = [data.get('workspace')]

        enable_query_expansion = data.get('enable_query_expansion', False)  # デフォルトで無効

        print(f"[DEBUG] 検索リクエスト: query='{query}', limit={limit}, workspaces={workspaces}, doc_types={doc_types}")

        if not query:
            return jsonify({'success': False, 'error': 'クエリが空です'}), 400

        # ユーザーコンテキストを読み込み、関連情報を抽出（検索用：軽量）
        from A_common.utils.context_extractor import ContextExtractor
        from A_common.config.yaml_loader import load_user_context

        user_context = load_user_context()
        context_extractor = ContextExtractor(user_context)
        extracted_context = context_extractor.extract_relevant_context(
            query,
            include_schedules=False  # 検索時はスケジュール不要
        )
        context_string = context_extractor.build_search_context_string(extracted_context)

        # クエリ拡張を適用（有効な場合）
        expanded_query = query
        expansion_info = None

        # ユーザーコンテキストがあればクエリに追加
        if context_string:
            expanded_query = f"{query} {context_string}"
            print(f"[DEBUG] コンテキスト追加: '{query}' → '{expanded_query}'")

        if enable_query_expansion:
            expansion_result = query_expander.expand_query(expanded_query)
            if expansion_result.get('expansion_applied'):
                expanded_query = expansion_result.get('expanded_query', expanded_query)
                expansion_info = {
                    'original': query,
                    'expanded': expanded_query,
                    'keywords': expansion_result.get('keywords', [])
                }
                print(f"[DEBUG] クエリ拡張適用: '{query}' → '{expanded_query}'")
            else:
                print(f"[DEBUG] クエリ拡張スキップ: '{expanded_query}'")

        # Embeddingを生成（拡張されたクエリを使用）
        embedding = llm_client.generate_embedding(expanded_query)

        # ベクトル検索を実行（同期ラッパーを使用）
        # 拡張されたクエリをテキスト検索にも使用
        results = db_client.search_documents_sync(
            expanded_query,
            embedding,
            limit,
            doc_types if doc_types else None
        )

        print(f"[DEBUG] 検索結果: {len(results)} 件（doc_types={doc_types}）")

        print(f"[DEBUG] 最終検索結果: {len(results)} 件返却")

        response_data = {
            'success': True,
            'results': results,
            'count': len(results)
        }

        # クエリ拡張情報を含める（デバッグ用）
        if expansion_info:
            response_data['query_expansion'] = expansion_info

        return jsonify(response_data)

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/answer', methods=['POST'])
def generate_answer():
    """
    回答生成API（構成フロー対応）
    検索結果を元にAIで自然な回答を生成
    """
    try:
        # クライアント取得（遅延初期化）
        db_client, llm_client, _ = get_clients()

        data = request.get_json()
        query = data.get('query', '')
        documents = data.get('documents', [])
        flow_id = data.get('flow', 'flash-x1')  # ユーザーが選択した構成フロー

        if not query:
            return jsonify({'success': False, 'error': 'クエリが空です'}), 400

        # ✅ 構成フローを取得
        from A_common.config.model_tiers import ResearchFlow
        flow_config = ResearchFlow.get_flow(flow_id)
        steps = flow_config.get('steps', ['gemini-2.5-flash'])

        print(f"[INFO] 構成フロー実行: {flow_id} ({len(steps)}ステップ)")

        # ✅ 構成フローの実行
        current_query = query
        current_documents = documents

        for step_idx, model_name in enumerate(steps, 1):
            print(f"[INFO] ステップ {step_idx}/{len(steps)}: {model_name}")

            # 2ステップ目以降は、前の回答を使ってクエリを改善
            if step_idx > 1 and 'answer' in locals():
                # クエリ改善プロンプト
                refinement_prompt = f"""以下のユーザーの質問と、これまでの回答を踏まえて、より的確な検索クエリを生成してください。

【元の質問】
{query}

【これまでの回答】
{answer}

【指示】
- 元の質問の意図を保ちつつ、より具体的で詳細な検索キーワードを含むクエリを生成してください
- 回答から得られた重要なキーワードを追加してください
- 改善されたクエリのみを出力してください（説明は不要）

【改善されたクエリ】"""

                refinement_response = llm_client.call_model(
                    tier="ui_response",
                    prompt=refinement_prompt,
                    model_name=model_name
                )

                if refinement_response.get('success'):
                    current_query = refinement_response.get('content', current_query).strip()
                    print(f"[INFO] クエリ改善: '{query}' → '{current_query}'")

                    # 改善されたクエリで再検索
                    embedding = llm_client.generate_embedding(current_query)
                    current_documents = db_client.search_documents_sync(
                        current_query,
                        embedding,
                        limit=5,
                        doc_types=None
                    )
                    print(f"[INFO] 再検索結果: {len(current_documents)} 件")

            # 現在のステップで回答生成
            answer, model_used = _generate_answer_with_model(
                llm_client,
                model_name,
                query,
                current_documents,
                is_final_step=(step_idx == len(steps))
            )

            if not answer:
                return jsonify({
                    'success': False,
                    'error': f'ステップ{step_idx}で回答生成に失敗しました'
                }), 500

        # 最終回答を返す
        return jsonify({
            'success': True,
            'answer': answer,
            'model': model_used,
            'provider': 'gemini',
            'flow': flow_id,
            'steps': len(steps)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def _generate_answer_with_model(
    llm_client,
    model_name: str,
    query: str,
    documents: List[Dict[str, Any]],
    is_final_step: bool = True
) -> tuple:
    """
    指定されたモデルで回答を生成

    Args:
        llm_client: LLMクライアント
        model_name: 使用するモデル名
        query: ユーザーの質問
        documents: 検索結果
        is_final_step: 最終ステップかどうか

    Returns:
        (回答テキスト, モデル名)
    """
    try:
        # ユーザーコンテキストを読み込み、関連情報を抽出（回答生成用：詳細）
        from A_common.utils.context_extractor import ContextExtractor
        from A_common.config.yaml_loader import load_user_context

        user_context = load_user_context()
        context_extractor = ContextExtractor(user_context)
        extracted_context = context_extractor.extract_relevant_context(
            query,
            include_schedules=True  # 回答生成時はスケジュールも含める
        )
        user_context_prompt = context_extractor.build_answer_context_string(extracted_context)

        # ドキュメントコンテキストを構築
        context = _build_context(documents)

        # ✅ コンテキストの文字数制限（2025年モデル対応: Gemini 2.5 Flashは100万トークン対応）
        MAX_CONTEXT_LENGTH = 100000  # 約10万文字まで（Gemini 2.5の性能に合わせて大幅引き上げ）
        if len(context) > MAX_CONTEXT_LENGTH:
            context = context[:MAX_CONTEXT_LENGTH] + "\n\n[... 以降は省略されました ...]"
            print(f"[WARNING] コンテキストを切り詰めました: {len(context)} → {MAX_CONTEXT_LENGTH} 文字")

        # プロンプトを作成（Phase 2.2.3: 構造的クエリ対応 + ユーザーコンテキスト追加）
        prompt_parts = []

        prompt_parts.append("以下の文書情報を参考に、ユーザーの質問に日本語で回答してください。")

        # ユーザーコンテキストがあれば追加
        if user_context_prompt:
            prompt_parts.append(f"\n{user_context_prompt}\n")

        prompt_parts.append(f"""
【質問】
{query}

【参考文書】
{context}

【回答の条件】
- 参考文書の情報を基に、正確に回答してください
- **ユーザーの前提情報を考慮してください**（上記に記載された子供の情報、学校や塾のスケジュールなど）
- **重要：ファイル名も重視してください**
  * ユーザーが特定のファイル名を質問している場合（例：「学年通信（29）」）、そのファイル名と完全一致または部分一致する文書を優先的に参照してください
  * ファイル名が一致する文書があれば、必ずその内容を回答に含めてください
- **【表データ】**が含まれている場合、表形式の情報を積極的に活用してください
  * 時間割やスケジュールに関する質問には、表データから該当する科目や予定を抽出して回答してください
  * 議事録の質問には、議題グループや担当者・期限情報を参照してください
  * 複数のクラスやグループがある場合、質問に該当するものを絞り込んで回答してください
- 情報が不足している場合は、その旨を伝えてください
- 簡潔で分かりやすい回答を心がけてください
- 回答の最後に、参考にした文書のタイトルを列挙してください

【回答】
""")

        # プロンプトを結合
        prompt = "\n".join(prompt_parts)

        # AIモデルで回答生成
        response = llm_client.call_model(
            tier="ui_response",
            prompt=prompt,
            model_name=model_name
        )

        if not response.get('success'):
            return None, None

        return response.get('content', ''), model_name

    except Exception as e:
        print(f"[ERROR] 回答生成エラー: {e}")
        return None, None


def _format_table_to_markdown(table_data: Dict[str, Any]) -> str:
    """
    表データをMarkdown形式のテーブルに変換（Phase 2.2.3 構造的クエリ対応）

    Args:
        table_data: 表データ（table_type, headers, rows などを含む）

    Returns:
        Markdown形式のテーブル文字列
    """
    try:
        table_type = table_data.get("table_type", "table")
        headers = table_data.get("headers", [])

        # ヘッダー行の構築
        if isinstance(headers, list) and headers:
            # シンプルなリスト形式のヘッダー
            header_line = "| " + " | ".join(str(h) for h in headers) + " |"
            separator_line = "|" + "|".join(["---" for _ in headers]) + "|"
            markdown_lines = [f"\n**表形式データ ({table_type})**\n", header_line, separator_line]
        elif isinstance(headers, dict):
            # 複雑なヘッダー構造（例: class_timetable の classes）
            classes = headers.get("classes", [])
            if classes:
                header_line = "| 日 | " + " | ".join(str(c) for c in classes) + " |"
                separator_line = "|" + "|".join(["---" for _ in range(len(classes) + 1)]) + "|"
                markdown_lines = [f"\n**クラス別時間割 ({table_type})**\n", header_line, separator_line]
            else:
                markdown_lines = [f"\n**表形式データ ({table_type})**\n"]
        else:
            markdown_lines = [f"\n**表形式データ ({table_type})**\n"]

        # 行データの処理
        rows = table_data.get("rows", [])
        if rows:
            for row in rows:
                # 行が辞書形式の場合
                if isinstance(row, dict):
                    # cells フィールドがある場合
                    if "cells" in row:
                        cells = row["cells"]
                        cell_values = []
                        for cell in cells:
                            if isinstance(cell, dict):
                                value = cell.get("value", "")
                                cell_values.append(str(value))
                            else:
                                cell_values.append(str(cell))
                        row_line = "| " + " | ".join(cell_values) + " |"
                        markdown_lines.append(row_line)
                    else:
                        # 通常の辞書行（キー: 値）
                        values = [str(v) for v in row.values()]
                        row_line = "| " + " | ".join(values) + " |"
                        markdown_lines.append(row_line)

        # daily_schedule や agenda_groups などの特殊構造
        if "daily_schedule" in table_data:
            markdown_lines.append("\n**日別スケジュール:**")
            for schedule in table_data["daily_schedule"]:
                day = schedule.get("day", "")
                markdown_lines.append(f"\n- **{day}曜日:**")

                if "class_schedules" in schedule:
                    for class_schedule in schedule["class_schedules"]:
                        class_name = class_schedule.get("class", "")
                        subjects = class_schedule.get("subjects", []) or class_schedule.get("periods", [])
                        markdown_lines.append(f"  - {class_name}: {', '.join(str(s) for s in subjects)}")

        if "agenda_groups" in table_data:
            markdown_lines.append("\n**議題グループ:**")
            for group in table_data["agenda_groups"]:
                topic = group.get("topic", "")
                markdown_lines.append(f"\n- **{topic}:**")
                for item in group.get("items", []):
                    decision = item.get("decision", "")
                    assignee = item.get("assignee", "")
                    deadline = item.get("deadline", "")
                    markdown_lines.append(f"  - {decision} (担当: {assignee}, 期限: {deadline})")

        return "\n".join(markdown_lines)

    except Exception as e:
        return f"\n[表データの変換エラー: {str(e)}]\n"


def _format_metadata(metadata: Dict[str, Any], indent: int = 0) -> str:
    """
    メタデータを見やすく整形（Phase 2.2.3: tables フィールド対応）

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
        # Phase 2.2.3: tables フィールドを特別に処理
        if key == "tables" and isinstance(value, list):
            if not value:
                continue
            lines.append(f"{prefix}【表データ】")
            for idx, table in enumerate(value, 1):
                if isinstance(table, dict):
                    # 表をMarkdown形式に変換
                    markdown_table = _format_table_to_markdown(table)
                    lines.append(markdown_table)
            continue

        # 通常のメタデータ処理
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
        # ✅ contentを優先的に使用、フォールバックとしてsummary, attachment_textをチェック
        content = doc.get('content') or doc.get('summary') or doc.get('attachment_text', '')
        similarity = doc.get('similarity', 0)
        metadata = doc.get('metadata', {})

        # 基本情報
        context_part = f"""
【文書{idx}】
ファイル名: {file_name}
文書タイプ: {doc_type}
類似度: {similarity:.2f}"""

        # コンテンツ追加（contentが空でない場合）
        if content:
            context_part += f"\n内容: {content}"

        # メタデータを整形して追加
        if metadata:
            formatted_metadata = _format_metadata(metadata)
            if formatted_metadata:
                context_part += f"\n\n詳細情報:\n{formatted_metadata}"

        context_parts.append(context_part)

    # ✅ デバッグ用: コンテキストの文字数をログ出力
    final_context = "\n".join(context_parts)
    print(f"[DEBUG] コンテキスト文字数: {len(final_context)} 文字")
    print(f"[DEBUG] 文書数: {len(documents)} 件")

    return final_context


@app.route('/api/health', methods=['GET'])
def health_check():
    """ヘルスチェックエンドポイント"""
    return jsonify({
        'status': 'ok',
        'message': 'Document Q&A System is running'
    })


@app.route('/api/debug/database', methods=['GET'])
def debug_database():
    """データベース接続とワークスペース情報のデバッグエンドポイント"""
    try:
        # クライアント取得
        db_client, _, _ = get_clients()

        # source_documentsテーブルの件数を確認
        count_response = db_client.client.table('10_rd_source_docs').select('id', count='exact').limit(1).execute()
        total_count = count_response.count if hasattr(count_response, 'count') else 'unknown'

        # サンプルデータを取得
        sample_response = db_client.client.table('10_rd_source_docs').select('workspace, doc_type').limit(10).execute()
        samples = sample_response.data if sample_response.data else []

        # get_workspace_hierarchy()を実行
        hierarchy = db_client.get_workspace_hierarchy()

        # 環境変数の確認（セキュリティのため一部のみ）
        supabase_url = os.getenv('SUPABASE_URL', 'NOT_SET')
        supabase_key_set = 'YES' if os.getenv('SUPABASE_KEY') else 'NO'

        return jsonify({
            'success': True,
            'database_info': {
                'total_documents': total_count,
                'sample_count': len(samples),
                'samples': samples[:5],  # 最初の5件のみ
                'workspace_count': len(hierarchy),
                'workspaces': list(hierarchy.keys()),
                'hierarchy_sample': {k: v for k, v in list(hierarchy.items())[:2]}  # 最初の2つのみ
            },
            'env_check': {
                'supabase_url_set': supabase_url[:30] + '...' if supabase_url != 'NOT_SET' else 'NOT_SET',
                'supabase_key_set': supabase_key_set
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__
        }), 500


if __name__ == '__main__':
    # 開発環境での実行
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)
