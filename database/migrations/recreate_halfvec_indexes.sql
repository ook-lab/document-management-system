-- ====================================================================
-- halfvec用インデックスを再作成
-- ====================================================================
-- 目的: halfvec変換後のインデックスを作成
-- 作成日: 2025-12-29
-- ====================================================================
-- 注意: メモリエラーを避けるため、HNSWインデックスを使用します
-- HNSWはIVFFlatよりメモリ効率が良く、検索精度も高いです
-- ====================================================================

-- ====================================================================
-- アプローチ: HNSW インデックス（推奨）
-- ====================================================================
-- HNSWの特徴:
-- - メモリ使用量が少ない
-- - 検索精度が高い
-- - 5,454件のデータ量に最適

CREATE INDEX IF NOT EXISTS idx_netsuper_general_name_embedding
  ON "Rawdata_NETSUPER_items"
  USING hnsw (general_name_embedding halfvec_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_netsuper_small_category_embedding
  ON "Rawdata_NETSUPER_items"
  USING hnsw (small_category_embedding halfvec_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_netsuper_keywords_embedding
  ON "Rawdata_NETSUPER_items"
  USING hnsw (keywords_embedding halfvec_cosine_ops);

-- 確認
DO $$
BEGIN
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '✅ HNSWインデックスを作成しました';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '';
    RAISE NOTICE '作成されたインデックス:';
    RAISE NOTICE '  - idx_netsuper_general_name_embedding';
    RAISE NOTICE '  - idx_netsuper_small_category_embedding';
    RAISE NOTICE '  - idx_netsuper_keywords_embedding';
    RAISE NOTICE '';
    RAISE NOTICE 'HNSWインデックスの特徴:';
    RAISE NOTICE '  ✅ メモリ使用量が少ない';
    RAISE NOTICE '  ✅ 検索精度が高い';
    RAISE NOTICE '  ✅ 5,454件のデータ量に最適';
    RAISE NOTICE '====================================================================';
END $$;

-- インデックスの確認
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'Rawdata_NETSUPER_items'
  AND indexname LIKE '%embedding%'
ORDER BY indexname;
