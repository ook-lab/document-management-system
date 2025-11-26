"""
Document Review UI
人間がAIの抽出結果を確認・修正するための管理画面
"""
import sys
from pathlib import Path

# プロジェクトのルートディレクトリをPythonパスに追加
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

import streamlit as st
import json
import base64
import tempfile
from typing import Dict, Any, Optional
import pandas as pd

from core.database.client import DatabaseClient
from core.connectors.google_drive import GoogleDriveConnector


def get_pdf_preview_html(file_path: str) -> str:
    """
    PDFファイルをBase64エンコードしてHTMLで表示可能にする

    Args:
        file_path: PDFファイルのパス

    Returns:
        PDFを表示するHTMLコード
    """
    with open(file_path, 'rb') as f:
        pdf_bytes = f.read()
        base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')

    # PDFをiframeで表示するHTML
    pdf_display = f'''
        <iframe
            src="data:application/pdf;base64,{base64_pdf}"
            width="100%"
            height="800"
            type="application/pdf"
            style="border: 1px solid #ccc; border-radius: 4px;">
        </iframe>
    '''
    return pdf_display


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


def format_metadata_json(metadata: Dict[str, Any]) -> str:
    """
    メタデータをきれいに整形されたJSONに変換

    Args:
        metadata: メタデータ辞書

    Returns:
        整形されたJSON文字列
    """
    return json.dumps(metadata, ensure_ascii=False, indent=2)


def parse_metadata_json(json_str: str) -> Optional[Dict[str, Any]]:
    """
    JSON文字列をメタデータ辞書に変換

    Args:
        json_str: JSON文字列

    Returns:
        メタデータ辞書、パースエラー時はNone
    """
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        st.error(f"JSON形式エラー: {e}")
        return None


def main():
    """メインUIロジック"""
    st.set_page_config(page_title="Document Review UI", layout="wide")
    st.title("📋 Document Review UI")
    st.markdown("AIが抽出したメタデータを確認・修正できます")

    # データベースクライアントの初期化
    try:
        db_client = DatabaseClient()
    except Exception as e:
        st.error(f"データベース接続エラー: {e}")
        st.stop()

    # サイドバー: フィルタ設定
    st.sidebar.header("フィルタ設定")
    max_confidence = st.sidebar.slider(
        "信頼度の上限",
        min_value=0.0,
        max_value=1.0,
        value=0.9,
        step=0.05
    )
    limit = st.sidebar.number_input("取得件数", min_value=10, max_value=500, value=100, step=10)

    # レビュー対象ドキュメントを取得
    if st.sidebar.button("🔄 リストを更新"):
        st.rerun()

    documents = db_client.get_documents_for_review(
        status='completed',
        max_confidence=max_confidence,
        limit=limit
    )

    if not documents:
        st.info("レビュー対象のドキュメントがありません")
        return

    st.sidebar.success(f"{len(documents)}件のドキュメントが見つかりました")

    # ドキュメントリストをDataFrameで表示
    df = pd.DataFrame([
        {
            'ID': doc.get('id', '')[:8],  # IDの最初の8文字
            'ファイル名': doc.get('file_name', ''),
            '文書タイプ': doc.get('doc_type', ''),
            '信頼度': round(doc.get('confidence', 0), 3),
            '作成日時': doc.get('created_at', '')[:10]
        }
        for doc in documents
    ])

    st.subheader("📁 レビュー対象ドキュメント一覧")
    st.dataframe(df, use_container_width=True)

    # ドキュメント選択
    st.subheader("🔍 ドキュメント詳細")
    selected_index = st.selectbox(
        "編集するドキュメントを選択",
        range(len(documents)),
        format_func=lambda i: f"{documents[i].get('file_name', 'Unknown')} (信頼度: {documents[i].get('confidence', 0):.3f})"
    )

    selected_doc = documents[selected_index]
    doc_id = selected_doc.get('id')
    drive_file_id = selected_doc.get('drive_file_id')
    source_id = selected_doc.get('source_id')
    file_id = drive_file_id or source_id
    file_name = selected_doc.get('file_name', 'unknown')
    doc_type = selected_doc.get('doc_type', '')
    metadata = selected_doc.get('metadata', {})
    confidence = selected_doc.get('confidence', 0)

    # 2カラムレイアウト
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("### 📄 PDFプレビュー")

        # PDFのダウンロードと表示
        if source_id and file_name.lower().endswith('.pdf'):
            with st.spinner("PDFをダウンロード中..."):
                file_path = download_file_from_drive(file_id, file_name)

            if file_path and Path(file_path).exists():
                # PDFをバイナリとして読み込み
                with open(file_path, 'rb') as f:
                    pdf_bytes = f.read()


                # Streamlitのネイティブダウンロードボタン
                st.download_button(
                    label="📥 PDFをダウンロード",
                    data=pdf_bytes,
                    file_name=file_name,
                    mime="application/pdf"
                )

                # Base64でプレビュー表示（Chrome対応版）
                import base64
                base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')

                # embedタグを使用（iframeより安全）
                pdf_display = f'<embed src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf">'

                st.markdown(pdf_display, unsafe_allow_html=True)
            else:
                st.warning("PDFファイルを読み込めませんでした")
                
        else:
            st.info("PDFファイル以外はプレビューできません")

    with col2:
        st.markdown("### ✏️ メタデータ編集")

        # ドキュメント基本情報
        st.markdown(f"**ファイル名**: {file_name}")
        st.markdown(f"**信頼度**: {confidence:.3f}")
        st.markdown(f"**ドキュメントID**: `{doc_id}`")

        st.markdown("---")

        # 文書タイプ編集
        doc_type_options = [
            "school_notice",
            "classroom_letter",
            "event_schedule",
            "newsletter",
            "other"
        ]
        new_doc_type = st.selectbox(
            "文書タイプ",
            options=doc_type_options,
            index=doc_type_options.index(doc_type) if doc_type in doc_type_options else 0
        )

        # メタデータ編集(JSON形式)
        st.markdown("#### メタデータ (JSON)")
        metadata_json = format_metadata_json(metadata)
        edited_metadata_json = st.text_area(
            "メタデータを編集",
            value=metadata_json,
            height=400,
            help="JSON形式で編集してください"
        )

        # 保存ボタン
        st.markdown("---")
        col_save, col_cancel = st.columns([1, 1])

        with col_save:
            if st.button("💾 保存", type="primary", use_container_width=True):
                # JSONパース
                new_metadata = parse_metadata_json(edited_metadata_json)

                if new_metadata is not None:
                    # データベース更新
                    success = db_client.update_document_metadata(
                        doc_id=doc_id,
                        new_metadata=new_metadata,
                        new_doc_type=new_doc_type
                    )

                    if success:
                        st.success("✅ 保存に成功しました！")
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
    st.caption("Document Management System - Review UI v1.0")


if __name__ == "__main__":
    main()