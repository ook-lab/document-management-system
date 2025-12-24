-- ============================================
-- ベクトル検索用のPostgreSQL関数を作成
-- ============================================

-- 商品をベクトル類似度で検索する関数
CREATE OR REPLACE FUNCTION search_products_by_embedding(
    query_embedding vector(1536),
    match_count int DEFAULT 200,
    filter_organizations text[] DEFAULT NULL
)
RETURNS TABLE (
    id uuid,
    product_name text,
    organization text,
    current_price_tax_included numeric,
    image_url text,
    metadata jsonb,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.id,
        p.product_name,
        p.organization,
        p.current_price_tax_included,
        p.image_url,
        p.metadata,
        1 - (p.embedding <=> query_embedding) AS similarity
    FROM
        "Rawdata_NETSUPER_items" p
    WHERE
        p.embedding IS NOT NULL
        AND (filter_organizations IS NULL OR p.organization = ANY(filter_organizations))
    ORDER BY
        p.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- 使用例:
-- SELECT * FROM search_products_by_embedding(
--     '[0.1, 0.2, ...]'::vector(1536),
--     200,
--     ARRAY['楽天西友ネットスーパー', '東急ストア ネットスーパー', 'ダイエーネットスーパー']
-- );
