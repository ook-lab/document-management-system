-- ====================================================================
-- レシートテーブル統合 Step 5: 旧テーブル削除
-- ====================================================================
-- 目的: 60_rd_standardized_itemsテーブルを削除（データは既にRawdata_RECEIPT_itemsに統合済み）
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-25
-- ====================================================================
-- ⚠️ 警告: このスクリプトは元に戻せません！
-- 実行前に必ずバックアップを取ってください。
-- ====================================================================

BEGIN;

-- ====================================================================
-- 1. データ確認（削除前の最終チェック）
-- ====================================================================
DO $$
DECLARE
    old_table_count INTEGER;
    new_table_count INTEGER;
BEGIN
    -- 60_rd_standardized_itemsのレコード数（存在すれば）
    SELECT COUNT(*) INTO old_table_count
    FROM "60_rd_standardized_items";

    -- Rawdata_RECEIPT_itemsの標準化済みレコード数
    SELECT COUNT(*) INTO new_table_count
    FROM "Rawdata_RECEIPT_items"
    WHERE std_amount IS NOT NULL;

    RAISE NOTICE '====================================================================';
    RAISE NOTICE '削除前の確認';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '60_rd_standardized_items: % 件', old_table_count;
    RAISE NOTICE 'Rawdata_RECEIPT_items (standardized): % 件', new_table_count;
    RAISE NOTICE '';

    IF old_table_count > new_table_count THEN
        RAISE WARNING 'データ損失の可能性があります！ 削除を中止してください。';
        RAISE EXCEPTION 'Data count mismatch detected';
    END IF;

    RAISE NOTICE '✅ データ確認OK。削除を続行します。';
END $$;

-- ====================================================================
-- 2. 旧テーブル削除
-- ====================================================================
DROP TABLE IF EXISTS "60_rd_standardized_items" CASCADE;

-- ====================================================================
-- 3. 完了メッセージ
-- ====================================================================
DO $$
BEGIN
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '削除完了';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '60_rd_standardized_items テーブルを削除しました';
    RAISE NOTICE '';
    RAISE NOTICE '✅ Step 5完了';
    RAISE NOTICE '✅ レシートテーブル統合が完了しました！';
    RAISE NOTICE '';
    RAISE NOTICE '📌 新しい構造:';
    RAISE NOTICE '   - Rawdata_RECEIPT_shops (親)';
    RAISE NOTICE '   - Rawdata_RECEIPT_items (子 + 標準化データ統合)';
END $$;

COMMIT;
