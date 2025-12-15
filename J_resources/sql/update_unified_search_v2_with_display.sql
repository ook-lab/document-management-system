-- =====================================================
-- unified_search_v2 関数を修正して display_* カラムを追加
-- 作成日: 2025-12-15
-- =====================================================

DROP FUNCTION IF EXISTS unified_search_v2(TEXT, vector, FLOAT, INT, FLOAT, FLOAT, TEXT[], TEXT[], TEXT);

CREATE OR REPLACE FUNCTION unified_search_v2(
    query_text TEXT,
    query_embedding vector,
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
    attachment_text TEXT,  -- ✅ 修正: full_text → attachment_text
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
    -- ✅ 追加: display_* カラム
    display_subject TEXT,
    display_sender VARCHAR,
    display_sent_at TIMESTAMPTZ,
    display_post_text TEXT,
    display_type VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    WITH chunk_scores AS (
        SELECT
            si.id AS chunk_id,
            si.document_id AS doc_id,
            si.chunk_index,
            si.chunk_content,
            si.chunk_type,
            COALESCE(si.search_weight, 1.0) AS search_weight,
            (1 - (si.embedding <=> query_embedding)) AS raw_sim,
            (1 - (si.embedding <=> query_embedding)) * COALESCE(si.search_weight, 1.0) AS weighted_sim,
            ts_rank_cd(
                to_tsvector('simple', si.chunk_content),
                websearch_to_tsquery('simple', query_text)
            ) AS ft_score
        FROM search_index si
        JOIN source_documents sd ON si.document_id = sd.id
        WHERE
            si.embedding IS NOT NULL
            AND (si.chunk_type IS NULL OR si.chunk_type != 'content_large')
            AND (1 - (si.embedding <=> query_embedding)) >= match_threshold
            AND (filter_chunk_types IS NULL OR si.chunk_type = ANY(filter_chunk_types))
            AND (filter_doc_types IS NULL OR sd.doc_type = ANY(filter_doc_types))
            AND (filter_workspace IS NULL OR sd.workspace = filter_workspace)
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
            rc.chunk_content,
            rc.chunk_type,
            rc.raw_sim,
            rc.weighted_sim,
            rc.ft_score,
            rc.combined,
            rc.is_title_match
        FROM ranked_chunks rc
        ORDER BY rc.doc_id, rc.is_title_match DESC, rc.combined DESC
    )
    SELECT
        sd.id AS document_id,
        sd.file_name,
        sd.doc_type,
        sd.workspace,
        sd.document_date,
        sd.metadata,
        sd.summary,
        sd.attachment_text,
        dbc.chunk_content AS best_chunk_text,
        dbc.chunk_type::VARCHAR AS best_chunk_type,
        dbc.chunk_id AS best_chunk_id,
        dbc.chunk_index AS best_chunk_index,
        dbc.raw_sim::FLOAT AS raw_similarity,
        dbc.weighted_sim::FLOAT AS weighted_similarity,
        dbc.ft_score::FLOAT AS fulltext_score,
        dbc.combined::FLOAT AS combined_score,
        dbc.is_title_match AS title_matched,
        sd.source_type,
        sd.source_url,
        sd.created_at,
        -- ✅ 追加: display_* カラム
        sd.display_subject,
        sd.display_sender,
        sd.display_sent_at,
        sd.display_post_text,
        sd.display_type
    FROM document_best_chunks dbc
    INNER JOIN source_documents sd ON sd.id = dbc.doc_id
    ORDER BY dbc.is_title_match DESC, dbc.combined DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 実行後の確認用クエリ
-- =====================================================
-- SELECT * FROM unified_search_v2(
--     'テスト',
--     (SELECT embedding FROM search_index LIMIT 1),
--     0.0,
--     5,
--     0.7,
--     0.3,
--     NULL,
--     NULL,
--     NULL
-- );
