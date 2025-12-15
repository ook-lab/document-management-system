-- ============================================================
-- B2: メタデータ別ベクトル化戦略
-- 実施日: 2025-12-12
-- 目的: チャンク種別と検索重みを追加し、検索精度を向上
-- ============================================================

-- 【実行場所】: Supabase SQL Editor
-- 【前提条件】: document_chunks テーブルが存在すること

BEGIN;

-- ============================================================
-- Step 1: document_chunks テーブルにカラム追加
-- ============================================================

-- chunk_type: チャンク種別
-- 値: 'title', 'summary', 'date', 'tags', 'content_small', 'content_large', 'synthetic'
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'document_chunks' AND column_name = 'chunk_type'
    ) THEN
        ALTER TABLE document_chunks
        ADD COLUMN chunk_type VARCHAR(50) DEFAULT 'content_small';

        COMMENT ON COLUMN document_chunks.chunk_type IS
            'チャンク種別: title(2.0), summary(1.5), date(1.3), tags(1.2), content_small(1.0), content_large(1.0), synthetic(1.0)';
    END IF;
END $$;

-- search_weight: 検索時の重み付け係数
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'document_chunks' AND column_name = 'search_weight'
    ) THEN
        ALTER TABLE document_chunks
        ADD COLUMN search_weight FLOAT DEFAULT 1.0;

        COMMENT ON COLUMN document_chunks.search_weight IS
            '検索重み: title=2.0, summary=1.5, date=1.3, tags=1.2, その他=1.0';
    END IF;
END $$;

-- ============================================================
-- Step 2: 既存データの更新（chunk_typeを推定）
-- ============================================================

-- chunk_index=0 で短いテキストはタイトルの可能性
-- ただし、既存データは content_small として扱う
UPDATE document_chunks
SET chunk_type = 'content_small', search_weight = 1.0
WHERE chunk_type IS NULL;

-- ============================================================
-- Step 3: インデックス追加（検索性能向上）
-- ============================================================

-- chunk_type でのフィルタリング用
CREATE INDEX IF NOT EXISTS idx_document_chunks_chunk_type
ON document_chunks(chunk_type);

-- 複合インデックス（document_id + chunk_type）
CREATE INDEX IF NOT EXISTS idx_document_chunks_doc_type
ON document_chunks(document_id, chunk_type);

-- ============================================================
-- Step 4: 重み付き検索関数の作成
-- ============================================================

-- 既存の match_document_chunks を拡張
CREATE OR REPLACE FUNCTION search_chunks_weighted(
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.0,
    match_count INT DEFAULT 50,
    chunk_types TEXT[] DEFAULT NULL,  -- フィルタ: NULL=全種別
    workspace_filter TEXT DEFAULT NULL
)
RETURNS TABLE (
    chunk_id UUID,
    document_id UUID,
    chunk_index INTEGER,
    chunk_text TEXT,
    chunk_type VARCHAR(50),
    search_weight FLOAT,
    raw_similarity FLOAT,
    weighted_similarity FLOAT,
    file_name TEXT,
    doc_type TEXT,
    document_date DATE,
    workspace TEXT,
    summary TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id AS chunk_id,
        dc.document_id,
        dc.chunk_index,
        dc.chunk_text,
        dc.chunk_type,
        dc.search_weight,
        (1 - (dc.embedding <=> query_embedding))::FLOAT AS raw_similarity,
        ((1 - (dc.embedding <=> query_embedding)) * COALESCE(dc.search_weight, 1.0))::FLOAT AS weighted_similarity,
        d.file_name,
        d.doc_type,
        d.document_date,
        d.workspace,
        d.summary
    FROM document_chunks dc
    JOIN documents d ON dc.document_id = d.id
    WHERE
        d.processing_status = 'completed'
        AND (1 - (dc.embedding <=> query_embedding)) > match_threshold
        AND (chunk_types IS NULL OR dc.chunk_type = ANY(chunk_types))
        AND (workspace_filter IS NULL OR d.workspace = workspace_filter)
    ORDER BY weighted_similarity DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION search_chunks_weighted IS
    'B2: 重み付きチャンク検索。chunk_type別の重みを考慮したスコアで並べ替え';

-- ============================================================
-- Step 5: タイトル優先検索関数
-- ============================================================

-- タイトルマッチを優先する2段階検索
CREATE OR REPLACE FUNCTION search_with_title_boost(
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.0,
    match_count INT DEFAULT 20,
    workspace_filter TEXT DEFAULT NULL
)
RETURNS TABLE (
    document_id UUID,
    file_name TEXT,
    doc_type TEXT,
    document_date DATE,
    workspace TEXT,
    summary TEXT,
    best_chunk_text TEXT,
    best_chunk_type VARCHAR(50),
    max_weighted_score FLOAT,
    title_matched BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    WITH ranked_chunks AS (
        SELECT
            dc.document_id,
            dc.chunk_text,
            dc.chunk_type,
            ((1 - (dc.embedding <=> query_embedding)) * COALESCE(dc.search_weight, 1.0))::FLOAT AS weighted_score,
            dc.chunk_type = 'title' AS is_title_match,
            ROW_NUMBER() OVER (
                PARTITION BY dc.document_id
                ORDER BY
                    CASE WHEN dc.chunk_type = 'title' THEN 0 ELSE 1 END,
                    ((1 - (dc.embedding <=> query_embedding)) * COALESCE(dc.search_weight, 1.0)) DESC
            ) AS rn
        FROM document_chunks dc
        JOIN documents d ON dc.document_id = d.id
        WHERE
            d.processing_status = 'completed'
            AND (1 - (dc.embedding <=> query_embedding)) > match_threshold
            AND (workspace_filter IS NULL OR d.workspace = workspace_filter)
    ),
    best_per_doc AS (
        SELECT *
        FROM ranked_chunks
        WHERE rn = 1
    )
    SELECT
        b.document_id,
        d.file_name,
        d.doc_type,
        d.document_date,
        d.workspace,
        d.summary,
        b.chunk_text AS best_chunk_text,
        b.chunk_type AS best_chunk_type,
        b.weighted_score AS max_weighted_score,
        b.is_title_match AS title_matched
    FROM best_per_doc b
    JOIN documents d ON b.document_id = d.id
    ORDER BY
        b.is_title_match DESC,  -- タイトルマッチを優先
        b.weighted_score DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION search_with_title_boost IS
    'B2: タイトルマッチを優先する検索。同一文書の最良チャンクを返す';

COMMIT;

-- ============================================================
-- 検証クエリ
-- ============================================================

-- カラム追加の確認
-- SELECT column_name, data_type, column_default
-- FROM information_schema.columns
-- WHERE table_name = 'document_chunks'
-- AND column_name IN ('chunk_type', 'search_weight');

-- 重み付き検索のテスト（実行例）
-- SELECT * FROM search_chunks_weighted(
--     '[0.1, 0.2, ...]'::vector(1536),  -- クエリembedding
--     0.3,  -- threshold
--     10,   -- limit
--     ARRAY['title', 'summary'],  -- チャンク種別フィルタ
--     'school'  -- workspace
-- );
