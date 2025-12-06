"""
Email Viewer Component

メール専用の表示コンポーネント
- メール一覧（表形式）
- メール詳細表示（メールらしい見た目）
"""
import streamlit as st
from datetime import datetime
from typing import Dict, List, Any, Optional
import json
import html
import pandas as pd


def render_email_list(emails: List[Dict[str, Any]]) -> Optional[str]:
    """
    メール一覧を表形式で表示（PDFレビューと同様）

    Args:
        emails: メールドキュメントのリスト

    Returns:
        選択されたメールのインデックス（None の場合は未選択）
    """
    st.subheader("📬 受信メール一覧")

    if not emails:
        st.info("メールがありません")
        return None

    # メールのDataFrameを作成
    df_data = []
    for email in emails:
        metadata = email.get('metadata', {})

        # メールの基本情報を取得
        sender = metadata.get('from', '送信者不明')
        subject = metadata.get('subject', '(件名なし)')
        date_str = metadata.get('date', '')

        # 送信者から名前とメールアドレスを抽出
        sender_name = sender
        if '<' in sender and '>' in sender:
            # "名前 <email>" の形式から名前だけを取得
            sender_name = sender.split('<')[0].strip().strip('"')

        # 日付をフォーマット
        try:
            display_date = date_str[:10] if date_str else ""
        except:
            display_date = date_str

        df_data.append({
            '件名': subject,
            '送信者': sender_name,
            '送信日時': display_date
        })

    df = pd.DataFrame(df_data)

    # DataFrameを表示
    st.dataframe(df, use_container_width=True, height=200)

    # セレクトボックスでメールを選択
    selected_index = st.selectbox(
        "表示するメールを選択",
        range(len(emails)),
        format_func=lambda i: f"{df_data[i]['件名']} ({df_data[i]['送信者']})",
        key="email_selector"
    )

    return selected_index


def render_email_detail(email: Dict[str, Any]):
    """
    メール詳細をタブ形式で表示（PDFレビューと同じスタイル）

    Args:
        email: メールドキュメント
    """
    metadata = email.get('metadata', {})

    st.markdown("### ✏️ メール情報")

    # タブで情報を整理
    tab1, tab2, tab3, tab4 = st.tabs(["📄 本文", "📊 要約", "🔍 重要情報", "⚙️ メタデータ"])

    with tab1:
        st.markdown("#### メール本文")
        full_text = email.get('full_text', '')

        if full_text:
            # 「メール情報:」以降の本文部分を抽出
            if '本文:' in full_text:
                body_text = full_text.split('本文:')[1]
                # 「重要な情報:」があればそこまで
                if '重要な情報:' in body_text:
                    body_text = body_text.split('重要な情報:')[0]
                st.text_area("", body_text.strip(), height=400, label_visibility="collapsed")
            else:
                st.text_area("", full_text, height=400, label_visibility="collapsed")
        else:
            st.info("本文がありません")

    with tab2:
        st.markdown("#### AI要約")
        summary = email.get('summary', metadata.get('summary', ''))

        if summary:
            # summaryがJSON文字列の場合はパースを試みる
            if summary.startswith('```json'):
                try:
                    # ```json と ``` を削除
                    json_str = summary.replace('```json', '').replace('```', '').strip()
                    summary_data = json.loads(json_str)
                    st.json(summary_data)
                except:
                    st.write(summary)
            else:
                st.write(summary)
        else:
            st.info("要約がありません")

    with tab3:
        st.markdown("#### 重要な情報")
        key_info = metadata.get('key_information', [])

        if key_info and isinstance(key_info, list):
            for i, info in enumerate(key_info, 1):
                st.markdown(f"{i}. {info}")
        else:
            st.info("重要な情報が抽出されていません")

        # リンクがある場合
        links = metadata.get('links', [])
        if links:
            st.markdown("#### 🔗 リンク")
            for link in links:
                st.markdown(f"- {link}")

        # 画像がある場合
        has_images = metadata.get('has_images', False)
        if has_images:
            st.info("📷 このメールには画像が含まれています")

    with tab4:
        st.markdown("#### メタデータ（JSON）")
        st.json(metadata)

    # Google Drive HTMLファイルへのリンク
    st.divider()
    drive_file_id = email.get('drive_file_id') or email.get('source_id')
    if drive_file_id:
        col1, col2 = st.columns(2)
        with col1:
            st.link_button(
                "📥 元のHTMLをダウンロード",
                f"https://drive.google.com/uc?export=download&id={drive_file_id}",
                use_container_width=True
            )
        with col2:
            st.link_button(
                "👁️ Google Driveで表示",
                f"https://drive.google.com/file/d/{drive_file_id}/view",
                use_container_width=True
            )


def render_email_html_preview(email: Dict[str, Any], drive_connector=None):
    """
    メールのHTMLプレビューを表示

    Args:
        email: メールドキュメント
        drive_connector: GoogleDriveConnector インスタンス（オプション）
    """
    st.markdown("### 📧 メールプレビュー")

    # メールドキュメントの検証
    if not email:
        st.warning("メールデータが見つかりません")
        return

    drive_file_id = email.get('drive_file_id') or email.get('source_id')

    if not drive_file_id:
        st.info("プレビュー可能なHTMLファイルがありません")
        # デバッグ情報
        with st.expander("🔍 デバッグ情報"):
            st.json({
                "email_keys": list(email.keys()),
                "drive_file_id": drive_file_id,
                "source_id": email.get('source_id')
            })
        return

    # Google DriveからHTMLをダウンロードして表示
    try:
        if drive_connector is None:
            from core.connectors.google_drive import GoogleDriveConnector
            drive_connector = GoogleDriveConnector()

        import tempfile
        temp_dir = tempfile.gettempdir()

        # より安全なファイル名の取得
        email_id = email.get('id', 'unknown')
        file_name = email.get('file_name', f"email_{email_id}.html")

        with st.spinner("メールHTMLを読み込み中..."):
            file_path = drive_connector.download_file(drive_file_id, file_name, temp_dir)

            if file_path:
                # HTMLファイルを読み込み
                with open(file_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()

                # iframeでHTMLを表示（セキュリティを考慮してサンドボックス化）
                st.components.v1.html(
                    html_content,
                    height=700,
                    scrolling=True
                )
            else:
                st.warning("HTMLファイルのダウンロードに失敗しました")

    except Exception as e:
        error_str = str(e)

        # 404エラーの場合は特別なメッセージを表示
        if "File not found" in error_str or "404" in error_str:
            st.warning("⚠️ HTMLファイルがGoogle Driveで見つかりませんでした")
            st.info("""
            考えられる原因：
            - ファイルが削除されている
            - サービスアカウントにアクセス権限がない
            - ファイルIDが正しくない
            """)
        else:
            st.error(f"HTMLプレビューの表示中にエラーが発生しました")

        # デバッグ情報を表示
        with st.expander("🔍 エラー詳細"):
            st.text(f"エラー: {error_str}")
            import traceback
            st.code(traceback.format_exc())
            st.json({
                "email_data": {
                    "id": email.get('id'),
                    "drive_file_id": drive_file_id,
                    "file_name": email.get('file_name'),
                    "available_keys": list(email.keys())
                }
            })

        # フォールバック：リンクボタンを表示
        if drive_file_id:
            st.markdown("---")
            st.caption("Google Driveで直接確認してください：")
            col1, col2 = st.columns(2)
            with col1:
                st.link_button(
                    "📥 元のHTMLをダウンロード",
                    f"https://drive.google.com/uc?export=download&id={drive_file_id}",
                    use_container_width=True
                )
            with col2:
                st.link_button(
                    "👁️ Google Driveで表示",
                    f"https://drive.google.com/file/d/{drive_file_id}/view",
                    use_container_width=True
                )


def render_email_filters() -> Dict[str, Any]:
    """
    メールフィルター（workspace, 期間など）

    Returns:
        フィルター条件の辞書
    """
    st.sidebar.markdown("### 🔍 メールフィルター")

    filters = {}

    # workspace フィルター
    workspace_options = [
        "すべて",
        "DM_MAIL",
        "WORK_MAIL",
        "IKUYA_MAIL",
        "EMA_MAIL",
        "MONEY_MAIL",
        "JOB_MAIL",
    ]
    selected_workspace = st.sidebar.selectbox(
        "Workspace",
        workspace_options
    )
    if selected_workspace != "すべて":
        filters['workspace'] = selected_workspace

    # 期間フィルター
    date_range = st.sidebar.radio(
        "期間",
        ["すべて", "今日", "今週", "今月", "カスタム"]
    )

    if date_range == "カスタム":
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.date_input("開始日")
            filters['start_date'] = start_date
        with col2:
            end_date = st.date_input("終了日")
            filters['end_date'] = end_date

    # 検索キーワード
    keyword = st.sidebar.text_input("🔎 キーワード検索")
    if keyword:
        filters['keyword'] = keyword

    return filters
