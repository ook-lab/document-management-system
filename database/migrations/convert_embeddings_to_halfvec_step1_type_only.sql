-- ====================================================================
-- Step 1: Embeddingカラムをhalfvecに変換（型変換のみ）
-- ====================================================================
-- 目的: インデックスなしで型変換だけを実行（メモリ不足エラー回避）
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-29
-- 削減効果: 44.2 MB → 22.1 MB（約22 MB削減）
-- ====================================================================

BEGIN;

-- ====================================================================
-- Step 1: 既存のインデックスを削除
-- ====================================================================

DROP INDEX IF EXISTS idx_netsuper_general_name_embedding;
DROP INDEX IF EXISTS idx_netsuper_small_category_embedding;
DROP INDEX IF EXISTS idx_netsuper_keywords_embedding;

-- ====================================================================
-- Step 2: カラムの型を変換
-- ====================================================================
-- vector(1536) は 1536 * 4 bytes (float32) = 6 KB
-- halfvec(1536) は 1536 * 2 bytes (float16) = 3 KB
-- 容量が正確に50%削減されます

ALTER TABLE "Rawdata_NETSUPER_items"
  ALTER COLUMN general_name_embedding TYPE halfvec(1536);

ALTER TABLE "Rawdata_NETSUPER_items"
  ALTER COLUMN small_category_embedding TYPE halfvec(1536);

ALTER TABLE "Rawdata_NETSUPER_items"
  ALTER COLUMN keywords_embedding TYPE halfvec(1536);

-- ====================================================================
-- Step 3: ディスク容量を解放
-- ====================================================================

VACUUM FULL "Rawdata_NETSUPER_items";

-- ====================================================================
-- 確認
-- ====================================================================

DO $$
BEGIN
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '✅ Embeddingカラムをhalfvecに変換しました（型変換のみ）';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '';
    RAISE NOTICE '変換されたカラム:';
    RAISE NOTICE '  1. general_name_embedding: vector(1536) → halfvec(1536)';
    RAISE NOTICE '  2. small_category_embedding: vector(1536) → halfvec(1536)';
    RAISE NOTICE '  3. keywords_embedding: vector(1536) → halfvec(1536)';
    RAISE NOTICE '';
    RAISE NOTICE '削減効果:';
    RAISE NOTICE '  - 元の容量: 44.2 MB';
    RAISE NOTICE '  - 変換後: 22.1 MB';
    RAISE NOTICE '  - 削減量: 22.1 MB（50%削減）';
    RAISE NOTICE '';
    RAISE NOTICE '⚠️  注意:';
    RAISE NOTICE '  - インデックスは作成していません';
    RAISE NOTICE '  - 5,454件のデータ量なら、インデックスなしでも検索は十分高速です';
    RAISE NOTICE '';
    RAISE NOTICE '次のステップ:';
    RAISE NOTICE '  1. 検索テストを実行: python netsuper_search_app/hybrid_search.py "牛乳"';
    RAISE NOTICE '  2. 検索速度が問題なければ、インデックスなしで運用可能';
    RAISE NOTICE '  3. 遅い場合は、別途インデックス作成SQLを実行';
    RAISE NOTICE '====================================================================';
END $$;

COMMIT;
