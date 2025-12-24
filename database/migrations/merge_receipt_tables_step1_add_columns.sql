-- ====================================================================
-- レシートテーブル統合 Step 1: カラム追加
-- ====================================================================
-- 目的: Rawdata_RECEIPT_itemsに60_rd_standardized_itemsのカラムを追加
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-25
-- ====================================================================

BEGIN;

-- ====================================================================
-- Rawdata_RECEIPT_itemsにカラムを追加
-- ====================================================================

-- 正規化・分類関連
ALTER TABLE "Rawdata_RECEIPT_items" ADD COLUMN IF NOT EXISTS official_name TEXT;
ALTER TABLE "Rawdata_RECEIPT_items" ADD COLUMN IF NOT EXISTS general_name TEXT;
ALTER TABLE "Rawdata_RECEIPT_items" ADD COLUMN IF NOT EXISTS category_id UUID REFERENCES "MASTER_Categories_expense"(id);
ALTER TABLE "Rawdata_RECEIPT_items" ADD COLUMN IF NOT EXISTS situation_id UUID REFERENCES "MASTER_Categories_purpose"(id);

-- カテゴリ分類（自由記入）
ALTER TABLE "Rawdata_RECEIPT_items" ADD COLUMN IF NOT EXISTS major_category TEXT;
ALTER TABLE "Rawdata_RECEIPT_items" ADD COLUMN IF NOT EXISTS middle_category TEXT;
ALTER TABLE "Rawdata_RECEIPT_items" ADD COLUMN IF NOT EXISTS minor_category TEXT;

-- メタ情報
ALTER TABLE "Rawdata_RECEIPT_items" ADD COLUMN IF NOT EXISTS purpose TEXT;
ALTER TABLE "Rawdata_RECEIPT_items" ADD COLUMN IF NOT EXISTS person TEXT;

-- 計算結果
ALTER TABLE "Rawdata_RECEIPT_items" ADD COLUMN IF NOT EXISTS std_unit_price INTEGER;
ALTER TABLE "Rawdata_RECEIPT_items" ADD COLUMN IF NOT EXISTS std_amount INTEGER;
ALTER TABLE "Rawdata_RECEIPT_items" ADD COLUMN IF NOT EXISTS calc_logic_log TEXT;

-- レビュー・メモ
ALTER TABLE "Rawdata_RECEIPT_items" ADD COLUMN IF NOT EXISTS needs_review BOOLEAN DEFAULT FALSE;
ALTER TABLE "Rawdata_RECEIPT_items" ADD COLUMN IF NOT EXISTS notes TEXT;

-- インデックス追加
CREATE INDEX IF NOT EXISTS idx_Rawdata_RECEIPT_items_category_id ON "Rawdata_RECEIPT_items"(category_id);
CREATE INDEX IF NOT EXISTS idx_Rawdata_RECEIPT_items_situation_id ON "Rawdata_RECEIPT_items"(situation_id);
CREATE INDEX IF NOT EXISTS idx_Rawdata_RECEIPT_items_needs_review ON "Rawdata_RECEIPT_items"(needs_review) WHERE needs_review = TRUE;

COMMIT;

-- ====================================================================
-- 実行後の確認クエリ
-- ====================================================================

-- カラム追加確認
-- SELECT column_name, data_type
-- FROM information_schema.columns
-- WHERE table_name = 'Rawdata_RECEIPT_items'
-- AND column_name IN ('official_name', 'general_name', 'category_id', 'situation_id', 'needs_review')
-- ORDER BY column_name;
