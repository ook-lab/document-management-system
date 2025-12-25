-- ====================================================================
-- product_name_normalizedカラムを削除
-- ====================================================================
-- 目的: 商品名の構造をシンプル化
--       - product_name: サイト表記（そのまま）
--       - general_name: 一般名詞（分析用）
--
-- 削除理由:
--   - product_name_normalized は単なる空白正規化で有用性が低い
--   - 検索は search_vector (全文検索) と embedding (ベクトル検索) で対応
--   - general_name で一般名詞化した方が分析に有用
--
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-26
-- ====================================================================

BEGIN;

-- ====================================================================
-- Step 1: Rawdata_NETSUPER_items から product_name_normalized を削除
-- ====================================================================

-- バックアップ用のコメント（念のため）
-- SELECT product_name, product_name_normalized, general_name
-- FROM "Rawdata_NETSUPER_items"
-- WHERE product_name_normalized IS NOT NULL
-- LIMIT 10;

ALTER TABLE "Rawdata_NETSUPER_items"
  DROP COLUMN IF EXISTS product_name_normalized;

COMMENT ON COLUMN "Rawdata_NETSUPER_items".product_name IS
  'サイト表記の商品名（例：「明治おいしい牛乳 1000ml」）';
COMMENT ON COLUMN "Rawdata_NETSUPER_items".general_name IS
  '一般名詞（例：「牛乳」）- 分析・集計用';

-- ====================================================================
-- Step 2: Rawdata_FLYER_items から product_name_normalized を削除
-- ====================================================================

ALTER TABLE "Rawdata_FLYER_items"
  DROP COLUMN IF EXISTS product_name_normalized;

COMMENT ON COLUMN "Rawdata_FLYER_items".product_name IS
  'チラシ記載の商品名（例：「国産豚肉 特売」）';

-- ====================================================================
-- Step 3: Rawdata_FLYER_shops から不要なカラムを削除（存在する場合）
-- ====================================================================

-- Rawdata_FLYER_shops は商品名を持たないので確認のみ
-- （このテーブルはチラシ情報のみを保持）

COMMIT;

-- ====================================================================
-- 確認クエリ
-- ====================================================================

-- カラムが削除されたことを確認
-- SELECT column_name, data_type
-- FROM information_schema.columns
-- WHERE table_name IN ('Rawdata_NETSUPER_items', 'Rawdata_FLYER_items')
-- AND column_name LIKE '%product_name%'
-- ORDER BY table_name, ordinal_position;

-- general_nameの状況を確認
-- SELECT
--   COUNT(*) as total_products,
--   COUNT(general_name) as has_general_name,
--   ROUND(100.0 * COUNT(general_name) / COUNT(*), 2) as coverage_percent
-- FROM "Rawdata_NETSUPER_items";
