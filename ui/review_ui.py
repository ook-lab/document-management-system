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
from typing import Dict, Any, Optional
import pandas as pd

from core.database.client import DatabaseClient
from core.connectors.google_drive import GoogleDriveConnector

# 新しいコンポーネントとユーティリティをインポート
from ui.utils.schema_detector import SchemaDetector
from ui.components.form_editor import render_form_editor
from ui.components.table_editor import render_table_editor
from ui.components.json_preview import render_json_preview, render_json_diff


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
    metadata = selected_doc.get('metadata', {})
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
                with open(file_path, 'rb') as f:
                    pdf_bytes = f.read()

                # PDFプレビュー表示
                try:
                    from streamlit_pdf_viewer import pdf_viewer
                    pdf_viewer(pdf_bytes, height=700)
                except ImportError:
                    st.warning("PDFビューアーライブラリがインストールされていません")
                    st.download_button(
                        label="📥 PDFをダウンロード",
                        data=pdf_bytes,
                        file_name=file_name,
                        mime="application/pdf",
                        use_container_width=True
                    )
                except Exception as e:
                    st.warning(f"PDFプレビュー表示エラー: {e}")
                    st.download_button(
                        label="📥 PDFをダウンロード",
                        data=pdf_bytes,
                        file_name=file_name,
                        mime="application/pdf",
                        use_container_width=True
                    )
            else:
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

        # タブUI: 3つの編集モード
        tab1, tab2, tab3 = st.tabs(["📝 フォーム編集", "📊 表エディタ", "🔍 JSONプレビュー"])

        edited_metadata = None

        with tab1:
            # フォーム編集タブ
            if editable_fields:
                edited_metadata = render_form_editor(metadata, editable_fields)
            else:
                st.info("フォーム編集には対応するスキーマが必要です")
                st.markdown("JSONプレビュータブで直接編集してください")

        with tab2:
            # 表エディタタブ
            edited_metadata = render_table_editor(metadata)

        with tab3:
            # JSONプレビュータブ
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
