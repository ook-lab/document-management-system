-- 【実行場所】: Supabase SQL Editor
-- 【対象】: チャンク分割対応への移行
-- 【目的】: 1文書複数embeddingによる検索精度向上

-- チャンク分割により、長いPDFの後半部分も確実に検索できるようになります

BEGIN;

-- document_chunks テーブル作成
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    -- チャンク情報
    chunk_index INTEGER NOT NULL,  -- 0から始まる連番
    chunk_text TEXT NOT NULL,      -- チャンクのテキスト
    chunk_size INTEGER NOT NULL,   -- 文字数

    -- ベクトル検索 (1536次元: OpenAI Embedding)
    embedding vector(1536) NOT NULL,

    -- メタデータ
    page_numbers INTEGER[],        -- このチャンクが含むページ番号（PDFの場合）
    section_title TEXT,            -- セクション見出し（該当する場合）

    -- タイムスタンプ
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- 複合ユニーク制約（同一文書内でchunk_indexは一意）
    UNIQUE(document_id, chunk_index)
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding ON document_chunks USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_document_chunks_chunk_index ON document_chunks(chunk_index);

-- updated_at 自動更新トリガー
DROP TRIGGER IF EXISTS trigger_set_updated_at_chunks ON document_chunks;
CREATE TRIGGER trigger_set_updated_at_chunks
  BEFORE UPDATE ON document_chunks
  FOR EACH ROW
  EXECUTE PROCEDURE refresh_updated_at_column();

-- チャンク検索関数（ベクトル検索）
CREATE OR REPLACE FUNCTION match_document_chunks(
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.0,
    match_count INT DEFAULT 50
)
RETURNS TABLE (
    chunk_id UUID,
    document_id UUID,
    chunk_index INTEGER,
    chunk_text TEXT,
    similarity FLOAT,
    -- 親ドキュメント情報も結合して返す
    file_name VARCHAR,
    doc_type VARCHAR,
    document_date DATE,
    metadata JSONB,
    summary TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id AS chunk_id,
        dc.document_id,
        dc.chunk_index,
        dc.chunk_text,
        1 - (dc.embedding <=> query_embedding) AS similarity,
        d.file_name,
        d.doc_type,
        d.document_date,
        d.metadata,
        d.summary
    FROM document_chunks dc
    JOIN documents d ON dc.document_id = d.id
    WHERE
        d.processing_status = 'completed'
        AND (1 - (dc.embedding <=> query_embedding)) > match_threshold
    ORDER BY similarity DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

-- documentsテーブルにchunk統計カラムを追加
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS chunk_count INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS chunking_strategy VARCHAR(50) DEFAULT 'none';

-- 既存のembeddingカラムを削除する前のバックアップコメント
COMMENT ON COLUMN documents.embedding IS 'DEPRECATED: チャンク分割移行後は document_chunks.embedding を使用してください。この列は互換性のために残されていますが、新規データでは使用されません。';

COMMIT;
