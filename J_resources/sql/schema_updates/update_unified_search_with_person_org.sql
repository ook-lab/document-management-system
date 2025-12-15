-- 【実行場所】: Supabase SQL Editor
-- 【対象ファイル】: 新規SQL実行
-- 【実行方法】: SupabaseダッシュボードでSQL Editorに貼り付け、実行
-- 【目的】: unified_search関数を更新してperson, organization, peopleカラムを返すようにする
-- 【前提】: add_person_organization_people.sqlを先に実行していること

BEGIN;

-- ============================================================
-- C1: 統一検索関数の更新（person, organization, people対応）
-- ============================================================

-- 既存の関数を削除（戻り値の型を変更するため必須）
DROP FUNCTION IF EXISTS unified_search(text,vector,double precision,integer,double precision,double precision,text[],text[],text);

-- 新しい戻り値の型で関数を再作成
CREATE FUNCTION unified_search(
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
    person TEXT,
    organization TEXT,
    people TEXT[],
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
    created_at TIMESTAMPTZ
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
        ORDER BY rc.doc_id, rc.is_title_match DESC, rc.combined DESC
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
        d.person,
        d.organization,
        d.people,
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
        d.created_at
    FROM document_best_chunks dbc
    INNER JOIN documents d ON d.id = dbc.doc_id
    ORDER BY dbc.is_title_match DESC, dbc.combined DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION unified_search IS 'C1統一検索: person, organization, people対応、B2メタデータ重み付け対応、タイトルマッチ優先';

COMMIT;
