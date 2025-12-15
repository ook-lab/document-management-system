-- =====================================================
-- search_indexテーブルの完全な構造分析
-- =====================================================

-- 1. search_indexテーブルの全カラム詳細
SELECT
    column_name,
    data_type,
    character_maximum_length,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'search_index'
ORDER BY ordinal_position;

-- 2. search_indexのインデックス確認
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'search_index';

-- 3. search_indexのサンプルデータ（構造理解用）
SELECT *
FROM search_index
LIMIT 3;

-- 4. chunk_type の種類を確認
SELECT
    chunk_type,
    COUNT(*) as count
FROM search_index
GROUP BY chunk_type
ORDER BY count DESC;

-- 5. embedding の有無を確認
SELECT
    COUNT(*) as total,
    COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as with_embedding,
    COUNT(CASE WHEN embedding IS NULL THEN 1 END) as without_embedding,
    ROUND(COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 2) as embedding_percentage
FROM search_index;

-- 6. chunk_weightの分布確認
SELECT
    chunk_weight,
    COUNT(*) as count
FROM search_index
GROUP BY chunk_weight
ORDER BY chunk_weight DESC;
