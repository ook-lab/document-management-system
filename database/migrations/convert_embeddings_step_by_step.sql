-- ====================================================================
-- Embeddingカラムをhalfvecに変換（段階的実行版）
-- ====================================================================
-- 実行方法: 以下のSQLを1つずつ、順番に実行してください
-- ====================================================================

-- ====================================================================
-- Step 1: インデックスを削除（1つずつ実行）
-- ====================================================================

-- まず1つ目のインデックスを削除
DROP INDEX IF EXISTS idx_netsuper_general_name_embedding;

-- 成功したら2つ目を実行
-- DROP INDEX IF EXISTS idx_netsuper_small_category_embedding;

-- 成功したら3つ目を実行
-- DROP INDEX IF EXISTS idx_netsuper_keywords_embedding;

-- ====================================================================
-- Step 2: カラムの型を変換（1つずつ実行）
-- ====================================================================

-- まず1つ目のカラムを変換
-- ALTER TABLE "Rawdata_NETSUPER_items"
--   ALTER COLUMN general_name_embedding TYPE halfvec(1536);

-- 成功したら2つ目を実行
-- ALTER TABLE "Rawdata_NETSUPER_items"
--   ALTER COLUMN small_category_embedding TYPE halfvec(1536);

-- 成功したら3つ目を実行
-- ALTER TABLE "Rawdata_NETSUPER_items"
--   ALTER COLUMN keywords_embedding TYPE halfvec(1536);

-- ====================================================================
-- 確認
-- ====================================================================

-- SELECT
--   column_name,
--   data_type,
--   udt_name
-- FROM information_schema.columns
-- WHERE table_name = 'Rawdata_NETSUPER_items'
--   AND column_name LIKE '%embedding%';
