-- ====================================================================
-- マスターテーブル整理ロールバックスクリプト
-- ====================================================================
-- 目的: テーブル名変更を元に戻す（問題が発生した場合）
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-25
-- ====================================================================

BEGIN;

-- ====================================================================
-- Step 1: テーブル名を元に戻す（MASTER_Categories グループ）
-- ====================================================================

ALTER TABLE "MASTER_Categories_expense" RENAME TO "MASTER_Categories_expense";
ALTER TABLE "MASTER_Categories_purpose" RENAME TO "MASTER_Categories_purpose";
ALTER TABLE "MASTER_Categories_product" RENAME TO "MASTER_Categories_product";

-- ====================================================================
-- Step 2: テーブル名を元に戻す（MASTER_Rules グループ）
-- ====================================================================

ALTER TABLE "MASTER_Rules_expense_mapping" RENAME TO "MASTER_Rules_expense_mapping";
ALTER TABLE "MASTER_Rules_transaction_dict" RENAME TO "MASTER_Rules_transaction_dict";

-- ====================================================================
-- Step 3: テーブル名を元に戻す（集計テーブル）
-- ====================================================================

ALTER TABLE "Aggregate_items_needs_review" RENAME TO "Aggregate_items_needs_review";

-- ====================================================================
-- Note: 削除したテーブルの復元
-- ====================================================================
-- 以下のテーブルは削除されているため、復元できません：
-- - 60_ms_categories
-- - 60_ms_situations
-- - 60_ms_product_dict
-- - 60_ms_ocr_aliases
--
-- これらのテーブルを復元する必要がある場合は、
-- バックアップから復元してください。

COMMIT;

-- ====================================================================
-- 確認クエリ
-- ====================================================================
-- SELECT table_name
-- FROM information_schema.tables
-- WHERE table_schema = 'public'
-- AND table_name LIKE '%ms_%'
-- ORDER BY table_name;
