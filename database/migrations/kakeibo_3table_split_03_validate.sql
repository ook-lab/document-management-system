-- ====================================================================
-- フェーズ3: 家計簿3分割テーブル - データ検証
-- ====================================================================
-- 目的: 移行されたデータが正しいことを確認
-- 実行場所: Supabase SQL Editor
-- 前提条件: フェーズ2のデータ移行が完了していること
-- ====================================================================

-- ====================================================================
-- 検証1: 件数チェック
-- ====================================================================

DO $$
DECLARE
    old_count INTEGER;
    receipt_count INTEGER;
    trans_count INTEGER;
    std_count INTEGER;
    expected_receipts INTEGER;
BEGIN
    -- 各テーブルの件数を取得
    SELECT COUNT(*) INTO old_count FROM "Rawdata_RECEIPT_items";
    SELECT COUNT(*) INTO receipt_count FROM "Rawdata_RECEIPT_shops";
    SELECT COUNT(*) INTO trans_count FROM "Rawdata_RECEIPT_items_new";
    SELECT COUNT(*) INTO std_count FROM "60_rd_standardized_items";
    SELECT COUNT(DISTINCT drive_file_id) INTO expected_receipts FROM "Rawdata_RECEIPT_items";

    RAISE NOTICE '====================================================================';
    RAISE NOTICE '検証1: 件数チェック';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '旧テーブル (Rawdata_RECEIPT_items):           % 件', old_count;
    RAISE NOTICE '新テーブル (Rawdata_RECEIPT_shops):               % 件 (期待: % 件)', receipt_count, expected_receipts;
    RAISE NOTICE '新テーブル (Rawdata_RECEIPT_items_new):       % 件 (期待: % 件)', trans_count, old_count;
    RAISE NOTICE '新テーブル (60_rd_standardized_items):     % 件 (期待: % 件)', std_count, old_count;
    RAISE NOTICE '';

    -- 判定
    IF trans_count = old_count AND std_count = old_count THEN
        RAISE NOTICE '✅ 件数チェック: 合格';
    ELSE
        RAISE WARNING '❌ 件数チェック: 不合格 - データ件数が一致しません';
    END IF;
    RAISE NOTICE '';
END $$;

-- ====================================================================
-- 検証2: 金額合計チェック
-- ====================================================================

DO $$
DECLARE
    old_total BIGINT;
    new_total BIGINT;
BEGIN
    -- 旧テーブルの合計金額
    SELECT COALESCE(SUM(total_amount), 0) INTO old_total FROM "Rawdata_RECEIPT_items";

    -- 新テーブル（孫）の合計金額
    SELECT COALESCE(SUM(std_amount), 0) INTO new_total FROM "60_rd_standardized_items";

    RAISE NOTICE '====================================================================';
    RAISE NOTICE '検証2: 金額合計チェック';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '旧テーブル合計金額:  ¥%', old_total;
    RAISE NOTICE '新テーブル合計金額:  ¥%', new_total;
    RAISE NOTICE '差分:                ¥%', (new_total - old_total);
    RAISE NOTICE '';

    -- 判定
    IF old_total = new_total THEN
        RAISE NOTICE '✅ 金額合計チェック: 合格';
    ELSE
        RAISE WARNING '❌ 金額合計チェック: 不合格 - 金額が一致しません';
    END IF;
    RAISE NOTICE '';
END $$;

-- ====================================================================
-- 検証3: 外部キー整合性チェック
-- ====================================================================

DO $$
DECLARE
    orphan_trans INTEGER;
    orphan_std INTEGER;
BEGIN
    -- 孤立した子レコード（親レシートが存在しない）
    SELECT COUNT(*) INTO orphan_trans
    FROM "Rawdata_RECEIPT_items_new" t
    LEFT JOIN "Rawdata_RECEIPT_shops" r ON t.receipt_id = r.id
    WHERE r.id IS NULL;

    -- 孤立した孫レコード（子トランザクションが存在しない）
    SELECT COUNT(*) INTO orphan_std
    FROM "60_rd_standardized_items" s
    LEFT JOIN "Rawdata_RECEIPT_items_new" t ON s.transaction_id = t.id
    WHERE t.id IS NULL;

    RAISE NOTICE '====================================================================';
    RAISE NOTICE '検証3: 外部キー整合性チェック';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '孤立した子レコード数 (Rawdata_RECEIPT_items_new):      % 件', orphan_trans;
    RAISE NOTICE '孤立した孫レコード数 (60_rd_standardized_items):    % 件', orphan_std;
    RAISE NOTICE '';

    -- 判定
    IF orphan_trans = 0 AND orphan_std = 0 THEN
        RAISE NOTICE '✅ 外部キー整合性チェック: 合格';
    ELSE
        RAISE WARNING '❌ 外部キー整合性チェック: 不合格 - 孤立レコードが存在します';
    END IF;
    RAISE NOTICE '';
END $$;

-- ====================================================================
-- 検証4: レシート単位での金額整合性チェック
-- ====================================================================

DO $$
DECLARE
    mismatch_count INTEGER;
BEGIN
    -- レシートの total_amount_check と、明細の合計が一致しないレシート数
    SELECT COUNT(*) INTO mismatch_count
    FROM (
        SELECT
            r.id,
            r.total_amount_check,
            COALESCE(SUM(s.std_amount), 0) AS calculated_total
        FROM "Rawdata_RECEIPT_shops" r
        LEFT JOIN "60_rd_standardized_items" s ON s.receipt_id = r.id
        GROUP BY r.id, r.total_amount_check
        HAVING r.total_amount_check != COALESCE(SUM(s.std_amount), 0)
    ) AS mismatches;

    RAISE NOTICE '====================================================================';
    RAISE NOTICE '検証4: レシート単位での金額整合性チェック';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '金額不一致のレシート数: % 件', mismatch_count;
    RAISE NOTICE '';

    -- 判定
    IF mismatch_count = 0 THEN
        RAISE NOTICE '✅ レシート金額整合性チェック: 合格';
    ELSE
        RAISE WARNING '❌ レシート金額整合性チェック: 不合格 - 金額不一致のレシートが存在します';
        RAISE NOTICE '不一致のレシートを確認してください（下記のクエリを実行）:';
        RAISE NOTICE 'SELECT * FROM validation_receipt_amount_mismatches;';
    END IF;
    RAISE NOTICE '';
END $$;

-- ====================================================================
-- 検証5: NULL値チェック（必須カラム）
-- ====================================================================

DO $$
DECLARE
    null_count INTEGER;
BEGIN
    -- 親テーブルの必須カラムにNULLがないか確認
    SELECT COUNT(*) INTO null_count
    FROM "Rawdata_RECEIPT_shops"
    WHERE transaction_date IS NULL
       OR shop_name IS NULL
       OR total_amount_check IS NULL;

    RAISE NOTICE '====================================================================';
    RAISE NOTICE '検証5: NULL値チェック（必須カラム）';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '親テーブル（Rawdata_RECEIPT_shops）のNULL件数: % 件', null_count;

    -- 子テーブルの必須カラムにNULLがないか確認
    SELECT COUNT(*) INTO null_count
    FROM "Rawdata_RECEIPT_items_new"
    WHERE receipt_id IS NULL
       OR line_number IS NULL
       OR product_name IS NULL;

    RAISE NOTICE '子テーブル（Rawdata_RECEIPT_items_new）のNULL件数: % 件', null_count;

    -- 孫テーブルの必須カラムにNULLがないか確認
    SELECT COUNT(*) INTO null_count
    FROM "60_rd_standardized_items"
    WHERE transaction_id IS NULL
       OR receipt_id IS NULL
       OR std_amount IS NULL;

    RAISE NOTICE '孫テーブル（60_rd_standardized_items）のNULL件数: % 件', null_count;
    RAISE NOTICE '';

    IF null_count = 0 THEN
        RAISE NOTICE '✅ NULL値チェック: 合格';
    ELSE
        RAISE WARNING '❌ NULL値チェック: 不合格 - 必須カラムにNULLが存在します';
    END IF;
    RAISE NOTICE '';
END $$;

-- ====================================================================
-- 検証結果サマリー
-- ====================================================================

DO $$
BEGIN
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '検証完了';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE 'すべての検証が合格した場合、次のステップ（フェーズ4）に進んでください';
    RAISE NOTICE '';
END $$;

-- ====================================================================
-- サンプルデータ確認クエリ（実行後に目視確認）
-- ====================================================================

-- 最新3件のレシートとその明細を確認
SELECT
    r.id AS receipt_id,
    r.transaction_date,
    r.shop_name,
    r.total_amount_check AS receipt_total,
    COUNT(t.id) AS item_count,
    SUM(s.std_amount) AS calculated_total,
    r.is_verified,
    r.drive_file_id
FROM "Rawdata_RECEIPT_shops" r
LEFT JOIN "Rawdata_RECEIPT_items_new" t ON t.receipt_id = r.id
LEFT JOIN "60_rd_standardized_items" s ON s.receipt_id = r.id
GROUP BY r.id, r.transaction_date, r.shop_name, r.total_amount_check, r.is_verified, r.drive_file_id
ORDER BY r.transaction_date DESC
LIMIT 10;

-- 詳細な明細確認（1件のレシートについて）
WITH sample_receipt AS (
    SELECT id FROM "Rawdata_RECEIPT_shops" ORDER BY transaction_date DESC LIMIT 1
)
SELECT
    t.line_number,
    t.product_name,
    t.quantity,
    t.unit_price,
    s.std_amount,
    s.tax_rate,
    s.tax_amount,
    t.ocr_raw_text,
    s.category_id,
    s.situation_id
FROM "Rawdata_RECEIPT_items_new" t
INNER JOIN "60_rd_standardized_items" s ON s.transaction_id = t.id
WHERE t.receipt_id = (SELECT id FROM sample_receipt)
ORDER BY t.line_number;

-- ====================================================================
-- 便利ビュー: 金額不一致レシート（検証4で使用）
-- ====================================================================

CREATE OR REPLACE VIEW validation_receipt_amount_mismatches AS
SELECT
    r.id AS receipt_id,
    r.transaction_date,
    r.shop_name,
    r.total_amount_check,
    COALESCE(SUM(s.std_amount), 0) AS calculated_total,
    (r.total_amount_check - COALESCE(SUM(s.std_amount), 0)) AS difference
FROM "Rawdata_RECEIPT_shops" r
LEFT JOIN "60_rd_standardized_items" s ON s.receipt_id = r.id
GROUP BY r.id, r.transaction_date, r.shop_name, r.total_amount_check
HAVING r.total_amount_check != COALESCE(SUM(s.std_amount), 0)
ORDER BY ABS(r.total_amount_check - COALESCE(SUM(s.std_amount), 0)) DESC;
