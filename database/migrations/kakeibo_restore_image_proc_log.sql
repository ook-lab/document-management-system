-- ====================================================================
-- 99_lg_image_proc_log の復元スクリプト
-- ====================================================================
-- 目的: 60_rd_receiptsから99_lg_image_proc_logを復元
-- 実行場所: Supabase SQL Editor
-- 前提条件: 60_rd_receiptsにデータが存在すること
-- ====================================================================

BEGIN;

DO $$
BEGIN
    RAISE NOTICE '==========================================';
    RAISE NOTICE '99_lg_image_proc_log 復元開始';
    RAISE NOTICE '==========================================';
END $$;

-- ====================================================================
-- ステップ1: 60_rd_receiptsから99_lg_image_proc_logを復元
-- ====================================================================

DO $$
DECLARE
    inserted_count INTEGER;
BEGIN
    RAISE NOTICE 'ステップ1: 60_rd_receiptsから処理ログを復元...';

    INSERT INTO "99_lg_image_proc_log" (
        file_name,
        drive_file_id,
        status,
        ocr_model,
        receipt_id,
        error_message
    )
    SELECT
        -- image_pathからファイル名を抽出（例: 99_Archive/2025-11/556648403.jpeg → 556648403.jpeg）
        SUBSTRING(image_path FROM '[^/]+$') AS file_name,
        drive_file_id,
        'success' AS status,
        ocr_model,
        id AS receipt_id,
        NULL AS error_message
    FROM "60_rd_receipts"
    WHERE NOT EXISTS (
        -- 重複防止：既にログが存在する場合はスキップ
        SELECT 1 FROM "99_lg_image_proc_log"
        WHERE drive_file_id = "60_rd_receipts".drive_file_id
    )
    ORDER BY created_at;

    GET DIAGNOSTICS inserted_count = ROW_COUNT;
    RAISE NOTICE '  - 99_lg_image_proc_log: % 件復元', inserted_count;
END $$;

-- ====================================================================
-- ステップ2: 最終確認
-- ====================================================================

DO $$
DECLARE
    log_count INTEGER;
    receipt_count INTEGER;
BEGIN
    RAISE NOTICE '==========================================';
    RAISE NOTICE '復元完了 - 最終確認';
    RAISE NOTICE '==========================================';

    SELECT COUNT(*) INTO log_count FROM "99_lg_image_proc_log";
    SELECT COUNT(*) INTO receipt_count FROM "60_rd_receipts";

    RAISE NOTICE '最終件数:';
    RAISE NOTICE '  - 99_lg_image_proc_log: % 件', log_count;
    RAISE NOTICE '  - 60_rd_receipts: % 件', receipt_count;
    RAISE NOTICE '';

    IF log_count = receipt_count THEN
        RAISE NOTICE '✅ 復元成功！処理ログとレシートが一致しています。';
    ELSE
        RAISE WARNING '⚠️ 件数が一致しません（log: %, receipt: %）', log_count, receipt_count;
    END IF;

    RAISE NOTICE '==========================================';
END $$;

COMMIT;

-- 確認用クエリ
DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '次のステップ:';
    RAISE NOTICE 'Review UIにアクセスして、レシート一覧が表示されることを確認してください';
    RAISE NOTICE '';
END $$;
