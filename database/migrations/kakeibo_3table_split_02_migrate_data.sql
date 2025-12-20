-- ====================================================================
-- フェーズ2: 家計簿3分割テーブル - データ移行
-- ====================================================================
-- 目的: 既存の 60_rd_transactions のデータを新3テーブルに変換・移行
-- 実行場所: Supabase SQL Editor
-- 前提条件: フェーズ1のスキーマ作成が完了していること
-- ====================================================================

BEGIN;

-- ====================================================================
-- 事前確認: 既存データ件数の記録
-- ====================================================================

DO $$
DECLARE
    old_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO old_count FROM "60_rd_transactions";
    RAISE NOTICE '既存データ件数: % 件', old_count;
    RAISE NOTICE '移行を開始します...';
END $$;

-- ====================================================================
-- ステップ1: 親テーブルへのデータ移行
-- ====================================================================
-- レシート単位にグループ化して親テーブルに挿入
-- グループ化キー: drive_file_id + transaction_date + shop_name

INSERT INTO "60_rd_receipts" (
    transaction_date,
    shop_name,
    total_amount_check,
    subtotal_amount,
    image_path,
    drive_file_id,
    source_folder,
    ocr_model,
    person,
    workspace,
    is_verified,
    notes,
    created_at,
    updated_at
)
SELECT
    transaction_date,
    shop_name,
    SUM(total_amount) AS total_amount_check,   -- 同一レシートの合計
    NULL AS subtotal_amount,                    -- 既存データにはないのでNULL
    MAX(image_path) AS image_path,              -- 同一レシート内で同じはず
    drive_file_id,
    MAX(source_folder) AS source_folder,        -- 同一レシート内で同じはず
    MAX(ocr_model) AS ocr_model,                -- 同一レシート内で同じはず
    MAX(person) AS person,                      -- 同一レシート内で同じはず
    'household' AS workspace,                   -- デフォルト値
    BOOL_AND(is_verified) AS is_verified,       -- 全明細が確認済みの場合のみTRUE
    MAX(notes) AS notes,                        -- レシート全体のメモ
    MIN(created_at) AS created_at,              -- 最初の明細の作成日時
    MAX(updated_at) AS updated_at               -- 最後の更新日時
FROM "60_rd_transactions"
GROUP BY drive_file_id, transaction_date, shop_name
ORDER BY transaction_date DESC, shop_name;

-- 確認
DO $$
DECLARE
    receipt_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO receipt_count FROM "60_rd_receipts";
    RAISE NOTICE '✅ ステップ1完了: % 件のレシートを作成', receipt_count;
END $$;

-- ====================================================================
-- ステップ2: 子テーブルへのデータ移行
-- ====================================================================
-- 旧トランザクションデータを子テーブルに挿入
-- 行番号はROW_NUMBER()で自動採番

INSERT INTO "60_rd_transactions_new" (
    receipt_id,
    line_number,
    line_type,
    ocr_raw_text,
    ocr_confidence,
    product_name,
    item_name,
    unit_price,
    quantity,
    marks_text,
    discount_text,
    created_at,
    updated_at
)
SELECT
    r.id AS receipt_id,
    ROW_NUMBER() OVER (PARTITION BY r.id ORDER BY t.created_at, t.id) AS line_number,
    'ITEM' AS line_type,                        -- 既存データはすべて商品行
    t.product_name AS ocr_raw_text,             -- OCR原文がないのでproduct_nameをコピー
    NULL AS ocr_confidence,                     -- 既存データにはないのでNULL
    t.product_name,
    t.item_name,
    t.unit_price,
    t.quantity,
    NULL AS marks_text,                         -- 既存データにはないのでNULL
    NULL AS discount_text,                      -- 既存データにはないのでNULL
    t.created_at,
    t.updated_at
FROM "60_rd_transactions" t
INNER JOIN "60_rd_receipts" r
    ON r.drive_file_id = t.drive_file_id
    AND r.transaction_date = t.transaction_date
    AND r.shop_name = t.shop_name
ORDER BY r.id, line_number;

-- 確認
DO $$
DECLARE
    trans_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO trans_count FROM "60_rd_transactions_new";
    RAISE NOTICE '✅ ステップ2完了: % 件の明細行を作成', trans_count;
END $$;

-- ====================================================================
-- ステップ3: 孫テーブルへのデータ移行
-- ====================================================================
-- 正規化された家計簿データを孫テーブルに挿入

INSERT INTO "60_rd_standardized_items" (
    transaction_id,
    receipt_id,
    official_name,
    category_id,
    situation_id,
    major_category,
    minor_category,
    purpose,
    person,
    tax_rate,
    std_unit_price,
    std_amount,
    tax_amount,
    calc_logic_log,
    needs_review,
    notes,
    created_at,
    updated_at
)
SELECT
    tr.id AS transaction_id,
    tr.receipt_id,
    t.official_name,
    t.category_id,
    t.situation_id,
    t.major_category,
    t.minor_category,
    t.purpose,
    t.person,
    COALESCE(t.tax_rate, 10) AS tax_rate,       -- デフォルト10%
    NULL AS std_unit_price,                      -- 既存データにはないのでNULL
    t.total_amount AS std_amount,                -- 最終支払金額
    t.tax_amount,
    'Migrated from old schema' AS calc_logic_log, -- マイグレーション由来であることを記録
    COALESCE(t.needs_tax_review, FALSE) AS needs_review,
    t.notes,
    t.created_at,
    t.updated_at
FROM "60_rd_transactions" t
INNER JOIN "60_rd_receipts" r
    ON r.drive_file_id = t.drive_file_id
    AND r.transaction_date = t.transaction_date
    AND r.shop_name = t.shop_name
INNER JOIN "60_rd_transactions_new" tr
    ON tr.receipt_id = r.id
    AND tr.product_name = t.product_name
    AND tr.created_at = t.created_at
ORDER BY tr.receipt_id, tr.line_number;

-- 確認
DO $$
DECLARE
    std_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO std_count FROM "60_rd_standardized_items";
    RAISE NOTICE '✅ ステップ3完了: % 件の正規化アイテムを作成', std_count;
END $$;

-- ====================================================================
-- データ件数の最終確認
-- ====================================================================

DO $$
DECLARE
    old_count INTEGER;
    receipt_count INTEGER;
    trans_count INTEGER;
    std_count INTEGER;
    unique_receipts INTEGER;
BEGIN
    -- 旧テーブルの件数
    SELECT COUNT(*) INTO old_count FROM "60_rd_transactions";

    -- 新テーブルの件数
    SELECT COUNT(*) INTO receipt_count FROM "60_rd_receipts";
    SELECT COUNT(*) INTO trans_count FROM "60_rd_transactions_new";
    SELECT COUNT(*) INTO std_count FROM "60_rd_standardized_items";

    -- 期待されるレシート数（drive_file_idのユニーク数）
    SELECT COUNT(DISTINCT drive_file_id) INTO unique_receipts FROM "60_rd_transactions";

    RAISE NOTICE '';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE 'データ移行完了';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '旧テーブル (60_rd_transactions):           % 件', old_count;
    RAISE NOTICE '新テーブル (60_rd_receipts):               % 件 (期待: % 件)', receipt_count, unique_receipts;
    RAISE NOTICE '新テーブル (60_rd_transactions_new):       % 件 (期待: % 件)', trans_count, old_count;
    RAISE NOTICE '新テーブル (60_rd_standardized_items):     % 件 (期待: % 件)', std_count, old_count;
    RAISE NOTICE '';

    -- 整合性チェック
    IF trans_count = old_count AND std_count = old_count THEN
        RAISE NOTICE '✅ 件数チェック: OK';
    ELSE
        RAISE WARNING '⚠️  件数チェック: NG - データ件数が一致しません';
    END IF;

    RAISE NOTICE '';
    RAISE NOTICE '次のステップ: フェーズ3（データ検証）を実行してください';
END $$;

COMMIT;

-- ====================================================================
-- 簡易確認クエリ（実行後に確認）
-- ====================================================================

-- サンプルデータの確認（最新3件のレシート）
SELECT
    r.id AS receipt_id,
    r.transaction_date,
    r.shop_name,
    r.total_amount_check AS receipt_total,
    COUNT(t.id) AS item_count,
    SUM(s.std_amount) AS calculated_total,
    r.is_verified
FROM "60_rd_receipts" r
LEFT JOIN "60_rd_transactions_new" t ON t.receipt_id = r.id
LEFT JOIN "60_rd_standardized_items" s ON s.receipt_id = r.id
GROUP BY r.id, r.transaction_date, r.shop_name, r.total_amount_check, r.is_verified
ORDER BY r.transaction_date DESC, r.shop_name
LIMIT 3;
