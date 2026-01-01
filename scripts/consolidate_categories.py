"""
カテゴリ統合スクリプト

処理内容：
1. 全カテゴリの大分類を「食料品」に統一
2. 「調味料１」「調味料２」→「調味料」のように数字を削除して統合
3. 商品のcategory_idを新カテゴリIDに更新
4. 古いカテゴリを削除
"""

import os
import re
from supabase import create_client
from typing import Dict, List
from collections import defaultdict

# 設定
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not all([SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY]):
    raise Exception("環境変数を設定してください")

db = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def remove_numbers(text: str) -> str:
    """文字列から数字（１、２、３、1、2、3など）を削除"""
    if not text:
        return text

    # 全角数字を削除
    text = re.sub(r'[０-９]+', '', text)
    # 半角数字を削除
    text = re.sub(r'[0-9]+', '', text)
    # 前後の空白を削除
    return text.strip()


def fetch_all_categories() -> List[Dict]:
    """全カテゴリを取得"""
    print("\n=== 既存カテゴリを取得中 ===")
    result = db.table('MASTER_Categories_product').select('*').execute()
    print(f"取得完了: {len(result.data)}件")
    return result.data


def normalize_category(cat: Dict) -> Dict:
    """
    カテゴリを正規化
    - 大分類を「食料品」に統一
    - 数字を削除
    """
    large = "食料品"  # 全て食料品に統一
    medium = remove_numbers(cat.get('medium_category', ''))
    small = remove_numbers(cat.get('small_category', ''))

    return {
        'large_category': large,
        'medium_category': medium,
        'small_category': small,
        'name': f"{large}>{medium}>{small}"
    }


def get_or_create_category(large: str, medium: str, small: str) -> str:
    """カテゴリを取得、なければ作成"""
    full_name = f"{large}>{medium}>{small}"

    # 既存カテゴリを検索
    result = db.table('MASTER_Categories_product').select('id').eq('name', full_name).execute()

    if result.data:
        return result.data[0]['id']

    # 新規作成
    new_cat = {
        'name': full_name,
        'large_category': large,
        'medium_category': medium,
        'small_category': small,
        'parent_id': None
    }

    try:
        result = db.table('MASTER_Categories_product').insert(new_cat).execute()
        return result.data[0]['id']
    except Exception as e:
        print(f"  ⚠️ カテゴリ作成失敗: {full_name} - {e}")
        # 既に存在する可能性があるので再検索
        result = db.table('MASTER_Categories_product').select('id').eq('name', full_name).execute()
        if result.data:
            return result.data[0]['id']
        raise


def consolidate_categories():
    """カテゴリを統合"""
    print("\n=== カテゴリ統合処理開始 ===")

    # 1. 全カテゴリを取得
    categories = fetch_all_categories()

    if not categories:
        print("カテゴリが見つかりません")
        return

    # 2. 各カテゴリを正規化して、old_id → new_id のマッピングを作成
    print("\n=== カテゴリを正規化中 ===")
    old_to_new_id = {}

    for cat in categories:
        old_id = cat['id']

        # 正規化
        normalized = normalize_category(cat)

        # 新カテゴリを取得/作成
        try:
            new_id = get_or_create_category(
                normalized['large_category'],
                normalized['medium_category'],
                normalized['small_category']
            )

            old_to_new_id[old_id] = new_id

            if old_id != new_id:
                print(f"  統合: {cat.get('name', 'N/A')} → {normalized['name']}")
        except Exception as e:
            print(f"  ❌ エラー: {cat.get('name', 'N/A')} - {e}")

    print(f"\n統合対象: {len(old_to_new_id)}件")

    # 3. 商品のcategory_idを更新
    print("\n=== 商品を更新中 ===")
    updated_count = 0

    for old_id, new_id in old_to_new_id.items():
        if old_id == new_id:
            # 同じIDの場合はスキップ
            continue

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

    # 4. 古いカテゴリを削除
    print("\n=== 古いカテゴリを削除中 ===")
    deleted_count = 0

    # 統合後、どのカテゴリIDが新しいものとして残るべきかを確認
    new_category_ids = set(old_to_new_id.values())

    for old_id in old_to_new_id.keys():
        # 新しいIDとして使われているものは削除しない
        if old_id in new_category_ids:
            continue

        try:
            db.table('MASTER_Categories_product').delete().eq('id', old_id).execute()
            deleted_count += 1
        except Exception as e:
            print(f"  ⚠️ 削除失敗: {old_id} - {e}")

    print(f"✅ 削除完了: {deleted_count}件")

    # 5. 結果サマリー
    print("\n" + "=" * 60)
    print("✅ カテゴリ統合完了！")
    print("=" * 60)
    print(f"処理したカテゴリ: {len(old_to_new_id)}件")
    print(f"更新した商品: {updated_count}件")
    print(f"削除したカテゴリ: {deleted_count}件")

    # 残ったカテゴリを確認
    final_categories = db.table('MASTER_Categories_product').select('*').execute()
    print(f"\n最終カテゴリ数: {len(final_categories.data)}件")

    # 大分類の確認
    large_cats = set([c['large_category'] for c in final_categories.data if c.get('large_category')])
    print(f"大分類: {large_cats}")


def main():
    """メイン処理"""
    print("=" * 60)
    print("カテゴリ統合スクリプト")
    print("=" * 60)

    print("\n⚠️  実行内容:")
    print("1. 全カテゴリの大分類を「食料品」に統一")
    print("2. 「調味料１」「調味料２」→「調味料」のように数字を削除")
    print("3. 商品のcategory_idを更新")
    print("4. 古いカテゴリを削除")

    # 環境変数でスキップ可能
    if os.getenv("AUTO_CONFIRM") != "yes":
        response = input("\n続行しますか？ (yes/no): ")

        if response.lower() != 'yes':
            print("キャンセルしました")
            return
    else:
        print("\n自動実行モード（AUTO_CONFIRM=yes）")

    consolidate_categories()


if __name__ == "__main__":
    main()
