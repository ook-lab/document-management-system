-- =====================================================
-- search_indexテーブルの完全な構造分析（修正版）
-- =====================================================

-- 1. search_indexテーブルの全カラム詳細
SELECT
    column_name,
    data_type,
    character_maximum_length,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'search_index'
ORDER BY ordinal_position;

-- 2. chunk_type の種類と件数
SELECT
    chunk_type,
    COUNT(*) as count
FROM search_index
GROUP BY chunk_type
ORDER BY count DESC;

-- 3. search_weight の分布確認
SELECT
    search_weight,
    COUNT(*) as count
FROM search_index
WHERE search_weight IS NOT NULL
GROUP BY search_weight
ORDER BY search_weight DESC;

-- 4. embedding の有無
SELECT
    COUNT(*) as total,
    COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as with_embedding,
    ROUND(COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 2) as percentage
FROM search_index;

-- 5. サンプルデータ（重要カラムのみ）
SELECT
    id,
    document_id,
    chunk_type,
    search_weight,
    LEFT(chunk_content, 100) as content_preview,
    CASE WHEN embedding IS NOT NULL THEN 'YES' ELSE 'NO' END as has_embedding
FROM search_index
ORDER BY search_weight DESC NULLS LAST
LIMIT 10;
