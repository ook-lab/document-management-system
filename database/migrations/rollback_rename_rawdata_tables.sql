-- ====================================================================
-- Rawdataテーブル名変更ロールバックスクリプト
-- ====================================================================
-- 目的: テーブル名変更を元に戻す（問題が発生した場合）
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-25
-- ====================================================================

BEGIN;

-- ====================================================================
-- テーブル名を元に戻す
-- ====================================================================

-- 1. ファイル・メール生データ
ALTER TABLE "Rawdata_FILE_AND_MAIL" RENAME TO "10_rd_source_docs";

-- 2. レシート店舗情報
ALTER TABLE "Rawdata_RECEIPT_shops" RENAME TO "60_rd_receipts";

-- 3. レシート商品明細
ALTER TABLE "Rawdata_RECEIPT_items" RENAME TO "60_rd_transactions";

-- 4. チラシ店舗情報
ALTER TABLE "Rawdata_FLYER_shops" RENAME TO "70_rd_flyer_docs";

-- 5. チラシ商品情報
ALTER TABLE "Rawdata_FLYER_items" RENAME TO "70_rd_flyer_items";

-- 6. ネットスーパー商品情報
ALTER TABLE "Rawdata_NETSUPER_items" RENAME TO "80_rd_products";

COMMIT;

-- ====================================================================
-- 確認クエリ
-- ====================================================================
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'public'
-- AND table_name LIKE '%_rd_%'
-- ORDER BY table_name;
