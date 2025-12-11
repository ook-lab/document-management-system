"""
緊急診断・修正スクリプト
検索が効かなくなった問題を診断し、修正します
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database.client import DatabaseClient
from supabase import create_client
from config.settings import settings

def main():
    print("="*80)
    print("検索機能 緊急診断・修正スクリプト")
    print("="*80)

    # データベース接続
    db = DatabaseClient()

    # 1. ドキュメント総数を確認
    print("\n[診断1] ドキュメント総数を確認...")
    try:
        result = db.client.table('documents').select('*', count='exact').execute()
        total = result.count if result.count else 0
        print(f"[OK] 総ドキュメント数: {total} 件")
    except Exception as e:
        print(f"[ERROR] エラー: {e}")
        return

    # 2. processing_status別の件数
    print("\n[診断2] processing_status別の件数...")
    try:
        result = db.client.rpc('execute_sql', {
            'query': """
                SELECT processing_status, COUNT(*) as count
                FROM documents
                GROUP BY processing_status
                ORDER BY count DESC;
            """
        }).execute()
        if result.data:
            for row in result.data:
                print(f"  {row.get('processing_status', 'NULL')}: {row.get('count')} 件")
    except Exception as e:
        # RPCが使えない場合は直接クエリ
        print(f"  [INFO] RPC経由では取得できません: {e}")

    # 3. embedding が存在するドキュメント数
    print("\n[診断3] embedding の有無...")
    try:
        all_docs = db.client.table('documents').select('id,embedding').limit(1000).execute()
        with_embedding = sum(1 for doc in all_docs.data if doc.get('embedding') is not None)
        without_embedding = len(all_docs.data) - with_embedding
        print(f"  embedding あり: {with_embedding} 件")
        print(f"  embedding なし: {without_embedding} 件")
    except Exception as e:
        print(f"[ERROR] エラー: {e}")

    # 4. doc_type別の件数
    print("\n[診断4] doc_type別の件数（上位10件）...")
    try:
        result = db.client.table('documents').select('doc_type').execute()
        doc_types = {}
        for doc in result.data:
            dt = doc.get('doc_type', 'NULL')
            doc_types[dt] = doc_types.get(dt, 0) + 1

        sorted_types = sorted(doc_types.items(), key=lambda x: x[1], reverse=True)[:10]
        for doc_type, count in sorted_types:
            print(f"  {doc_type}: {count} 件")
    except Exception as e:
        print(f"[ERROR] エラー: {e}")

    # 5. SQL関数を修正
    print("\n[修正] search_documents_final 関数を更新中...")

    fix_sql = """
BEGIN;

-- 既存の関数を削除
DROP FUNCTION IF EXISTS search_documents_final(TEXT, vector(1536), FLOAT, INT, FLOAT, FLOAT, TEXT[]);

-- より緩い条件で再作成
CREATE OR REPLACE FUNCTION search_documents_final(
    query_text TEXT,
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.0,
    match_count INT DEFAULT 10,
    vector_weight FLOAT DEFAULT 0.7,
    fulltext_weight FLOAT DEFAULT 0.3,
    filter_doc_types TEXT[] DEFAULT NULL
)
RETURNS TABLE (
    document_id UUID,
    file_name VARCHAR,
    doc_type VARCHAR,
    workspace VARCHAR,
    document_date DATE,
    metadata JSONB,
    summary TEXT,
    large_chunk_text TEXT,
    large_chunk_id UUID,
    combined_score FLOAT,
    small_chunk_id UUID,
    source_type VARCHAR,
    source_url TEXT,
    full_text TEXT,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id AS document_id,
        d.file_name,
        d.doc_type,
        d.workspace,
        d.document_date,
        d.metadata,
        d.summary,
        d.full_text AS large_chunk_text,
        d.id AS large_chunk_id,
        COALESCE(
            (1 - (d.embedding <=> query_embedding)) * vector_weight +
            ts_rank(to_tsvector('simple', COALESCE(d.full_text, '')), plainto_tsquery('simple', query_text)) * fulltext_weight,
            0
        )::FLOAT AS combined_score,
        d.id AS small_chunk_id,
        d.source_type,
        d.source_url,
        d.full_text,
        d.created_at
    FROM documents d
    WHERE
        -- doc_type絞り込みのみ（processing_status条件を削除）
        (filter_doc_types IS NULL
         OR cardinality(filter_doc_types) = 0
         OR d.doc_type = ANY(filter_doc_types))
    ORDER BY combined_score DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

COMMIT;
"""

    try:
        # Supabaseのクライアントで直接SQL実行
        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

        # SQL関数を実行
        # 注: supabase-pyはDDL実行に対応していないため、手動実行が必要
        print("\n[WARNING] SQL関数の更新はSupabase SQL Editorで手動実行してください")
        print("\n--- 以下のSQLをコピーしてSupabase SQL Editorで実行 ---")
        print(fix_sql)
        print("--- SQL終了 ---\n")

    except Exception as e:
        print(f"[ERROR] エラー: {e}")

    # 6. 修正SQLをファイルに保存
    with open('database/emergency_fix_search_function.sql', 'w', encoding='utf-8') as f:
        f.write(fix_sql)
    print("\n[OK] 修正SQLを database/emergency_fix_search_function.sql に保存しました")

    print("\n" + "="*80)
    print("診断完了")
    print("="*80)
    print("\n次の手順:")
    print("1. 上記のSQLをコピー")
    print("2. Supabase Dashboard → SQL Editor を開く")
    print("3. SQLを貼り付けて実行")
    print("4. アプリケーションで検索を再テスト")
    print("="*80)

if __name__ == "__main__":
    main()
