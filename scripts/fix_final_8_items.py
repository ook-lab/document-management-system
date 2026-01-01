#!/usr/bin/env python3
"""
最後の8件を手動で適切な小分類に修正
"""

import pandas as pd
from datetime import datetime

# CSVを読み込み
df = pd.read_csv('netsuper_classification_list.csv')

# 中分類と小分類が同じ商品を抽出
same_cat = df[df['中分類'] == df['小分類（カテゴリ）']].copy()

print(f"残りの同名商品: {len(same_cat)}件\n")

# 各商品を表示して適切な分類を決定
manual_fixes = []

for idx, row in same_cat.iterrows():
    product_name = row['商品名']
    general_name = row['一般名詞']
    medium = row['中分類']
    small = row['小分類（カテゴリ）']

    print(f"{len(manual_fixes) + 1}. {product_name}")
    print(f"   一般名詞: {general_name}")
    print(f"   現在: {medium} > {small}")

    # 商品名から適切な小分類を推測
    if 'チョコ' in product_name or 'マフィン' in product_name or 'タルト' in product_name:
        new_small = '菓子パン'  # パンカテゴリに移動すべきだが、まず調味料内で処理
        new_medium = 'パン'
        print(f"   → 修正: {new_medium} > {new_small}")
        manual_fixes.append({
            'idx': idx,
            '商品名': product_name,
            '新中分類': new_medium,
            '新小分類': new_small
        })
    elif 'カリーパン' in product_name or 'パン' in product_name:
        new_small = '惣菜パン'
        new_medium = 'パン'
        print(f"   → 修正: {new_medium} > {new_small}")
        manual_fixes.append({
            'idx': idx,
            '商品名': product_name,
            '新中分類': new_medium,
            '新小分類': new_small
        })
    elif 'トッポギ' in product_name or 'トッポ' in product_name:
        new_small = 'トッポギ'
        new_medium = 'その他加工食品'
        print(f"   → 修正: {new_medium} > {new_small}")
        manual_fixes.append({
            'idx': idx,
            '商品名': product_name,
            '新中分類': new_medium,
            '新小分類': new_small
        })
    elif medium == '調味料' and small == '調味料':
        # その他の調味料は既存の「その他調味料」小分類に
        new_small = 'その他調味料'
        print(f"   → 修正: {medium} > {new_small}")
        manual_fixes.append({
            'idx': idx,
            '商品名': product_name,
            '新中分類': medium,
            '新小分類': new_small
        })
    else:
        print(f"   → 要確認")
        manual_fixes.append({
            'idx': idx,
            '商品名': product_name,
            '新中分類': medium,
            '新小分類': small
        })

    print()

# 修正を適用
print(f"\n{'='*60}")
print(f"修正を適用中...")

for fix in manual_fixes:
    idx = fix['idx']
    # 中分類も変更する場合がある
    if fix['新中分類'] != df.loc[idx, '中分類']:
        df.loc[idx, '中分類'] = fix['新中分類']
        print(f"  中分類変更: {fix['商品名'][:40]}... → {fix['新中分類']}")
    df.loc[idx, '小分類（カテゴリ）'] = fix['新小分類']
    print(f"  小分類修正: {fix['商品名'][:40]}... → {fix['新小分類']}")

# バックアップ
backup_file = f"netsuper_classification_list_backup_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
df_original = pd.read_csv('netsuper_classification_list.csv')
df_original.to_csv(backup_file, index=False, encoding='utf-8-sig')
print(f"\nバックアップ作成: {backup_file}")

# 保存
df.to_csv('netsuper_classification_list.csv', index=False, encoding='utf-8-sig')
print(f"CSV更新完了: netsuper_classification_list.csv")

# 最終検証
print(f"\n{'='*60}")
print("最終検証:")
same_cat_final = df[df['中分類'] == df['小分類（カテゴリ）']]
print(f"中分類と小分類が同じ商品数: {len(same_cat_final)}件")

if len(same_cat_final) == 0:
    print("\n🎉 完了！全ての同名問題を解決しました！")
else:
    print(f"\n残り{len(same_cat_final)}件:")
    for idx, row in same_cat_final.iterrows():
        print(f"  - {row['商品名']}: {row['中分類']} > {row['小分類（カテゴリ）']}")
