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

    for key, value in metadata.items():
        # _list または _blocks で終わるキーを構造化データとして認識
        if (key.endswith("_list") or key.endswith("_blocks")) and isinstance(value, list) and len(value) > 0:
            # 配列の最初の要素が辞書であることを確認（構造化データの証拠）
            if isinstance(value[0], dict):
                structured_fields.append({
                    "key": key,
                    "label": _format_field_name(key),
                    "data": value
                })

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


def main():
    """メインUIロジック"""
    st.set_page_config(
        page_title="Document Review UI v2.0",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("📋 Document Review UI v2.0")
    st.markdown("AIが抽出したメタデータを**3つのタブ**で確認・修正できます")

    # データベースクライアントとスキーマ検出器の初期化
    try:
        db_client = DatabaseClient()
        schema_detector = SchemaDetector()
    except Exception as e:
        st.error(f"初期化エラー: {e}")
        st.stop()

    # サイドバー: フィルタ設定
    st.sidebar.header("🔧 フィルタ設定")
    limit = st.sidebar.number_input(
        "取得件数",
        min_value=10,
        max_value=500,
        value=100,
        step=10,
        help="表示するドキュメントの最大件数"
    )

    # レビュー対象ドキュメントを取得
    if st.sidebar.button("🔄 リストを更新", use_container_width=True):
        st.rerun()

    with st.spinner("ドキュメントを取得中..."):
        documents = db_client.get_documents_for_review(
            limit=limit
        )

    # デバッグログ: 取得後の確認
    logger.info(f"DBから取得したドキュメント数: {len(documents)}件")

    if not documents:
        st.info("レビュー対象のドキュメントがありません")
        return

    st.sidebar.success(f"✅ {len(documents)}件のドキュメント")

    # ドキュメントリストをDataFrameで表示
    df = pd.DataFrame([
        {
            'ID': doc.get('id', '')[:8],
            'ファイル名': doc.get('file_name', ''),
            '文書タイプ': doc.get('doc_type', ''),
            '信頼度': round(doc.get('confidence') or 0, 3),
            '作成日時': doc.get('created_at', '')[:10]
        }
        for doc in documents
    ])

    # デバッグログ: DataFrame作成後の確認
    logger.info(f"表示用DataFrameの行数: {len(df)}件")

    st.subheader("📁 レビュー対象ドキュメント一覧")
    st.dataframe(df, use_container_width=True, height=200)

    # ドキュメント選択
    st.subheader("🔍 ドキュメント詳細")
    selected_index = st.selectbox(
        "編集するドキュメントを選択",
        range(len(documents)),
        format_func=lambda i: f"{documents[i].get('file_name', 'Unknown')} (信頼度: {documents[i].get('confidence') or 0:.3f})"
    )

    selected_doc = documents[selected_index]
    doc_id = selected_doc.get('id')
    drive_file_id = selected_doc.get('drive_file_id')
    source_id = selected_doc.get('source_id')
    file_id = drive_file_id or source_id
    file_name = selected_doc.get('file_name', 'unknown')
    doc_type = selected_doc.get('doc_type', '')
    metadata = selected_doc.get('metadata') or {}
    confidence = selected_doc.get('confidence') or 0

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
        tab_names = ["📝 フォーム編集"]

        # 構造化データごとにタブを追加
        for field in structured_fields:
            tab_names.append(field["label"])

        # 固定タブ：JSONプレビュー
        tab_names.append("🔍 JSONプレビュー")

        # タブを動的に生成
        tabs = st.tabs(tab_names)
        edited_metadata = None

        # タブ1: フォーム編集
        with tabs[0]:
            if editable_fields:
                # 構造化データフィールドをフォームから除外
                form_fields = [f for f in editable_fields if f["name"] not in structured_field_keys]

                if form_fields:
                    edited_metadata = render_form_editor(metadata, form_fields)
                else:
                    st.info("このドキュメントのフィールドは全て専用タブで編集できます")
                    st.markdown("各データタブまたはJSONプレビュータブをご利用ください")
            else:
                st.info("フォーム編集には対応するスキーマが必要です")
                st.markdown("JSONプレビュータブで直接編集してください")

        # タブ2以降: 構造化データタブ（動的に生成）
        for idx, field in enumerate(structured_fields):
            with tabs[idx + 1]:
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

        # 最後のタブ: JSONプレビュー
        with tabs[-1]:
            edited_metadata = render_json_preview(metadata, editable=True)

        # 保存ボタンエリア
        st.markdown("---")
        col_save, col_validate, col_cancel = st.columns([1, 1, 1])

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

        with col_cancel:
            if st.button("🔄 リセット", use_container_width=True):
                st.rerun()

    # フッター
    st.markdown("---")
    col_footer1, col_footer2 = st.columns([3, 1])
    with col_footer1:
        st.caption("Document Management System - Review UI v2.0 (Tab Edition)")
    with col_footer2:
        st.caption(f"🎨 検出スキーマ: {detected_schema or 'N/A'}")


if __name__ == "__main__":
    main()
