import streamlit as st
import requests
from typing import Dict, List, Any, Optional
import json

# Backend API URL
BACKEND_URL = "https://mail-doc-search-system-983922127476.asia-northeast1.run.app"

st.set_page_config(
    page_title="メール・ドキュメント検索システム",
    page_icon="🔍",
    layout="wide"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
    }
    .search-result {
        padding: 15px;
        border-radius: 5px;
        background-color: #f0f2f6;
        margin-bottom: 10px;
    }
    .answer-box {
        padding: 20px;
        border-radius: 10px;
        background-color: #e8f4f8;
        border-left: 5px solid #1f77b4;
        margin: 20px 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'search_results' not in st.session_state:
    st.session_state.search_results = None
if 'answer' not in st.session_state:
    st.session_state.answer = None
if 'filters' not in st.session_state:
    st.session_state.filters = None

# Title
st.title("🔍 メール・ドキュメント検索システム")
st.markdown("---")

# Sidebar for filters
with st.sidebar:
    st.header("フィルター設定")

    # Fetch available filters
    if st.session_state.filters is None:
        try:
            response = requests.get(f"{BACKEND_URL}/api/filters", timeout=10)
            if response.status_code == 200:
                st.session_state.filters = response.json()
        except Exception as e:
            st.error(f"フィルター取得エラー: {str(e)}")
            st.session_state.filters = {}

    # Date range filter
    st.subheader("📅 日付範囲")
    date_from = st.date_input("開始日", value=None, key="date_from")
    date_to = st.date_input("終了日", value=None, key="date_to")

    # Sender filter
    st.subheader("👤 送信者")
    if st.session_state.filters and 'senders' in st.session_state.filters:
        selected_senders = st.multiselect(
            "送信者を選択",
            options=st.session_state.filters.get('senders', []),
            key="senders"
        )
    else:
        sender_input = st.text_input("送信者を入力", key="sender_input")
        selected_senders = [sender_input] if sender_input else []

    # Tag filter
    st.subheader("🏷️ タグ")
    if st.session_state.filters and 'tags' in st.session_state.filters:
        selected_tags = st.multiselect(
            "タグを選択",
            options=st.session_state.filters.get('tags', []),
            key="tags"
        )
    else:
        selected_tags = []

    # Search parameters
    st.subheader("⚙️ 検索設定")
    top_k = st.slider("表示件数", min_value=1, max_value=20, value=5, key="top_k")
    search_mode = st.selectbox(
        "検索モード",
        options=["hybrid", "semantic", "keyword"],
        index=0,
        key="search_mode"
    )

# Main content area
col1, col2 = st.columns([2, 1])

with col1:
    # Search input
    query = st.text_input(
        "検索クエリを入力してください",
        placeholder="例: プロジェクトの進捗について",
        key="query_input"
    )

    col_search, col_answer = st.columns(2)

    with col_search:
        search_button = st.button("🔍 検索", type="primary", use_container_width=True)

    with col_answer:
        answer_button = st.button("💡 AI回答を生成", use_container_width=True)

# Execute search
if search_button and query:
    with st.spinner("検索中..."):
        try:
            # Prepare request payload
            payload = {
                "query": query,
                "top_k": top_k,
                "mode": search_mode
            }

            # Add filters
            if date_from:
                payload["date_from"] = date_from.isoformat()
            if date_to:
                payload["date_to"] = date_to.isoformat()
            if selected_senders:
                payload["senders"] = selected_senders
            if selected_tags:
                payload["tags"] = selected_tags

            # Make API request
            response = requests.post(
                f"{BACKEND_URL}/api/search",
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                st.session_state.search_results = response.json()
                st.success(f"✅ {len(st.session_state.search_results.get('results', []))} 件の結果が見つかりました")
            else:
                st.error(f"❌ 検索エラー: {response.status_code}")
                st.session_state.search_results = None

        except Exception as e:
            st.error(f"❌ エラーが発生しました: {str(e)}")
            st.session_state.search_results = None

# Execute answer generation
if answer_button and query:
    with st.spinner("AI回答を生成中..."):
        try:
            # Prepare request payload
            payload = {
                "query": query,
                "top_k": top_k,
                "mode": search_mode
            }

            # Add filters
            if date_from:
                payload["date_from"] = date_from.isoformat()
            if date_to:
                payload["date_to"] = date_to.isoformat()
            if selected_senders:
                payload["senders"] = selected_senders
            if selected_tags:
                payload["tags"] = selected_tags

            # Make API request
            response = requests.post(
                f"{BACKEND_URL}/api/answer",
                json=payload,
                timeout=60
            )

            if response.status_code == 200:
                st.session_state.answer = response.json()
                st.success("✅ AI回答を生成しました")
            else:
                st.error(f"❌ 回答生成エラー: {response.status_code}")
                st.session_state.answer = None

        except Exception as e:
            st.error(f"❌ エラーが発生しました: {str(e)}")
            st.session_state.answer = None

# Display AI answer
if st.session_state.answer:
    st.markdown("### 💡 AI回答")
    answer_data = st.session_state.answer

    st.markdown(f"""
    <div class="answer-box">
        <h4>回答</h4>
        <p>{answer_data.get('answer', '')}</p>
    </div>
    """, unsafe_allow_html=True)

    # Show metadata
    with st.expander("📊 詳細情報"):
        col_meta1, col_meta2 = st.columns(2)
        with col_meta1:
            st.metric("使用したドキュメント数", answer_data.get('num_documents_used', 0))
        with col_meta2:
            st.metric("検索スコア", f"{answer_data.get('search_score', 0):.3f}")

        if 'sources' in answer_data and answer_data['sources']:
            st.markdown("**参照元:**")
            for idx, source in enumerate(answer_data['sources'], 1):
                st.markdown(f"{idx}. {source}")

# Display search results
if st.session_state.search_results:
    st.markdown("### 📄 検索結果")

    results = st.session_state.search_results.get('results', [])

    if not results:
        st.info("検索結果がありません")
    else:
        for idx, result in enumerate(results, 1):
            with st.expander(f"📧 {idx}. {result.get('title', '無題')} (スコア: {result.get('score', 0):.3f})"):
                # Metadata
                col_meta1, col_meta2, col_meta3 = st.columns(3)
                with col_meta1:
                    st.markdown(f"**送信者:** {result.get('sender', 'N/A')}")
                with col_meta2:
                    st.markdown(f"**日付:** {result.get('date', 'N/A')}")
                with col_meta3:
                    tags = result.get('tags', [])
                    if tags:
                        st.markdown(f"**タグ:** {', '.join(tags)}")

                st.markdown("---")

                # Content
                st.markdown("**内容:**")
                content = result.get('content', '')
                if len(content) > 500:
                    st.markdown(content[:500] + "...")
                    if st.button(f"全文を表示 ({idx})", key=f"show_full_{idx}"):
                        st.markdown(content)
                else:
                    st.markdown(content)

                # Additional metadata
                if result.get('file_path'):
                    st.markdown(f"**ファイルパス:** `{result.get('file_path')}`")

with col2:
    st.markdown("### ℹ️ 使い方")
    st.markdown("""
    1. **検索クエリを入力**
       - 探したい内容をテキストボックスに入力

    2. **フィルターを設定** (任意)
       - 左サイドバーから日付、送信者、タグなどを選択

    3. **検索実行**
       - 🔍 検索: 関連するドキュメントを検索
       - 💡 AI回答: AIが回答を生成

    4. **結果を確認**
       - 検索結果や回答を確認
    """)

    st.markdown("---")
    st.markdown("### 📊 システム情報")
    st.info(f"バックエンド: {BACKEND_URL}")

    # Health check
    if st.button("接続確認"):
        try:
            response = requests.get(f"{BACKEND_URL}/", timeout=5)
            if response.status_code == 200:
                st.success("✅ バックエンドに接続できました")
            else:
                st.warning(f"⚠️ ステータスコード: {response.status_code}")
        except Exception as e:
            st.error(f"❌ 接続エラー: {str(e)}")
