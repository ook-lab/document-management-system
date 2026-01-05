"""
Streamlit UI for Document Processing
process_queued_documents.py を実行するUI
"""
import streamlit as st
import asyncio
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from process_queued_documents import DocumentProcessor

st.set_page_config(
    page_title="ドキュメント処理システム",
    page_icon="📄",
    layout="wide"
)

st.title("📄 ドキュメント処理システム")
st.markdown("---")

# Initialize session state
if 'processor' not in st.session_state:
    st.session_state.processor = None
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'logs' not in st.session_state:
    st.session_state.logs = []

# Initialize processor
@st.cache_resource
def get_processor():
    return DocumentProcessor()

try:
    processor = get_processor()
except Exception as e:
    st.error(f"❌ 初期化エラー: {str(e)}")
    st.stop()

# Sidebar settings
with st.sidebar:
    st.header("⚙️ 処理設定")

    workspace = st.text_input(
        "ワークスペース",
        value="all",
        help="'all' で全ワークスペース、または特定のワークスペース名を入力"
    )

    limit = st.number_input(
        "処理件数上限",
        min_value=1,
        max_value=1000,
        value=100,
        help="一度に処理する最大件数"
    )

    preserve_workspace = st.checkbox(
        "ワークスペースを保持",
        value=True,
        help="ドキュメントのworkspaceを保持するか"
    )

    st.markdown("---")

    if st.button("🔄 統計情報を更新", use_container_width=True):
        st.rerun()

# Main content
col1, col2 = st.columns([2, 1])

with col1:
    st.header("📊 処理キューの状態")

    try:
        stats = processor.get_queue_stats(workspace)

        if stats:
            # Metrics in columns
            metric_cols = st.columns(5)

            with metric_cols[0]:
                st.metric("⏳ 待機中", stats.get('pending', 0))
            with metric_cols[1]:
                st.metric("🔄 処理中", stats.get('processing', 0))
            with metric_cols[2]:
                st.metric("✅ 完了", stats.get('completed', 0))
            with metric_cols[3]:
                st.metric("❌ 失敗", stats.get('failed', 0))
            with metric_cols[4]:
                st.metric("📝 未処理", stats.get('null', 0))

            st.markdown("---")

            # Summary
            col_summary1, col_summary2 = st.columns(2)
            with col_summary1:
                st.metric("📦 合計", stats.get('total', 0))
            with col_summary2:
                processed = stats.get('completed', 0) + stats.get('failed', 0)
                if processed > 0:
                    success_rate = stats.get('success_rate', 0)
                    st.metric("✨ 成功率", f"{success_rate:.1f}%")
                else:
                    st.metric("✨ 成功率", "N/A")
        else:
            st.warning("統計情報を取得できませんでした")

    except Exception as e:
        st.error(f"❌ 統計取得エラー: {str(e)}")

with col2:
    st.header("🚀 処理実行")

    pending_count = stats.get('pending', 0) if stats else 0

    if pending_count == 0:
        st.info("処理待ちのドキュメントはありません")
        process_button_disabled = True
    else:
        st.success(f"{pending_count} 件のドキュメントが処理待ちです")
        process_button_disabled = False

    if st.button(
        "▶️ 処理を開始",
        type="primary",
        use_container_width=True,
        disabled=process_button_disabled or st.session_state.processing
    ):
        st.session_state.processing = True
        st.session_state.logs = []
        st.rerun()

# Processing section
if st.session_state.processing:
    st.markdown("---")
    st.header("🔄 処理中...")

    progress_bar = st.progress(0)
    status_text = st.empty()
    log_container = st.container()

    async def run_processing():
        """処理を実行"""
        try:
            # pending ドキュメントを取得
            docs = processor.get_pending_documents(workspace, limit)

            if not docs:
                st.session_state.logs.append("処理対象のドキュメントがありません")
                return

            total = len(docs)
            st.session_state.logs.append(f"処理対象: {total}件")

            success_count = 0
            failed_count = 0

            for i, doc in enumerate(docs, 1):
                file_name = doc.get('file_name', 'unknown')
                title = doc.get('title', '')
                display_name = title if title else '(タイトル未生成)'

                # Update progress
                progress = i / total
                progress_bar.progress(progress)
                status_text.text(f"[{i}/{total}] 処理中: {display_name}")

                # Log
                log_msg = f"[{i}/{total}] 処理開始: {display_name}"
                st.session_state.logs.append(log_msg)

                # Process document
                success = await processor.process_document(doc, preserve_workspace)

                if success:
                    success_count += 1
                    result_msg = f"✅ 成功: {display_name}"
                else:
                    failed_count += 1
                    result_msg = f"❌ 失敗: {display_name}"

                st.session_state.logs.append(result_msg)

                # Update log display
                with log_container:
                    for log in st.session_state.logs[-10:]:  # Show last 10 logs
                        st.text(log)

            # Final summary
            st.session_state.logs.append("=" * 80)
            st.session_state.logs.append("処理完了")
            st.session_state.logs.append(f"成功: {success_count}件")
            st.session_state.logs.append(f"失敗: {failed_count}件")
            st.session_state.logs.append(f"合計: {total}件")

            progress_bar.progress(1.0)
            status_text.text("✅ 処理完了")

        except Exception as e:
            st.session_state.logs.append(f"❌ エラー: {str(e)}")
            status_text.text(f"❌ エラー発生: {str(e)}")

        finally:
            st.session_state.processing = False

    # Run async processing
    asyncio.run(run_processing())

    # Show complete logs
    with st.expander("📋 完全なログを表示", expanded=True):
        for log in st.session_state.logs:
            st.text(log)

    # Rerun to update UI
    if not st.session_state.processing:
        st.success("✅ 処理が完了しました！")
        if st.button("🔄 ページを更新"):
            st.rerun()

# Instructions
with st.sidebar:
    st.markdown("---")
    st.markdown("### ℹ️ 使い方")
    st.markdown("""
    1. **ワークスペースを選択**
       - 'all' で全ワークスペース
       - または特定のワークスペース名

    2. **処理件数を設定**
       - 一度に処理する最大件数

    3. **処理を開始**
       - ▶️ ボタンをクリック
       - OCR処理、チャンク化、埋め込み生成を実行

    4. **結果を確認**
       - 処理状況をリアルタイムで確認
    """)

# Footer
st.markdown("---")
st.markdown("**注意:** 処理には時間がかかる場合があります。ブラウザを閉じずにお待ちください。")
