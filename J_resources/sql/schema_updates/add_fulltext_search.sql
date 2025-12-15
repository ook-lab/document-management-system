-- 【実行場所】: Supabase SQL Editor
-- 【対象】: ハイブリッド検索の強化（全文検索）
-- 【目的】: ベクトル検索 + キーワード検索で検索精度を大幅向上

-- ハイブリッド検索により、「ID:12345」のような完全一致が必要な検索や
-- 固有名詞の検索が確実にヒットするようになります

BEGIN;

-- documents テーブルに tsvector カラムを追加（日本語全文検索用）
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS full_text_tsv tsvector;

-- document_chunks テーブルにも tsvector カラムを追加
ALTER TABLE document_chunks
    ADD COLUMN IF NOT EXISTS chunk_text_tsv tsvector;

-- tsvectorを自動更新するトリガー関数（documents）
CREATE OR REPLACE FUNCTION documents_tsvector_update_trigger()
RETURNS TRIGGER AS $$
BEGIN
    -- full_text を日本語で tsvector に変換
    NEW.full_text_tsv := to_tsvector('simple', COALESCE(NEW.full_text, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- tsvectorを自動更新するトリガー関数（document_chunks）
CREATE OR REPLACE FUNCTION document_chunks_tsvector_update_trigger()
RETURNS TRIGGER AS $$
BEGIN
    -- chunk_text を日本語で tsvector に変換
    NEW.chunk_text_tsv := to_tsvector('simple', COALESCE(NEW.chunk_text, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- トリガー作成（documents）
DROP TRIGGER IF EXISTS tsvector_update_trigger ON documents;
CREATE TRIGGER tsvector_update_trigger
    BEFORE INSERT OR UPDATE OF full_text
    ON documents
    FOR EACH ROW
    EXECUTE FUNCTION documents_tsvector_update_trigger();

-- トリガー作成（document_chunks）
DROP TRIGGER IF EXISTS tsvector_update_trigger ON document_chunks;
CREATE TRIGGER tsvector_update_trigger
    BEFORE INSERT OR UPDATE OF chunk_text
    ON document_chunks
    FOR EACH ROW
    EXECUTE FUNCTION document_chunks_tsvector_update_trigger();

-- GINインデックス作成（高速全文検索のため）
CREATE INDEX IF NOT EXISTS idx_documents_full_text_tsv ON documents USING GIN(full_text_tsv);
CREATE INDEX IF NOT EXISTS idx_document_chunks_chunk_text_tsv ON document_chunks USING GIN(chunk_text_tsv);

-- 既存データの tsvector を更新
UPDATE documents SET full_text_tsv = to_tsvector('simple', COALESCE(full_text, '')) WHERE full_text_tsv IS NULL;
UPDATE document_chunks SET chunk_text_tsv = to_tsvector('simple', COALESCE(chunk_text, '')) WHERE chunk_text_tsv IS NULL;

-- ハイブリッド検索関数（ベクトル検索 + 全文検索）
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
        1 - (dc.embedding <=> query_embedding) AS similarity,
        ts_rank(dc.chunk_text_tsv, plainto_tsquery('simple', query_text)) AS fulltext_rank,
        -- ハイブリッドスコア: ベクトル検索（70%） + 全文検索（30%）
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
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

-- キーワード検索専用関数（完全一致重視）
CREATE OR REPLACE FUNCTION keyword_search_chunks(
    query_text TEXT,
    match_count INT DEFAULT 50,
    -- メタデータフィルタ
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
        ts_rank(dc.chunk_text_tsv, plainto_tsquery('simple', query_text)) AS fulltext_rank,
        d.file_name,
        d.doc_type,
        d.document_date
    FROM document_chunks dc
    JOIN documents d ON dc.document_id = d.id
    WHERE
        d.processing_status = 'completed'
        AND dc.chunk_text_tsv @@ plainto_tsquery('simple', query_text)
        -- メタデータフィルタリング
        AND (filter_year IS NULL OR d.year = filter_year)
        AND (filter_month IS NULL OR d.month = filter_month)
        AND (filter_doc_type IS NULL OR d.doc_type = filter_doc_type)
    ORDER BY fulltext_rank DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

COMMIT;
