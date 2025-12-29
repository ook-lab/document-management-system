-- ====================================================================
-- 旧embeddingカラムを削除（未使用カラムの削除）
-- ====================================================================
-- 目的: 未使用のembeddingカラムを削除して容量を削減
-- 削減効果: 約6 MB削減（1,018レコード × 6 KB）
-- 作成日: 2025-12-29
-- ====================================================================
-- 背景:
-- - 12/25: embedding カラムを作成（シンプルな検索用）
-- - 12/27: 3つの新カラム追加（リッチな重み付け検索用）
--   - general_name_embedding
--   - small_category_embedding
--   - keywords_embedding
-- - 現在: 旧embeddingカラムは使われていないため削除
-- ====================================================================

-- Step 1: インデックスを削除（存在する場合）
DROP INDEX IF EXISTS idx_Rawdata_NETSUPER_items_embedding;

-- Step 2: カラムを削除
ALTER TABLE "Rawdata_NETSUPER_items"
  DROP COLUMN IF EXISTS embedding;

-- 確認
DO $$
BEGIN
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '✅ 旧embeddingカラムを削除しました';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '';
    RAISE NOTICE '削減効果: 約6 MB（1,018レコード分）';
    RAISE NOTICE '';
    RAISE NOTICE '残っているembeddingカラム:';
    RAISE NOTICE '  ✅ general_name_embedding (halfvec)';
    RAISE NOTICE '  ✅ small_category_embedding (halfvec)';
    RAISE NOTICE '  ✅ keywords_embedding (halfvec)';
    RAISE NOTICE '';
    RAISE NOTICE '合計削減量: 約28 MB（halfvec変換22MB + カラム削除6MB）';
    RAISE NOTICE '====================================================================';
END $$;

-- 確認クエリ（残っているembeddingカラムを表示）
SELECT
  column_name,
  udt_name as type
FROM information_schema.columns
WHERE table_name = 'Rawdata_NETSUPER_items'
  AND column_name LIKE '%embedding%'
ORDER BY column_name;
