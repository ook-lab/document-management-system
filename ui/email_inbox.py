"""
Email Inbox UI

メール受信トレイ専用UI
- file_type = 'email' のドキュメントのみを表示
- PDFデータには一切触れない
"""
import streamlit as st
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from core.database.client import DatabaseClient
from ui.components.email_viewer import render_email_list, render_email_detail, render_email_filters

# ページ設定
st.set_page_config(
    page_title="📬 メール受信トレイ",
    page_icon="📬",
    layout="wide"
)

def load_emails(filters: dict = None):
    """
    Supabaseからメールデータを取得

    Args:
        filters: フィルター条件

    Returns:
        メールドキュメントのリスト
    """
    db = DatabaseClient()

    # 基本クエリ: file_type = 'email' のみ（PDFを除外）
    query = db.client.table('documents').select('*').eq('file_type', 'email')

    # workspace フィルター
    if filters and filters.get('workspace'):
        query = query.eq('workspace', filters['workspace'])

    # キーワード検索（件名または本文）
    if filters and filters.get('keyword'):
        keyword = filters['keyword']
        # full_textにキーワードが含まれるものを検索
        query = query.ilike('full_text', f'%{keyword}%')

    # 日付順にソート（新しい順）
    query = query.order('created_at', desc=True)

    # 最大100件取得
    query = query.limit(100)

    result = query.execute()
    return result.data


def main():
    st.title("📬 メール受信トレイ")
    st.caption("Gmail Vision処理されたメール一覧")

    # サイドバーでフィルター
    filters = render_email_filters()

    # メールを取得
    with st.spinner("メールを読み込み中..."):
        emails = load_emails(filters)

    # セッションステートで選択されたメールを管理
    if 'selected_email_id' not in st.session_state:
        st.session_state.selected_email_id = None

    # レイアウト: 2カラム
    col1, col2 = st.columns([1, 2])

    with col1:
        # メール一覧
        selected_id = render_email_list(emails)
        if selected_id:
            st.session_state.selected_email_id = selected_id
            st.rerun()

    with col2:
        # メール詳細
        if st.session_state.selected_email_id:
            # 選択されたメールを取得
            selected_email = next(
                (email for email in emails if email['id'] == st.session_state.selected_email_id),
                None
            )

            if selected_email:
                render_email_detail(selected_email)
            else:
                st.info("メールを選択してください")

                # 戻るボタン
                if st.button("← 一覧に戻る"):
                    st.session_state.selected_email_id = None
                    st.rerun()
        else:
            st.info("📩 左のリストからメールを選択してください")

    # 統計情報
    st.sidebar.divider()
    st.sidebar.markdown("### 📊 統計")
    st.sidebar.metric("総メール数", len(emails))

    # workspace別の件数
    if emails:
        workspace_counts = {}
        for email in emails:
            ws = email.get('workspace', 'unknown')
            workspace_counts[ws] = workspace_counts.get(ws, 0) + 1

        st.sidebar.markdown("#### Workspace別")
        for ws, count in sorted(workspace_counts.items(), key=lambda x: x[1], reverse=True):
            st.sidebar.caption(f"{ws}: {count}件")


if __name__ == "__main__":
    main()
