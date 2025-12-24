-- ====================================================================
-- Rawdataテーブル名変更スクリプト
-- ====================================================================
-- 目的: Rawdataテーブルを整理し、統一的な命名規則に変更
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-25
-- ====================================================================

BEGIN;

-- ====================================================================
-- テーブル名変更
-- ====================================================================
-- 注意: ALTER TABLE RENAME は外部キー、インデックス、トリガーを自動的に更新します

-- 1. ファイル・メール生データ
ALTER TABLE "10_rd_source_docs" RENAME TO "Rawdata_FILE_AND_MAIL";

-- 2. レシート店舗情報
ALTER TABLE "60_rd_receipts" RENAME TO "Rawdata_RECEIPT_shops";

-- 3. レシート商品明細
ALTER TABLE "60_rd_transactions" RENAME TO "Rawdata_RECEIPT_items";

-- 4. チラシ店舗情報
ALTER TABLE "70_rd_flyer_docs" RENAME TO "Rawdata_FLYER_shops";

-- 5. チラシ商品情報
ALTER TABLE "70_rd_flyer_items" RENAME TO "Rawdata_FLYER_items";

-- 6. ネットスーパー商品情報
ALTER TABLE "80_rd_products" RENAME TO "Rawdata_NETSUPER_items";

-- ====================================================================
-- 確認クエリ（コメントアウト - 実行後に手動で確認してください）
-- ====================================================================
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'public'
-- AND table_name LIKE 'Rawdata_%'
-- ORDER BY table_name;

COMMIT;

-- ====================================================================
-- 実行後の確認事項
-- ====================================================================
-- 1. すべてのテーブルが正常にRENAMEされたか確認
-- 2. 外部キー制約が正常に動作しているか確認
-- 3. アプリケーション側のコード修正を実施
-- 4. テストを実行して問題がないか確認
