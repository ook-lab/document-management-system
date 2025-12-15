-- search_documents_final関数を source_documents に更新
-- documentsテーブル → source_documentsテーブルへの移行

BEGIN;

-- 既存の関数を削除
DROP FUNCTION IF EXISTS search_documents_final(TEXT, vector(1536), FLOAT, INT, FLOAT, FLOAT, INT, INT, TEXT);
DROP FUNCTION IF EXISTS search_documents_final(TEXT, vector(1536), FLOAT, INT, FLOAT, FLOAT, INT, INT, TEXT[], TEXT[]);
DROP FUNCTION IF EXISTS search_documents_final(text, vector, double precision, integer, double precision, double precision, integer, integer, text[]);

-- 新しい関数を作成（source_documentsを参照）
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
    FROM source_documents d  -- ✅ ここを documents → source_documents に変更
    WHERE
        -- 処理完了済みのみ
        d.processing_status = 'completed'
        -- 年フィルタ
        AND (filter_year IS NULL OR EXTRACT(YEAR FROM d.document_date) = filter_year)
        -- 月フィルタ
        AND (filter_month IS NULL OR EXTRACT(MONTH FROM d.document_date) = filter_month)
        -- doc_type絞り込み
        AND (filter_doc_types IS NULL OR cardinality(filter_doc_types) = 0 OR d.doc_type = ANY(filter_doc_types))
        -- 類似度フィルタ
        AND (1 - (d.embedding <=> query_embedding)) >= match_threshold
    ORDER BY combined_score DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

COMMIT;

-- 確認
SELECT '✅ search_documents_final function updated to use source_documents' as status;
