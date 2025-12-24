-- ====================================================================
-- 60番台テーブルの最終整理スクリプト
-- ====================================================================
-- 目的: Aggregateビューのリネームと不要バックアップの削除
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-25
-- ====================================================================

BEGIN;

-- ====================================================================
-- Step 1: Aggregateビュー/テーブルのリネーム
-- ====================================================================

ALTER TABLE "60_ag_items_needs_review" RENAME TO "AGGREGATE_items_needs_review";
ALTER TABLE "60_ag_receipt_summary" RENAME TO "AGGREGATE_receipt_summary";
ALTER TABLE "60_ag_unverified_receipts" RENAME TO "AGGREGATE_unverified_receipts";

-- ====================================================================
-- Step 2: 古いバックアップテーブルの削除
-- ====================================================================

DROP TABLE IF EXISTS "60_rd_transactions_OLD_BACKUP" CASCADE;

COMMIT;

-- ====================================================================
-- 実行後の確認クエリ
-- ====================================================================

-- Aggregateテーブル確認
-- SELECT table_name
-- FROM information_schema.tables
-- WHERE table_schema = 'public'
-- AND table_name LIKE 'AGGREGATE_%'
-- ORDER BY table_name;

-- 60番台の残存テーブル確認
-- SELECT table_name
-- FROM information_schema.tables
-- WHERE table_schema = 'public'
-- AND table_name LIKE '60_%'
-- ORDER BY table_name;
