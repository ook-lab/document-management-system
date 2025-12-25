-- Weighted Search Vector Implementation for Rawdata_NETSUPER_items
-- 重み付け: A (小分類 + general_name) > B (keywords) > C (product_name)
--
-- 注意: 全文検索設定に 'simple' を使用しています
-- 'simple' は言語に依存しない基本的なトークナイザーで、日本語を含む全ての言語に対応します
-- より高度な日本語検索が必要な場合は、pg_bigm拡張の使用を検討してください

-- ========================================
-- Step 1: トリガー関数の作成
-- ========================================

CREATE OR REPLACE FUNCTION update_netsuper_search_vector()
RETURNS TRIGGER AS $$
DECLARE
    category_name TEXT;
BEGIN
    -- category_idがある場合、小分類名を取得
    IF NEW.category_id IS NOT NULL THEN
        SELECT name INTO category_name
        FROM "MASTER_Categories_product"
        WHERE id = NEW.category_id;
    END IF;

    -- 重み付きsearch_vectorを生成
    -- Weight A: 小分類 + general_name (最重要)
    -- Weight B: keywords (重要)
    -- Weight C: product_name (参考)
    NEW.search_vector :=
        -- Weight A: 小分類（あれば）+ general_name
        setweight(to_tsvector('simple',
            COALESCE(category_name, '') || ' ' || COALESCE(NEW.general_name, '')
        ), 'A') ||
        -- Weight B: keywords
        setweight(to_tsvector('simple',
            COALESCE(
                (SELECT string_agg(value::text, ' ')
                 FROM jsonb_array_elements_text(NEW.keywords)),
                ''
            )), 'B') ||
        -- Weight C: product_name
        setweight(to_tsvector('simple', COALESCE(NEW.product_name, '')), 'C');

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ========================================
-- Step 2: トリガーの作成
-- ========================================

-- 既存のトリガーがあれば削除
DROP TRIGGER IF EXISTS netsuper_search_vector_update ON "Rawdata_NETSUPER_items";

-- 新しいトリガーを作成
CREATE TRIGGER netsuper_search_vector_update
    BEFORE INSERT OR UPDATE OF general_name, keywords, product_name
    ON "Rawdata_NETSUPER_items"
    FOR EACH ROW
    EXECUTE FUNCTION update_netsuper_search_vector();

-- ========================================
-- Step 3: 既存データのsearch_vector更新
-- ========================================

-- 注意: 大量データの場合、この更新は時間がかかる可能性があります
-- 必要に応じてバッチ処理で実行してください

UPDATE "Rawdata_NETSUPER_items" AS items
SET search_vector =
    -- Weight A: 小分類（あれば）+ general_name
    setweight(to_tsvector('simple',
        COALESCE(
            (SELECT name FROM "MASTER_Categories_product" WHERE id = items.category_id),
            ''
        ) || ' ' || COALESCE(items.general_name, '')
    ), 'A') ||
    -- Weight B: keywords
    setweight(to_tsvector('simple',
        COALESCE(
            (SELECT string_agg(value::text, ' ')
             FROM jsonb_array_elements_text(items.keywords)),
            ''
        )), 'B') ||
    -- Weight C: product_name
    setweight(to_tsvector('simple', COALESCE(items.product_name, '')), 'C')
WHERE items.product_name IS NOT NULL;

-- ========================================
-- 完了メッセージ
-- ========================================

-- SELECT 'Weighted search_vector setup completed!' AS status;
