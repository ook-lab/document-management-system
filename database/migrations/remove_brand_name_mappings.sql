-- ====================================================================
-- ブランド名→商品種類の誤ったマッピングを削除
-- ====================================================================
-- 目的: ブランド名だけでは商品種類を特定できないため削除
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-27
-- ====================================================================

BEGIN;

-- 全てのマッピングを削除（AIに完全に任せる）
TRUNCATE TABLE "MASTER_Product_generalize";

-- 確認
DO $$
DECLARE
    remaining_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO remaining_count
    FROM "MASTER_Product_generalize";

    RAISE NOTICE '====================================================================';
    RAISE NOTICE '✅ 全てのマッピングを削除しました（AI完全移行）';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '';
    RAISE NOTICE '残りのマッピング: % 件（0件であるべき）', remaining_count;
    RAISE NOTICE '';
    RAISE NOTICE '今後の動作:';
    RAISE NOTICE '  - MASTER_Product_generalize は使用されない';
    RAISE NOTICE '  - 全ての商品でGemini AIがgeneral_nameを抽出';
    RAISE NOTICE '  - より正確な分類が期待できる';
    RAISE NOTICE '';
    RAISE NOTICE '次のステップ:';
    RAISE NOTICE '  1. python K_kakeibo/cleanup_generated_data.py --all';
    RAISE NOTICE '  2. python -m L_product_classification.daily_auto_classifier';
    RAISE NOTICE '  3. python netsuper_search_app/generate_multi_embeddings.py';
    RAISE NOTICE '====================================================================';
END $$;

COMMIT;
