-- ====================================================================
-- ハイブリッド検索用のSQL関数
-- ====================================================================
-- 目的: 複数embeddingとテキスト検索を組み合わせた検索関数
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-26
-- ====================================================================

BEGIN;

-- ====================================================================
-- 関数1: ベクトル類似度検索（単一embedding）
-- ====================================================================
CREATE OR REPLACE FUNCTION search_by_embedding(
    query_embedding vector(1536),
    embedding_column_name text,
    match_threshold float DEFAULT 0.5,
    match_count int DEFAULT 100
)
RETURNS TABLE (
    id uuid,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY EXECUTE format(
        'SELECT id, 1 - (%I <=> $1) as similarity
         FROM "Rawdata_NETSUPER_items"
         WHERE %I IS NOT NULL
           AND 1 - (%I <=> $1) > $2
         ORDER BY %I <=> $1
         LIMIT $3',
        embedding_column_name,
        embedding_column_name,
        embedding_column_name,
        embedding_column_name
    )
    USING query_embedding, match_threshold, match_count;
END;
$$;

-- ====================================================================
-- 関数2: ハイブリッド検索（重み付き統合）
-- ====================================================================
CREATE OR REPLACE FUNCTION hybrid_search(
    query_embedding vector(1536),
    query_text text,
    match_count int DEFAULT 20,
    general_weight float DEFAULT 0.4,
    category_weight float DEFAULT 0.3,
    keywords_weight float DEFAULT 0.2,
    text_weight float DEFAULT 0.1
)
RETURNS TABLE (
    id uuid,
    product_name text,
    general_name text,
    small_category text,
    keywords jsonb,
    organization text,
    price numeric,
    final_score float,
    general_score float,
    category_score float,
    keywords_score float,
    text_score float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH
    -- 1. general_name_embedding 検索
    general_search AS (
        SELECT
            items.id,
            COALESCE(1 - (items.general_name_embedding <=> query_embedding), 0) as score
        FROM "Rawdata_NETSUPER_items" items
        WHERE items.general_name_embedding IS NOT NULL
    ),
    -- 2. small_category_embedding 検索
    category_search AS (
        SELECT
            items.id,
            COALESCE(1 - (items.small_category_embedding <=> query_embedding), 0) as score
        FROM "Rawdata_NETSUPER_items" items
        WHERE items.small_category_embedding IS NOT NULL
    ),
    -- 3. keywords_embedding 検索
    keywords_search AS (
        SELECT
            items.id,
            COALESCE(1 - (items.keywords_embedding <=> query_embedding), 0) as score
        FROM "Rawdata_NETSUPER_items" items
        WHERE items.keywords_embedding IS NOT NULL
    ),
    -- 4. テキスト検索
    text_search AS (
        SELECT
            items.id,
            GREATEST(
                COALESCE(similarity(items.product_name, query_text), 0),
                COALESCE(similarity(items.general_name, query_text), 0),
                CASE WHEN items.product_name ILIKE '%' || query_text || '%' THEN 0.5 ELSE 0 END,
                CASE WHEN items.general_name ILIKE '%' || query_text || '%' THEN 0.5 ELSE 0 END
            ) as score
        FROM "Rawdata_NETSUPER_items" items
        WHERE
            items.product_name % query_text
            OR items.general_name % query_text
            OR items.product_name ILIKE '%' || query_text || '%'
            OR items.general_name ILIKE '%' || query_text || '%'
    ),
    -- スコア統合
    combined_scores AS (
        SELECT
            items.id,
            items.product_name,
            items.general_name,
            items.small_category,
            items.keywords,
            items.organization,
            items.price,
            COALESCE(g.score, 0) as g_score,
            COALESCE(c.score, 0) as c_score,
            COALESCE(k.score, 0) as k_score,
            COALESCE(t.score, 0) as t_score,
            (
                COALESCE(g.score, 0) * general_weight +
                COALESCE(c.score, 0) * category_weight +
                COALESCE(k.score, 0) * keywords_weight +
                COALESCE(t.score, 0) * text_weight
            ) as final_score
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
        combined_scores.product_name,
        combined_scores.general_name,
        combined_scores.small_category,
        combined_scores.keywords,
        combined_scores.organization,
        combined_scores.price,
        combined_scores.final_score,
        combined_scores.g_score as general_score,
        combined_scores.c_score as category_score,
        combined_scores.k_score as keywords_score,
        combined_scores.t_score as text_score
    FROM combined_scores
    WHERE combined_scores.final_score > 0
    ORDER BY combined_scores.final_score DESC
    LIMIT match_count;
END;
$$;

-- ====================================================================
-- 使用例
-- ====================================================================
COMMENT ON FUNCTION hybrid_search IS
'ハイブリッド検索: 複数embeddingとテキスト検索を重み付き統合

使用例:
SELECT * FROM hybrid_search(
    ''[0.1, 0.2, ...]''::vector(1536),  -- クエリのembedding
    ''ほうれん草'',                      -- 検索テキスト
    20,                                  -- 取得件数
    0.4,                                 -- general_name重み
    0.3,                                 -- small_category重み
    0.2,                                 -- keywords重み
    0.1                                  -- text検索重み
);
';

-- 統計情報
DO $$
BEGIN
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '✅ ハイブリッド検索関数を作成しました';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE '';
    RAISE NOTICE '作成された関数:';
    RAISE NOTICE '  1. search_by_embedding() - 単一embeddingで検索';
    RAISE NOTICE '  2. hybrid_search() - 重み付きハイブリッド検索';
    RAISE NOTICE '';
    RAISE NOTICE '使用方法:';
    RAISE NOTICE '  Python側でクエリのembeddingを生成';
    RAISE NOTICE '  → hybrid_search()関数を呼び出し';
    RAISE NOTICE '  → 重み付けされた検索結果を取得';
    RAISE NOTICE '';
    RAISE NOTICE '重み設定（デフォルト）:';
    RAISE NOTICE '  general_name:     0.4 (重め)';
    RAISE NOTICE '  small_category:   0.3 (重め)';
    RAISE NOTICE '  keywords:         0.2 (軽め)';
    RAISE NOTICE '  text_search:      0.1 (補助)';
    RAISE NOTICE '====================================================================';
END $$;

COMMIT;
