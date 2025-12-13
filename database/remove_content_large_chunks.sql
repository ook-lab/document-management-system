-- 大チャンク（content_large）を削除
-- 理由: OpenAI embedding APIのトークン制限（8192トークン）を超えるためエラーが発生
-- 今後は作成しないため、既存のものも削除してデータの一貫性を保つ

-- 削除前の確認: content_largeチャンクの数を確認
SELECT
    chunk_type,
    COUNT(*) as count,
    SUM(chunk_size) as total_size,
    AVG(chunk_size) as avg_size,
    MAX(chunk_size) as max_size
FROM document_chunks
WHERE chunk_type = 'content_large'
GROUP BY chunk_type;

-- content_largeチャンクを削除
DELETE FROM document_chunks
WHERE chunk_type = 'content_large';

-- 削除後の確認
SELECT
    chunk_type,
    COUNT(*) as count
FROM document_chunks
GROUP BY chunk_type
ORDER BY count DESC;
