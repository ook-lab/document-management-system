"""
データベースの現状調査スクリプト
- documentsテーブルのカラム構成を確認
- full_textの保存状況を確認
- extracted_tablesの有無を確認
"""
import asyncio
from core.database.client import DatabaseClient

def check_database_schema():
    print("=" * 60)
    print("データベース現状調査")
    print("=" * 60)

    db = DatabaseClient()

    # documentsテーブルのカラム情報を取得
    print("\n[1] documentsテーブルのカラム構成")
    print("-" * 60)

    try:
        # サンプルデータから推測
        response = db.client.table('documents').select('*').limit(1).execute()

        if response.data:
            sample_doc = response.data[0]
            print(f"\n検出されたカラム:")
            for key in sample_doc.keys():
                value = sample_doc[key]
                value_type = type(value).__name__
                has_data = "✅" if value else "❌"
                print(f"  {has_data} {key:<30} (型: {value_type})")
        else:
            print("❌ データが1件も存在しません")

    except Exception as e:
        print(f"❌ エラー: {e}")

    # full_textの保存状況を確認
    print("\n[2] full_text カラムの保存状況")
    print("-" * 60)

    try:
        # 全ドキュメント数
        total_response = db.client.table('documents').select('id', count='exact').execute()
        total_count = total_response.count

        # full_textが存在するドキュメント数
        with_text_response = db.client.table('documents').select('id', count='exact').not_.is_('full_text', 'null').execute()
        with_text_count = with_text_response.count

        print(f"全ドキュメント数: {total_count}")
        print(f"full_text有り: {with_text_count} ({with_text_count/total_count*100:.1f}%)" if total_count > 0 else "データなし")

        # サンプルを1件表示
        sample_response = db.client.table('documents').select('file_name, full_text').not_.is_('full_text', 'null').limit(1).execute()

        if sample_response.data:
            sample = sample_response.data[0]
            text_preview = sample['full_text'][:200] if sample['full_text'] else "(空)"
            print(f"\nサンプル:")
            print(f"  ファイル名: {sample['file_name']}")
            print(f"  full_text (先頭200文字): {text_preview}...")

    except Exception as e:
        print(f"❌ エラー: {e}")

    # extracted_tablesの有無を確認
    print("\n[3] extracted_tables カラムの有無")
    print("-" * 60)

    try:
        # サンプルを1件取得してextracted_tablesカラムがあるか確認
        response = db.client.table('documents').select('*').limit(1).execute()

        if response.data:
            sample = response.data[0]
            if 'extracted_tables' in sample:
                print("✅ extracted_tables カラムは存在します")

                # データが入っているか確認
                has_tables_response = db.client.table('documents').select('id', count='exact').not_.is_('extracted_tables', 'null').execute()
                has_tables_count = has_tables_response.count

                print(f"   extracted_tables有りのドキュメント: {has_tables_count}")
            else:
                print("❌ extracted_tables カラムは存在しません（追加が必要）")
        else:
            print("⚠️ データが存在しないため確認できません")

    except Exception as e:
        print(f"⚠️ 確認中にエラー: {e}")
        print("   → extracted_tablesカラムは存在しない可能性が高いです")

    print("\n" + "=" * 60)
    print("調査完了")
    print("=" * 60)

if __name__ == "__main__":
    check_database_schema()
