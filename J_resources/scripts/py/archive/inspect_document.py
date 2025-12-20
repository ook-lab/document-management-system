#!/usr/bin/env python3
"""
ドキュメント詳細情報確認スクリプト

Supabaseの documents テーブルから検索キーワードに一致する
ドキュメントの詳細情報を見やすく出力します。
"""
import sys
import os
import json

# プロジェクトルートをPythonパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from supabase import create_client
from config.settings import settings


def format_metadata(metadata: dict) -> str:
    """メタデータを見やすくフォーマット"""
    if not metadata:
        return "  (メタデータなし)"

    formatted = []
    for key, value in metadata.items():
        if isinstance(value, (dict, list)):
            formatted.append(f"  {key}:")
            formatted.append("    " + json.dumps(value, ensure_ascii=False, indent=2).replace("\n", "\n    "))
        else:
            formatted.append(f"  {key}: {value}")

    return "\n".join(formatted)


def inspect_documents(keyword: str):
    """ドキュメント検索と詳細表示"""

    # Supabaseクライアント初期化
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        print("❌ エラー: SUPABASE_URL と SUPABASE_KEY が設定されていません")
        sys.exit(1)

    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

    print(f"🔍 検索キーワード: '{keyword}'")
    print("=" * 80)

    try:
        # file_name で部分一致検索
        response = client.table('10_rd_source_docs').select(
            'id, file_name, doc_type, confidence, summary, document_date, tags, metadata, workspace, created_at'
        ).ilike('file_name', f'%{keyword}%').execute()

        if not response.data or len(response.data) == 0:
            print(f"⚠️  キーワード '{keyword}' に一致するドキュメントが見つかりませんでした。")
            return

        print(f"✅ {len(response.data)} 件のドキュメントが見つかりました\n")

        for idx, doc in enumerate(response.data, 1):
            print(f"📄 ドキュメント #{idx}")
            print("-" * 80)
            print(f"ID: {doc.get('id')}")
            print(f"ファイル名: {doc.get('file_name')}")
            print(f"ドキュメントタイプ: {doc.get('doc_type')}")
            print(f"信頼度: {doc.get('confidence'):.2f}" if doc.get('confidence') else "信頼度: N/A")
            print(f"ワークスペース: {doc.get('workspace')}")
            print(f"ドキュメント日付: {doc.get('document_date') or 'N/A'}")
            print(f"作成日時: {doc.get('created_at')}")

            # サマリー
            summary = doc.get('summary', '')
            if summary:
                print(f"\n📝 サマリー:")
                print(f"  {summary}")

            # タグ
            tags = doc.get('tags', [])
            if tags:
                print(f"\n🏷️  タグ: {', '.join(tags)}")

            # メタデータ
            metadata = doc.get('metadata', {})
            if metadata:
                print(f"\n📊 メタデータ:")
                print(format_metadata(metadata))

            print("\n" + "=" * 80 + "\n")

    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """メインエントリーポイント"""
    if len(sys.argv) < 2:
        print("使用方法: python scripts/inspect_document.py <検索キーワード>")
        print("例: python scripts/inspect_document.py 黒姫")
        sys.exit(1)

    keyword = sys.argv[1]
    inspect_documents(keyword)


if __name__ == "__main__":
    main()
