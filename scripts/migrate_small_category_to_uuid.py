"""
既存のsmall_category（テキスト）をcategory_id（UUID）にマイグレーション

処理内容：
1. Rawdata_NETSUPER_items の全商品を取得
2. small_category の値を元に MASTER_Categories_product を検索
3. 見つかった場合：そのUUIDをcategory_idに設定
4. 見つからない場合：新規カテゴリを作成（親なし）してUUIDを設定
"""

import os
from supabase import create_client
from typing import Dict, Optional

# Supabase接続
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise Exception("環境変数 SUPABASE_URL と SUPABASE_SERVICE_ROLE_KEY を設定してください")

db = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def get_category_uuid(category_name: str, category_cache: Dict[str, str]) -> Optional[str]:
    """
    カテゴリ名からUUIDを取得（キャッシュ利用）
    見つからない場合は新規作成
    """
    if category_name in category_cache:
        return category_cache[category_name]

    # MASTER_Categories_product から検索
    # 同じ名前が複数ある場合、親なし（大分類）を優先
    result = db.table('MASTER_Categories_product').select('id, name, parent_id').eq('name', category_name).execute()

    if result.data:
        # 親なしを優先
        for cat in result.data:
            if cat['parent_id'] is None:
                category_cache[category_name] = cat['id']
                return cat['id']

        # 親なしがなければ最初の結果を使用
        category_cache[category_name] = result.data[0]['id']
        return result.data[0]['id']

    # 見つからない場合、新規作成（親なし = 大分類として作成）
    print(f"  新規カテゴリ作成: {category_name}")
    new_cat = {
        'name': category_name,
        'parent_id': None
    }
    result = db.table('MASTER_Categories_product').insert(new_cat).execute()

    if result.data:
        category_cache[category_name] = result.data[0]['id']
        return result.data[0]['id']

    return None


def migrate_products():
    """
    全商品のsmall_categoryをcategory_idにマイグレーション
    """
    print("=== マイグレーション開始 ===")

    # カテゴリ名→UUIDのキャッシュ
    category_cache: Dict[str, str] = {}

    # 全商品を取得（バッチ処理）
    batch_size = 1000
    offset = 0
    total_updated = 0
    total_skipped = 0
    total_failed = 0

    while True:
        print(f"\n--- バッチ {offset // batch_size + 1} 処理中（{offset}件目から） ---")

        # 商品を取得（category_idがnullまたはsmall_categoryがある商品のみ）
        products = db.table('Rawdata_NETSUPER_items').select(
            'id, product_name, small_category, category_id'
        ).is_('category_id', 'null').not_.is_('small_category', 'null').range(
            offset, offset + batch_size - 1
        ).execute()

        if not products.data:
            print("処理完了：これ以上の商品がありません")
            break

        print(f"取得: {len(products.data)}件")

        for product in products.data:
            product_id = product['id']
            small_category = product.get('small_category')

            if not small_category:
                total_skipped += 1
                continue

            # カテゴリUUIDを取得
            category_uuid = get_category_uuid(small_category, category_cache)

            if not category_uuid:
                print(f"  ❌ 失敗: {product['product_name'][:50]} - カテゴリUUID取得失敗")
                total_failed += 1
                continue

            # category_idを更新
            try:
                db.table('Rawdata_NETSUPER_items').update({
                    'category_id': category_uuid
                }).eq('id', product_id).execute()
                total_updated += 1

                if total_updated % 100 == 0:
                    print(f"  進捗: {total_updated}件更新完了")

            except Exception as e:
                print(f"  ❌ 更新失敗: {product['product_name'][:50]} - {e}")
                total_failed += 1

        offset += batch_size

        # 安全のため、最大10,000件で停止（必要に応じて変更）
        if offset >= 10000:
            print("\n警告: 10,000件に達したため停止しました")
            print("続行する場合はコードを修正してください")
            break

    print("\n=== マイグレーション完了 ===")
    print(f"更新: {total_updated}件")
    print(f"スキップ: {total_skipped}件（small_categoryが空）")
    print(f"失敗: {total_failed}件")
    print(f"新規作成カテゴリ数: {len([k for k, v in category_cache.items() if v])}")


if __name__ == "__main__":
    # 確認
    print("このスクリプトは全商品のcategory_idを更新します。")
    print("実行前にバックアップを取ることを推奨します。")
    response = input("続行しますか？ (yes/no): ")

    if response.lower() == 'yes':
        migrate_products()
    else:
        print("キャンセルしました")
