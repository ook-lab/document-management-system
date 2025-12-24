-- ====================================================================
-- フェーズ6: 家計簿3分割テーブル - クリーンアップ
-- ====================================================================
-- 目的: 旧テーブルをバックアップしてリネーム、最終的に削除
-- 実行場所: Supabase SQL Editor
-- 前提条件:
--   - フェーズ5までが完了していること
--   - 新テーブルで1週間〜1ヶ月程度の運用確認が完了していること
--   - Pythonコードの更新が完了していること
-- ====================================================================
-- ⚠️ 警告: このスクリプトは旧テーブルを削除します
--          実行前に必ずバックアップを取得してください
-- ====================================================================

BEGIN;

-- ====================================================================
-- ステップ1: 最終確認
-- ====================================================================

DO $$
DECLARE
    old_count INTEGER;
    new_count INTEGER;
    receipt_count INTEGER;
BEGIN
    -- 件数の最終確認
    SELECT COUNT(*) INTO old_count FROM "Rawdata_RECEIPT_items";
    SELECT COUNT(*) INTO new_count FROM "Rawdata_RECEIPT_items_new";
    SELECT COUNT(*) INTO receipt_count FROM "Rawdata_RECEIPT_shops";

    RAISE NOTICE '====================================================================';
    RAISE NOTICE 'クリーンアップ前の最終確認';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '旧テーブル (Rawdata_RECEIPT_items):       % 件', old_count;
    RAISE NOTICE '新テーブル (Rawdata_RECEIPT_items_new):   % 件', new_count;
    RAISE NOTICE '新テーブル (Rawdata_RECEIPT_shops):           % 件', receipt_count;
    RAISE NOTICE '';

    IF old_count != new_count THEN
        RAISE EXCEPTION 'データ件数が一致しません！クリーンアップを中止します';
    END IF;

    RAISE NOTICE '✅ 件数チェック: OK';
    RAISE NOTICE '';
END $$;

-- ====================================================================
-- ステップ2: 旧テーブルのバックアップリネーム
-- ====================================================================

-- 旧テーブルを _OLD_BACKUP サフィックスでリネーム
ALTER TABLE "Rawdata_RECEIPT_items" RENAME TO "Rawdata_RECEIPT_items_OLD_BACKUP";

-- インデックスもリネーム（PostgreSQLが自動で行うが、明示的に記録）
COMMENT ON TABLE "Rawdata_RECEIPT_items_OLD_BACKUP" IS 'バックアップテーブル - 削除予定';

DO $$
BEGIN
    RAISE NOTICE '✅ 旧テーブルをバックアップとしてリネームしました';
    RAISE NOTICE '   Rawdata_RECEIPT_items → Rawdata_RECEIPT_items_OLD_BACKUP';
    RAISE NOTICE '';
END $$;

-- ====================================================================
-- ステップ3: 新テーブルを正式名称にリネーム
-- ====================================================================

-- 新テーブルの _new サフィックスを削除
ALTER TABLE "Rawdata_RECEIPT_items_new" RENAME TO "Rawdata_RECEIPT_items";

-- 外部キー制約の更新（孫テーブルの参照を新テーブルに変更）
-- 注意: 既に外部キー制約が設定されているため、この操作は不要
--      60_rd_standardized_items.transaction_id は既に Rawdata_RECEIPT_items_new を参照

DO $$
BEGIN
    RAISE NOTICE '✅ 新テーブルを正式名称にリネームしました';
    RAISE NOTICE '   Rawdata_RECEIPT_items_new → Rawdata_RECEIPT_items';
    RAISE NOTICE '';
END $$;

-- ====================================================================
-- ステップ4: インデックス名の調整（必要に応じて）
-- ====================================================================

-- リネーム後のインデックス名を確認（必要に応じて手動でリネーム）
-- 例: idx_60_rd_trans_new_receipt → idx_Rawdata_RECEIPT_items_receipt

-- 既存のインデックスをDROP + CREATE（名前を統一するため）
DROP INDEX IF EXISTS idx_60_rd_trans_new_receipt CASCADE;
CREATE INDEX IF NOT EXISTS idx_Rawdata_RECEIPT_items_receipt
    ON "Rawdata_RECEIPT_items"(receipt_id);

DROP INDEX IF EXISTS idx_60_rd_trans_new_line CASCADE;
CREATE INDEX IF NOT EXISTS idx_Rawdata_RECEIPT_items_line
    ON "Rawdata_RECEIPT_items"(receipt_id, line_number);

DROP INDEX IF EXISTS idx_60_rd_trans_new_type CASCADE;
CREATE INDEX IF NOT EXISTS idx_Rawdata_RECEIPT_items_type
    ON "Rawdata_RECEIPT_items"(line_type);

DROP INDEX IF EXISTS idx_60_rd_trans_new_low_confidence CASCADE;
CREATE INDEX IF NOT EXISTS idx_Rawdata_RECEIPT_items_low_confidence
    ON "Rawdata_RECEIPT_items"(ocr_confidence) WHERE ocr_confidence < 0.8;

DROP INDEX IF EXISTS idx_60_rd_trans_new_created CASCADE;
CREATE INDEX IF NOT EXISTS idx_Rawdata_RECEIPT_items_created
    ON "Rawdata_RECEIPT_items"(created_at DESC);

DO $$
BEGIN
    RAISE NOTICE '✅ インデックス名を調整しました';
    RAISE NOTICE '';
END $$;

-- ====================================================================
-- ステップ5: RLSポリシーの更新
-- ====================================================================

-- 旧ポリシーをDROP
DROP POLICY IF EXISTS "Allow authenticated users full access to transactions_new" ON "Rawdata_RECEIPT_items";
DROP POLICY IF EXISTS "Allow service role full access to transactions_new" ON "Rawdata_RECEIPT_items";

-- 新ポリシーを作成
CREATE POLICY "Allow authenticated users full access to transactions"
    ON "Rawdata_RECEIPT_items"
    FOR ALL
    TO authenticated
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Allow service role full access to transactions"
    ON "Rawdata_RECEIPT_items"
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

DO $$
BEGIN
    RAISE NOTICE '✅ RLSポリシーを更新しました';
    RAISE NOTICE '';
END $$;

-- ====================================================================
-- ステップ6: 動作確認期間の案内
-- ====================================================================

DO $$
BEGIN
    RAISE NOTICE '====================================================================';
    RAISE NOTICE 'クリーンアップ（ステップ6-1）完了';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '';
    RAISE NOTICE '✅ 旧テーブルをバックアップとして保存しました';
    RAISE NOTICE '✅ 新テーブルを正式名称にリネームしました';
    RAISE NOTICE '';
    RAISE NOTICE '【重要】';
    RAISE NOTICE '1. 今後1週間〜1ヶ月程度、新テーブルで運用してください';
    RAISE NOTICE '2. 問題がないことを確認してから、バックアップテーブルを削除してください';
    RAISE NOTICE '3. バックアップテーブル削除手順:';
    RAISE NOTICE '     DROP TABLE "Rawdata_RECEIPT_items_OLD_BACKUP" CASCADE;';
    RAISE NOTICE '';
END $$;

COMMIT;

-- ====================================================================
-- 動作確認クエリ（実行後に確認）
-- ====================================================================

-- 新テーブルの確認
SELECT
    table_name,
    table_type
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('Rawdata_RECEIPT_shops', 'Rawdata_RECEIPT_items', '60_rd_standardized_items', 'Rawdata_RECEIPT_items_OLD_BACKUP')
ORDER BY table_name;

-- サンプルデータ確認
SELECT * FROM "Rawdata_RECEIPT_shops" ORDER BY transaction_date DESC LIMIT 3;
SELECT * FROM "Rawdata_RECEIPT_items" ORDER BY created_at DESC LIMIT 5;
SELECT * FROM "60_rd_standardized_items" ORDER BY created_at DESC LIMIT 5;

-- ====================================================================
-- 【運用確認後】バックアップテーブルの削除
-- ====================================================================
-- ⚠️ 以下のコマンドは、運用確認が完了してから実行してください

-- バックアップテーブルの削除（コメントアウト状態）
-- DROP TABLE "Rawdata_RECEIPT_items_OLD_BACKUP" CASCADE;

-- 削除確認用のクエリ
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'public' AND table_name LIKE '%OLD_BACKUP%';
