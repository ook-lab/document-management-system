-- =========================================
-- search_documents_final関数を複数workspace/doc_type対応に更新
-- 実行場所: Supabase SQL Editor
-- 目的: データベースレベルで複数フィルタに対応し、効率的な検索を実現
-- =========================================

BEGIN;

-- 既存の関数を削除（パラメータが変わるため）
DROP FUNCTION IF EXISTS search_documents_final(TEXT, vector(1536), FLOAT, INT, FLOAT, FLOAT, INT, INT, TEXT);
DROP FUNCTION IF EXISTS search_documents_final(TEXT, vector(1536), FLOAT, INT, FLOAT, FLOAT, INT, INT, TEXT[], TEXT[]);

-- 新しい関数を作成（doc_typeのみで絞り込み）
CREATE OR REPLACE FUNCTION search_documents_final(
    query_text TEXT,
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.0,
    match_count INT DEFAULT 10,
    vector_weight FLOAT DEFAULT 0.7,
    fulltext_weight FLOAT DEFAULT 0.3,
    filter_year INT DEFAULT NULL,
    filter_month INT DEFAULT NULL,
    filter_doc_types TEXT[] DEFAULT NULL  -- doc_typeのみ
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
    year INT,
    month INT,
    source_type VARCHAR,
    source_url TEXT,
    full_text TEXT,
    created_at TIMESTAMP
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
         ts_rank(to_tsvector('japanese', COALESCE(d.full_text, '')), plainto_tsquery('japanese', query_text)) * fulltext_weight)::FLOAT AS combined_score,
        d.id AS small_chunk_id,  -- 簡略化（実際は小チャンクテーブルから取得する場合がある）
        EXTRACT(YEAR FROM d.document_date)::INT AS year,
        EXTRACT(MONTH FROM d.document_date)::INT AS month,
        d.source_type,
        d.source_url,
        d.full_text,
        d.created_at
    FROM documents d
    WHERE
        -- 処理完了済みのみ
        d.processing_status = 'completed'
        -- 年フィルタ
        AND (filter_year IS NULL OR EXTRACT(YEAR FROM d.document_date) = filter_year)
        -- 月フィルタ
        AND (filter_month IS NULL OR EXTRACT(MONTH FROM d.document_date) = filter_month)
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
-- 理由: workspace内の全doc_typeがON = workspaceがON（冗長なため）
--
-- SELECT * FROM search_documents_final(
--     'テストクエリ',
--     '[0.1, 0.2, ...]'::vector(1536),
--     0.0,
--     10,
--     0.7,
--     0.3,
--     NULL,
--     NULL,
--     ARRAY['2025_5B', '2025年度小オケ']::TEXT[]  -- doc_typeのみ
-- );
