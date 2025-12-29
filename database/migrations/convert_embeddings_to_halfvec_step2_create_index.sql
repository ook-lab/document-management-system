-- ====================================================================
-- Step 2: halfvec用インデックスを作成（オプション）
-- ====================================================================
-- 目的: 検索速度が遅い場合のみ実行
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-29
-- ====================================================================
-- 注意: このSQLは Step 1 の型変換が完了してから実行してください
-- ====================================================================

BEGIN;

-- ====================================================================
-- アプローチ A: HNSW インデックス（メモリ効率が良い）
-- ====================================================================
-- IVFFlatより少ないメモリで作成できる可能性があります

CREATE INDEX idx_netsuper_general_name_embedding
  ON "Rawdata_NETSUPER_items"
  USING hnsw (general_name_embedding halfvec_cosine_ops);

CREATE INDEX idx_netsuper_small_category_embedding
  ON "Rawdata_NETSUPER_items"
  USING hnsw (small_category_embedding halfvec_cosine_ops);

CREATE INDEX idx_netsuper_keywords_embedding
  ON "Rawdata_NETSUPER_items"
  USING hnsw (keywords_embedding halfvec_cosine_ops);

DO $$
BEGIN
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '✅ HNSW インデックスを作成しました';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '';
    RAISE NOTICE 'HNSWインデックスの特徴:';
    RAISE NOTICE '  ✅ メモリ使用量が少ない';
    RAISE NOTICE '  ✅ 検索精度が高い';
    RAISE NOTICE '  ⚠️  作成時間がIVFFlatより長い';
    RAISE NOTICE '====================================================================';
END $$;

COMMIT;

-- ====================================================================
-- アプローチ B: IVFFlat インデックス（lists をさらに減らす）
-- ====================================================================
-- もし HNSW でもメモリエラーが出る場合は、以下を試してください：
--
-- BEGIN;
--
-- CREATE INDEX idx_netsuper_general_name_embedding
--   ON "Rawdata_NETSUPER_items"
--   USING ivfflat (general_name_embedding halfvec_cosine_ops)
--   WITH (lists = 10);
--
-- CREATE INDEX idx_netsuper_small_category_embedding
--   ON "Rawdata_NETSUPER_items"
--   USING ivfflat (small_category_embedding halfvec_cosine_ops)
--   WITH (lists = 10);
--
-- CREATE INDEX idx_netsuper_keywords_embedding
--   ON "Rawdata_NETSUPER_items"
--   USING ivfflat (keywords_embedding halfvec_cosine_ops)
--   WITH (lists = 10);
--
-- COMMIT;
--
-- ====================================================================
