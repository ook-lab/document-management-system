-- ====================================================================
-- Embeddingカラムをhalfvecに変換（最小限版・メモリエラー回避）
-- ====================================================================
-- 目的: 型変換のみ実行（VACUUM FULLなし、インデックスなし）
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-29
-- ====================================================================

BEGIN;

-- Step 1: 既存のインデックスを削除
DROP INDEX IF EXISTS idx_netsuper_general_name_embedding;
DROP INDEX IF EXISTS idx_netsuper_small_category_embedding;
DROP INDEX IF EXISTS idx_netsuper_keywords_embedding;

-- Step 2: カラムの型を変換
ALTER TABLE "Rawdata_NETSUPER_items"
  ALTER COLUMN general_name_embedding TYPE halfvec(1536);

ALTER TABLE "Rawdata_NETSUPER_items"
  ALTER COLUMN small_category_embedding TYPE halfvec(1536);

ALTER TABLE "Rawdata_NETSUPER_items"
  ALTER COLUMN keywords_embedding TYPE halfvec(1536);

-- 確認メッセージ
DO $$
BEGIN
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '✅ 型変換完了: vector(1536) → halfvec(1536)';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '';
    RAISE NOTICE '削減効果: 44.2 MB → 22.1 MB（50%削減）';
    RAISE NOTICE '';
    RAISE NOTICE '⚠️  注意:';
    RAISE NOTICE '  - インデックスなし（5,454件なら問題なし）';
    RAISE NOTICE '  - ディスク容量解放は後で実行（VACUUMなし）';
    RAISE NOTICE '';
    RAISE NOTICE '次のステップ:';
    RAISE NOTICE '  1. 検索テスト: python netsuper_search_app/hybrid_search.py "牛乳"';
    RAISE NOTICE '  2. 検索が動作すればOK';
    RAISE NOTICE '====================================================================';
END $$;

COMMIT;
