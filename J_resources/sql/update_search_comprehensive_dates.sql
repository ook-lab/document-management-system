-- search_documents_final関数を更新して包括的な日付検索対応
-- 実行場所: Supabase SQL Editor
-- 目的: document_date、event_dates、all_mentioned_dates、classroom_sent_at すべてをチェック

BEGIN;

-- 既存の関数を削除
DROP FUNCTION IF EXISTS search_documents_final(text, vector, double precision, integer, double precision, double precision, integer, integer, text[]);

-- 新しい関数を作成（包括的な日付検索対応）
CREATE OR REPLACE FUNCTION search_documents_final(
    query_text TEXT,
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.0,
    match_count INT DEFAULT 10,
    vector_weight FLOAT DEFAULT 0.7,
    fulltext_weight FLOAT DEFAULT 0.3,
    filter_year INT DEFAULT NULL,
    filter_month INT DEFAULT NULL,
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
    year INT,
    month INT,
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
        ((1 - (d.embedding <=> query_embedding)) * vector_weight +
         ts_rank(to_tsvector('simple', COALESCE(d.full_text, '')), plainto_tsquery('simple', query_text)) * fulltext_weight)::FLOAT AS combined_score,
        d.id AS small_chunk_id,
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
        -- 【包括的な年フィルタ】すべての日付フィールドをチェック
        AND (
            filter_year IS NULL
            -- document_date
            OR EXTRACT(YEAR FROM d.document_date) = filter_year
            -- classroom_sent_at
            OR EXTRACT(YEAR FROM d.classroom_sent_at) = filter_year
            -- event_dates配列
            OR EXISTS (
                SELECT 1 FROM unnest(d.event_dates) AS event_date
                WHERE EXTRACT(YEAR FROM event_date) = filter_year
            )
            -- all_mentioned_dates配列
            OR EXISTS (
                SELECT 1 FROM unnest(d.all_mentioned_dates) AS mentioned_date
                WHERE EXTRACT(YEAR FROM mentioned_date) = filter_year
            )
        )
        -- 【包括的な月フィルタ】すべての日付フィールドをチェック
        AND (
            filter_month IS NULL
            -- document_date
            OR EXTRACT(MONTH FROM d.document_date) = filter_month
            -- classroom_sent_at
            OR EXTRACT(MONTH FROM d.classroom_sent_at) = filter_month
            -- event_dates配列
            OR EXISTS (
                SELECT 1 FROM unnest(d.event_dates) AS event_date
                WHERE EXTRACT(MONTH FROM event_date) = filter_month
            )
            -- all_mentioned_dates配列
            OR EXISTS (
                SELECT 1 FROM unnest(d.all_mentioned_dates) AS mentioned_date
                WHERE EXTRACT(MONTH FROM mentioned_date) = filter_month
            )
        )
        -- doc_type絞り込み
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
-- SELECT * FROM search_documents_final(
--     '12月7日',
--     '[0.1, 0.2, ...]'::vector(1536),
--     0.0,
--     10,
--     0.7,
--     0.3,
--     2025,  -- 年フィルタ
--     12,    -- 月フィルタ
--     NULL
-- );
