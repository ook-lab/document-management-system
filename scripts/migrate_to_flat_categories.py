"""
既存の階層構造カテゴリを新形式（大分類>中分類>小分類）に変換

処理内容：
1. 既存のparent_id階層を辿って大中小を特定
2. 新形式（name="大分類>中分類>小分類"）でレコードを作成
3. 商品のcategory_idを新IDに更新
4. 古い階層カテゴリを削除
"""

import os
from supabase import create_client
from typing import Dict, List
from collections import defaultdict

# 設定
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not all([SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY]):
    raise Exception("環境変数を設定してください")

db = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def fetch_all_categories() -> List[Dict]:
    """全カテゴリを取得"""
    print("\n=== 既存カテゴリを取得中 ===")
    result = db.table('MASTER_Categories_product').select('*').execute()
    print(f"取得完了: {len(result.data)}件")
    return result.data


def build_hierarchy_tree(categories: List[Dict]) -> Dict:
    """parent_idを使って階層ツリーを構築"""
    print("\n=== 階層ツリーを構築中 ===")

    # IDでインデックス
    cat_by_id = {cat['id']: cat for cat in categories}

    # 子を親にマッピング
    children_by_parent = defaultdict(list)
    for cat in categories:
        parent_id = cat.get('parent_id')
        children_by_parent[parent_id].append(cat)

    return cat_by_id, children_by_parent


def get_category_path(cat_id: str, cat_by_id: Dict) -> List[str]:
    """カテゴリIDから階層パスを取得（下から上へ）"""
    path = []
    current_id = cat_id

    while current_id:
        cat = cat_by_id.get(current_id)
        if not cat:
            break
        path.append(cat['name'])
        current_id = cat.get('parent_id')

    return list(reversed(path))  # 上から下に反転


def create_flat_categories(cat_by_id: Dict, children_by_parent: Dict) -> Dict[str, str]:
    """
    新形式のカテゴリを作成
    Returns: {old_id: new_id} のマッピング
    """
    print("\n=== 新形式カテゴリを作成中 ===")

    old_to_new_id = {}
    created_names = set()  # 重複防止

    # 大分類（parent_id=NULL）から開始
    large_categories = children_by_parent.get(None, [])

    for large_cat in large_categories:
        large_name = large_cat['name']

        # 中分類を取得
        medium_categories = children_by_parent.get(large_cat['id'], [])

        for medium_cat in medium_categories:
            medium_name = medium_cat['name']

            # 小分類を取得
            small_categories = children_by_parent.get(medium_cat['id'], [])

            for small_cat in small_categories:
                small_name = small_cat['name']

                # 新形式の名前
                full_name = f"{large_name}>{medium_name}>{small_name}"

                # 重複チェック
                if full_name in created_names:
                    print(f"  ⚠️  重複スキップ: {full_name}")
                    continue

                # 新規作成
                try:
                    new_cat = db.table('MASTER_Categories_product').insert({
                        'name': full_name,
                        'large_category': large_name,
                        'medium_category': medium_name,
                        'small_category': small_name,
                        'parent_id': None
                    }).execute()

                    new_id = new_cat.data[0]['id']
                    old_to_new_id[small_cat['id']] = new_id
                    created_names.add(full_name)

                    print(f"  ✅ {full_name}")

                except Exception as e:
                    print(f"  ❌ 作成失敗: {full_name} - {e}")

    print(f"\n作成完了: {len(old_to_new_id)}件")
    return old_to_new_id


def update_product_categories(old_to_new_id: Dict[str, str]):
    """商品のcategory_idを新IDに更新"""
    print("\n=== 商品のcategory_idを更新中 ===")

    updated_count = 0

    for old_id, new_id in old_to_new_id.items():
        # この old_id を持つ商品を検索
        result = db.table('Rawdata_NETSUPER_items').select('id').eq('category_id', old_id).execute()

        if result.data:
            product_count = len(result.data)

            # 一括更新
            db.table('Rawdata_NETSUPER_items').update({
                'category_id': new_id
            }).eq('category_id', old_id).execute()

            updated_count += product_count

            if updated_count % 100 == 0:
                print(f"  進捗: {updated_count}件")

    print(f"✅ 完了: {updated_count}件の商品を更新")


def delete_old_hierarchy_categories(cat_by_id: Dict, old_to_new_id: Dict):
    """古い階層カテゴリを削除"""
    print("\n=== 古い階層カテゴリを削除中 ===")

    # 削除対象: parent_idがNULLでないもの、または変換されたもの
    delete_ids = []

    for cat_id, cat in cat_by_id.items():
        # 新形式に変換されたものは削除
        if cat_id in old_to_new_id:
            delete_ids.append(cat_id)
        # parent_idを持つ中分類・大分類も削除
        elif cat.get('parent_id') is not None:
            delete_ids.append(cat_id)
        # parent_idがNULLで、名前に">"が含まれないものも削除（古い大分類・中分類）
        elif '>' not in cat.get('name', ''):
            delete_ids.append(cat_id)

    print(f"削除対象: {len(delete_ids)}件")

    for cat_id in delete_ids:
        try:
            db.table('MASTER_Categories_product').delete().eq('id', cat_id).execute()
        except Exception as e:
            print(f"  ❌ 削除失敗: {cat_id} - {e}")

    print("✅ 削除完了")


def main():
    """メイン処理"""
    print("=" * 60)
    print("カテゴリ階層構造 → フラット構造への変換")
    print("=" * 60)

    # 確認
    print("\n⚠️  警告:")
    print("- 既存の階層構造カテゴリを新形式に変換します")
    print("- 商品のcategory_idを更新します")
    print("- 古い階層カテゴリを削除します")

    response = input("\n続行しますか？ (yes/no): ")

    if response.lower() != 'yes':
        print("キャンセルしました")
        return

    # 1. 既存カテゴリを取得
    categories = fetch_all_categories()

    if not categories:
        print("カテゴリが見つかりません")
        return

    # 2. 階層ツリーを構築
    cat_by_id, children_by_parent = build_hierarchy_tree(categories)

    # 3. 新形式カテゴリを作成
    old_to_new_id = create_flat_categories(cat_by_id, children_by_parent)

    if not old_to_new_id:
        print("⚠️  新規作成されたカテゴリがありません")
        return

    # 4. 商品のcategory_idを更新
    update_product_categories(old_to_new_id)

    # 5. 古い階層カテゴリを削除
    delete_old_hierarchy_categories(cat_by_id, old_to_new_id)

    print("\n" + "=" * 60)
    print("✅ 変換完了！")
    print("=" * 60)
    print(f"新形式カテゴリ: {len(old_to_new_id)}件")


if __name__ == "__main__":
    main()
