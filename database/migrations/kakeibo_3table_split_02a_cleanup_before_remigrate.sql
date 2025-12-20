-- ====================================================================
-- フェーズ2A: 家計簿3分割テーブル - 再移行前のクリーンアップ
-- ====================================================================
-- 目的: 新3テーブルの既存データを削除（再移行の準備）
-- 実行場所: Supabase SQL Editor
-- 前提条件: 60_rd_transactions_OLD_BACKUPにデータが保存されていること
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
    SELECT COUNT(*) INTO backup_count FROM "60_rd_transactions_OLD_BACKUP";
    SELECT COUNT(*) INTO receipt_count FROM "60_rd_receipts";
    SELECT COUNT(*) INTO trans_count FROM "60_rd_transactions";
    SELECT COUNT(*) INTO std_count FROM "60_rd_standardized_items";

    RAISE NOTICE '====================================================================';
    RAISE NOTICE 'クリーンアップ前のデータ件数';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE 'OLD_BACKUP: % 件', backup_count;
    RAISE NOTICE '60_rd_receipts: % 件', receipt_count;
    RAISE NOTICE '60_rd_transactions: % 件', trans_count;
    RAISE NOTICE '60_rd_standardized_items: % 件', std_count;
    RAISE NOTICE '';

    IF backup_count = 0 THEN
        RAISE EXCEPTION 'OLD_BACKUPテーブルにデータがありません！クリーンアップを中止します';
    END IF;

    RAISE NOTICE '⚠️  新テーブルのデータを全て削除します...';
END $$;

-- ====================================================================
-- ステップ1: 全テーブルのデータを一括削除（TRUNCATE CASCADE使用）
-- ====================================================================

-- 親テーブルからTRUNCATEすると、CASCADE で子・孫も削除される
TRUNCATE TABLE "60_rd_receipts" CASCADE;

DO $$
BEGIN
    RAISE NOTICE '✅ 60_rd_receipts (CASCADE) を削除しました';
    RAISE NOTICE '   → 60_rd_transactions も削除されました';
    RAISE NOTICE '   → 60_rd_standardized_items も削除されました';
END $$;

-- ====================================================================
-- ステップ2: 99_lg_image_proc_logのreceipt_idをクリア
-- ====================================================================

DO $$
DECLARE
    cleared_count INTEGER;
BEGIN
    UPDATE "99_lg_image_proc_log"
    SET receipt_id = NULL
    WHERE receipt_id IS NOT NULL;

    GET DIAGNOSTICS cleared_count = ROW_COUNT;
    RAISE NOTICE '✅ 99_lg_image_proc_log の receipt_id をクリアしました (% 件)', cleared_count;
END $$;

-- ====================================================================
-- 最終確認
-- ====================================================================

DO $$
DECLARE
    receipt_count INTEGER;
    trans_count INTEGER;
    std_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO receipt_count FROM "60_rd_receipts";
    SELECT COUNT(*) INTO trans_count FROM "60_rd_transactions";
    SELECT COUNT(*) INTO std_count FROM "60_rd_standardized_items";

    RAISE NOTICE '';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE 'クリーンアップ完了';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '60_rd_receipts: % 件 (期待: 0件)', receipt_count;
    RAISE NOTICE '60_rd_transactions: % 件 (期待: 0件)', trans_count;
    RAISE NOTICE '60_rd_standardized_items: % 件 (期待: 0件)', std_count;
    RAISE NOTICE '';

    IF receipt_count = 0 AND trans_count = 0 AND std_count = 0 THEN
        RAISE NOTICE '✅ クリーンアップ成功';
        RAISE NOTICE '次のステップ: kakeibo_3table_split_02b_remigrate_from_backup.sql を実行してください';
    ELSE
        RAISE WARNING '⚠️  クリーンアップ失敗 - データが残っています';
    END IF;
END $$;

COMMIT;
