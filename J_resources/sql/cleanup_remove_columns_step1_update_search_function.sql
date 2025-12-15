-- =========================================
-- search_documents_final関数を更新（削除対象列への参照を除去）
-- 実行場所: Supabase SQL Editor
-- 目的: year, month カラムへの参照を削除
-- =========================================

BEGIN;

-- 既存の関数を削除（パラメータが変わるため）
DROP FUNCTION IF EXISTS search_documents_final(TEXT, vector(1536), FLOAT, INT, FLOAT, FLOAT, INT, INT, TEXT);
DROP FUNCTION IF EXISTS search_documents_final(TEXT, vector(1536), FLOAT, INT, FLOAT, FLOAT, INT, INT, TEXT[], TEXT[]);
DROP FUNCTION IF EXISTS search_documents_final(text, vector, double precision, integer, double precision, double precision, integer, integer, text[]);
DROP FUNCTION IF EXISTS search_documents_final(text, vector, double precision, integer, double precision, double precision, text[]);

-- 新しい関数を作成（filter_year, filter_month, year, month を削除）
CREATE OR REPLACE FUNCTION search_documents_final(
    query_text TEXT,
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.0,
    match_count INT DEFAULT 10,
    vector_weight FLOAT DEFAULT 0.7,
    fulltext_weight FLOAT DEFAULT 0.3,
    filter_doc_types TEXT[] DEFAULT NULL  -- doc_typeのみで絞り込み
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
        d.full_text AS large_chunk_text,  -- 大チャンク（全文）
        d.id AS large_chunk_id,
        ((1 - (d.embedding <=> query_embedding)) * vector_weight +
         ts_rank(to_tsvector('simple', COALESCE(d.full_text, '')), plainto_tsquery('simple', query_text)) * fulltext_weight)::FLOAT AS combined_score,
        d.id AS small_chunk_id,  -- 簡略化（実際は小チャンクテーブルから取得する場合がある）
        d.source_type,
        d.source_url,
        d.full_text,
        d.created_at
    FROM documents d
    WHERE
        -- 処理完了済みのみ
        d.processing_status = 'completed'
        -- doc_type絞り込み（配列が空またはNULLならすべて、指定があれば該当のみ）
        AND (filter_doc_types IS NULL OR cardinality(filter_doc_types) = 0 OR d.doc_type = ANY(filter_doc_types))
        -- 類似度フィルタ
        AND (1 - (d.embedding <=> query_embedding)) >= match_threshold
    ORDER BY combined_score DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

COMMIT;

-- =========================================
-- 実行後の確認クエリ（参考）
-- =========================================
-- 階層構造はフロントエンドで維持、検索はdoc_typeのみで絞り込み
-- 日付検索は all_mentioned_dates 配列を使用
--
-- SELECT * FROM search_documents_final(
--     'テストクエリ',
--     '[0.1, 0.2, ...]'::vector(1536),
--     0.0,
--     10,
--     0.7,
--     0.3,
--     ARRAY['2025_5B', '2025年度小オケ']::TEXT[]  -- doc_typeのみ
-- );
