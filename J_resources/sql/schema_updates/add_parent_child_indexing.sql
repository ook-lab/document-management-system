-- 【実行場所】: Supabase SQL Editor
-- 【対象】: Parent-Child Indexing（親子インデックス）
-- 【目的】: 小さなチャンク（子）で検索、大きなチャンク（親）でコンテキスト提供

-- Parent-Child Indexing により：
-- - 検索精度が向上（小さなチャンクで細かくヒット）
-- - 回答精度が向上（大きなチャンクで十分なコンテキスト）
-- - LLMの混乱を防ぐ（ファイル全体ではなく適切な範囲）

BEGIN;

-- document_chunks テーブルに parent_chunk_id を追加
ALTER TABLE document_chunks
    ADD COLUMN IF NOT EXISTS parent_chunk_id UUID REFERENCES document_chunks(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS is_parent BOOLEAN DEFAULT false,
    ADD COLUMN IF NOT EXISTS chunk_level VARCHAR(20) DEFAULT 'standard';

-- parent_chunk_id にインデックスを作成（高速検索のため）
CREATE INDEX IF NOT EXISTS idx_document_chunks_parent_chunk_id ON document_chunks(parent_chunk_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_is_parent ON document_chunks(is_parent);

-- コメント追加
COMMENT ON COLUMN document_chunks.parent_chunk_id IS '親チャンクのID（子チャンクの場合のみ）';
COMMENT ON COLUMN document_chunks.is_parent IS '親チャンクかどうか（true: 親、false: 子）';
COMMENT ON COLUMN document_chunks.chunk_level IS 'チャンクレベル（parent: 親、child: 子、standard: 標準）';

-- 親チャンクを取得する関数
CREATE OR REPLACE FUNCTION get_parent_chunks(
    child_chunk_ids UUID[]
)
RETURNS TABLE (
    parent_chunk_id UUID,
    parent_chunk_text TEXT,
    parent_chunk_size INTEGER,
    document_id UUID,
    file_name VARCHAR,
    doc_type VARCHAR,
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        pc.id AS parent_chunk_id,
        pc.chunk_text AS parent_chunk_text,
        pc.chunk_size AS parent_chunk_size,
        pc.document_id,
        d.file_name,
        d.doc_type,
        d.metadata
    FROM document_chunks cc
    JOIN document_chunks pc ON cc.parent_chunk_id = pc.id
    JOIN documents d ON pc.document_id = d.id
    WHERE cc.id = ANY(child_chunk_ids)
        AND pc.is_parent = true
        AND d.processing_status = 'completed';
END;
$$ LANGUAGE plpgsql;

-- Parent-Child 対応のハイブリッド検索関数
CREATE OR REPLACE FUNCTION hybrid_search_with_parent_child(
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
    filter_workspace VARCHAR DEFAULT NULL,
    -- Parent-Child設定
    use_parent_context BOOLEAN DEFAULT true
)
RETURNS TABLE (
    chunk_id UUID,
    document_id UUID,
    chunk_index INTEGER,
    chunk_text TEXT,
    parent_chunk_text TEXT,
    is_parent BOOLEAN,
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
    WITH child_results AS (
        -- 子チャンク（または標準チャンク）で検索
        SELECT
            dc.id AS chunk_id,
            dc.document_id,
            dc.chunk_index,
            dc.chunk_text,
            dc.parent_chunk_id,
            dc.is_parent,
            1 - (dc.embedding <=> query_embedding) AS similarity,
            ts_rank(dc.chunk_text_tsv, plainto_tsquery('simple', query_text)) AS fulltext_rank,
            (1 - (dc.embedding <=> query_embedding)) * vector_weight +
            ts_rank(dc.chunk_text_tsv, plainto_tsquery('simple', query_text)) * fulltext_weight AS combined_score,
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
            -- 子チャンクまたは標準チャンクのみ検索（親チャンクは検索対象外）
            AND dc.is_parent = false
            -- ベクトル検索またはキーワード検索のどちらかでヒット
            AND (
                (1 - (dc.embedding <=> query_embedding)) > match_threshold
                OR
                dc.chunk_text_tsv @@ plainto_tsquery('simple', query_text)
            )
            -- メタデータフィルタリング
            AND (filter_year IS NULL OR d.year = filter_year)
            AND (filter_month IS NULL OR d.month = filter_month)
            AND (filter_doc_type IS NULL OR d.doc_type = filter_doc_type)
            AND (filter_workspace IS NULL OR d.workspace = filter_workspace)
        ORDER BY combined_score DESC
        LIMIT match_count
    )
    SELECT
        cr.chunk_id,
        cr.document_id,
        cr.chunk_index,
        cr.chunk_text,
        CASE
            WHEN use_parent_context AND cr.parent_chunk_id IS NOT NULL THEN pc.chunk_text
            ELSE cr.chunk_text
        END AS parent_chunk_text,
        cr.is_parent,
        cr.similarity,
        cr.fulltext_rank,
        cr.combined_score,
        cr.file_name,
        cr.doc_type,
        cr.document_date,
        cr.metadata,
        cr.summary,
        cr.year,
        cr.month
    FROM child_results cr
    LEFT JOIN document_chunks pc ON cr.parent_chunk_id = pc.id
    ORDER BY cr.combined_score DESC;
END;
$$ LANGUAGE plpgsql;

COMMIT;
