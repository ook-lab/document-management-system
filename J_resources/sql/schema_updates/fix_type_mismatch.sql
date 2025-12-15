-- 型の不一致エラーを修正
-- エラー: "Returned type real does not match expected type double precision"

BEGIN;

-- hybrid_search_chunks 関数を修正（型キャストを追加）
CREATE OR REPLACE FUNCTION hybrid_search_chunks(
    query_text TEXT,
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.0,
    match_count INT DEFAULT 50,
    vector_weight FLOAT DEFAULT 0.7,
    fulltext_weight FLOAT DEFAULT 0.3,
    -- メタデータフィルタ
    filter_year INT DEFAULT NULL,
    filter_month INT DEFAULT NULL,
    filter_doc_type VARCHAR DEFAULT NULL,
    filter_workspace VARCHAR DEFAULT NULL
)
RETURNS TABLE (
    chunk_id UUID,
    document_id UUID,
    chunk_index INTEGER,
    chunk_text TEXT,
    similarity FLOAT,
    fulltext_rank FLOAT,
    combined_score FLOAT,
    -- 親ドキュメント情報
    file_name VARCHAR,
    doc_type VARCHAR,
    document_date DATE,
    metadata JSONB,
    summary TEXT,
    year INTEGER,
    month INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id AS chunk_id,
        dc.document_id,
        dc.chunk_index,
        dc.chunk_text,
        (1 - (dc.embedding <=> query_embedding))::FLOAT AS similarity,
        ts_rank(dc.chunk_text_tsv, plainto_tsquery('simple', query_text))::FLOAT AS fulltext_rank,
        ((1 - (dc.embedding <=> query_embedding)) * vector_weight +
        ts_rank(dc.chunk_text_tsv, plainto_tsquery('simple', query_text)) * fulltext_weight)::FLOAT AS combined_score,
        d.file_name,
        d.doc_type,
        d.document_date,
        d.metadata,
        d.summary,
        d.year,
        d.month
    FROM document_chunks dc
    JOIN documents d ON dc.document_id = d.id
    WHERE
        d.processing_status = 'completed'
        AND (
            (1 - (dc.embedding <=> query_embedding)) > match_threshold
            OR
            dc.chunk_text_tsv @@ plainto_tsquery('simple', query_text)
        )
        AND (filter_year IS NULL OR d.year = filter_year)
        AND (filter_month IS NULL OR d.month = filter_month)
        AND (filter_doc_type IS NULL OR d.doc_type = filter_doc_type)
        AND (filter_workspace IS NULL OR d.workspace = filter_workspace)
    ORDER BY combined_score DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

-- keyword_search_chunks 関数も修正
CREATE OR REPLACE FUNCTION keyword_search_chunks(
    query_text TEXT,
    match_count INT DEFAULT 50,
    filter_year INT DEFAULT NULL,
    filter_month INT DEFAULT NULL,
    filter_doc_type VARCHAR DEFAULT NULL
)
RETURNS TABLE (
    chunk_id UUID,
    document_id UUID,
    chunk_text TEXT,
    fulltext_rank FLOAT,
    file_name VARCHAR,
    doc_type VARCHAR,
    document_date DATE
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id AS chunk_id,
        dc.document_id,
        dc.chunk_text,
        ts_rank(dc.chunk_text_tsv, plainto_tsquery('simple', query_text))::FLOAT AS fulltext_rank,
        d.file_name,
        d.doc_type,
        d.document_date
    FROM document_chunks dc
    JOIN documents d ON dc.document_id = d.id
    WHERE
        d.processing_status = 'completed'
        AND dc.chunk_text_tsv @@ plainto_tsquery('simple', query_text)
        AND (filter_year IS NULL OR d.year = filter_year)
        AND (filter_month IS NULL OR d.month = filter_month)
        AND (filter_doc_type IS NULL OR d.doc_type = filter_doc_type)
    ORDER BY fulltext_rank DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

COMMIT;
