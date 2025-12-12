-- ============================================================
-- C1: 検索関数の完全統一
-- 実施日: 2025-12-12
-- 目的: 複数の検索関数を1つに統合し、B2のメタデータ重み付けを活用
-- ============================================================

-- 【実行場所】: Supabase SQL Editor

BEGIN;

-- ============================================================
-- 統一検索関数: unified_search
-- ============================================================
-- 機能:
-- 1. 小チャンク検索（content_small）+ メタデータチャンク検索
-- 2. chunk_typeによる重み付け（B2対応）
-- 3. ベクトル検索 + 全文検索のハイブリッド
-- 4. ドキュメント単位で重複排除
-- 5. 大チャンク（全文）を返却

DROP FUNCTION IF EXISTS unified_search(TEXT, vector(1536), FLOAT, INT, FLOAT, FLOAT, TEXT[], TEXT[], TEXT);

CREATE OR REPLACE FUNCTION unified_search(
    query_text TEXT,
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.0,
    match_count INT DEFAULT 10,
    vector_weight FLOAT DEFAULT 0.7,
    fulltext_weight FLOAT DEFAULT 0.3,
    filter_doc_types TEXT[] DEFAULT NULL,
    filter_chunk_types TEXT[] DEFAULT NULL,  -- B2: チャンク種別フィルタ
    filter_workspace TEXT DEFAULT NULL       -- ワークスペースフィルタ
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
        -- 全チャンクでベクトル検索 + 全文検索（B2: search_weight適用）
        SELECT
            dc.id AS chunk_id,
            dc.document_id AS doc_id,
            dc.chunk_index,
            dc.chunk_text,
            dc.chunk_type,
            COALESCE(dc.search_weight, 1.0) AS search_weight,
            -- ベクトル類似度（生スコア）
            (1 - (dc.embedding <=> query_embedding)) AS raw_sim,
            -- B2: 重み付き類似度
            (1 - (dc.embedding <=> query_embedding)) * COALESCE(dc.search_weight, 1.0) AS weighted_sim,
            -- 全文検索スコア
            ts_rank_cd(
                to_tsvector('simple', dc.chunk_text),
                websearch_to_tsquery('simple', query_text)
            ) AS ft_score
        FROM document_chunks dc
        JOIN documents d ON dc.document_id = d.id
        WHERE
            dc.embedding IS NOT NULL
            -- 大チャンクは検索対象外（回答生成用）
            AND (dc.chunk_type IS NULL OR dc.chunk_type != 'content_large')
            -- 類似度フィルタ
            AND (1 - (dc.embedding <=> query_embedding)) >= match_threshold
            -- チャンク種別フィルタ（B2）
            AND (filter_chunk_types IS NULL OR dc.chunk_type = ANY(filter_chunk_types))
            -- doc_typeフィルタ
            AND (filter_doc_types IS NULL OR d.doc_type = ANY(filter_doc_types))
            -- ワークスペースフィルタ
            AND (filter_workspace IS NULL OR d.workspace = filter_workspace)
            -- 完了済みドキュメントのみ
            AND d.processing_status = 'completed'
    ),
    ranked_chunks AS (
        -- 統合スコアを計算
        SELECT
            cs.*,
            -- 統合スコア: 重み付きベクトル + 全文検索
            (cs.weighted_sim * vector_weight + cs.ft_score * fulltext_weight) AS combined,
            -- タイトルマッチフラグ
            (cs.chunk_type = 'title') AS is_title_match
        FROM chunk_scores cs
    ),
    document_best_chunks AS (
        -- ドキュメントごとに最高スコアのチャンクを選択
        -- タイトルマッチを優先
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
            rc.is_title_match DESC,  -- タイトルマッチ優先
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
        d.created_at
    FROM document_best_chunks dbc
    INNER JOIN documents d ON d.id = dbc.doc_id
    ORDER BY
        dbc.is_title_match DESC,
        dbc.combined DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION unified_search IS 'C1: 統一検索関数。B2のメタデータ重み付け対応、タイトルマッチ優先';

-- ============================================================
-- 既存の search_documents_with_chunks を更新
-- unified_search のラッパーとして機能
-- ============================================================

DROP FUNCTION IF EXISTS search_documents_with_chunks(TEXT, vector(1536), FLOAT, INT, FLOAT, FLOAT, TEXT[]);

CREATE OR REPLACE FUNCTION search_documents_with_chunks(
    query_text TEXT,
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.0,
    match_count INT DEFAULT 10,
    vector_weight FLOAT DEFAULT 0.7,
    fulltext_weight FLOAT DEFAULT 0.3,
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
    full_text TEXT,
    chunk_content TEXT,
    chunk_id UUID,
    chunk_index INTEGER,
    chunk_score FLOAT,
    combined_score FLOAT,
    source_type VARCHAR,
    source_url TEXT,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    -- unified_search を呼び出し、既存のインターフェースに変換
    RETURN QUERY
    SELECT
        us.document_id,
        us.file_name,
        us.doc_type,
        us.workspace,
        us.document_date,
        us.metadata,
        us.summary,
        us.full_text,
        us.best_chunk_text AS chunk_content,
        us.best_chunk_id AS chunk_id,
        us.best_chunk_index AS chunk_index,
        us.weighted_similarity AS chunk_score,
        us.combined_score,
        us.source_type,
        us.source_url,
        us.created_at
    FROM unified_search(
        query_text,
        query_embedding,
        match_threshold,
        match_count,
        vector_weight,
        fulltext_weight,
        filter_doc_types,
        NULL,  -- filter_chunk_types
        NULL   -- filter_workspace
    ) us;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION search_documents_with_chunks IS '後方互換用ラッパー。内部でunified_searchを呼び出し';

-- ============================================================
-- 未使用関数の削除（オプション）
-- ============================================================
-- 以下の関数は使用されていないため削除可能
-- 注意: 本番環境では慎重に実行

-- DROP FUNCTION IF EXISTS hybrid_search(TEXT, vector(1536), FLOAT, INT);
-- DROP FUNCTION IF EXISTS match_documents(vector(1536), FLOAT, INT);

COMMIT;

-- ============================================================
-- 検証クエリ
-- ============================================================

-- 統一検索テスト
-- SELECT * FROM unified_search(
--     'テスト検索',
--     '[0.1, 0.2, ...]'::vector(1536),
--     0.3,  -- threshold
--     10,   -- limit
--     0.7,  -- vector_weight
--     0.3,  -- fulltext_weight
--     NULL, -- doc_types
--     ARRAY['title', 'summary', 'content_small'],  -- chunk_types
--     'school'  -- workspace
-- );

-- 後方互換テスト
-- SELECT * FROM search_documents_with_chunks(
--     'テスト検索',
--     '[0.1, 0.2, ...]'::vector(1536),
--     0.3,
--     10
-- );
