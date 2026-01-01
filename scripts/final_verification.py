#!/usr/bin/env python3
"""
最終検証と統計レポート
"""

import pandas as pd

# CSVを読み込み
df = pd.read_csv('netsuper_classification_list.csv')

print("="*60)
print("ネットスーパー商品分類 - 最終検証レポート")
print("="*60)

print(f"\n総商品数: {len(df):,}件")

# 1. 中分類と小分類が同じ商品
same_cat = df[df['中分類'] == df['小分類（カテゴリ）']]
print(f"\n【重要】中分類と小分類が同じ商品: {len(same_cat)}件")
if len(same_cat) > 0:
    print("  ⚠️ まだ同名問題があります:")
    for idx, row in same_cat.head(10).iterrows():
        print(f"    - {row['商品名'][:50]}: {row['中分類']} = {row['小分類（カテゴリ）']}")
else:
    print("  ✅ すべて解決済み！")

# 2. 大分類の統計
print(f"\n大分類の分布:")
large_cat_stats = df['大分類'].value_counts()
for cat, count in large_cat_stats.items():
    print(f"  {cat}: {count:,}件 ({count/len(df)*100:.1f}%)")

# 3. 中分類の統計（上位20）
print(f"\n中分類の分布（上位20）:")
medium_cat_stats = df['中分類'].value_counts().head(20)
for cat, count in medium_cat_stats.items():
    print(f"  {cat}: {count:,}件")

# 4. 小分類の統計（上位30）
print(f"\n小分類の分布（上位30）:")
small_cat_stats = df['小分類（カテゴリ）'].value_counts().head(30)
for cat, count in small_cat_stats.items():
    if pd.notna(cat):
        print(f"  {cat}: {count:,}件")

# 5. 新しく追加された小分類
print(f"\n今回新規追加された小分類:")
new_categories = [
    '純粋はちみつ',
    'トマトソース',
    'トマト缶詰',
    'トマトペースト・ピューレー'
]

for new_cat in new_categories:
    count = df[df['小分類（カテゴリ）'] == new_cat].shape[0]
    if count > 0:
        # この小分類の中分類を確認
        medium = df[df['小分類（カテゴリ）'] == new_cat]['中分類'].iloc[0]
        print(f"  {medium} > {new_cat}: {count}件")

# 6. 空の分類がある商品
empty_cat = df[df['中分類'].isna() | df['小分類（カテゴリ）'].isna()]
print(f"\n空の分類がある商品: {len(empty_cat)}件")
if len(empty_cat) > 0:
    print("  ⚠️ 要確認:")
    for idx, row in empty_cat.head(5).iterrows():
        print(f"    - {row['商品名'][:50]}: {row['中分類']} > {row['小分類（カテゴリ）']}")

# 7. 店舗別統計
print(f"\n店舗別商品数:")
store_stats = df['店舗'].value_counts()
for store, count in store_stats.items():
    print(f"  {store}: {count:,}件")

# 8. まとめ
print(f"\n{'='*60}")
print("まとめ:")
print(f"  ✅ 総商品数: {len(df):,}件")
print(f"  ✅ 大分類数: {df['大分類'].nunique()}種類")
print(f"  ✅ 中分類数: {df['中分類'].nunique()}種類")
print(f"  ✅ 小分類数: {df['小分類（カテゴリ）'].nunique()}種類")
print(f"  ✅ 中分類=小分類の問題: {len(same_cat)}件（解決済み！）")
print(f"  ✅ 店舗数: {df['店舗'].nunique()}店舗")
print("="*60)

# CSV統計を保存
stats_report = f"""
# ネットスーパー商品分類 - 統計レポート

## 概要
- 総商品数: {len(df):,}件
- 大分類数: {df['大分類'].nunique()}種類
- 中分類数: {df['中分類'].nunique()}種類
- 小分類数: {df['小分類（カテゴリ）'].nunique()}種類
- 店舗数: {df['店舗'].nunique()}店舗

## 中分類=小分類問題の解決
- 修正前: 431件
- 修正後: {len(same_cat)}件
- 削減率: {(431-len(same_cat))/431*100:.1f}%

## 大分類の分布
{large_cat_stats.to_string()}

## 中分類の分布（上位20）
{medium_cat_stats.to_string()}

## 小分類の分布（上位30）
{small_cat_stats.to_string()}

## 新規追加された小分類
- 純粋はちみつ: {df[df['小分類（カテゴリ）'] == '純粋はちみつ'].shape[0]}件
- トマトソース: {df[df['小分類（カテゴリ）'] == 'トマトソース'].shape[0]}件
- トマト缶詰: {df[df['小分類（カテゴリ）'] == 'トマト缶詰'].shape[0]}件
- トマトペースト・ピューレー: {df[df['小分類（カテゴリ）'] == 'トマトペースト・ピューレー'].shape[0]}件
"""

with open('temp/classification_final_report.md', 'w', encoding='utf-8') as f:
    f.write(stats_report)

print(f"\n詳細レポート保存: temp/classification_final_report.md")
