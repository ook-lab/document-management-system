-- ====================================================================
-- Rawdata_NETSUPER_items に小分類カラムを追加
-- ====================================================================
-- 目的: 検索精度向上のため、general_name + 小分類の組み合わせを実現
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-26
-- ====================================================================
-- 重要: general_name × 小分類の組み合わせがベクトル検索の精度を決定する
-- 例: general_name='ほうれん草' + 小分類='葉物野菜' → 生ほうれん草
--     general_name='ほうれん草' + 小分類='冷凍食品' → 冷凍ほうれん草
-- ====================================================================

BEGIN;

-- ====================================================================
-- フェーズ1: カラム追加
-- ====================================================================

-- product_category_id カラムを追加（小分類を格納）
ALTER TABLE "Rawdata_NETSUPER_items"
  ADD COLUMN IF NOT EXISTS product_category_id UUID REFERENCES "MASTER_Categories_product"(id) ON DELETE SET NULL;

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_Rawdata_NETSUPER_items_product_category
  ON "Rawdata_NETSUPER_items"(product_category_id);

-- 複合インデックス（general_name + product_category_id）
CREATE INDEX IF NOT EXISTS idx_Rawdata_NETSUPER_items_general_product
  ON "Rawdata_NETSUPER_items"(general_name, product_category_id);

-- カラムコメント
COMMENT ON COLUMN "Rawdata_NETSUPER_items".product_category_id IS
  '1次分類（小分類） - 葉物野菜、練り物、根菜類などの詳細な商品分類。general_nameと組み合わせてベクトル検索精度を向上';

-- ====================================================================
-- フェーズ2: 既存データへの自動反映
-- ====================================================================

-- MASTER_Product_category_mapping を使用して、
-- general_name から product_category_id（小分類）を自動設定

UPDATE "Rawdata_NETSUPER_items" items
SET product_category_id = mapping.product_category_id
FROM "MASTER_Product_category_mapping" mapping
WHERE items.general_name = mapping.general_name
  AND items.product_category_id IS NULL;

-- ====================================================================
-- 統計情報の表示
-- ====================================================================

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
    WHERE product_category_id IS NOT NULL;

    -- 未マッピング件数
    unmapped_count := total_count - mapped_count;

    -- カバー率
    coverage_rate := CASE
        WHEN total_count > 0 THEN ROUND(mapped_count::NUMERIC / total_count * 100, 1)
        ELSE 0
    END;

    -- カテゴリ別Top10
    SELECT string_agg(
        small_cat.name || ' (' || mid_cat.name || ')' || ': ' || cat_count::TEXT || '件',
        E'\n     '
    )
    INTO category_stats
    FROM (
        SELECT
            items.product_category_id,
            COUNT(*) as cat_count
        FROM "Rawdata_NETSUPER_items" items
        WHERE items.product_category_id IS NOT NULL
        GROUP BY items.product_category_id
        ORDER BY COUNT(*) DESC
        LIMIT 10
    ) counts
    JOIN "MASTER_Categories_product" small_cat ON counts.product_category_id = small_cat.id
    LEFT JOIN "MASTER_Categories_product" mid_cat ON small_cat.parent_id = mid_cat.id;

    RAISE NOTICE '====================================================================';
    RAISE NOTICE '✅ Rawdata_NETSUPER_items に小分類カラムを追加しました';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '';
    RAISE NOTICE 'カラム追加:';
    RAISE NOTICE '  - product_category_id (UUID) → MASTER_Categories_product(小分類)';
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
    RAISE NOTICE '  ✅ general_name + product_category_id の組み合わせでベクトル生成';
    RAISE NOTICE '  ✅ 例: ほうれん草 + 葉物野菜 → 生ほうれん草';
    RAISE NOTICE '  ✅ 例: ほうれん草 + 冷凍食品 → 冷凍ほうれん草';
    RAISE NOTICE '';
    RAISE NOTICE '次のステップ:';
    RAISE NOTICE '  1. 未マッピング商品の確認と追加';
    RAISE NOTICE '  2. Embedding生成ロジックの更新（general_name + 小分類名を結合）';
    RAISE NOTICE '  3. 新規商品取得時に自動設定するようコード更新';
    RAISE NOTICE '====================================================================';
END $$;

COMMIT;

-- ====================================================================
-- 実行後の確認クエリ
-- ====================================================================

-- マッピング状況の確認
-- SELECT
--     COUNT(*) FILTER (WHERE product_category_id IS NOT NULL) as mapped,
--     COUNT(*) FILTER (WHERE product_category_id IS NULL) as unmapped,
--     COUNT(*) as total,
--     ROUND(COUNT(*) FILTER (WHERE product_category_id IS NOT NULL)::NUMERIC / COUNT(*) * 100, 1) as coverage_rate
-- FROM "Rawdata_NETSUPER_items";

-- 小分類別の集計（階層表示）
-- SELECT
--     large.name as 大分類,
--     mid.name as 中分類,
--     small.name as 小分類,
--     COUNT(*) as 商品数
-- FROM "Rawdata_NETSUPER_items" items
-- JOIN "MASTER_Categories_product" small ON items.product_category_id = small.id
-- LEFT JOIN "MASTER_Categories_product" mid ON small.parent_id = mid.id
-- LEFT JOIN "MASTER_Categories_product" large ON mid.parent_id = large.id
-- GROUP BY large.name, mid.name, small.name
-- ORDER BY large.name, mid.name, small.name;

-- 未マッピング商品の確認（上位30件）
-- SELECT
--     product_name,
--     general_name,
--     organization
-- FROM "Rawdata_NETSUPER_items"
-- WHERE product_category_id IS NULL
-- AND general_name IS NOT NULL
-- ORDER BY created_at DESC
-- LIMIT 30;

-- general_nameと小分類の組み合わせ例
-- SELECT
--     items.general_name,
--     small.name as 小分類,
--     mid.name as 中分類,
--     COUNT(*) as 商品数
-- FROM "Rawdata_NETSUPER_items" items
-- JOIN "MASTER_Categories_product" small ON items.product_category_id = small.id
-- LEFT JOIN "MASTER_Categories_product" mid ON small.parent_id = mid.id
-- WHERE items.general_name IN ('ほうれん草', '牛乳', 'チーズ', 'ビール')
-- GROUP BY items.general_name, small.name, mid.name
-- ORDER BY items.general_name, small.name;
