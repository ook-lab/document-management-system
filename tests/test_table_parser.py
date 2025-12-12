#!/usr/bin/env python3
"""
Markdown表パーサーのテスト
"""

from ui.utils.table_parser import parse_markdown_table, parse_extracted_tables

# テストケース1: シンプルなMarkdown表
markdown_table = """| 項目 | 価格 | 税込 |
| --- | --- | --- |
| ブレザー | 23,300 | 25,630 |
| 長袖シャツ | 4,380 | 4,818 |
| 男子半ズボン | 8,840 | 9,724 |"""

print("=" * 60)
print("テスト1: シンプルなMarkdown表のパース")
print("=" * 60)
print("\n入力:")
print(markdown_table)

parsed = parse_markdown_table(markdown_table)
print("\n出力:")
print(f"ヘッダー: {parsed['headers']}")
print(f"行数: {len(parsed['rows'])}")
for i, row in enumerate(parsed['rows'], 1):
    print(f"  行{i}: {row}")

# テストケース2: extracted_tablesのパース
print("\n" + "=" * 60)
print("テスト2: extracted_tables形式のパース")
print("=" * 60)

# データベースから取得した形式をシミュレート
extracted_tables = [
    [
        "| 項目 | 価格 |\n| --- | --- |\n| ブレザー | 25,630 |\n| シャツ | 4,818 |",
        "| 曜日 | 行事 |\n| --- | --- |\n| 月 | 始業式 |\n| 火 | 健康診断 |"
    ],
    [
        "| 持ち物 | 備考 |\n| --- | --- |\n| 体操着 | 必須 |\n| 水筒 | 推奨 |"
    ]
]

parsed_tables = parse_extracted_tables(extracted_tables)
print(f"\n解析された表数: {len(parsed_tables)}")
for table in parsed_tables:
    print(f"\nページ{table['page']}, 表{table['table_number']}:")
    print(f"  ヘッダー: {table['headers']}")
    print(f"  行数: {len(table['rows'])}")
    for row in table['rows']:
        print(f"    {row}")

print("\n" + "=" * 60)
print("全テスト完了")
print("=" * 60)
