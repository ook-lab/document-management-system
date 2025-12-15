-- =========================================
-- 緊急修正: embeddingカラムなしで動作する検索関数
-- 問題: embeddingカラムが削除されたため検索が動作しない
-- 対策: 全文検索のみで動作するように修正
-- =========================================

BEGIN;

-- 既存の関数を削除
DROP FUNCTION IF EXISTS search_documents_final(TEXT, vector(1536), FLOAT, INT, FLOAT, FLOAT, TEXT[]);
DROP FUNCTION IF EXISTS search_documents_final(TEXT, vector, FLOAT, INT, FLOAT, FLOAT, TEXT[]);

-- 全文検索のみで動作する関数を作成（embeddingなし）
CREATE OR REPLACE FUNCTION search_documents_final(
    query_text TEXT,
    query_embedding vector(1536) DEFAULT NULL,  -- embeddingは使用しないがインターフェース互換性のため残す
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
    large_chunk_text TEXT,
    large_chunk_id UUID,
    combined_score FLOAT,
    small_chunk_id UUID,
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
        -- 全文検索スコアのみを使用（embeddingなし）
        ts_rank_cd(
            to_tsvector('simple', COALESCE(d.full_text, '') || ' ' || COALESCE(d.summary, '') || ' ' || COALESCE(d.file_name, '')),
            websearch_to_tsquery('simple', query_text)
        )::FLOAT AS combined_score,
        d.id AS small_chunk_id,
        d.source_type,
        d.source_url,
        d.full_text,
        d.created_at
    FROM documents d
    WHERE
        -- 全文検索条件
        (
            to_tsvector('simple', COALESCE(d.full_text, '') || ' ' || COALESCE(d.summary, '') || ' ' || COALESCE(d.file_name, ''))
            @@ websearch_to_tsquery('simple', query_text)
        )
        -- doc_type絞り込み
        AND (filter_doc_types IS NULL
             OR cardinality(filter_doc_types) = 0
             OR d.doc_type = ANY(filter_doc_types))
    ORDER BY combined_score DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

COMMIT;

-- =========================================
-- 説明
-- =========================================
-- この関数は embeddingカラムなしで動作します
-- ベクトル検索の代わりに全文検索（ts_rank）のみを使用
-- full_text, summary, file_name を検索対象とします
--
-- 注意: ベクトル検索に比べて精度は低下しますが、
-- embeddingカラムが復元されるまでの応急措置です
