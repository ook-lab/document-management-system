"""
Document Review UI (v2.0 - Tab Edition)
人間がAIの抽出結果を確認・修正するための管理画面

新機能:
- タブベースUI (フォーム編集 / 表エディタ / JSONプレビュー)
- スキーマベースのフォーム編集
- データフレームによる表形式編集
- JSON差分表示
"""
import sys
from pathlib import Path

# プロジェクトのルートディレクトリをPythonパスに追加
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

import streamlit as st
import json
import tempfile
from typing import Dict, Any, Optional, List
import pandas as pd
from loguru import logger

from core.database.client import DatabaseClient
from core.connectors.google_drive import GoogleDriveConnector

# 新しいコンポーネントとユーティリティをインポート
from ui.utils.schema_detector import SchemaDetector
from ui.components.form_editor import render_form_editor
from ui.components.table_editor import render_table_editor, _render_array_table, _format_field_name
from ui.components.json_preview import render_json_preview, render_json_diff


def detect_structured_fields(metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    メタデータから構造化データフィールドを自動検出

    Args:
        metadata: メタデータ辞書

    Returns:
        構造化フィールドのリスト [{"key": str, "label": str, "data": list}, ...]
    """
    structured_fields = []

    logger.info("=" * 60)
    logger.info("🔍 構造化フィールド検出を開始")
    logger.info(f"メタデータのキー数: {len(metadata)}")
    logger.info("=" * 60)

    for key, value in metadata.items():
        # デバッグログ: 全てのキーと値の型を出力
        logger.debug(f"Key: {key}, Type: {type(value)}, Value start: {str(value)[:50]}")

        # extracted_tablesの特別処理
        if key == "extracted_tables":
            logger.info(f"🎯 FOUND extracted_tables! Type: {type(value)}, Length: {len(value) if isinstance(value, list) else 'N/A'}")
            if isinstance(value, list):
                logger.info(f"  First element type: {type(value[0]) if len(value) > 0 else 'empty'}")

        # text_blocksはフォーム編集で表示するため、構造化フィールドとして検出しない
        if key == "text_blocks":
            logger.info(f"⚠️ '{key}' はフォーム編集で表示するため、構造化フィールドから除外")
            continue

        # _list, _blocks, _matrix, _tables で終わるキー、または structured_tables, weekly_schedule, extracted_tables を構造化データとして認識
        if (key.endswith("_list") or key.endswith("_blocks") or
            key.endswith("_matrix") or key.endswith("_tables") or
            key == "structured_tables" or key == "weekly_schedule" or key == "extracted_tables"):
            logger.info(f"✓ '{key}' は構造化データフィールドとして検出")

            if not isinstance(value, list):
                logger.warning(f"  ⚠️ '{key}' はリストではありません。Type: {type(value)}")
                continue

            if len(value) == 0:
                logger.warning(f"  ⚠️ '{key}' は空のリストです")
                continue

            logger.info(f"  ✓ '{key}' はリストで、要素数: {len(value)}")

            # extracted_tablesは特別処理（文字列のリストをパースして構造化データに変換）
            if key == "extracted_tables":
                logger.info(f"  ✓ '{key}' は extracted_tables として検出 - パース処理を実行")
                from ui.utils.table_parser import parse_extracted_tables
                parsed_tables = parse_extracted_tables(value)
                if parsed_tables:
                    logger.info(f"  ✓ {len(parsed_tables)} 個の表をパースしました")
                    structured_fields.append({
                        "key": key,
                        "label": _format_field_name(key),
                        "data": parsed_tables
                    })
                else:
                    logger.warning(f"  ⚠️ '{key}' のパースに失敗しました")
                continue

            # 配列の最初の要素が辞書であることを確認（構造化データの証拠）
            if isinstance(value[0], dict):
                logger.info(f"  ✓ '{key}' の最初の要素は辞書です → 構造化フィールドとして検出!")
                structured_fields.append({
                    "key": key,
                    "label": _format_field_name(key),
                    "data": value
                })
            else:
                logger.warning(f"  ⚠️ '{key}' の最初の要素は辞書ではありません。Type: {type(value[0])}")

    logger.info("=" * 60)
    logger.info(f"🎯 検出された構造化フィールド数: {len(structured_fields)}")
    for field in structured_fields:
        logger.info(f"  - {field['key']} ({field['label']}) - {len(field['data'])} 件")
    logger.info("=" * 60)

    return structured_fields


def download_file_from_drive(source_id: str, file_name: str) -> Optional[str]:
    """
    Google Driveからファイルを一時ディレクトリにダウンロード

    Args:
        source_id: Google DriveのファイルID
        file_name: ファイル名

    Returns:
        ダウンロードされたファイルのパス、失敗時はNone
    """
    try:
        drive_connector = GoogleDriveConnector()
        temp_dir = tempfile.gettempdir()
        file_path = drive_connector.download_file(source_id, file_name, temp_dir)
        return file_path
    except Exception as e:
        st.error(f"ファイルのダウンロードに失敗しました: {e}")
        return None


def pdf_review_ui():
    """PDFレビューUIロジック"""
    st.markdown("#### 📋 PDFドキュメントレビュー")
    st.caption("AIが抽出したメタデータを確認・修正できます")

    # データベースクライアントとスキーマ検出器の初期化
    try:
        db_client = DatabaseClient()
        schema_detector = SchemaDetector()
    except Exception as e:
        st.error(f"初期化エラー: {e}")
        st.stop()

    # サイドバー: 検索とフィルタ設定
    st.sidebar.header("🔍 検索 & フィルタ")

    # Workspaceフィルタ
    workspace_filter = st.sidebar.selectbox(
        "Workspace",
        options=["全て", "business", "personal"],
        index=0,
        help="ワークスペースでフィルタリング"
    )

    # 検索ボックス
    search_query = st.sidebar.text_input(
        "IDやファイル名で検索",
        placeholder="例: 学年通信, abc123...",
        help="検索ワードを入力すると、レビュー状態に関係なく全データから検索します"
    )

    # 取得件数
    limit = st.sidebar.number_input(
        "取得件数",
        min_value=10,
        max_value=500,
        value=50,
        step=10,
        help="表示するドキュメントの最大件数"
    )

    # モード表示
    if search_query:
        st.sidebar.info("🔎 **検索モード**: 全データから検索中")
    else:
        st.sidebar.success("📝 **通常モード**: 未レビューのみ表示")

    # 進捗表示
    st.sidebar.markdown("---")
    st.sidebar.header("📊 レビュー進捗")
    progress_data = db_client.get_review_progress()

    col_p1, col_p2 = st.sidebar.columns(2)
    with col_p1:
        st.metric("未レビュー", f"{progress_data['unreviewed']} 件")
    with col_p2:
        st.metric("完了", f"{progress_data['reviewed']} 件")

    st.sidebar.progress(progress_data['progress_percent'] / 100)
    st.sidebar.caption(f"進捗率: {progress_data['progress_percent']}%")

    # リスト更新ボタン
    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 リストを更新", use_container_width=True, key="refresh_pdf_list"):
        st.rerun()

    # レビュー対象ドキュメントを取得
    with st.spinner("ドキュメントを取得中..."):
        # Workspaceフィルタの値を変換（"全て"の場合はNone）
        workspace_value = workspace_filter if workspace_filter != "全て" else None

        documents = db_client.get_documents_for_review(
            limit=limit,
            search_query=search_query if search_query else None,
            workspace=workspace_value
        )

    # デバッグログ: 取得後の確認
    logger.info(f"DBから取得したドキュメント数: {len(documents)}件")

    if not documents:
        st.info("レビュー対象のドキュメントがありません")
        return

    st.sidebar.success(f"✅ {len(documents)}件のドキュメント")

    # ドキュメントリストをDataFrameで表示（チェックボックス付き）
    df_data = []
    for idx, doc in enumerate(documents):
        df_data.append({
            '選択': False,  # チェックボックス用
            'ID': doc.get('id', '')[:8],
            'ファイル名': doc.get('file_name', ''),
            '文書タイプ': doc.get('doc_type', ''),
            '信頼度': round(doc.get('confidence') or 0, 3),
            '作成日時': doc.get('created_at', '')[:10]
        })

    df = pd.DataFrame(df_data)

    # デバッグログ: DataFrame作成後の確認
    logger.info(f"表示用DataFrameの行数: {len(df)}件")

    st.subheader("📁 レビュー対象ドキュメント一覧")

    # まとめて削除機能
    col_list_header, col_bulk_delete = st.columns([3, 1])
    with col_list_header:
        st.markdown("一覧から選択してまとめて削除できます")
    with col_bulk_delete:
        # セッション状態でチェックボックスの状態を管理
        if 'selected_docs' not in st.session_state:
            st.session_state.selected_docs = []

    # データエディタでチェックボックス付きの表を表示
    edited_df = st.data_editor(
        df,
        use_container_width=True,
        height=200,
        hide_index=True,
        column_config={
            "選択": st.column_config.CheckboxColumn(
                "選択",
                help="削除するドキュメントを選択",
                default=False,
            )
        },
        disabled=["ID", "ファイル名", "文書タイプ", "信頼度", "作成日時"],
        key="document_list_editor"
    )

    # 選択されたドキュメントを取得
    selected_indices = edited_df[edited_df['選択'] == True].index.tolist()
    selected_count = len(selected_indices)

    # まとめて削除ボタン
    if selected_count > 0:
        col_bulk1, col_bulk2, col_spacer = st.columns([1, 1, 2])

        with col_bulk1:
            st.warning(f"⚠️ {selected_count}件のドキュメントが選択されています")

        with col_bulk2:
            # 一括削除確認用のセッション状態
            if 'bulk_delete_confirm' not in st.session_state:
                st.session_state.bulk_delete_confirm = False

            if not st.session_state.bulk_delete_confirm:
                if st.button(f"🗑️ {selected_count}件をまとめて削除", use_container_width=True, type="secondary"):
                    st.session_state.bulk_delete_confirm = True
                    st.rerun()
            else:
                if st.button(f"✅ {selected_count}件の削除を実行", use_container_width=True, type="primary"):
                    with st.spinner(f"{selected_count}件のドキュメントを削除中..."):
                        success_count = 0
                        fail_count = 0

                        for idx in selected_indices:
                            doc = documents[idx]
                            doc_id = doc.get('id')
                            file_id = doc.get('drive_file_id') or doc.get('source_id')

                            # Google Driveから削除
                            if file_id:
                                try:
                                    drive_connector = GoogleDriveConnector()
                                    drive_connector.trash_file(file_id)
                                except Exception as e:
                                    logger.error(f"Google Drive削除エラー: {e}")

                            # データベースから削除
                            if db_client.delete_document(doc_id):
                                success_count += 1
                            else:
                                fail_count += 1

                        if success_count > 0:
                            st.success(f"✅ {success_count}件のドキュメントを削除しました")
                        if fail_count > 0:
                            st.error(f"❌ {fail_count}件の削除に失敗しました")

                        st.session_state.bulk_delete_confirm = False
                        st.balloons()
                        import time
                        time.sleep(1)
                        st.rerun()

                if st.button("❌ キャンセル", use_container_width=True):
                    st.session_state.bulk_delete_confirm = False
                    st.rerun()

    # ドキュメント選択
    st.subheader("🔍 ドキュメント詳細")

    # セレクトボックスのキーに検索クエリを含めることで、モード変更時にリセット
    selector_key = f"document_selector_{search_query or 'normal'}"

    selected_index = st.selectbox(
        "編集するドキュメントを選択",
        range(len(documents)),
        format_func=lambda i: f"{documents[i].get('file_name', 'Unknown')} (信頼度: {documents[i].get('confidence') or 0:.3f})",
        key=selector_key
    )

    selected_doc = documents[selected_index]
    doc_id = selected_doc.get('id')

    # デバッグ: 選択されたドキュメントを確認
    logger.info(f"=== 選択されたドキュメント ===")
    logger.info(f"selected_index: {selected_index}")
    logger.info(f"doc_id: {doc_id}")
    logger.info(f"file_name: {selected_doc.get('file_name')}")

    # 先にドキュメント情報を取得（st.rerun()の前に）
    drive_file_id = selected_doc.get('drive_file_id')
    source_id = selected_doc.get('source_id')
    file_id = drive_file_id or source_id
    file_name = selected_doc.get('file_name', 'unknown')
    doc_type = selected_doc.get('doc_type', '')

    # metadataをパース（JSON文字列の場合と辞書の場合の両方に対応）
    metadata = selected_doc.get('metadata') or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse metadata JSON for doc_id: {doc_id}")
            metadata = {}

    # extracted_tables カラムの内容を metadata に統合
    if 'extracted_tables' in selected_doc and selected_doc['extracted_tables']:
        extracted_tables = selected_doc['extracted_tables']
        if isinstance(extracted_tables, str):
            try:
                extracted_tables = json.loads(extracted_tables)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse extracted_tables JSON for doc_id: {doc_id}")
                extracted_tables = None
        if extracted_tables:
            metadata['extracted_tables'] = extracted_tables
            logger.info(f"Added extracted_tables to metadata: {len(extracted_tables)} tables")

    confidence = selected_doc.get('confidence') or 0

    # デバッグ: メタデータの状態を確認
    logger.info(f"metadata keys: {list(metadata.keys())}")
    logger.info(f"metadata size: {len(str(metadata))} bytes")
    if 'extracted_tables' in metadata:
        logger.info(f"extracted_tables found in metadata: {len(metadata['extracted_tables'])} tables")

    # ドキュメント変更を検出して、セッション状態をリセット
    if 'previous_doc_id' not in st.session_state:
        st.session_state.previous_doc_id = doc_id

    if st.session_state.previous_doc_id != doc_id:
        # ドキュメントが変更された場合、全ての編集関連のキーをクリア
        logger.info(f"ドキュメント変更を検出: {st.session_state.previous_doc_id} -> {doc_id}")
        logger.info(f"新しいファイル名: {file_name}")

        # 編集関連のセッション状態をクリア
        # 古いドキュメントのキーを削除
        old_doc_id = st.session_state.previous_doc_id
        keys_to_remove = [
            key for key in st.session_state.keys()
            if (key.startswith('form_') or
                key.startswith(f'json_editor_{old_doc_id}') or
                key.startswith(f'text_editor_{old_doc_id}') or
                key.startswith('table_editor_'))
        ]

        for key in keys_to_remove:
            del st.session_state[key]
            logger.debug(f"  削除: {key}")

        st.session_state.previous_doc_id = doc_id
        logger.info(f"セッション状態をクリア: {len(keys_to_remove)} keys removed")

        # ページを再レンダリング
        st.rerun()

    # 基本情報表示
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown(f"**ファイル名**: {file_name}")
    with col2:
        st.markdown(f"**文書タイプ**: {doc_type}")
    with col3:
        st.markdown(f"**信頼度**: {confidence:.3f}")

    st.markdown("---")

    # 修正履歴とロールバック機能（Phase 2）
    latest_correction_id = selected_doc.get('latest_correction_id')
    if latest_correction_id:
        with st.expander("📜 修正履歴とロールバック", expanded=False):
            correction_history = db_client.get_correction_history(doc_id, limit=5)

            if correction_history:
                st.markdown(f"**修正回数**: {len(correction_history)}回")

                # 最新の修正情報
                latest_correction = correction_history[0]
                st.markdown(f"**最新の修正日時**: {latest_correction.get('corrected_at')}")
                if latest_correction.get('corrector_email'):
                    st.markdown(f"**修正者**: {latest_correction.get('corrector_email')}")

                # ロールバックボタン
                col_rollback, col_spacer = st.columns([1, 2])
                with col_rollback:
                    if st.button("⏮️ ロールバック（元に戻す）", use_container_width=True, type="secondary"):
                        with st.spinner("ロールバック中..."):
                            rollback_success = db_client.rollback_document(doc_id)

                        if rollback_success:
                            st.success("✅ ロールバックに成功しました！前の状態に戻りました。")
                            st.rerun()
                        else:
                            st.error("❌ ロールバックに失敗しました")

                # 修正履歴の詳細表示
                with st.expander("修正履歴の詳細を表示", expanded=False):
                    for idx, correction in enumerate(correction_history):
                        st.markdown(f"### 修正 #{idx + 1}")
                        st.markdown(f"**日時**: {correction.get('corrected_at')}")
                        if correction.get('notes'):
                            st.markdown(f"**メモ**: {correction.get('notes')}")

                        # 修正前後の差分を表示
                        col_before, col_after = st.columns(2)
                        with col_before:
                            st.markdown("**修正前**")
                            st.json(correction.get('old_metadata', {}), expanded=False)
                        with col_after:
                            st.markdown("**修正後**")
                            st.json(correction.get('new_metadata', {}), expanded=False)

                        st.markdown("---")
            else:
                st.info("修正履歴がありません")

    st.markdown("---")

    # レイアウト: 左にPDFプレビュー、右に編集タブ
    col_left, col_right = st.columns([1, 1.2])

    with col_left:
        st.markdown("### 📄 PDFプレビュー")

        # PDFのダウンロードと表示
        if file_id and file_name.lower().endswith('.pdf'):
            with st.spinner("PDFをダウンロード中..."):
                file_path = download_file_from_drive(file_id, file_name)

            if file_path and Path(file_path).exists():
                # デバッグログ: PDFプレビュー前の確認
                import os
                logger.info(f"PDFプレビュー開始。ローカルパス: {file_path}")
                logger.info(f"ファイルサイズ: {os.path.getsize(file_path)} bytes")

                # PDFプレビュー表示（ファイルパスを直接渡す）
                try:
                    from streamlit_pdf_viewer import pdf_viewer
                    logger.info("streamlit_pdf_viewer を使用してPDF表示（ファイルパス直接渡し）")
                    # ファイルパスを直接渡すことで、巨大なBase64文字列の生成を回避
                    pdf_viewer(file_path, height=700)
                except ImportError:
                    logger.warning("streamlit_pdf_viewer がインストールされていません。ダウンロードボタンを表示します")
                    st.warning("PDFビューアーライブラリがインストールされていません")
                    # ダウンロードボタン用にバイトデータを読み込む
                    with open(file_path, 'rb') as f:
                        pdf_bytes = f.read()
                    st.download_button(
                        label="📥 PDFをダウンロード",
                        data=pdf_bytes,
                        file_name=file_name,
                        mime="application/pdf",
                        use_container_width=True
                    )
                except Exception as e:
                    logger.error(f"PDFプレビュー表示エラー: {e}", exc_info=True)
                    st.warning(f"PDFプレビュー表示エラー: {e}")
                    # エラー時のダウンロードボタン用にバイトデータを読み込む
                    try:
                        with open(file_path, 'rb') as f:
                            pdf_bytes = f.read()
                        st.download_button(
                            label="📥 PDFをダウンロード",
                            data=pdf_bytes,
                            file_name=file_name,
                            mime="application/pdf",
                            use_container_width=True
                        )
                    except Exception as read_error:
                        logger.error(f"PDFファイル読み込みエラー: {read_error}", exc_info=True)
                        st.error("PDFファイルの読み込みに失敗しました")
            else:
                logger.warning(f"PDFファイルを読み込めませんでした。file_path={file_path}, exists={Path(file_path).exists() if file_path else False}")
                st.warning("PDFファイルを読み込めませんでした")
        else:
            st.info("PDFファイル以外はプレビューできません")

    with col_right:
        st.markdown("### ✏️ メタデータ編集")

        # スキーマを検出
        detected_schema = schema_detector.detect_schema(doc_type, metadata)

        if detected_schema:
            st.info(f"🎯 検出されたスキーマ: **{detected_schema}**")
            editable_fields = schema_detector.get_editable_fields(detected_schema)
        else:
            st.warning("⚠️ スキーマが検出されませんでした。JSON編集モードを使用してください。")
            editable_fields = []

        # 【動的タブ生成】構造化データフィールドを自動検出
        structured_fields = detect_structured_fields(metadata)

        # 構造化フィールドのキーセットを作成（フォーム編集から除外するため）
        structured_field_keys = {field["key"] for field in structured_fields}

        # タブリストを動的に構築
        tab_names = ["📝 フォーム編集"]  # フォーム編集タブのみ

        # 構造化データごとにタブを追加
        logger.info(f"🏷️ タブ生成: 構造化データタブを {len(structured_fields)} 個追加します")
        for field in structured_fields:
            logger.info(f"  タブ追加: {field['label']} (キー: {field['key']})")
            tab_names.append(field["label"])

        # 固定タブ：JSONプレビュー
        tab_names.append("🔍 JSONプレビュー")

        logger.info(f"📑 生成されるタブ一覧 ({len(tab_names)} 個): {tab_names}")

        # タブを動的に生成
        tabs = st.tabs(tab_names)
        edited_metadata = None

        # タブ1: フォーム編集
        with tabs[0]:
            if editable_fields:
                # 構造化データフィールドをフォームから除外
                form_fields = [f for f in editable_fields if f["name"] not in structured_field_keys]

                if form_fields:
                    edited_metadata = render_form_editor(metadata, form_fields, doc_id)
                else:
                    st.info("このドキュメントのフィールドは全て専用タブで編集できます")
                    st.markdown("各データタブまたはJSONプレビュータブをご利用ください")
            else:
                st.info("フォーム編集には対応するスキーマが必要です")

        # タブ2以降: 構造化データタブ（動的に生成）
        for idx, field in enumerate(structured_fields):
            with tabs[idx + 1]:  # フォーム編集の次から
                logger.info(f"📊 タブ {idx + 1} をレンダリング: {field['label']} ({field['key']})")
                logger.info(f"  データ件数: {len(field['data'])} 件")

                st.markdown(f"### {field['label']}")
                st.markdown("表形式で編集できます")
                st.markdown("---")

                # 表エディタでレンダリング
                edited_value = _render_array_table(
                    field["key"],
                    field["data"],
                    field["label"]
                )

                # edited_metadataを初期化（必要に応じて）
                if edited_metadata is None:
                    edited_metadata = metadata.copy()

                edited_metadata[field["key"]] = edited_value
                logger.info(f"  ✓ {field['label']} タブのレンダリング完了")

        # 最後のタブ: JSONプレビュー
        with tabs[-1]:
            edited_metadata = render_json_preview(metadata, editable=True, key_suffix=doc_id)

        # 保存ボタンエリア
        st.markdown("---")

        # レビュー状態の表示
        is_reviewed = selected_doc.get('is_reviewed', False)
        if is_reviewed:
            reviewed_at = selected_doc.get('reviewed_at', '')
            reviewed_by = selected_doc.get('reviewed_by', '')
            st.info(f"✅ レビュー済み（{reviewed_at[:10] if reviewed_at else '日時不明'}）" +
                   (f" by {reviewed_by}" if reviewed_by else ""))

        col_save, col_validate, col_review, col_cancel = st.columns([1, 1, 1, 1])

        with col_validate:
            if st.button("🔍 変更を確認", use_container_width=True):
                if edited_metadata:
                    with st.expander("変更内容の詳細", expanded=True):
                        render_json_diff(metadata, edited_metadata)

        with col_save:
            if st.button("💾 保存", type="primary", use_container_width=True):
                if edited_metadata is None:
                    st.error("編集されたデータがありません")
                else:
                    # スキーマ検証
                    if detected_schema:
                        is_valid, errors = schema_detector.validate_metadata(detected_schema, edited_metadata)
                        if not is_valid:
                            st.error("❌ スキーマ検証エラー:")
                            for error in errors:
                                st.error(f"  - {error}")
                            st.stop()

                    # データベース更新（修正履歴を記録）
                    success = db_client.record_correction(
                        doc_id=doc_id,
                        new_metadata=edited_metadata,
                        new_doc_type=doc_type,
                        corrector_email=None,  # 将来的に認証情報から取得
                        notes="Review UIからの手動修正"
                    )

                    if success:
                        st.success("✅ 保存に成功しました！修正履歴が記録されました。")
                        st.balloons()
                        # ページをリロード
                        st.rerun()
                    else:
                        st.error("❌ 保存に失敗しました")

        with col_review:
            # レビュー状態切り替えボタン
            if is_reviewed:
                # レビュー済み → 未完了に戻す
                if st.button("↩️ 未完了に戻す", use_container_width=True, type="secondary"):
                    success = db_client.mark_document_unreviewed(doc_id)
                    if success:
                        st.success("✅ 未完了に戻しました")
                        st.rerun()
                    else:
                        st.error("❌ 操作に失敗しました")
            else:
                # 未レビュー → チェック完了
                if st.button("✅ チェック完了", use_container_width=True, type="primary"):
                    success = db_client.mark_document_reviewed(doc_id)
                    if success:
                        st.success("✅ レビュー完了としてマークしました")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error("❌ 操作に失敗しました")

        with col_cancel:
            if st.button("🔄 リセット", use_container_width=True):
                st.rerun()

    # 削除機能（危険な操作のため、別セクションに配置）
    st.markdown("---")
    st.markdown("### ⚠️ 危険な操作")

    # 削除確認用のセッション状態
    delete_confirm_key = f"delete_confirm_{doc_id}"
    if delete_confirm_key not in st.session_state:
        st.session_state[delete_confirm_key] = False

    col_delete1, col_delete2, col_spacer = st.columns([1, 1, 2])

    with col_delete1:
        if not st.session_state[delete_confirm_key]:
            if st.button("🗑️ データを削除", use_container_width=True, type="secondary"):
                st.session_state[delete_confirm_key] = True
                st.rerun()
        else:
            st.warning("本当に削除しますか？")

    with col_delete2:
        if st.session_state[delete_confirm_key]:
            if st.button("✅ 削除を実行", use_container_width=True, type="primary"):
                with st.spinner("削除中..."):
                    # 1. まずGoogle Driveからファイルをゴミ箱に移動
                    drive_success = False
                    if file_id:
                        try:
                            drive_connector = GoogleDriveConnector()
                            drive_success = drive_connector.trash_file(file_id)
                            if drive_success:
                                st.success(f"✅ Google Driveのファイルをゴミ箱に移動しました")
                            else:
                                st.warning(f"⚠️ Google Driveファイルの削除に失敗しましたが、データベースからは削除します")
                        except Exception as e:
                            st.error(f"Google Drive削除エラー: {e}")
                            st.warning(f"⚠️ Google Driveファイルの削除に失敗しましたが、データベースからは削除します")
                    else:
                        st.warning("Google DriveのファイルIDが見つかりません。データベースのみ削除します。")

                    # 2. データベースから削除
                    db_success = db_client.delete_document(doc_id)

                    if db_success:
                        st.success("✅ データベースからドキュメントを削除しました")
                        st.balloons()
                        # 削除確認状態をリセット
                        st.session_state[delete_confirm_key] = False
                        # 少し待ってからリロード
                        import time
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ データベースからの削除に失敗しました")
                        st.session_state[delete_confirm_key] = False

            if st.button("❌ キャンセル", use_container_width=True):
                st.session_state[delete_confirm_key] = False
                st.rerun()

    # フッター
    st.markdown("---")
    col_footer1, col_footer2 = st.columns([3, 1])
    with col_footer1:
        st.caption("Document Management System - Review UI v2.0 (Tab Edition)")
    with col_footer2:
        st.caption(f"🎨 検出スキーマ: {detected_schema or 'N/A'}")


def main():
    """メインUIロジック - タブ切り替え"""
    st.set_page_config(
        page_title="Document Management System",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("📚 Document Management System")
    st.markdown("PDFレビューとメール受信トレイを統合管理")

    # トップレベルのタブ
    tab1, tab2 = st.tabs(["📋 PDFレビュー", "📬 メール受信トレイ"])

    with tab1:
        pdf_review_ui()

    with tab2:
        # メールUIをインポートして表示
        from ui.email_inbox import email_inbox_ui
        email_inbox_ui()


if __name__ == "__main__":
    main()
