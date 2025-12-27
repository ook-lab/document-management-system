-- ====================================================================
-- Embedding自動リセットトリガー
-- ====================================================================
-- 目的: general_name, small_category, keywords が変更されたら
--       自動的に embedding をリセットして再生成を促す
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-28
-- ====================================================================

BEGIN;

-- トリガー関数の作成
CREATE OR REPLACE FUNCTION reset_embeddings_on_classification_change()
RETURNS TRIGGER AS $$
BEGIN
    -- general_name, small_category, keywords のいずれかが変更された場合
    IF (NEW.general_name IS DISTINCT FROM OLD.general_name) OR
       (NEW.small_category IS DISTINCT FROM OLD.small_category) OR
       (NEW.keywords IS DISTINCT FROM OLD.keywords) THEN

        -- embedding をリセット
        NEW.general_name_embedding := NULL;
        NEW.small_category_embedding := NULL;
        NEW.keywords_embedding := NULL;

        RAISE NOTICE 'Embeddings reset for product ID: %', NEW.id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- トリガーの作成
DROP TRIGGER IF EXISTS trigger_reset_embeddings ON "Rawdata_NETSUPER_items";
CREATE TRIGGER trigger_reset_embeddings
    BEFORE UPDATE ON "Rawdata_NETSUPER_items"
    FOR EACH ROW
    EXECUTE FUNCTION reset_embeddings_on_classification_change();

-- 確認
DO $$
BEGIN
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '✅ Embedding自動リセットトリガーを作成しました';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '';
    RAISE NOTICE '動作:';
    RAISE NOTICE '  - general_name 変更時 → embedding を自動リセット';
    RAISE NOTICE '  - small_category 変更時 → embedding を自動リセット';
    RAISE NOTICE '  - keywords 変更時 → embedding を自動リセット';
    RAISE NOTICE '';
    RAISE NOTICE '対象:';
    RAISE NOTICE '  - Pythonスクリプトからの更新';
    RAISE NOTICE '  - Supabase Dashboardでの手動修正';
    RAISE NOTICE '  - 全ての更新操作';
    RAISE NOTICE '';
    RAISE NOTICE '次のステップ:';
    RAISE NOTICE '  1. 分類を更新: python -m L_product_classification.daily_auto_classifier';
    RAISE NOTICE '  2. Embedding生成: python netsuper_search_app/generate_multi_embeddings.py';
    RAISE NOTICE '====================================================================';
END $$;

COMMIT;
