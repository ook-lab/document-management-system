"""
ネットスーパー商品分類管理UI

商品のgeneral_nameとsmall_categoryを分類ごとにレビュー・修正します。
"""

import streamlit as st
import pandas as pd
import os
from datetime import datetime, timezone
from supabase import create_client

# ページ設定
st.set_page_config(
    page_title="商品分類管理",
    page_icon="🏷️",
    layout="wide"
)

st.title("🏷️ ネットスーパー商品分類管理")

# Supabase接続
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("環境変数 SUPABASE_URL と SUPABASE_KEY を設定してください")
    st.stop()

db = create_client(SUPABASE_URL, SUPABASE_KEY)

# タブで表示方法を切り替え
tabs = st.tabs(["一般名詞で分類", "小カテゴリで分類", "統計情報"])

# =============================================================================
# タブ1: 一般名詞で分類
# =============================================================================
with tabs[0]:
    st.header("一般名詞（general_name）ごとに商品を確認・修正")

    # 一般名詞のリストを取得
    result = db.table('Rawdata_NETSUPER_items').select(
        'general_name'
    ).not_.is_('general_name', 'null').execute()

    general_names = sorted(list(set([r['general_name'] for r in result.data if r.get('general_name')])))

    if not general_names:
        st.info("一般名詞が設定されている商品がありません。")
    else:
        # 一般名詞を選択
        selected_general_name = st.selectbox(
            "一般名詞を選択",
            general_names,
            key="general_name_select"
        )

        if selected_general_name:
            # 選択した一般名詞の商品を取得
            products = db.table('Rawdata_NETSUPER_items').select(
                'id, product_name, general_name, small_category, organization, current_price_tax_included'
            ).eq('general_name', selected_general_name).limit(100).execute()

            st.subheader(f"一般名詞: {selected_general_name} ({len(products.data)}件)")

            if products.data:
                # データフレームに変換
                df_data = []
                for p in products.data:
                    df_data.append({
                        "ID": p['id'],
                        "商品名": p['product_name'],
                        "一般名詞": p.get('general_name', ''),
                        "小カテゴリ": p.get('small_category', ''),
                        "店舗": p.get('organization', ''),
                        "価格": p.get('current_price_tax_included', 0)
                    })

                df = pd.DataFrame(df_data)

                # データエディタで編集
                edited_df = st.data_editor(
                    df,
                    column_config={
                        "ID": st.column_config.TextColumn("ID", disabled=True, width="small"),
                        "商品名": st.column_config.TextColumn("商品名", disabled=True, width="large"),
                        "一般名詞": st.column_config.TextColumn("一般名詞", width="medium"),
                        "小カテゴリ": st.column_config.TextColumn("小カテゴリ", width="medium"),
                        "店舗": st.column_config.TextColumn("店舗", disabled=True, width="medium"),
                        "価格": st.column_config.NumberColumn("価格", disabled=True, width="small")
                    },
                    hide_index=True,
                    key=f"editor_general_{selected_general_name}"
                )

                # 保存ボタン
                if st.button("💾 変更を保存", type="primary", key="save_general"):
                    # 変更を反映
                    current_time = datetime.now(timezone.utc).isoformat()
                    success_count = 0
                    has_verified_column = True

                    for idx, row in edited_df.iterrows():
                        product_id = row["ID"]
                        update_data = {
                            "general_name": row["一般名詞"],
                            "small_category": row["小カテゴリ"]
                        }

                        # manually_verified カラムが存在する場合のみ追加
                        if has_verified_column:
                            update_data["manually_verified"] = True
                            update_data["last_verified_at"] = current_time

                        try:
                            db.table('Rawdata_NETSUPER_items').update(update_data).eq('id', product_id).execute()
                            success_count += 1
                        except Exception as e:
                            # manually_verified カラムが存在しない場合、フラグなしで再試行
                            if "manually_verified" in str(e) and has_verified_column:
                                has_verified_column = False
                                update_data = {
                                    "general_name": row["一般名詞"],
                                    "small_category": row["小カテゴリ"]
                                }
                                db.table('Rawdata_NETSUPER_items').update(update_data).eq('id', product_id).execute()
                                success_count += 1
                            else:
                                raise

                    if has_verified_column:
                        st.success(f"✅ {success_count}件の商品を更新しました（検証済みとしてマーク）")
                    else:
                        st.success(f"✅ {success_count}件の商品を更新しました")
                        st.info("💡 ヒント: マイグレーション実行後、検証済みフラグが自動的に付くようになります")
                    st.rerun()

# =============================================================================
# タブ2: 小カテゴリで分類
# =============================================================================
with tabs[1]:
    st.header("小カテゴリ（small_category）ごとに商品を確認・修正")

    # 小カテゴリのリストを取得
    result = db.table('Rawdata_NETSUPER_items').select(
        'small_category'
    ).not_.is_('small_category', 'null').execute()

    small_categories = sorted(list(set([r['small_category'] for r in result.data if r.get('small_category')])))

    if not small_categories:
        st.info("小カテゴリが設定されている商品がありません。")
    else:
        # 小カテゴリを選択
        selected_category = st.selectbox(
            "小カテゴリを選択",
            small_categories,
            key="category_select"
        )

        if selected_category:
            # 選択した小カテゴリの商品を取得
            products = db.table('Rawdata_NETSUPER_items').select(
                'id, product_name, general_name, small_category, organization, current_price_tax_included'
            ).eq('small_category', selected_category).limit(100).execute()

            st.subheader(f"小カテゴリ: {selected_category} ({len(products.data)}件)")

            if products.data:
                # データフレームに変換
                df_data = []
                for p in products.data:
                    df_data.append({
                        "ID": p['id'],
                        "商品名": p['product_name'],
                        "一般名詞": p.get('general_name', ''),
                        "小カテゴリ": p.get('small_category', ''),
                        "店舗": p.get('organization', ''),
                        "価格": p.get('current_price_tax_included', 0)
                    })

                df = pd.DataFrame(df_data)

                # データエディタで編集
                edited_df = st.data_editor(
                    df,
                    column_config={
                        "ID": st.column_config.TextColumn("ID", disabled=True, width="small"),
                        "商品名": st.column_config.TextColumn("商品名", disabled=True, width="large"),
                        "一般名詞": st.column_config.TextColumn("一般名詞", width="medium"),
                        "小カテゴリ": st.column_config.TextColumn("小カテゴリ", width="medium"),
                        "店舗": st.column_config.TextColumn("店舗", disabled=True, width="medium"),
                        "価格": st.column_config.NumberColumn("価格", disabled=True, width="small")
                    },
                    hide_index=True,
                    key=f"editor_category_{selected_category}"
                )

                # 保存ボタン
                if st.button("💾 変更を保存", type="primary", key="save_category"):
                    # 変更を反映
                    current_time = datetime.now(timezone.utc).isoformat()
                    success_count = 0
                    has_verified_column = True

                    for idx, row in edited_df.iterrows():
                        product_id = row["ID"]
                        update_data = {
                            "general_name": row["一般名詞"],
                            "small_category": row["小カテゴリ"]
                        }

                        # manually_verified カラムが存在する場合のみ追加
                        if has_verified_column:
                            update_data["manually_verified"] = True
                            update_data["last_verified_at"] = current_time

                        try:
                            db.table('Rawdata_NETSUPER_items').update(update_data).eq('id', product_id).execute()
                            success_count += 1
                        except Exception as e:
                            # manually_verified カラムが存在しない場合、フラグなしで再試行
                            if "manually_verified" in str(e) and has_verified_column:
                                has_verified_column = False
                                update_data = {
                                    "general_name": row["一般名詞"],
                                    "small_category": row["小カテゴリ"]
                                }
                                db.table('Rawdata_NETSUPER_items').update(update_data).eq('id', product_id).execute()
                                success_count += 1
                            else:
                                raise

                    if has_verified_column:
                        st.success(f"✅ {success_count}件の商品を更新しました（検証済みとしてマーク）")
                    else:
                        st.success(f"✅ {success_count}件の商品を更新しました")
                        st.info("💡 ヒント: マイグレーション実行後、検証済みフラグが自動的に付くようになります")
                    st.rerun()

# =============================================================================
# タブ3: 統計情報
# =============================================================================
with tabs[2]:
    st.header("📊 分類統計情報")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("一般名詞別の商品数")

        # 一般名詞ごとの商品数を集計
        result = db.table('Rawdata_NETSUPER_items').select(
            'general_name'
        ).not_.is_('general_name', 'null').execute()

        general_name_counts = {}
        for r in result.data:
            name = r.get('general_name', '未分類')
            general_name_counts[name] = general_name_counts.get(name, 0) + 1

        # データフレームに変換して表示
        if general_name_counts:
            df_general = pd.DataFrame([
                {"一般名詞": name, "商品数": count}
                for name, count in sorted(general_name_counts.items(), key=lambda x: x[1], reverse=True)
            ])
            st.dataframe(df_general, hide_index=True, height=400)

    with col2:
        st.subheader("小カテゴリ別の商品数")

        # 小カテゴリごとの商品数を集計
        result = db.table('Rawdata_NETSUPER_items').select(
            'small_category'
        ).not_.is_('small_category', 'null').execute()

        category_counts = {}
        for r in result.data:
            cat = r.get('small_category', '未分類')
            category_counts[cat] = category_counts.get(cat, 0) + 1

        # データフレームに変換して表示
        if category_counts:
            df_category = pd.DataFrame([
                {"小カテゴリ": cat, "商品数": count}
                for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
            ])
            st.dataframe(df_category, hide_index=True, height=400)

    # 未分類商品の数
    st.divider()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total = db.table('Rawdata_NETSUPER_items').select('id', count='exact').execute()
        st.metric("総商品数", total.count)

    with col2:
        no_general = db.table('Rawdata_NETSUPER_items').select('id', count='exact').is_('general_name', 'null').execute()
        st.metric("一般名詞未設定", no_general.count)

    with col3:
        no_category = db.table('Rawdata_NETSUPER_items').select('id', count='exact').is_('small_category', 'null').execute()
        st.metric("小カテゴリ未設定", no_category.count)

    with col4:
        try:
            verified = db.table('Rawdata_NETSUPER_items').select('id', count='exact').eq('manually_verified', True).execute()
            st.metric("手動検証済み", verified.count, delta="AI学習用データ")
        except Exception:
            # manually_verified カラムがまだ存在しない場合
            st.metric("手動検証済み", 0, delta="要マイグレーション", delta_color="off")
