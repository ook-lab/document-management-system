-- ====================================================================
-- Rawdata_RECEIPT_itemsテーブルにgeneral_nameカラムを追加
-- ====================================================================
-- 目的: 商品名を一般名詞化してカテゴリ判定に活用
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-26
-- ====================================================================

BEGIN;

-- general_nameカラムを追加
ALTER TABLE "Rawdata_RECEIPT_items" ADD COLUMN IF NOT EXISTS general_name TEXT;

-- インデックス追加（検索高速化）
CREATE INDEX IF NOT EXISTS idx_Rawdata_RECEIPT_items_general_name
ON "Rawdata_RECEIPT_items"(general_name);

-- コメント追加
COMMENT ON COLUMN "Rawdata_RECEIPT_items".general_name IS '一般名詞（カテゴリ判定用、例：「明治おいしい牛乳」→「牛乳」）';

COMMIT;

-- ====================================================================
-- 確認クエリ
-- ====================================================================
-- SELECT column_name, data_type, column_default
-- FROM information_schema.columns
-- WHERE table_name = 'Rawdata_RECEIPT_items'
-- AND column_name = 'general_name';
