-- ====================================================================
-- フェーズ4: 家計簿3分割テーブル - ビュー更新
-- ====================================================================
-- 目的: 集計ビューを新テーブル構造に対応させる
-- 実行場所: Supabase SQL Editor
-- 前提条件: フェーズ3のデータ検証が合格していること
-- ====================================================================

BEGIN;

-- ====================================================================
-- 1. 日次集計ビューの更新
-- ====================================================================
-- 新テーブル構造に対応させる
-- 親（Rawdata_RECEIPT_shops）と孫（60_rd_standardized_items）を結合

CREATE OR REPLACE VIEW "Aggregate_daily_summary" AS
SELECT
    r.transaction_date,
    sit.name AS situation,
    cat.name AS category,
    COUNT(*) AS item_count,
    SUM(s.std_amount) AS total
FROM "Rawdata_RECEIPT_shops" r
INNER JOIN "60_rd_standardized_items" s ON s.receipt_id = r.id
LEFT JOIN "MASTER_Categories_purpose" sit ON s.situation_id = sit.id
LEFT JOIN "MASTER_Categories_expense" cat ON s.category_id = cat.id
WHERE cat.is_expense = TRUE  -- 集計対象のみ
GROUP BY r.transaction_date, sit.name, cat.name
ORDER BY r.transaction_date DESC;

-- コメント
COMMENT ON VIEW "Aggregate_daily_summary" IS '日次集計ビュー - 新3層テーブル構造対応';

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
INNER JOIN "60_rd_standardized_items" s ON s.receipt_id = r.id
LEFT JOIN "MASTER_Categories_purpose" sit ON s.situation_id = sit.id
LEFT JOIN "MASTER_Categories_expense" cat ON s.category_id = cat.id
WHERE cat.is_expense = TRUE  -- 集計対象のみ
GROUP BY month, sit.name, cat.name
ORDER BY month DESC;

-- コメント
COMMENT ON VIEW "Aggregate_monthly_summary" IS '月次集計ビュー - 新3層テーブル構造対応';

-- ====================================================================
-- 3. 新規ビュー: レシート一覧ビュー（追加）
-- ====================================================================
-- レシート単位での確認を容易にするためのビュー

CREATE OR REPLACE VIEW "Aggregate_receipt_summary" AS
SELECT
    r.id AS receipt_id,
    r.transaction_date,
    r.shop_name,
    r.total_amount_check,
    COUNT(t.id) AS item_count,
    SUM(s.std_amount) AS calculated_total,
    (r.total_amount_check - COALESCE(SUM(s.std_amount), 0)) AS amount_diff,
    r.is_verified,
    r.drive_file_id,
    r.ocr_model,
    r.person,
    r.created_at
FROM "Rawdata_RECEIPT_shops" r
LEFT JOIN "Rawdata_RECEIPT_items_new" t ON t.receipt_id = r.id
LEFT JOIN "60_rd_standardized_items" s ON s.receipt_id = r.id
GROUP BY r.id, r.transaction_date, r.shop_name, r.total_amount_check, r.is_verified, r.drive_file_id, r.ocr_model, r.person, r.created_at
ORDER BY r.transaction_date DESC, r.created_at DESC;

-- コメント
COMMENT ON VIEW "Aggregate_receipt_summary" IS 'レシート一覧サマリービュー - レビューUI用';

-- ====================================================================
-- 4. 新規ビュー: 未確認レシート一覧（追加）
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
LEFT JOIN "Rawdata_RECEIPT_items_new" t ON t.receipt_id = r.id
WHERE r.is_verified = FALSE
GROUP BY r.id, r.transaction_date, r.shop_name, r.total_amount_check, r.drive_file_id, r.created_at
ORDER BY r.created_at DESC;

-- コメント
COMMENT ON VIEW "Aggregate_unverified_receipts" IS '未確認レシート一覧 - レビュー対象抽出用';

-- ====================================================================
-- 5. 新規ビュー: 要確認アイテム一覧（追加）
-- ====================================================================

CREATE OR REPLACE VIEW "Aggregate_items_needs_review" AS
SELECT
    r.transaction_date,
    r.shop_name,
    t.product_name,
    s.std_amount,
    s.tax_rate,
    s.needs_review,
    t.ocr_confidence,
    r.id AS receipt_id,
    t.id AS transaction_id,
    s.id AS standardized_id
FROM "Rawdata_RECEIPT_shops" r
INNER JOIN "Rawdata_RECEIPT_items_new" t ON t.receipt_id = r.id
INNER JOIN "60_rd_standardized_items" s ON s.transaction_id = t.id
WHERE s.needs_review = TRUE
   OR t.ocr_confidence < 0.8
ORDER BY r.transaction_date DESC, t.line_number;

-- コメント
COMMENT ON VIEW "Aggregate_items_needs_review" IS '要確認アイテム一覧 - OCR信頼度が低い、または税額計算要確認';

-- ====================================================================
-- 動作確認
-- ====================================================================

DO $$
DECLARE
    daily_count INTEGER;
    monthly_count INTEGER;
    receipt_count INTEGER;
    unverified_count INTEGER;
BEGIN
    -- 各ビューのレコード数を確認
    SELECT COUNT(*) INTO daily_count FROM "Aggregate_daily_summary";
    SELECT COUNT(*) INTO monthly_count FROM "Aggregate_monthly_summary";
    SELECT COUNT(*) INTO receipt_count FROM "Aggregate_receipt_summary";
    SELECT COUNT(*) INTO unverified_count FROM "Aggregate_unverified_receipts";

    RAISE NOTICE '====================================================================';
    RAISE NOTICE 'ビュー更新完了';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '日次集計ビュー (60_ag_daily_summary):          % 件', daily_count;
    RAISE NOTICE '月次集計ビュー (60_ag_monthly_summary):        % 件', monthly_count;
    RAISE NOTICE 'レシート一覧ビュー (60_ag_receipt_summary):    % 件', receipt_count;
    RAISE NOTICE '未確認レシート一覧 (60_ag_unverified_receipts): % 件', unverified_count;
    RAISE NOTICE '';
    RAISE NOTICE '✅ フェーズ4完了';
    RAISE NOTICE '';
    RAISE NOTICE '次のステップ: フェーズ5（Pythonコード更新）に進んでください';
END $$;

COMMIT;

-- ====================================================================
-- 動作確認クエリ（実行後に確認）
-- ====================================================================

-- 日次集計ビューの確認
SELECT * FROM "Aggregate_daily_summary" LIMIT 10;

-- 月次集計ビューの確認
SELECT * FROM "Aggregate_monthly_summary" LIMIT 10;

-- レシート一覧ビューの確認
SELECT * FROM "Aggregate_receipt_summary" LIMIT 10;

-- 未確認レシート一覧の確認
SELECT * FROM "Aggregate_unverified_receipts" LIMIT 10;

-- 要確認アイテム一覧の確認
SELECT * FROM "Aggregate_items_needs_review" LIMIT 10;
