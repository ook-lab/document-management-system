-- ====================================================================
-- レシートテーブル統合 Step 3: ビュー更新
-- ====================================================================
-- 目的: 60_rd_standardized_itemsからRawdata_RECEIPT_itemsに切り替え
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-25
-- ====================================================================

BEGIN;

-- ====================================================================
-- 1. 日次集計ビューの更新
-- ====================================================================
CREATE OR REPLACE VIEW "Aggregate_daily_summary" AS
SELECT
    r.transaction_date,
    sit.name AS situation,
    cat.name AS category,
    COUNT(*) AS item_count,
    SUM(s.std_amount) AS total
FROM "Rawdata_RECEIPT_shops" r
INNER JOIN "Rawdata_RECEIPT_items" s ON s.receipt_id = r.id
LEFT JOIN "MASTER_Categories_purpose" sit ON s.situation_id = sit.id
LEFT JOIN "MASTER_Categories_expense" cat ON s.category_id = cat.id
WHERE s.std_amount IS NOT NULL  -- 標準化済みアイテムのみ
GROUP BY r.transaction_date, sit.name, cat.name
ORDER BY r.transaction_date DESC;

COMMENT ON VIEW "Aggregate_daily_summary" IS '日次集計ビュー - 統合テーブル対応';

-- ====================================================================
-- 2. 月次集計ビューの更新
-- ====================================================================
CREATE OR REPLACE VIEW "Aggregate_monthly_summary" AS
SELECT
    DATE_TRUNC('month', r.transaction_date) AS month,
    sit.name AS situation,
    cat.name AS category,
    COUNT(*) AS item_count,
    SUM(s.std_amount) AS total
FROM "Rawdata_RECEIPT_shops" r
INNER JOIN "Rawdata_RECEIPT_items" s ON s.receipt_id = r.id
LEFT JOIN "MASTER_Categories_purpose" sit ON s.situation_id = sit.id
LEFT JOIN "MASTER_Categories_expense" cat ON s.category_id = cat.id
WHERE s.std_amount IS NOT NULL  -- 標準化済みアイテムのみ
GROUP BY month, sit.name, cat.name
ORDER BY month DESC;

COMMENT ON VIEW "Aggregate_monthly_summary" IS '月次集計ビュー - 統合テーブル対応';

-- ====================================================================
-- 3. レシート一覧ビューの更新
-- ====================================================================
CREATE OR REPLACE VIEW "Aggregate_receipt_summary" AS
SELECT
    r.id AS receipt_id,
    r.transaction_date,
    r.shop_name,
    r.total_amount_check,
    COUNT(t.id) AS item_count,
    SUM(t.std_amount) AS calculated_total,
    (r.total_amount_check - COALESCE(SUM(t.std_amount), 0)) AS amount_diff,
    r.is_verified,
    r.drive_file_id,
    r.ocr_model,
    r.person,
    r.created_at
FROM "Rawdata_RECEIPT_shops" r
LEFT JOIN "Rawdata_RECEIPT_items" t ON t.receipt_id = r.id
GROUP BY r.id, r.transaction_date, r.shop_name, r.total_amount_check, r.is_verified, r.drive_file_id, r.ocr_model, r.person, r.created_at
ORDER BY r.transaction_date DESC, r.created_at DESC;

COMMENT ON VIEW "Aggregate_receipt_summary" IS 'レシート一覧サマリービュー - 統合テーブル対応';

-- ====================================================================
-- 4. 未確認レシート一覧の更新
-- ====================================================================
CREATE OR REPLACE VIEW "Aggregate_unverified_receipts" AS
SELECT
    r.id AS receipt_id,
    r.transaction_date,
    r.shop_name,
    r.total_amount_check,
    COUNT(t.id) AS item_count,
    r.drive_file_id,
    r.created_at
FROM "Rawdata_RECEIPT_shops" r
LEFT JOIN "Rawdata_RECEIPT_items" t ON t.receipt_id = r.id
WHERE r.is_verified = FALSE
GROUP BY r.id, r.transaction_date, r.shop_name, r.total_amount_check, r.drive_file_id, r.created_at
ORDER BY r.created_at DESC;

COMMENT ON VIEW "Aggregate_unverified_receipts" IS '未確認レシート一覧 - 統合テーブル対応';

-- ====================================================================
-- 5. 要確認アイテム一覧の更新
-- ====================================================================
CREATE OR REPLACE VIEW "Aggregate_items_needs_review" AS
SELECT
    r.transaction_date,
    r.shop_name,
    t.product_name,
    t.std_amount,
    t.tax_rate,
    t.needs_review,
    t.ocr_confidence,
    r.id AS receipt_id,
    t.id AS item_id
FROM "Rawdata_RECEIPT_shops" r
INNER JOIN "Rawdata_RECEIPT_items" t ON t.receipt_id = r.id
WHERE t.needs_review = TRUE
   OR t.ocr_confidence < 0.8
ORDER BY r.transaction_date DESC, t.line_number;

COMMENT ON VIEW "Aggregate_items_needs_review" IS '要確認アイテム一覧 - 統合テーブル対応';

-- ====================================================================
-- 動作確認
-- ====================================================================
DO $$
DECLARE
    daily_count INTEGER;
    monthly_count INTEGER;
    receipt_count INTEGER;
    unverified_count INTEGER;
    review_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO daily_count FROM "Aggregate_daily_summary";
    SELECT COUNT(*) INTO monthly_count FROM "Aggregate_monthly_summary";
    SELECT COUNT(*) INTO receipt_count FROM "Aggregate_receipt_summary";
    SELECT COUNT(*) INTO unverified_count FROM "Aggregate_unverified_receipts";
    SELECT COUNT(*) INTO review_count FROM "Aggregate_items_needs_review";

    RAISE NOTICE '====================================================================';
    RAISE NOTICE 'ビュー更新完了';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '日次集計ビュー:              % 件', daily_count;
    RAISE NOTICE '月次集計ビュー:              % 件', monthly_count;
    RAISE NOTICE 'レシート一覧ビュー:          % 件', receipt_count;
    RAISE NOTICE '未確認レシート一覧:          % 件', unverified_count;
    RAISE NOTICE '要確認アイテム一覧:          % 件', review_count;
    RAISE NOTICE '';
    RAISE NOTICE '✅ Step 3完了';
END $$;

COMMIT;
