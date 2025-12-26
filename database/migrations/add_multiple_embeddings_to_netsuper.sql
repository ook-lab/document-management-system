-- ====================================================================
-- Rawdata_NETSUPER_items に複数のembeddingカラムを追加
-- ====================================================================
-- 目的: ハイブリッド検索のため、3種類のembeddingを個別に保存
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-26
-- ====================================================================

BEGIN;

-- general_name用embedding（重め）
ALTER TABLE "Rawdata_NETSUPER_items"
  ADD COLUMN IF NOT EXISTS general_name_embedding vector(1536);

-- small_category用embedding（重め）
ALTER TABLE "Rawdata_NETSUPER_items"
  ADD COLUMN IF NOT EXISTS small_category_embedding vector(1536);

-- keywords用embedding（軽め）
ALTER TABLE "Rawdata_NETSUPER_items"
  ADD COLUMN IF NOT EXISTS keywords_embedding vector(1536);

-- インデックス作成（ベクトル検索の高速化）
CREATE INDEX IF NOT EXISTS idx_netsuper_general_name_embedding
  ON "Rawdata_NETSUPER_items"
  USING ivfflat (general_name_embedding vector_cosine_ops)
  WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_netsuper_small_category_embedding
  ON "Rawdata_NETSUPER_items"
  USING ivfflat (small_category_embedding vector_cosine_ops)
  WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_netsuper_keywords_embedding
  ON "Rawdata_NETSUPER_items"
  USING ivfflat (keywords_embedding vector_cosine_ops)
  WITH (lists = 100);

-- SQL検索用のインデックス（文字列検索の高速化）
-- LIKE検索用のインデックス
CREATE INDEX IF NOT EXISTS idx_netsuper_product_name_text
  ON "Rawdata_NETSUPER_items"(product_name);

CREATE INDEX IF NOT EXISTS idx_netsuper_general_name_text
  ON "Rawdata_NETSUPER_items"(general_name);

-- トライグラムインデックス（部分一致検索の高速化）
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_netsuper_product_name_trgm
  ON "Rawdata_NETSUPER_items"
  USING gin (product_name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_netsuper_general_name_trgm
  ON "Rawdata_NETSUPER_items"
  USING gin (general_name gin_trgm_ops);

-- カラムコメント
COMMENT ON COLUMN "Rawdata_NETSUPER_items".general_name_embedding IS
  'general_name（一般名）のembedding - 検索時に重めのウェイト';

COMMENT ON COLUMN "Rawdata_NETSUPER_items".small_category_embedding IS
  'small_category（小分類）のembedding - 検索時に重めのウェイト';

COMMENT ON COLUMN "Rawdata_NETSUPER_items".keywords_embedding IS
  'keywords（キーワード）のembedding - 検索時に軽めのウェイト';

-- 統計情報
DO $$
BEGIN
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '✅ 複数embeddingカラムを追加しました';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '';
    RAISE NOTICE '追加されたカラム:';
    RAISE NOTICE '  1. general_name_embedding (vector 1536) - 重め';
    RAISE NOTICE '  2. small_category_embedding (vector 1536) - 重め';
    RAISE NOTICE '  3. keywords_embedding (vector 1536) - 軽め';
    RAISE NOTICE '';
    RAISE NOTICE 'インデックス:';
    RAISE NOTICE '  - IVFFlat インデックス（ベクトル検索用） × 3';
    RAISE NOTICE '  - B-tree インデックス（LIKE検索用） × 2';
    RAISE NOTICE '  - GIN トライグラム インデックス（部分一致検索用） × 2';
    RAISE NOTICE '';
    RAISE NOTICE 'ハイブリッド検索の構成:';
    RAISE NOTICE '  ✅ ベクトル検索（3種類、重み付き）';
    RAISE NOTICE '  ✅ SQL文字列検索（LIKE、fulltext）';
    RAISE NOTICE '  ✅ 統合スコアリングで最終結果';
    RAISE NOTICE '';
    RAISE NOTICE '次のステップ:';
    RAISE NOTICE '  1. 各embeddingを生成するコードの実装';
    RAISE NOTICE '  2. ハイブリッド検索関数の実装';
    RAISE NOTICE '====================================================================';
END $$;

COMMIT;
