-- =====================================================
-- search_indexテーブルの構造とデータを確認
-- =====================================================

-- 1. search_indexテーブルのカラム構造
SELECT column_name, data_type, character_maximum_length
FROM information_schema.columns
WHERE table_name = 'search_index'
ORDER BY ordinal_position;

-- 2. search_indexテーブルのデータ件数
SELECT COUNT(*) as total_rows
FROM search_index;

-- 3. search_indexのサンプルデータ（最初の3件）
SELECT *
FROM search_index
LIMIT 3;

-- 4. embeddingカラムの有無確認
SELECT
    COUNT(*) as total,
    COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as with_embedding,
    COUNT(CASE WHEN embedding IS NULL THEN 1 END) as without_embedding
FROM search_index;
