-- ====================================================================
-- 既存のハイブリッド検索関数を削除
-- ====================================================================

BEGIN;

-- すべてのhybrid_search関数を削除
DO $$
DECLARE
    func_record RECORD;
BEGIN
    FOR func_record IN
        SELECT
            n.nspname as schema_name,
            p.proname as function_name,
            pg_get_function_identity_arguments(p.oid) as args
        FROM pg_proc p
        JOIN pg_namespace n ON p.pronamespace = n.oid
        WHERE p.proname IN ('hybrid_search', 'search_by_embedding')
          AND n.nspname = 'public'
    LOOP
        EXECUTE format('DROP FUNCTION IF EXISTS %I.%I(%s) CASCADE',
            func_record.schema_name,
            func_record.function_name,
            func_record.args
        );
        RAISE NOTICE '削除: %.%(%)',
            func_record.schema_name,
            func_record.function_name,
            func_record.args;
    END LOOP;
END $$;

COMMIT;

-- 確認
DO $$
BEGIN
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '✅ 既存関数の削除完了';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '';
    RAISE NOTICE '次のステップ:';
    RAISE NOTICE '  create_hybrid_search_function_v2.sql を実行してください';
    RAISE NOTICE '====================================================================';
END $$;
