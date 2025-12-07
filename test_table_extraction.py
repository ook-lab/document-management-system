"""
テーブル抽出テストスクリプト
価格表PDFからテーブルが正しく抽出されるかテスト
"""
from core.processors.pdf import PDFProcessor
from core.ai.llm_client import LLMClient
import json

# PDFファイルパス
pdf_path = "/Users/ookuboyoshinori/document_management_system/価格表(小）2025.5.1以降 (1).pdf"

print("=" * 60)
print("テーブル抽出テスト")
print("=" * 60)

# PDFProcessorを初期化
llm_client = LLMClient()
processor = PDFProcessor(llm_client=llm_client)

# テキスト抽出
print(f"\n対象PDF: {pdf_path}")
print("\nテキスト抽出開始...")

result = processor.extract_text(pdf_path)

print(f"\n抽出結果:")
print(f"  success: {result['success']}")
print(f"  content length: {len(result.get('content', ''))} 文字")
print(f"  metadata: {result.get('metadata', {})}")

# page_tablesの確認
if 'page_tables' in result:
    page_tables = result['page_tables']
    print(f"\n✅ page_tables が存在します")
    print(f"  ページ数: {len(page_tables)}")

    for i, tables in enumerate(page_tables):
        print(f"\n  ページ {i+1}:")
        print(f"    テーブル数: {len(tables)}")

        if tables:
            for j, table in enumerate(tables):
                print(f"\n    テーブル {j+1}:")
                print(f"      文字数: {len(table)}")
                print(f"      プレビュー (先頭200文字):")
                print(f"      {table[:200]}")
        else:
            print(f"    テーブルなし")

    # JSON形式で保存されるデータのプレビュー
    print(f"\n" + "=" * 60)
    print("extracted_tables として保存されるデータ:")
    print("=" * 60)
    print(json.dumps(page_tables, ensure_ascii=False, indent=2)[:500] + "...")

else:
    print(f"\n❌ page_tables が存在しません")
    print(f"  戻り値のキー: {list(result.keys())}")

print("\n" + "=" * 60)
print("テスト完了")
print("=" * 60)
