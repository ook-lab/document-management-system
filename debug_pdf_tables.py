"""
pdfplumberのテーブル検出をデバッグ
"""
import pdfplumber

pdf_path = "/Users/ookuboyoshinori/document_management_system/価格表(小）2025.5.1以降 (1).pdf"

print("=" * 60)
print("pdfplumber テーブル検出デバッグ")
print("=" * 60)

with pdfplumber.open(pdf_path) as pdf:
    for i, page in enumerate(pdf.pages):
        print(f"\nページ {i+1}:")

        # デフォルト設定でテーブル抽出
        tables = page.extract_tables()
        print(f"  デフォルト設定: {len(tables)} テーブル")

        # より厳しい設定でテーブル抽出
        tables_strict = page.extract_tables(table_settings={
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
        })
        print(f"  厳しい設定（lines only）: {len(tables_strict)} テーブル")

        # より寛容な設定でテーブル抽出
        tables_relaxed = page.extract_tables(table_settings={
            "vertical_strategy": "text",
            "horizontal_strategy": "text",
            "min_words_vertical": 2,
            "min_words_horizontal": 2,
        })
        print(f"  寛容な設定（text strategy）: {len(tables_relaxed)} テーブル")

        # テキストを確認
        text = page.extract_text()
        print(f"\n  抽出テキスト（先頭300文字）:")
        print(f"  {text[:300]}")

        # テーブルが検出された場合、内容を表示
        if tables_relaxed:
            print(f"\n  🎯 寛容な設定でテーブルを検出しました:")
            for j, table in enumerate(tables_relaxed[:2]):  # 最初の2つのみ
                print(f"\n  テーブル {j+1}:")
                print(f"    行数: {len(table)}")
                print(f"    列数: {len(table[0]) if table else 0}")
                print(f"    最初の3行:")
                for row in table[:3]:
                    print(f"      {row}")

print("\n" + "=" * 60)
print("デバッグ完了")
print("=" * 60)
