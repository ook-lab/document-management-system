-- ============================================
-- Rawdata_NETSUPER_itemsテーブルにembeddingカラムを追加
-- OpenAI text-embedding-3-small (1536次元) を使用
-- ============================================

-- embeddingカラムを追加（1536次元ベクトル）
ALTER TABLE "Rawdata_NETSUPER_items"
ADD COLUMN IF NOT EXISTS embedding vector(1536);

-- ベクトル検索用のIVFFlatインデックスを作成
-- cosine距離を使用（商品名の類似度検索に適している）
CREATE INDEX IF NOT EXISTS idx_Rawdata_NETSUPER_items_embedding
ON "Rawdata_NETSUPER_items"
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- 確認
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'Rawdata_NETSUPER_items'
AND column_name = 'embedding';
