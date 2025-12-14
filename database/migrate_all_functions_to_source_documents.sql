-- =========================================
-- 全てのSQL関数を source_documents に移行
-- documentsテーブル → source_documentsテーブル
-- =========================================

BEGIN;

-- ■■■ 1. search_documents_final 関数 ■■■
DROP FUNCTION IF EXISTS search_documents_final(TEXT, vector(1536), FLOAT, INT, FLOAT, FLOAT, INT, INT, TEXT);
DROP FUNCTION IF EXISTS search_documents_final(TEXT, vector(1536), FLOAT, INT, FLOAT, FLOAT, INT, INT, TEXT[], TEXT[]);
DROP FUNCTION IF EXISTS search_documents_final(text, vector, double precision, integer, double precision, double precision, integer, integer, text[]);

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
    FROM source_documents d  -- ✅ documents → source_documents
    WHERE
        d.processing_status = 'completed'
        AND (filter_year IS NULL OR EXTRACT(YEAR FROM d.document_date) = filter_year)
        AND (filter_month IS NULL OR EXTRACT(MONTH FROM d.document_date) = filter_month)
        AND (filter_doc_types IS NULL OR cardinality(filter_doc_types) = 0 OR d.doc_type = ANY(filter_doc_types))
        AND (1 - (d.embedding <=> query_embedding)) >= match_threshold
    ORDER BY combined_score DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;


-- ■■■ 2. get_active_workspaces 関数 ■■■
CREATE OR REPLACE FUNCTION get_active_workspaces()
RETURNS TABLE (workspace TEXT) AS $$
BEGIN
  RETURN QUERY
  SELECT DISTINCT d.workspace
  FROM source_documents d  -- ✅ documents → source_documents
  WHERE d.workspace IS NOT NULL
    AND d.processing_status = 'completed'
  ORDER BY d.workspace;
END;
$$ LANGUAGE plpgsql;


-- ■■■ 3. get_active_doc_types 関数 ■■■
CREATE OR REPLACE FUNCTION get_active_doc_types(filter_workspace TEXT DEFAULT NULL)
RETURNS TABLE (doc_type TEXT, doc_count BIGINT) AS $$
BEGIN
  RETURN QUERY
  SELECT d.doc_type, COUNT(*)::BIGINT as doc_count
  FROM source_documents d  -- ✅ documents → source_documents
  WHERE d.doc_type IS NOT NULL
    AND d.processing_status = 'completed'
    AND (filter_workspace IS NULL OR d.workspace = filter_workspace)
  GROUP BY d.doc_type
  ORDER BY d.doc_type;
END;
$$ LANGUAGE plpgsql;


-- ■■■ 4. hybrid_search 関数 ■■■
DROP FUNCTION IF EXISTS hybrid_search(TEXT, vector(1536), TEXT, TEXT, INT);
DROP FUNCTION IF EXISTS hybrid_search(TEXT, vector(1536), TEXT[], TEXT[], INT);

CREATE OR REPLACE FUNCTION hybrid_search(
    query_text TEXT,
    query_embedding vector(1536),
    target_workspaces TEXT[] DEFAULT NULL,
    target_types TEXT[] DEFAULT NULL,
    limit_results INT DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    source_type VARCHAR,
    source_url TEXT,
    file_name VARCHAR,
    doc_type VARCHAR,
    workspace VARCHAR,
    summary TEXT,
    full_text TEXT,
    metadata JSONB,
    document_date DATE,
    similarity_score FLOAT,
    text_rank FLOAT,
    combined_score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.source_type,
        d.source_url,
        d.file_name,
        d.doc_type,
        d.workspace,
        d.summary,
        d.full_text,
        d.metadata,
        d.document_date,
        (1 - (d.embedding <=> query_embedding))::FLOAT AS similarity_score,
        ts_rank(to_tsvector('japanese', COALESCE(d.full_text, '')), plainto_tsquery('japanese', query_text))::FLOAT AS text_rank,
        ((1 - (d.embedding <=> query_embedding)) * 0.7 +
         ts_rank(to_tsvector('japanese', COALESCE(d.full_text, '')), plainto_tsquery('japanese', query_text)) * 0.3)::FLOAT AS combined_score
    FROM source_documents d  -- ✅ documents → source_documents
    WHERE
        (target_workspaces IS NULL OR cardinality(target_workspaces) = 0 OR d.workspace = ANY(target_workspaces))
        AND (target_types IS NULL OR cardinality(target_types) = 0 OR d.doc_type = ANY(target_types))
        AND d.processing_status = 'completed'
    ORDER BY combined_score DESC
    LIMIT limit_results;
END;
$$ LANGUAGE plpgsql;

COMMIT;

-- =========================================
-- 確認クエリ
-- =========================================
SELECT '✅ All SQL functions migrated to source_documents' as status;

-- 確認: 関数が正しく作成されているか
SELECT
    routine_name,
    routine_type,
    data_type
FROM information_schema.routines
WHERE routine_schema = 'public'
    AND routine_name IN ('search_documents_final', 'get_active_workspaces', 'get_active_doc_types', 'hybrid_search')
ORDER BY routine_name;
