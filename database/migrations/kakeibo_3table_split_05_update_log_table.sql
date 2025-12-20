-- ====================================================================
-- フェーズ5: 家計簿3分割テーブル - ログテーブル更新
-- ====================================================================
-- 目的: 処理ログテーブルに receipt_id カラムを追加
-- 実行場所: Supabase SQL Editor
-- 前提条件: フェーズ4のビュー更新が完了していること
-- ====================================================================

BEGIN;

-- ====================================================================
-- 1. 処理ログテーブルに receipt_id カラムを追加
-- ====================================================================

ALTER TABLE "99_lg_image_proc_log"
ADD COLUMN IF NOT EXISTS receipt_id UUID REFERENCES "60_rd_receipts"(id) ON DELETE SET NULL;

-- コメント
COMMENT ON COLUMN "99_lg_image_proc_log".receipt_id IS '処理対象のレシートID（新3層構造対応）';

-- ====================================================================
-- 2. インデックス作成
-- ====================================================================

CREATE INDEX IF NOT EXISTS idx_image_proc_log_receipt
    ON "99_lg_image_proc_log"(receipt_id);

-- ====================================================================
-- 3. 既存データへの receipt_id 紐付け（バックフィル）
-- ====================================================================
-- 既存の処理ログに対して、drive_file_id を使って receipt_id を設定

UPDATE "99_lg_image_proc_log" log
SET receipt_id = r.id
FROM "60_rd_receipts" r
WHERE log.drive_file_id = r.drive_file_id
  AND log.receipt_id IS NULL;

-- 確認
DO $$
DECLARE
    total_logs INTEGER;
    linked_logs INTEGER;
    unlinked_logs INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_logs FROM "99_lg_image_proc_log";
    SELECT COUNT(*) INTO linked_logs FROM "99_lg_image_proc_log" WHERE receipt_id IS NOT NULL;
    SELECT COUNT(*) INTO unlinked_logs FROM "99_lg_image_proc_log" WHERE receipt_id IS NULL;

    RAISE NOTICE '====================================================================';
    RAISE NOTICE '処理ログテーブル更新完了';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '総ログ件数:         % 件', total_logs;
    RAISE NOTICE 'レシート紐付け済み: % 件', linked_logs;
    RAISE NOTICE 'レシート紐付けなし: % 件', unlinked_logs;
    RAISE NOTICE '';

    IF unlinked_logs > 0 THEN
        RAISE WARNING '⚠️  一部のログがレシートに紐付けられていません';
        RAISE NOTICE 'これは、drive_file_id が存在しないログ、またはレシート作成前のログです';
    ELSE
        RAISE NOTICE '✅ すべてのログがレシートに紐付けられました';
    END IF;
END $$;

-- ====================================================================
-- 4. 新規ビュー: 処理ログとレシートの結合ビュー
-- ====================================================================

CREATE OR REPLACE VIEW "99_ag_processing_log_with_receipt" AS
SELECT
    log.id AS log_id,
    log.file_name,
    log.drive_file_id,
    log.status,
    log.error_message,
    log.ocr_model,
    log.processed_at,
    log.retry_count,
    log.receipt_id,
    r.transaction_date,
    r.shop_name,
    r.total_amount_check,
    r.is_verified,
    COUNT(t.id) AS item_count
FROM "99_lg_image_proc_log" log
LEFT JOIN "60_rd_receipts" r ON r.id = log.receipt_id
LEFT JOIN "60_rd_transactions_new" t ON t.receipt_id = r.id
GROUP BY log.id, log.file_name, log.drive_file_id, log.status, log.error_message, log.ocr_model, log.processed_at, log.retry_count, log.receipt_id, r.transaction_date, r.shop_name, r.total_amount_check, r.is_verified
ORDER BY log.processed_at DESC;

-- コメント
COMMENT ON VIEW "99_ag_processing_log_with_receipt" IS '処理ログとレシート情報の結合ビュー - レビューUI用';

-- ====================================================================
-- 完了メッセージ
-- ====================================================================

DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '✅ フェーズ5完了: ログテーブル更新完了';
    RAISE NOTICE '';
    RAISE NOTICE '次のステップ: フェーズ6（クリーンアップ）またはPythonコード更新に進んでください';
    RAISE NOTICE '';
END $$;

COMMIT;

-- ====================================================================
-- 動作確認クエリ（実行後に確認）
-- ====================================================================

-- 処理ログとレシートの結合状況を確認
SELECT
    log.file_name,
    log.status,
    r.transaction_date,
    r.shop_name,
    r.total_amount_check,
    COUNT(t.id) AS item_count
FROM "99_lg_image_proc_log" log
LEFT JOIN "60_rd_receipts" r ON r.id = log.receipt_id
LEFT JOIN "60_rd_transactions_new" t ON t.receipt_id = r.id
GROUP BY log.id, log.file_name, log.status, r.transaction_date, r.shop_name, r.total_amount_check
ORDER BY log.processed_at DESC
LIMIT 10;

-- ビューの確認
SELECT * FROM "99_ag_processing_log_with_receipt" LIMIT 10;
