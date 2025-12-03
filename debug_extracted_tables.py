#!/usr/bin/env python3
"""
extracted_tablesのデータ構造をデバッグ
"""
from core.database.client import DatabaseClient
import json

def debug_extracted_tables():
    db = DatabaseClient()

    # 価格表のドキュメントを取得
    result = db.client.table('documents').select('id, file_name, extracted_tables').ilike('file_name', '%価格表%').limit(1).execute()

    if not result.data or len(result.data) == 0:
        print("❌ ドキュメントが見つかりません")
        return

    doc = result.data[0]
    print("=" * 60)
    print(f"📄 ファイル名: {doc['file_name']}")
    print(f"🆔 ID: {doc['id']}")
    print("=" * 60)

    extracted_tables = doc.get('extracted_tables')

    print(f"\n📊 extracted_tables の型: {type(extracted_tables)}")
    print(f"📊 extracted_tables の長さ: {len(extracted_tables) if extracted_tables else 0}")

    if extracted_tables:
        print(f"\n📊 extracted_tables の内容:")
        print(json.dumps(extracted_tables, ensure_ascii=False, indent=2)[:2000])
        print("\n...")

        # 最初の要素の型を確認
        if isinstance(extracted_tables, list) and len(extracted_tables) > 0:
            print(f"\n📊 最初の要素の型: {type(extracted_tables[0])}")
            if isinstance(extracted_tables[0], str):
                print(f"📊 最初の要素の長さ: {len(extracted_tables[0])}")
                print(f"📊 最初の要素の先頭100文字:")
                print(extracted_tables[0][:100])
    else:
        print("❌ extracted_tables が空です")

    # parse_extracted_tables関数をテスト
    if extracted_tables:
        print("\n" + "=" * 60)
        print("🔍 parse_extracted_tables関数をテスト")
        print("=" * 60)

        from ui.utils.table_parser import parse_extracted_tables

        try:
            parsed_tables = parse_extracted_tables(extracted_tables)
            print(f"\n✅ パースされた表の数: {len(parsed_tables)}")

            for i, table in enumerate(parsed_tables, 1):
                print(f"\n表 {i}:")
                print(f"  ページ: {table.get('page')}")
                print(f"  表番号: {table.get('table_number')}")
                print(f"  ヘッダー: {table.get('headers', [])[:5]}...")  # 最初の5列だけ
                print(f"  行数: {len(table.get('rows', []))}")
                if table.get('rows'):
                    print(f"  最初の行: {table['rows'][0][:5]}...")  # 最初の5セルだけ
        except Exception as e:
            print(f"❌ エラー: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    debug_extracted_tables()
