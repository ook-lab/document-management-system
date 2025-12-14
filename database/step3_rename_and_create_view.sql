-- ============================================================
-- ステップ3: 旧テーブルのリネームとビュー作成
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-14
-- 前提: step1_create_tables.sql と step2_migrate_data.sql が実行済みであること
-- ============================================================

BEGIN;

-- ============================================================
-- 1. 既存テーブルのリネーム（バックアップ）
-- ============================================================
ALTER TABLE documents RENAME TO documents_legacy;
ALTER TABLE document_chunks RENAME TO document_chunks_legacy;

-- ============================================================
-- 2. 互換性ビューの作成
-- ============================================================
CREATE VIEW documents AS
SELECT
    sd.id,
    sd.source_type,
    sd.source_id,
    sd.source_url,
    sd.ingestion_route,
    sd.file_name,
    sd.file_type,
    sd.file_size_bytes,
    sd.workspace,
    sd.doc_type,
    sd.full_text,
    sd.summary,
    sd.metadata,
    sd.tags,
    sd.document_date,
    sd.content_hash,
    sd.created_at,
    sd.updated_at,
    pl.processing_status,
    pl.processing_stage,
    pl.stageA_classifier_model,
    pl.stageB_vision_model,
    pl.stageC_extractor_model,
    pl.text_extraction_model,
    pl.prompt_version,
    pl.error_message,
    pl.processed_at
FROM source_documents sd
LEFT JOIN LATERAL (
    SELECT *
    FROM process_logs
    WHERE process_logs.document_id = sd.id
    ORDER BY created_at DESC
    LIMIT 1
) pl ON true;

COMMENT ON VIEW documents IS
'互換性ビュー: 既存アプリケーションのためにsource_documentsとprocess_logsを結合';

-- ============================================================
-- 3. 統一検索関数の作成
-- ============================================================
CREATE OR REPLACE FUNCTION unified_search_v2(
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
    created_at TIMESTAMPTZ
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
        sd.full_text,
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
        sd.created_at
    FROM document_best_chunks dbc
    INNER JOIN source_documents sd ON sd.id = dbc.doc_id
    ORDER BY dbc.is_title_match DESC, dbc.combined DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION unified_search_v2 IS
'3層構造対応の統一検索関数: source_documents + search_indexを使用';

COMMIT;

-- ============================================================
-- 完了メッセージ
-- ============================================================
SELECT
    'ステップ3完了: マイグレーションが全て完了しました！' AS status,
    '旧テーブル: documents_legacy, document_chunks_legacy' AS legacy_tables,
    '新ビュー: documents' AS new_view,
    '新検索関数: unified_search_v2' AS new_function;
