-- ====================================================================
-- マスターテーブル整理・統合スクリプト
-- ====================================================================
-- 目的: マスターテーブルを整理し、統一的な命名規則に変更
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-25
-- ====================================================================

BEGIN;

-- ====================================================================
-- Step 1: データ統合
-- ====================================================================

-- 1-1. situations → purposes に統合
-- 重複しない新しいシチュエーションのみを追加
INSERT INTO "MASTER_Categories_purpose" (name, description, display_order, created_at, updated_at)
SELECT
    s.name,
    s.description,
    100 as display_order,  -- デフォルト値
    s.created_at,
    NOW() as updated_at
FROM "60_ms_situations" s
WHERE NOT EXISTS (
    SELECT 1 FROM "MASTER_Categories_purpose" p WHERE p.name = s.name
)
ON CONFLICT (name) DO NOTHING;

-- 1-2. categories → expense_categories に統合
-- is_expense = true のカテゴリのみを統合（費目として妥当なもの）
-- 重複しない新しいカテゴリのみを追加
INSERT INTO "MASTER_Categories_expense" (name, description, display_order, created_at, updated_at)
SELECT
    c.name,
    NULL as description,  -- categoriesにはdescriptionがない
    100 as display_order,  -- デフォルト値
    c.created_at,
    NOW() as updated_at
FROM "60_ms_categories" c
WHERE c.is_expense = true
AND NOT EXISTS (
    SELECT 1 FROM "MASTER_Categories_expense" e WHERE e.name = c.name
)
ON CONFLICT (name) DO NOTHING;

-- ====================================================================
-- Step 2: テーブルリネーム（MASTER_Categories グループ）
-- ====================================================================

ALTER TABLE "MASTER_Categories_expense" RENAME TO "MASTER_Categories_expense";
ALTER TABLE "MASTER_Categories_purpose" RENAME TO "MASTER_Categories_purpose";
ALTER TABLE "MASTER_Categories_product" RENAME TO "MASTER_Categories_product";

-- ====================================================================
-- Step 3: テーブルリネーム（MASTER_Rules グループ）
-- ====================================================================

ALTER TABLE "MASTER_Rules_expense_mapping" RENAME TO "MASTER_Rules_expense_mapping";
ALTER TABLE "MASTER_Rules_transaction_dict" RENAME TO "MASTER_Rules_transaction_dict";

-- ====================================================================
-- Step 4: テーブルリネーム（集計テーブル）
-- ====================================================================

ALTER TABLE "Aggregate_items_needs_review" RENAME TO "Aggregate_items_needs_review";

-- ====================================================================
-- Step 5: 不要なテーブルを削除
-- ====================================================================

DROP TABLE IF EXISTS "60_ms_categories" CASCADE;
DROP TABLE IF EXISTS "60_ms_situations" CASCADE;
DROP TABLE IF EXISTS "60_ms_product_dict" CASCADE;
DROP TABLE IF EXISTS "60_ms_ocr_aliases" CASCADE;

-- ====================================================================
-- Step 6: 外部キー制約の確認と修正
-- ====================================================================

-- MASTER_Rules_expense_mapping の外部キー制約を更新
-- （purpose_id が MASTER_Categories_purpose を参照するように）
-- Note: テーブルリネームでは外部キー制約は自動更新されるため、通常は不要
-- ただし、念のため確認用のクエリをコメントとして残す

-- SELECT
--     tc.constraint_name,
--     tc.table_name,
--     kcu.column_name,
--     ccu.table_name AS foreign_table_name,
--     ccu.column_name AS foreign_column_name
-- FROM information_schema.table_constraints AS tc
-- JOIN information_schema.key_column_usage AS kcu
--   ON tc.constraint_name = kcu.constraint_name
-- JOIN information_schema.constraint_column_usage AS ccu
--   ON ccu.constraint_name = tc.constraint_name
-- WHERE tc.constraint_type = 'FOREIGN KEY'
-- AND tc.table_name LIKE 'MASTER_%';

COMMIT;

-- ====================================================================
-- 実行後の確認クエリ
-- ====================================================================

-- マスターテーブル一覧を確認
-- SELECT table_name
-- FROM information_schema.tables
-- WHERE table_schema = 'public'
-- AND (table_name LIKE 'MASTER_%' OR table_name LIKE 'Aggregate_%')
-- ORDER BY table_name;

-- レコード数を確認
-- SELECT 'MASTER_Categories_expense' as table_name, COUNT(*) FROM "MASTER_Categories_expense"
-- UNION ALL
-- SELECT 'MASTER_Categories_purpose', COUNT(*) FROM "MASTER_Categories_purpose"
-- UNION ALL
-- SELECT 'MASTER_Categories_product', COUNT(*) FROM "MASTER_Categories_product"
-- UNION ALL
-- SELECT 'MASTER_Rules_expense_mapping', COUNT(*) FROM "MASTER_Rules_expense_mapping"
-- UNION ALL
-- SELECT 'MASTER_Rules_transaction_dict', COUNT(*) FROM "MASTER_Rules_transaction_dict"
-- ORDER BY table_name;

-- ====================================================================
-- 実行後の確認事項
-- ====================================================================
-- 1. すべてのテーブルが正常にRENAMEされたか確認
-- 2. データが統合されたか確認（purposes, expense_categories）
-- 3. 不要なテーブルが削除されたか確認
-- 4. アプリケーション側のコード修正を実施
-- 5. テストを実行して問題がないか確認
