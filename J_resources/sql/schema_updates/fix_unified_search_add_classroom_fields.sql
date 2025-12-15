-- ============================================================
-- unified_search関数にClassroomフィールドを追加
-- 実施日: 2025-12-12
-- 目的: classroom_subject等をAPI経由でフロントエンドに返せるようにする
-- ============================================================

BEGIN;

-- 既存の関数を削除
DROP FUNCTION IF EXISTS unified_search(TEXT, vector(1536), FLOAT, INT, FLOAT, FLOAT, TEXT[], TEXT[], TEXT);

-- Classroomフィールドを含む新しい関数を作成
CREATE OR REPLACE FUNCTION unified_search(
    query_text TEXT,
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.0,
    match_count INT DEFAULT 10,
    vector_weight FLOAT DEFAULT 0.7,
    fulltext_weight FLOAT DEFAULT 0.3,
    filter_doc_types TEXT[] DEFAULT NULL,
    filter_chunk_types TEXT[] DEFAULT NULL,
    filter_workspace TEXT DEFAULT NULL
)
RETURNS TABLE (
    document_id UUID,
    file_name VARCHAR,
    doc_type VARCHAR,
    workspace VARCHAR,
    document_date DATE,
    metadata JSONB,
    summary TEXT,
    full_text TEXT,
    best_chunk_text TEXT,
    best_chunk_type VARCHAR,
    best_chunk_id UUID,
    best_chunk_index INTEGER,
    raw_similarity FLOAT,
    weighted_similarity FLOAT,
    fulltext_score FLOAT,
    combined_score FLOAT,
    title_matched BOOLEAN,
    source_type VARCHAR,
    source_url TEXT,
    created_at TIMESTAMPTZ,
    -- ✅ Classroomフィールドを追加
    classroom_subject TEXT,
    classroom_sender VARCHAR,
    classroom_sender_email VARCHAR,
    classroom_sent_at TIMESTAMPTZ,
    classroom_course_id VARCHAR,
    classroom_course_name VARCHAR,
    ingestion_route VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    WITH chunk_scores AS (
        SELECT
            dc.id AS chunk_id,
            dc.document_id AS doc_id,
            dc.chunk_index,
            dc.chunk_text,
            dc.chunk_type,
            COALESCE(dc.search_weight, 1.0) AS search_weight,
            (1 - (dc.embedding <=> query_embedding)) AS raw_sim,
            (1 - (dc.embedding <=> query_embedding)) * COALESCE(dc.search_weight, 1.0) AS weighted_sim,
            ts_rank_cd(
                to_tsvector('simple', dc.chunk_text),
                websearch_to_tsquery('simple', query_text)
            ) AS ft_score
        FROM document_chunks dc
        JOIN documents d ON dc.document_id = d.id
        WHERE
            dc.embedding IS NOT NULL
            AND (dc.chunk_type IS NULL OR dc.chunk_type != 'content_large')
            AND (1 - (dc.embedding <=> query_embedding)) >= match_threshold
            AND (filter_chunk_types IS NULL OR dc.chunk_type = ANY(filter_chunk_types))
            AND (filter_doc_types IS NULL OR d.doc_type = ANY(filter_doc_types))
            AND (filter_workspace IS NULL OR d.workspace = filter_workspace)
            AND d.processing_status = 'completed'
    ),
    ranked_chunks AS (
        SELECT
            cs.*,
            (cs.weighted_sim * vector_weight + cs.ft_score * fulltext_weight) AS combined,
            (cs.chunk_type = 'title') AS is_title_match
        FROM chunk_scores cs
    ),
    document_best_chunks AS (
        SELECT DISTINCT ON (rc.doc_id)
            rc.chunk_id,
            rc.doc_id,
            rc.chunk_index,
            rc.chunk_text,
            rc.chunk_type,
            rc.raw_sim,
            rc.weighted_sim,
            rc.ft_score,
            rc.combined,
            rc.is_title_match
        FROM ranked_chunks rc
        ORDER BY
            rc.doc_id,
            rc.is_title_match DESC,
            rc.combined DESC
    )
    SELECT
        d.id AS document_id,
        d.file_name,
        d.doc_type,
        d.workspace,
        d.document_date,
        d.metadata,
        d.summary,
        d.full_text,
        dbc.chunk_text AS best_chunk_text,
        dbc.chunk_type::VARCHAR AS best_chunk_type,
        dbc.chunk_id AS best_chunk_id,
        dbc.chunk_index AS best_chunk_index,
        dbc.raw_sim::FLOAT AS raw_similarity,
        dbc.weighted_sim::FLOAT AS weighted_similarity,
        dbc.ft_score::FLOAT AS fulltext_score,
        dbc.combined::FLOAT AS combined_score,
        dbc.is_title_match AS title_matched,
        d.source_type,
        d.source_url,
        d.created_at,
        -- ✅ Classroomフィールドを追加
        d.classroom_subject,
        d.classroom_sender,
        d.classroom_sender_email,
        d.classroom_sent_at,
        d.classroom_course_id,
        d.classroom_course_name,
        d.ingestion_route
    FROM document_best_chunks dbc
    INNER JOIN documents d ON d.id = dbc.doc_id
    ORDER BY
        dbc.is_title_match DESC,
        dbc.combined DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

COMMIT;
