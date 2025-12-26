-- ====================================================================
-- ハイブリッド検索関数（最終版・1回実行）
-- ====================================================================

BEGIN;

-- 既存関数を完全削除
DO $$
DECLARE
    func_record RECORD;
BEGIN
    FOR func_record IN
        SELECT
            p.oid,
            n.nspname || '.' || p.proname || '(' || pg_get_function_identity_arguments(p.oid) || ')' as func_sig
        FROM pg_proc p
        JOIN pg_namespace n ON p.pronamespace = n.oid
        WHERE p.proname IN ('hybrid_search', 'search_by_embedding')
          AND n.nspname = 'public'
    LOOP
        EXECUTE 'DROP FUNCTION ' || func_record.func_sig || ' CASCADE';
    END LOOP;
END $$;

-- ====================================================================
-- ハイブリッド検索関数
-- ====================================================================
CREATE FUNCTION hybrid_search(
    query_embedding vector(1536),
    query_text text,
    match_count int DEFAULT 20,
    general_weight double precision DEFAULT 0.4,
    category_weight double precision DEFAULT 0.3,
    keywords_weight double precision DEFAULT 0.2,
    text_weight double precision DEFAULT 0.1
)
RETURNS TABLE (
    id uuid,
    product_name text,
    general_name text,
    small_category text,
    keywords jsonb,
    organization text,
    current_price text,
    final_score double precision,
    general_score double precision,
    category_score double precision,
    keywords_score double precision,
    text_score double precision
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH
    general_search AS (
        SELECT
            items.id,
            (1.0 - (items.general_name_embedding <=> query_embedding))::double precision as score
        FROM "Rawdata_NETSUPER_items" items
        WHERE items.general_name_embedding IS NOT NULL
    ),
    category_search AS (
        SELECT
            items.id,
            (1.0 - (items.small_category_embedding <=> query_embedding))::double precision as score
        FROM "Rawdata_NETSUPER_items" items
        WHERE items.small_category_embedding IS NOT NULL
    ),
    keywords_search AS (
        SELECT
            items.id,
            (1.0 - (items.keywords_embedding <=> query_embedding))::double precision as score
        FROM "Rawdata_NETSUPER_items" items
        WHERE items.keywords_embedding IS NOT NULL
    ),
    text_search AS (
        SELECT
            items.id,
            GREATEST(
                COALESCE(similarity(items.product_name, query_text), 0.0),
                COALESCE(similarity(items.general_name, query_text), 0.0),
                CASE WHEN items.product_name ILIKE '%' || query_text || '%' THEN 0.5 ELSE 0.0 END,
                CASE WHEN items.general_name ILIKE '%' || query_text || '%' THEN 0.5 ELSE 0.0 END
            )::double precision as score
        FROM "Rawdata_NETSUPER_items" items
        WHERE
            items.product_name % query_text
            OR items.general_name % query_text
            OR items.product_name ILIKE '%' || query_text || '%'
            OR items.general_name ILIKE '%' || query_text || '%'
    ),
    combined_scores AS (
        SELECT
            items.id,
            items.product_name,
            items.general_name,
            items.small_category,
            items.keywords,
            items.organization,
            items.current_price,
            COALESCE(g.score, 0.0)::double precision as g_score,
            COALESCE(c.score, 0.0)::double precision as c_score,
            COALESCE(k.score, 0.0)::double precision as k_score,
            COALESCE(t.score, 0.0)::double precision as t_score,
            (
                COALESCE(g.score, 0.0) * general_weight +
                COALESCE(c.score, 0.0) * category_weight +
                COALESCE(k.score, 0.0) * keywords_weight +
                COALESCE(t.score, 0.0) * text_weight
            )::double precision as final_score
        FROM "Rawdata_NETSUPER_items" items
        LEFT JOIN general_search g ON items.id = g.id
        LEFT JOIN category_search c ON items.id = c.id
        LEFT JOIN keywords_search k ON items.id = k.id
        LEFT JOIN text_search t ON items.id = t.id
        WHERE
            g.id IS NOT NULL
            OR c.id IS NOT NULL
            OR k.id IS NOT NULL
            OR t.id IS NOT NULL
    )
    SELECT
        combined_scores.id,
        combined_scores.product_name::text,
        combined_scores.general_name::text,
        combined_scores.small_category::text,
        combined_scores.keywords,
        combined_scores.organization::text,
        combined_scores.current_price::text,
        combined_scores.final_score,
        combined_scores.g_score,
        combined_scores.c_score,
        combined_scores.k_score,
        combined_scores.t_score
    FROM combined_scores
    WHERE combined_scores.final_score > 0
    ORDER BY combined_scores.final_score DESC
    LIMIT match_count;
END;
$$;

-- 確認
DO $$
BEGIN
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '✅ ハイブリッド検索関数を作成しました';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE 'これで python netsuper_search_app\hybrid_search.py "牛乳" が実行できます';
    RAISE NOTICE '====================================================================';
END $$;

COMMIT;
