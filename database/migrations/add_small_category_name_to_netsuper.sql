-- ====================================================================
-- Rawdata_NETSUPER_items に小分類名を追加
-- ====================================================================
-- 目的: 小分類の「名前」を直接表示できるようにする
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-26
-- ====================================================================

BEGIN;

-- 小分類カラムを追加（テキスト型）
ALTER TABLE "Rawdata_NETSUPER_items"
  ADD COLUMN IF NOT EXISTS small_category TEXT;

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_Rawdata_NETSUPER_items_small_category
  ON "Rawdata_NETSUPER_items"(small_category);

-- 複合インデックス（general_name + small_category）
CREATE INDEX IF NOT EXISTS idx_Rawdata_NETSUPER_items_general_small
  ON "Rawdata_NETSUPER_items"(general_name, small_category);

-- カラムコメント
COMMENT ON COLUMN "Rawdata_NETSUPER_items".small_category IS
  '小分類名 - 葉物野菜、練り物、根菜類などの詳細な商品分類。general_nameと組み合わせてベクトル検索精度を向上';

-- 既存データへの反映
-- MASTER_Product_category_mapping → MASTER_Categories_product から小分類名を取得して設定
UPDATE "Rawdata_NETSUPER_items" items
SET small_category = cat.name
FROM "MASTER_Product_category_mapping" mapping
JOIN "MASTER_Categories_product" cat ON mapping.product_category_id = cat.id
WHERE items.general_name = mapping.general_name
  AND items.small_category IS NULL;

-- 統計情報の表示
DO $$
DECLARE
    total_count INTEGER;
    mapped_count INTEGER;
    unmapped_count INTEGER;
    coverage_rate NUMERIC;
    category_stats TEXT;
BEGIN
    -- 総件数
    SELECT COUNT(*) INTO total_count
    FROM "Rawdata_NETSUPER_items";

    -- マッピング済み件数
    SELECT COUNT(*) INTO mapped_count
    FROM "Rawdata_NETSUPER_items"
    WHERE small_category IS NOT NULL;

    -- 未マッピング件数
    unmapped_count := total_count - mapped_count;

    -- カバー率
    coverage_rate := CASE
        WHEN total_count > 0 THEN ROUND(mapped_count::NUMERIC / total_count * 100, 1)
        ELSE 0
    END;

    -- カテゴリ別Top10
    SELECT string_agg(
        small_category || ': ' || cat_count::TEXT || '件',
        E'\n     '
    )
    INTO category_stats
    FROM (
        SELECT
            small_category,
            COUNT(*) as cat_count
        FROM "Rawdata_NETSUPER_items"
        WHERE small_category IS NOT NULL
        GROUP BY small_category
        ORDER BY COUNT(*) DESC
        LIMIT 10
    ) counts;

    RAISE NOTICE '====================================================================';
    RAISE NOTICE '✅ Rawdata_NETSUPER_items に小分類（名前）を追加しました';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '';
    RAISE NOTICE 'カラム追加:';
    RAISE NOTICE '  - small_category (TEXT) → 小分類名（葉物野菜、練り物など）';
    RAISE NOTICE '';
    RAISE NOTICE '既存データへの反映:';
    RAISE NOTICE '  総商品数:        % 件', total_count;
    RAISE NOTICE '  マッピング済み:  % 件 (%%%)', mapped_count, coverage_rate;
    RAISE NOTICE '  未マッピング:    % 件 (%%%)', unmapped_count, ROUND((100 - coverage_rate), 1);
    RAISE NOTICE '';
    RAISE NOTICE '小分類別Top10:';
    RAISE NOTICE '     %', category_stats;
    RAISE NOTICE '';
    RAISE NOTICE '検索精度への影響:';
    RAISE NOTICE '  ✅ general_name + small_category の組み合わせでベクトル生成';
    RAISE NOTICE '  ✅ 例: ほうれん草 + 葉物野菜 → 生ほうれん草';
    RAISE NOTICE '  ✅ 例: ほうれん草 + 冷凍食品 → 冷凍ほうれん草';
    RAISE NOTICE '';
    RAISE NOTICE '次のステップ:';
    RAISE NOTICE '  1. 未マッピング商品の確認と追加';
    RAISE NOTICE '  2. Embedding生成ロジックの更新（general_name + small_category を結合）';
    RAISE NOTICE '  3. 新規商品取得時に自動設定するようコード更新';
    RAISE NOTICE '====================================================================';
END $$;

COMMIT;
