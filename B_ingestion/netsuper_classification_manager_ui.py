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

# セッション状態の初期化
if 'general_name_index' not in st.session_state:
    st.session_state.general_name_index = 0
if 'large_category' not in st.session_state:
    st.session_state.large_category = None
if 'medium_category' not in st.session_state:
    st.session_state.medium_category = None
if 'small_category' not in st.session_state:
    st.session_state.small_category = None

# 一般名詞リスト取得（キャッシュ）
@st.cache_data(ttl=60)
def get_general_names():
    result = db.table('Rawdata_NETSUPER_items').select(
        'general_name'
    ).not_.is_('general_name', 'null').execute()
    return sorted(list(set([r['general_name'] for r in result.data if r.get('general_name')])))

# カテゴリ階層を構築（キャッシュ）
@st.cache_data(ttl=60)
def build_category_hierarchy():
    """MASTER_Categories_productから階層パスを構築"""
    result = db.table('MASTER_Categories_product').select('id, name, parent_id').execute()

    categories = {cat['id']: cat for cat in result.data}

    def get_path(cat_id):
        """カテゴリIDから階層パスを取得"""
        path = []
        current_id = cat_id
        while current_id:
            cat = categories.get(current_id)
            if cat:
                path.insert(0, cat['name'])
                current_id = cat['parent_id']
            else:
                break
        return ' > '.join(path)

    # 各カテゴリのパスを構築
    paths = {}
    for cat_id, cat in categories.items():
        paths[cat['name']] = get_path(cat_id)

    return paths

# カテゴリ階層取得（キャッシュ）
@st.cache_data(ttl=60)
def get_category_tree():
    """MASTER_Categories_productから階層構造を取得"""
    result = db.table('MASTER_Categories_product').select('id, name, parent_id').execute()
    categories = {cat['id']: cat for cat in result.data}

    # {category_name: {id, parent_id, children}} の辞書を構築
    tree = {}
    for cat in result.data:
        tree[cat['name']] = {
            'id': cat['id'],
            'parent_id': cat['parent_id'],
            'children': []
        }

    # 親子関係を構築
    for cat_name, cat_data in tree.items():
        if cat_data['parent_id']:
            # 親カテゴリの名前を見つける
            parent_name = next((name for name, data in tree.items() if data['id'] == cat_data['parent_id']), None)
            if parent_name:
                tree[parent_name]['children'].append(cat_name)

    return tree

# 大分類（親なし）を取得（商品数付き）
@st.cache_data(ttl=60)
def get_large_categories():
    """大分類（parent_id が null）を取得（商品1件以上のみ、件数表示）"""
    # 全大分類を取得
    categories = db.table('MASTER_Categories_product').select('id, name').is_('parent_id', 'null').execute()

    # 各大分類配下の商品数をカウント
    cat_with_counts = {}
    tree = get_category_tree()

    for cat in categories.data:
        cat_name = cat['name']
        cat_id = cat['id']

        # 配下の全カテゴリー名を取得（small_categoryとのマッチング用）
        def get_all_descendant_names(name):
            if name not in tree:
                return []
            names = [name]
            for child in tree[name]['children']:
                names.extend(get_all_descendant_names(child))
            return names

        # 配下の全カテゴリーIDを取得
        def get_all_descendant_ids(name):
            if name not in tree:
                return []
            ids = [tree[name]['id']]
            for child in tree[name]['children']:
                ids.extend(get_all_descendant_ids(child))
            return ids

        all_ids = get_all_descendant_ids(cat_name)
        all_names = get_all_descendant_names(cat_name)

        # category_idでカウント
        count = 0
        if all_ids:
            count_result = db.client.table('Rawdata_NETSUPER_items').select('id', count='exact').in_('category_id', all_ids).execute()
            count += count_result.count if count_result.count else 0

        # small_category（テキスト）でもカウント
        for name in all_names:
            count_result = db.client.table('Rawdata_NETSUPER_items').select('id', count='exact').eq('small_category', name).execute()
            count += count_result.count if count_result.count else 0

        # 商品が1件以上ある場合のみ追加
        if count > 0:
            cat_with_counts[f"{cat_name} ({count}件)"] = cat_name

    return cat_with_counts

# 中分類を取得（商品数付き）
def get_medium_categories(large_category_name):
    """指定した大分類の子カテゴリを取得（商品1件以上のみ、件数表示）"""
    tree = get_category_tree()
    if large_category_name not in tree:
        return {}

    children = tree[large_category_name]['children']
    cat_with_counts = {}

    for child_name in children:
        # 配下の全カテゴリー名を取得
        def get_all_descendant_names(name):
            if name not in tree:
                return []
            names = [name]
            for c in tree[name]['children']:
                names.extend(get_all_descendant_names(c))
            return names

        # 配下の全カテゴリーIDを取得
        def get_all_descendant_ids(name):
            if name not in tree:
                return []
            ids = [tree[name]['id']]
            for c in tree[name]['children']:
                ids.extend(get_all_descendant_ids(c))
            return ids

        all_ids = get_all_descendant_ids(child_name)
        all_names = get_all_descendant_names(child_name)

        # category_idでカウント
        count = 0
        if all_ids:
            count_result = db.client.table('Rawdata_NETSUPER_items').select('id', count='exact').in_('category_id', all_ids).execute()
            count += count_result.count if count_result.count else 0

        # small_category（テキスト）でもカウント
        for name in all_names:
            count_result = db.client.table('Rawdata_NETSUPER_items').select('id', count='exact').eq('small_category', name).execute()
            count += count_result.count if count_result.count else 0

        # 商品が1件以上ある場合のみ追加
        if count > 0:
            cat_with_counts[f"{child_name} ({count}件)"] = child_name

    return cat_with_counts

# 小分類を取得（商品数付き）
def get_small_categories_by_medium(medium_category_name):
    """指定した中分類の子カテゴリを取得（件数表示）"""
    tree = get_category_tree()
    if medium_category_name not in tree:
        return {}

    children = tree[medium_category_name]['children']
    cat_with_counts = {}

    for child_name in children:
        # category_idとsmall_categoryの両方でカウント
        count = 0
        if child_name in tree:
            cat_id = tree[child_name]['id']
            # category_idでカウント
            count_by_id = db.client.table('Rawdata_NETSUPER_items').select('id', count='exact').eq('category_id', cat_id).execute()
            count += count_by_id.count if count_by_id.count else 0

        # small_category（テキストフィールド）でもカウント
        count_by_name = db.client.table('Rawdata_NETSUPER_items').select('id', count='exact').eq('small_category', child_name).execute()
        count += count_by_name.count if count_by_name.count else 0

        # 商品が1件以上ある場合のみ追加
        if count > 0:
            cat_with_counts[f"{child_name} ({count}件)"] = child_name

    return cat_with_counts

# タブで表示方法を切り替え
tabs = st.tabs(["一般名詞で分類", "小カテゴリで分類", "統計情報"])

# =============================================================================
# タブ1: 一般名詞で分類
# =============================================================================
with tabs[0]:
    st.header("一般名詞（general_name）ごとに商品を確認・修正")

    general_names = get_general_names()

    if not general_names:
        st.info("一般名詞が設定されている商品がありません。")
    else:
        # 検索ボックス
        search_term = st.text_input(
            "🔍 一般名詞を検索",
            placeholder="例: 牛乳、卵、パン...",
            key="general_name_search"
        )

        # 検索フィルタリング
        if search_term:
            filtered_names = [name for name in general_names if search_term.lower() in name.lower()]
        else:
            filtered_names = general_names

        if not filtered_names:
            st.warning(f"「{search_term}」に一致する一般名詞が見つかりません。")
        else:
            # 一般名詞を選択
            selected_general_name = st.selectbox(
                f"一般名詞を選択（{len(filtered_names)}件）",
                filtered_names,
                index=min(st.session_state.general_name_index, len(filtered_names)-1),
                key="general_name_select",
                on_change=lambda: setattr(st.session_state, 'general_name_index', filtered_names.index(st.session_state.general_name_select) if st.session_state.general_name_select in filtered_names else 0)
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
# タブ2: 小カテゴリで分類（3段階連動プルダウン + 未分類対応）
# =============================================================================
with tabs[1]:
    st.header("小カテゴリ（small_category）ごとに商品を確認・修正")

    # 大分類を取得（{表示名: 実名} の辞書）
    large_categories_dict = get_large_categories()
    large_display_names = list(large_categories_dict.keys())

    col1, col2, col3 = st.columns(3)

    with col1:
        # 大分類プルダウン（「未分類」を追加）
        selected_large_display = st.selectbox(
            "🏢 大分類",
            ["選択してください", "未分類"] + large_display_names,
            key="large_cat_select"
        )

    # 表示名から実名を取得
    if selected_large_display in large_categories_dict:
        selected_large = large_categories_dict[selected_large_display]
    else:
        selected_large = selected_large_display  # "選択してください" or "未分類"

    # 中分類を取得
    medium_categories_dict = {}
    if selected_large and selected_large not in ["選択してください", "未分類"]:
        medium_categories_dict = get_medium_categories(selected_large)
    medium_display_names = list(medium_categories_dict.keys())

    with col2:
        # 中分類プルダウン（「未分類」を追加）
        if selected_large == "選択してください":
            st.selectbox("📂 中分類", ["大分類を選択してください"], disabled=True)
            selected_medium_display = None
            selected_medium = None
        elif selected_large == "未分類":
            selected_medium_display = st.selectbox("📂 中分類", ["未分類"], key="medium_cat_select")
            selected_medium = "未分類"
        elif medium_display_names:
            selected_medium_display = st.selectbox(
                "📂 中分類",
                ["選択してください", "未分類"] + medium_display_names,
                key="medium_cat_select"
            )
            # 表示名から実名を取得
            if selected_medium_display in medium_categories_dict:
                selected_medium = medium_categories_dict[selected_medium_display]
            else:
                selected_medium = selected_medium_display
        else:
            selected_medium_display = st.selectbox("📂 中分類", ["未分類"], key="medium_cat_select")
            selected_medium = "未分類"

    # 小分類を取得
    small_categories_dict = {}
    if selected_medium and selected_medium not in ["選択してください"]:
        if selected_medium == "未分類":
            # 未分類の場合、階層なし小カテゴリーを全て取得
            result = db.table('Rawdata_NETSUPER_items').select('small_category').not_.is_('small_category', 'null').execute()
            all_small = list(set([r['small_category'] for r in result.data if r.get('small_category')]))

            # MASTER_Categories_productに存在するカテゴリーを除外
            tree = get_category_tree()
            small_list = sorted([cat for cat in all_small if cat not in tree])
            # リストを辞書に変換（未分類の場合は件数表示なし）
            small_categories_dict = {cat: cat for cat in small_list}
        else:
            small_categories_dict = get_small_categories_by_medium(selected_medium)

    small_display_names = list(small_categories_dict.keys())

    with col3:
        # 小分類プルダウン
        if selected_medium is None or selected_medium == "選択してください":
            st.selectbox("📄 小分類", ["中分類を選択してください"], disabled=True)
            selected_small_display = None
            selected_small = None
        elif small_display_names:
            selected_small_display = st.selectbox(
                "📄 小分類",
                ["選択してください"] + small_display_names,
                key="small_cat_select"
            )
            # 表示名から実名を取得
            if selected_small_display in small_categories_dict:
                selected_small = small_categories_dict[selected_small_display]
            else:
                selected_small = selected_small_display
        else:
            st.selectbox("📄 小分類", ["該当なし"], disabled=True)
            selected_small_display = None
            selected_small = None

    # 商品を表示（部分選択対応）
    products = None
    display_path = ""

    # 再帰的な子孫ID取得関数（共通）
    def get_all_descendant_ids(cat_name):
        tree = get_category_tree()
        if cat_name not in tree:
            return []
        ids = [tree[cat_name]['id']]
        for child in tree[cat_name]['children']:
            ids.extend(get_all_descendant_ids(child))
        return ids

    # 小分類まで選択されている場合
    if selected_small and selected_small != "選択してください":
        products = db.table('Rawdata_NETSUPER_items').select(
            'id, product_name, general_name, small_category, category_id, organization, current_price_tax_included'
        ).eq('small_category', selected_small).limit(100).execute()

        if selected_large == "未分類":
            display_path = f"📂 未分類 > 未分類 > {selected_small}"
        else:
            display_path = f"📂 {selected_large} > {selected_medium} > {selected_small}"

    # 大+中分類選択、小分類は未選択
    elif selected_medium and selected_medium not in ["選択してください", "未分類", None]:
        all_cat_ids = get_all_descendant_ids(selected_medium)
        if all_cat_ids:
            products = db.table('Rawdata_NETSUPER_items').select(
                'id, product_name, general_name, small_category, category_id, organization, current_price_tax_included'
            ).in_('category_id', all_cat_ids).limit(1000).execute()
            display_path = f"📂 {selected_large} > {selected_medium} （配下全て）"

    # 大分類のみ選択、中分類は未選択
    elif selected_large and selected_large not in ["選択してください", "未分類"]:
        all_cat_ids = get_all_descendant_ids(selected_large)
        if all_cat_ids:
            products = db.table('Rawdata_NETSUPER_items').select(
                'id, product_name, general_name, small_category, category_id, organization, current_price_tax_included'
            ).in_('category_id', all_cat_ids).limit(1000).execute()
            display_path = f"📂 {selected_large} （配下全て）"

    if products and products.data:
        st.subheader(f"{display_path} ({len(products.data)}件)")

        # カテゴリー名からID逆引き用の辞書を作成
        tree = get_category_tree()

        # 各商品のcategory_idから大・中・小カテゴリーを取得する関数
        def get_category_hierarchy_from_id(category_id):
            if not category_id:
                return "未分類", "未分類", ""

            # category_idから該当するカテゴリー名を見つける
            cat_name = next((name for name, data in tree.items() if data['id'] == category_id), None)
            if not cat_name:
                return "未分類", "未分類", ""

            # 小カテゴリー名
            small = cat_name

            # 中カテゴリー名（親）
            parent_id = tree[cat_name]['parent_id']
            medium = next((name for name, data in tree.items() if data['id'] == parent_id), "未分類") if parent_id else "未分類"

            # 大カテゴリー名（親の親）
            if medium != "未分類" and tree[medium]['parent_id']:
                large = next((name for name, data in tree.items() if data['id'] == tree[medium]['parent_id']), "未分類")
            else:
                large = "未分類"

            return large, medium, small

        # データフレームに変換（ID列を削除、大中分類を追加）
        df_data = []
        for p in products.data:
            large, medium, small = get_category_hierarchy_from_id(p.get('category_id'))
            # small_categoryフィールドがあればそれを優先
            if p.get('small_category'):
                small = p.get('small_category')

            df_data.append({
                "_id": p['id'],  # 内部用（非表示）
                "商品名": p['product_name'],
                "一般名詞": p.get('general_name', ''),
                "大分類": large,
                "中分類": medium,
                "小分類": small,
                "店舗": p.get('organization', ''),
                "価格": p.get('current_price_tax_included', 0)
            })

        df = pd.DataFrame(df_data)

        # データエディタで編集
        edited_df = st.data_editor(
            df,
            column_config={
                "_id": None,  # 非表示
                "商品名": st.column_config.TextColumn("商品名", disabled=True, width="large"),
                "一般名詞": st.column_config.TextColumn("一般名詞", width="medium"),
                "大分類": st.column_config.TextColumn("大分類", width="small"),
                "中分類": st.column_config.TextColumn("中分類", width="small"),
                "小分類": st.column_config.TextColumn("小分類", width="medium"),
                "店舗": st.column_config.TextColumn("店舗", disabled=True, width="small"),
                "価格": st.column_config.NumberColumn("価格", disabled=True, width="small")
            },
            hide_index=True,
            key=f"editor_category_{selected_large}_{selected_medium}_{selected_small}"
        )

        # カテゴリー作成/取得ヘルパー関数
        def get_or_create_category(category_name, parent_id=None):
            """カテゴリーを取得、なければ作成"""
            if not category_name or category_name == "未分類":
                return None

            # 既存カテゴリーを検索
            query = db.table('MASTER_Categories_product').select('id, name, parent_id')
            if parent_id:
                result = query.eq('name', category_name).eq('parent_id', parent_id).execute()
            else:
                result = query.eq('name', category_name).is_('parent_id', 'null').execute()

            if result.data:
                return result.data[0]['id']

            # 新規作成
            new_cat = {
                'name': category_name,
                'parent_id': parent_id
            }
            result = db.table('MASTER_Categories_product').insert(new_cat).execute()
            return result.data[0]['id']

        # 保存ボタン
        if st.button("💾 変更を保存", type="primary", key="save_category"):
            # 変更を反映
            current_time = datetime.now(timezone.utc).isoformat()
            success_count = 0
            has_verified_column = True

            for idx, row in edited_df.iterrows():
                product_id = row["_id"]

                # カテゴリー階層を作成/取得
                large_name = row["大分類"]
                medium_name = row["中分類"]
                small_name = row["小分類"]

                # 大分類 → 中分類 → 小分類の順に作成/取得
                large_id = get_or_create_category(large_name, parent_id=None)
                medium_id = get_or_create_category(medium_name, parent_id=large_id) if large_id else None
                small_id = get_or_create_category(small_name, parent_id=medium_id) if medium_id else None

                # 小分類のIDが取得できなかった場合、small_nameだけで検索
                if not small_id and small_name and small_name != "未分類":
                    small_id = get_or_create_category(small_name, parent_id=None)

                update_data = {
                    "general_name": row["一般名詞"],
                    "small_category": small_name if small_name != "未分類" else None,
                    "category_id": small_id
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
                            "small_category": small_name if small_name != "未分類" else None,
                            "category_id": small_id
                        }
                        db.table('Rawdata_NETSUPER_items').update(update_data).eq('id', product_id).execute()
                        success_count += 1
                    else:
                        raise

            # キャッシュをクリア（新しいカテゴリーが追加された場合）
            st.cache_data.clear()

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
