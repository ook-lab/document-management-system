"""
3ネットスーパー横断商品検索アプリ

楽天西友、東急ストア、ダイエーの商品を横断検索
安い順に表示
"""

import streamlit as st
import os
from supabase import create_client

# ページ設定
st.set_page_config(
    page_title="ネットスーパー横断検索",
    page_icon="🛒",
    layout="wide"
)

# Supabase接続
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("環境変数 SUPABASE_URL と SUPABASE_KEY を設定してください")
    st.stop()

db = create_client(SUPABASE_URL, SUPABASE_KEY)

# タイトル
st.title("🛒 ネットスーパー横断検索")
st.markdown("**楽天西友・東急ストア・ダイエー**の商品を一括検索！安い順に表示します")

# URLのクエリパラメータから検索キーワードを取得
query_params = st.query_params
default_query = query_params.get("q", "")

# 検索欄
st.subheader("🔍 商品を検索")
col1, col2 = st.columns([4, 1])
with col1:
    search_query = st.text_input("商品名", value=default_query, placeholder="例: 牛乳、卵、パン", label_visibility="collapsed")
with col2:
    search_button = st.button("検索", type="primary", use_container_width=True)

# 検索ボタンが押されたらクエリパラメータを更新
if search_button and search_query:
    st.query_params.update(q=search_query)
    st.rerun()

if search_query:
    # 80_rd_productsから検索
    try:
        # ネットスーパー3社の商品のみ検索
        result = db.table('80_rd_products').select(
            'id, product_name, organization, current_price_tax_included, image_url, metadata'
        ).in_(
            'organization',
            ['楽天西友ネットスーパー', '東急ストア ネットスーパー', 'ダイエーネットスーパー']
        ).ilike(
            'product_name',
            f'%{search_query}%'
        ).order(
            'current_price_tax_included',
            desc=False
        ).limit(20).execute()

        products = result.data

        # current_price_tax_includedがnullまたは0の商品を除外
        products = [p for p in products if p.get('current_price_tax_included') and float(p.get('current_price_tax_included', 0)) > 0]

        if products:
            st.success(f"✅ {len(products)}件の商品が見つかりました")

            # 商品一覧表示
            for i, product in enumerate(products, 1):
                with st.container():
                    col1, col2 = st.columns([1, 4])

                    with col1:
                        # 商品画像
                        if product.get('image_url'):
                            st.image(product['image_url'], width=150)
                        else:
                            st.image("https://via.placeholder.com/150?text=No+Image", width=150)

                    with col2:
                        # 商品情報
                        st.markdown(f"### {i}. {product['product_name']}")

                        # 価格（大きく表示）
                        price = product.get('current_price_tax_included', 0)
                        st.markdown(f"## ¥{price:,.0f} (税込)")

                        # 店舗名
                        organization = product.get('organization', '不明')
                        if organization == '楽天西友ネットスーパー':
                            st.markdown(f"🏪 **{organization}** 🟢")
                        elif organization == '東急ストア ネットスーパー':
                            st.markdown(f"🏪 **{organization}** 🔵")
                        elif organization == 'ダイエーネットスーパー':
                            st.markdown(f"🏪 **{organization}** 🔴")
                        else:
                            st.markdown(f"🏪 **{organization}**")

                        # 商品リンク（metadataから取得）
                        metadata = product.get('metadata', {})
                        if isinstance(metadata, dict):
                            product_url = metadata.get('raw_data', {}).get('url')
                            if product_url:
                                st.markdown(f"[🔗 商品ページを開く]({product_url})")

                    st.divider()
        else:
            st.warning(f"「{search_query}」に該当する商品が見つかりませんでした")
            st.info("💡 ヒント: 別のキーワードを試してみてください")

    except Exception as e:
        st.error(f"❌ 検索エラー: {e}")
        st.exception(e)

else:
    # 初期画面
    st.info("👆 上の検索欄に商品名を入力してください")

    # サンプル検索
    st.markdown("### 💡 試してみる")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🥛 牛乳"):
            st.query_params.update(q="牛乳")
            st.rerun()

    with col2:
        if st.button("🥚 卵"):
            st.query_params.update(q="卵")
            st.rerun()

    with col3:
        if st.button("🍞 パン"):
            st.query_params.update(q="パン")
            st.rerun()

# フッター
st.markdown("---")
st.markdown("**対象ストア:** 楽天西友ネットスーパー / 東急ストア ネットスーパー / ダイエーネットスーパー")
