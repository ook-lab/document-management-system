-- 小チャンクテーブル作成
-- ドキュメントを300文字程度の小チャンクに分割して保存
-- 各チャンクに対してembeddingを生成し、ベクトル検索を実現

BEGIN;

-- small_chunksテーブル作成
CREATE TABLE IF NOT EXISTS small_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    token_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT unique_chunk_per_document UNIQUE (document_id, chunk_index)
);

-- ベクトル検索用インデックス（IVFFlat方式）
-- cosine類似度で検索を高速化
CREATE INDEX IF NOT EXISTS small_chunks_embedding_idx
ON small_chunks USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- ドキュメントID検索用インデックス
-- 特定のドキュメントの全チャンクを取得する際に使用
CREATE INDEX IF NOT EXISTS small_chunks_document_id_idx ON small_chunks(document_id);

-- チャンクインデックス検索用インデックス
-- ドキュメント内での順序を保証
CREATE INDEX IF NOT EXISTS small_chunks_chunk_index_idx ON small_chunks(document_id, chunk_index);

-- コメント追加
COMMENT ON TABLE small_chunks IS '小チャンクテーブル：ドキュメントを300文字程度に分割して保存';
COMMENT ON COLUMN small_chunks.id IS 'チャンクID（UUID）';
COMMENT ON COLUMN small_chunks.document_id IS 'ドキュメントID（documents.id参照）';
COMMENT ON COLUMN small_chunks.chunk_index IS 'ドキュメント内でのチャンク位置（0始まり）';
COMMENT ON COLUMN small_chunks.content IS 'チャンクのテキスト内容';
COMMENT ON COLUMN small_chunks.embedding IS 'チャンクのembeddingベクトル（1536次元）';
COMMENT ON COLUMN small_chunks.token_count IS 'チャンクのトークン数';
COMMENT ON COLUMN small_chunks.created_at IS '作成日時';
COMMENT ON COLUMN small_chunks.updated_at IS '更新日時';

COMMIT;
