-- ============================================
-- 80_rd_productsテーブルにembeddingカラムを追加
-- OpenAI text-embedding-3-small (1536次元) を使用
-- ============================================

-- embeddingカラムを追加（1536次元ベクトル）
ALTER TABLE "80_rd_products"
ADD COLUMN IF NOT EXISTS embedding vector(1536);

-- ベクトル検索用のIVFFlatインデックスを作成
-- cosine距離を使用（商品名の類似度検索に適している）
CREATE INDEX IF NOT EXISTS idx_80_rd_products_embedding
ON "80_rd_products"
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- 確認
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = '80_rd_products'
AND column_name = 'embedding';
