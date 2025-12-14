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
from ui.components.email_viewer import render_email_list, render_email_detail, render_email_filters, render_email_html_preview

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
    query = db.client.table('source_documents').select('*').eq('file_type', 'email')

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

    # 最大20件取得
    query = query.limit(20)

    result = query.execute()
    return result.data


def email_inbox_ui():
    """メール受信トレイUI（PDFレビューと同じ構成）"""
    st.markdown("#### 📬 メール受信トレイ")
    st.caption("Gmail Vision処理されたメール一覧")

    # サイドバーでフィルター
    filters = render_email_filters()

    # メールを取得
    with st.spinner("メールを読み込み中..."):
        emails = load_emails(filters)

    if not emails:
        st.info("メールがありません")
        return

    # 統計情報（サイドバー）
    st.sidebar.divider()
    st.sidebar.markdown("### 📊 統計")
    st.sidebar.metric("総メール数", len(emails))

    # workspace別の件数
    workspace_counts = {}
    for email in emails:
        ws = email.get('workspace', 'unknown')
        workspace_counts[ws] = workspace_counts.get(ws, 0) + 1

    st.sidebar.markdown("#### Workspace別")
    for ws, count in sorted(workspace_counts.items(), key=lambda x: x[1], reverse=True):
        st.sidebar.caption(f"{ws}: {count}件")

    # リスト更新ボタン
    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 リストを更新", use_container_width=True, key="refresh_email_list"):
        st.rerun()

    # メール一覧を表形式で表示（上部、チェックボックス付き）
    selected_index, edited_df = render_email_list(emails)

    if selected_index is None:
        st.info("メールを選択してください")
        return

    # まとめて削除機能
    if edited_df is not None:
        selected_indices = edited_df[edited_df['選択'] == True].index.tolist()
        selected_count = len(selected_indices)

        if selected_count > 0:
            col_bulk1, col_bulk2, col_spacer = st.columns([1, 1, 2])

            with col_bulk1:
                st.warning(f"⚠️ {selected_count}件のメールが選択されています")

            with col_bulk2:
                # 一括削除確認用のセッション状態
                if 'email_bulk_delete_confirm' not in st.session_state:
                    st.session_state.email_bulk_delete_confirm = False

                if not st.session_state.email_bulk_delete_confirm:
                    if st.button(f"🗑️ {selected_count}件をまとめて削除", use_container_width=True, type="secondary", key="email_bulk_delete_btn"):
                        st.session_state.email_bulk_delete_confirm = True
                        st.rerun()
                else:
                    if st.button(f"✅ {selected_count}件の削除を実行", use_container_width=True, type="primary", key="email_bulk_delete_execute"):
                        from core.connectors.google_drive import GoogleDriveConnector
                        db = DatabaseClient()

                        with st.spinner(f"{selected_count}件のメールを削除中..."):
                            success_count = 0
                            fail_count = 0

                            for idx in selected_indices:
                                email = emails[idx]
                                doc_id = email.get('id')
                                file_id = email.get('drive_file_id') or email.get('source_id')

                                # Google Driveから削除（メールのHTMLファイル）
                                if file_id:
                                    try:
                                        drive_connector = GoogleDriveConnector()
                                        drive_connector.trash_file(file_id)
                                    except Exception as e:
                                        import logging
                                        logging.error(f"Google Drive削除エラー: {e}")

                                # データベースから削除
                                if db.delete_document(doc_id):
                                    success_count += 1
                                else:
                                    fail_count += 1

                            if success_count > 0:
                                st.success(f"✅ {success_count}件のメールを削除しました")
                            if fail_count > 0:
                                st.error(f"❌ {fail_count}件の削除に失敗しました")

                            st.session_state.email_bulk_delete_confirm = False
                            st.balloons()
                            import time
                            time.sleep(1)
                            st.rerun()

                    if st.button("❌ キャンセル", use_container_width=True, key="email_bulk_delete_cancel"):
                        st.session_state.email_bulk_delete_confirm = False
                        st.rerun()

    selected_email = emails[selected_index]

    # 基本情報表示
    metadata = selected_email.get('metadata', {})
    st.markdown("---")
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown(f"**件名**: {metadata.get('subject', '(件名なし)')}")
    with col2:
        sender = metadata.get('from', '送信者不明')
        sender_name = sender
        if '<' in sender and '>' in sender:
            sender_name = sender.split('<')[0].strip().strip('"')
        st.markdown(f"**送信者**: {sender_name}")
    with col3:
        st.markdown(f"**日時**: {metadata.get('date', '')[:10]}")

    st.markdown("---")

    # レイアウト: 左にHTMLプレビュー、右にメール詳細（PDFレビューと同じ構成）
    col_left, col_right = st.columns([1, 1.2])

    with col_left:
        # HTMLプレビュー
        render_email_html_preview(selected_email)

    with col_right:
        # メール詳細（タブ形式）
        render_email_detail(selected_email)


def main():
    """スタンドアロン実行用のmain関数"""
    st.set_page_config(
        page_title="📬 メール受信トレイ",
        page_icon="📬",
        layout="wide"
    )
    st.title("📬 メール受信トレイ")
    email_inbox_ui()


if __name__ == "__main__":
    main()
