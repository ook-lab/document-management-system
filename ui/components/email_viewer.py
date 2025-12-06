"""
Email Viewer Component

メール専用の表示コンポーネント
- メール一覧（受信トレイ風）
- メール詳細表示（メールらしい見た目）
"""
import streamlit as st
from datetime import datetime
from typing import Dict, List, Any, Optional
import json
import html


def render_email_list(emails: List[Dict[str, Any]]) -> Optional[str]:
    """
    メール一覧を受信トレイ風に表示

    Args:
        emails: メールドキュメントのリスト

    Returns:
        選択されたメールのID（クリックされた場合）
    """
    st.markdown("### 📬 受信メール一覧")

    if not emails:
        st.info("メールがありません")
        return None

    # メール件数表示
    st.caption(f"全 {len(emails)} 件のメール")

    selected_email_id = None

    for email in emails:
        metadata = email.get('metadata', {})

        # メールの基本情報を取得
        sender = metadata.get('from', '送信者不明')
        subject = metadata.get('subject', '(件名なし)')
        date_str = metadata.get('date', '')
        summary = email.get('summary', '')

        # 送信者から名前とメールアドレスを抽出
        sender_name = sender
        if '<' in sender and '>' in sender:
            # "名前 <email>" の形式から名前だけを取得
            sender_name = sender.split('<')[0].strip().strip('"')

        # 日付をフォーマット
        try:
            # ここで日付パースを試みる（フォーマットは調整が必要かも）
            display_date = date_str[:10] if date_str else ""
        except:
            display_date = date_str

        # メールカード
        with st.container():
            col1, col2 = st.columns([4, 1])

            with col1:
                # 件名をボタンとして表示（クリック可能）
                if st.button(
                    f"**{subject}**",
                    key=f"email_{email['id']}",
                    use_container_width=True
                ):
                    selected_email_id = email['id']

                # 送信者と要約を小さく表示
                st.caption(f"👤 {sender_name}")
                if summary:
                    # 要約を最初の100文字だけ表示
                    preview = summary[:100] + "..." if len(summary) > 100 else summary
                    st.caption(f"📝 {preview}")

            with col2:
                # 日付を右側に表示
                st.caption(display_date)

            st.divider()

    return selected_email_id


def render_email_detail(email: Dict[str, Any]):
    """
    メール詳細を表示

    Args:
        email: メールドキュメント
    """
    metadata = email.get('metadata', {})

    # ヘッダー部分
    st.markdown("### 📧 メール詳細")

    # メールヘッダー（見やすく整形）
    with st.container():
        # HTMLエスケープして安全に表示
        subject_escaped = html.escape(metadata.get('subject', '(件名なし)'))
        from_escaped = html.escape(metadata.get('from', '不明'))
        to_escaped = html.escape(metadata.get('to', '不明'))
        date_escaped = html.escape(metadata.get('date', '不明'))

        st.markdown(f"""
        <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
            <h3 style="margin: 0 0 15px 0;">{subject_escaped}</h3>
            <div style="display: flex; flex-direction: column; gap: 8px;">
                <div><strong>送信者:</strong> {from_escaped}</div>
                <div><strong>宛先:</strong> {to_escaped}</div>
                <div><strong>日時:</strong> {date_escaped}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

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
