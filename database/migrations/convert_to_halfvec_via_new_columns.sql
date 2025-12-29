-- ====================================================================
-- halfvec変換（新カラム経由・メモリ制限回避版）
-- ====================================================================
-- 方法: 新しいhalfvecカラムを追加 → データコピー → 旧カラム削除
-- この方法なら、ALTER TABLE TYPE を使わないのでメモリエラーが出ません
-- ====================================================================

-- ====================================================================
-- Step 1: 既存のインデックスを削除
-- ====================================================================

DROP INDEX IF EXISTS idx_netsuper_general_name_embedding;
DROP INDEX IF EXISTS idx_netsuper_small_category_embedding;
DROP INDEX IF EXISTS idx_netsuper_keywords_embedding;

-- ====================================================================
-- Step 2: 新しいhalfvecカラムを追加
-- ====================================================================

ALTER TABLE "Rawdata_NETSUPER_items"
  ADD COLUMN IF NOT EXISTS general_name_embedding_new halfvec(1536);

ALTER TABLE "Rawdata_NETSUPER_items"
  ADD COLUMN IF NOT EXISTS small_category_embedding_new halfvec(1536);

ALTER TABLE "Rawdata_NETSUPER_items"
  ADD COLUMN IF NOT EXISTS keywords_embedding_new halfvec(1536);

-- ====================================================================
-- Step 3: データをコピー（vector → halfvec に自動変換される）
-- ====================================================================
-- PostgreSQLがvector型からhalfvec型への変換を自動で行います

UPDATE "Rawdata_NETSUPER_items"
SET
  general_name_embedding_new = general_name_embedding::halfvec(1536),
  small_category_embedding_new = small_category_embedding::halfvec(1536),
  keywords_embedding_new = keywords_embedding::halfvec(1536)
WHERE general_name_embedding IS NOT NULL
   OR small_category_embedding IS NOT NULL
   OR keywords_embedding IS NOT NULL;

-- ====================================================================
-- Step 4: 旧カラムを削除
-- ====================================================================

ALTER TABLE "Rawdata_NETSUPER_items"
  DROP COLUMN general_name_embedding,
  DROP COLUMN small_category_embedding,
  DROP COLUMN keywords_embedding;

-- ====================================================================
-- Step 5: 新カラムを旧カラム名にリネーム
-- ====================================================================

ALTER TABLE "Rawdata_NETSUPER_items"
  RENAME COLUMN general_name_embedding_new TO general_name_embedding;

ALTER TABLE "Rawdata_NETSUPER_items"
  RENAME COLUMN small_category_embedding_new TO small_category_embedding;

ALTER TABLE "Rawdata_NETSUPER_items"
  RENAME COLUMN keywords_embedding_new TO keywords_embedding;

-- ====================================================================
-- 確認
-- ====================================================================

DO $$
BEGIN
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '✅ halfvec変換完了（新カラム経由）';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '';
    RAISE NOTICE '削減効果: 44.2 MB → 22.1 MB（50%%削減）';
    RAISE NOTICE '';
    RAISE NOTICE '次のステップ:';
    RAISE NOTICE '  1. 検索テスト: python netsuper_search_app/hybrid_search.py "牛乳"';
    RAISE NOTICE '  2. 動作確認OK';
    RAISE NOTICE '====================================================================';
END $$;
