-- ====================================================================
-- レシートテーブル統合 Step 2: データマイグレーション
-- ====================================================================
-- 目的: 60_rd_standardized_itemsのデータをRawdata_RECEIPT_itemsにコピー
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-25
-- ====================================================================

BEGIN;

-- ====================================================================
-- データマイグレーション
-- ====================================================================

-- 60_rd_standardized_itemsのデータをRawdata_RECEIPT_itemsに統合
UPDATE "Rawdata_RECEIPT_items" r
SET
    official_name = s.official_name,
    general_name = s.general_name,
    category_id = s.category_id,
    situation_id = s.situation_id,
    major_category = s.major_category,
    middle_category = s.middle_category,
    minor_category = s.minor_category,
    purpose = s.purpose,
    person = s.person,
    std_unit_price = s.std_unit_price,
    std_amount = s.std_amount,
    calc_logic_log = s.calc_logic_log,
    needs_review = s.needs_review,
    notes = s.notes
FROM "60_rd_standardized_items" s
WHERE s.transaction_id = r.id;

COMMIT;

-- ====================================================================
-- 実行後の確認クエリ
-- ====================================================================

-- マイグレーション結果確認
-- SELECT
--     COUNT(*) as total_items,
--     COUNT(official_name) as with_official_name,
--     COUNT(category_id) as with_category,
--     COUNT(situation_id) as with_situation,
--     COUNT(CASE WHEN needs_review = TRUE THEN 1 END) as needs_review_count
-- FROM "Rawdata_RECEIPT_items";

-- サンプルデータ確認
-- SELECT
--     product_name,
--     official_name,
--     general_name,
--     category_id,
--     situation_id,
--     std_amount,
--     needs_review
-- FROM "Rawdata_RECEIPT_items"
-- WHERE official_name IS NOT NULL
-- ORDER BY created_at DESC
-- LIMIT 5;
