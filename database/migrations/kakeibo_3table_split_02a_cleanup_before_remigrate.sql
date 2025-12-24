-- ====================================================================
-- フェーズ2A: 家計簿3分割テーブル - 再移行前のクリーンアップ
-- ====================================================================
-- 目的: 新3テーブルの既存データを削除（再移行の準備）
-- 実行場所: Supabase SQL Editor
-- 前提条件: Rawdata_RECEIPT_items_OLD_BACKUPにデータが保存されていること
-- ====================================================================

BEGIN;

-- ====================================================================
-- 事前確認: 現在のデータ件数
-- ====================================================================

DO $$
DECLARE
    backup_count INTEGER;
    receipt_count INTEGER;
    trans_count INTEGER;
    std_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO backup_count FROM "Rawdata_RECEIPT_items_OLD_BACKUP";
    SELECT COUNT(*) INTO receipt_count FROM "Rawdata_RECEIPT_shops";
    SELECT COUNT(*) INTO trans_count FROM "Rawdata_RECEIPT_items";
    SELECT COUNT(*) INTO std_count FROM "60_rd_standardized_items";

    RAISE NOTICE '====================================================================';
    RAISE NOTICE 'クリーンアップ前のデータ件数';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE 'OLD_BACKUP: % 件', backup_count;
    RAISE NOTICE 'Rawdata_RECEIPT_shops: % 件', receipt_count;
    RAISE NOTICE 'Rawdata_RECEIPT_items: % 件', trans_count;
    RAISE NOTICE '60_rd_standardized_items: % 件', std_count;
    RAISE NOTICE '';

    IF backup_count = 0 THEN
        RAISE EXCEPTION 'OLD_BACKUPテーブルにデータがありません！クリーンアップを中止します';
    END IF;

    RAISE NOTICE '⚠️  新テーブルのデータを全て削除します...';
END $$;

-- ====================================================================
-- ステップ1: 99_lg_image_proc_logのreceipt_idをクリア（先に実行）
-- ====================================================================
-- 重要: TRUNCATE CASCADEで99_lg_image_proc_logが削除されないように先にクリア

DO $$
DECLARE
    cleared_count INTEGER;
BEGIN
    RAISE NOTICE 'ステップ1: 99_lg_image_proc_log の receipt_id をクリア...';

    UPDATE "99_lg_image_proc_log"
    SET receipt_id = NULL
    WHERE receipt_id IS NOT NULL;

    GET DIAGNOSTICS cleared_count = ROW_COUNT;
    RAISE NOTICE '  - 99_lg_image_proc_log: % 件のreceipt_idをクリア', cleared_count;
END $$;

-- ====================================================================
-- ステップ2: 全テーブルのデータを削除（DELETE使用）
-- ====================================================================
-- TRUNCATE CASCADEは99_lg_image_proc_logも削除してしまうため、DELETEを使用

DO $$
DECLARE
    items_deleted INTEGER;
    trans_deleted INTEGER;
    receipts_deleted INTEGER;
BEGIN
    RAISE NOTICE 'ステップ2: データ削除...';

    -- 孫テーブル削除
    DELETE FROM "60_rd_standardized_items";
    GET DIAGNOSTICS items_deleted = ROW_COUNT;
    RAISE NOTICE '  - 60_rd_standardized_items: % 件削除', items_deleted;

    -- 子テーブル削除
    DELETE FROM "Rawdata_RECEIPT_items";
    GET DIAGNOSTICS trans_deleted = ROW_COUNT;
    RAISE NOTICE '  - Rawdata_RECEIPT_items: % 件削除', trans_deleted;

    -- 親テーブル削除
    DELETE FROM "Rawdata_RECEIPT_shops";
    GET DIAGNOSTICS receipts_deleted = ROW_COUNT;
    RAISE NOTICE '  - Rawdata_RECEIPT_shops: % 件削除', receipts_deleted;
END $$;

-- ====================================================================
-- 最終確認
-- ====================================================================

DO $$
DECLARE
    receipt_count INTEGER;
    trans_count INTEGER;
    std_count INTEGER;
    log_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO receipt_count FROM "Rawdata_RECEIPT_shops";
    SELECT COUNT(*) INTO trans_count FROM "Rawdata_RECEIPT_items";
    SELECT COUNT(*) INTO std_count FROM "60_rd_standardized_items";
    SELECT COUNT(*) INTO log_count FROM "99_lg_image_proc_log";

    RAISE NOTICE '';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE 'クリーンアップ完了';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE 'Rawdata_RECEIPT_shops: % 件 (期待: 0件)', receipt_count;
    RAISE NOTICE 'Rawdata_RECEIPT_items: % 件 (期待: 0件)', trans_count;
    RAISE NOTICE '60_rd_standardized_items: % 件 (期待: 0件)', std_count;
    RAISE NOTICE '99_lg_image_proc_log: % 件 (保護されました)', log_count;
    RAISE NOTICE '';

    IF receipt_count = 0 AND trans_count = 0 AND std_count = 0 THEN
        RAISE NOTICE '✅ クリーンアップ成功';
        RAISE NOTICE '⚠️  99_lg_image_proc_logは保護されています（receipt_idはNULL）';
        RAISE NOTICE '次のステップ: kakeibo_3table_split_02b_remigrate_from_backup.sql を実行してください';
    ELSE
        RAISE WARNING '⚠️  クリーンアップ失敗 - データが残っています';
    END IF;
END $$;

COMMIT;
