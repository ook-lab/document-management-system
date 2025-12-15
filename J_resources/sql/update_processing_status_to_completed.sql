-- =========================================
-- 全ドキュメントのprocessing_statusをcompletedに更新
-- search_indexにデータがあるドキュメントは処理完了とみなす
-- =========================================

BEGIN;

-- 1. search_indexにデータがあるドキュメントをcompletedに更新
UPDATE process_logs pl
SET processing_status = 'completed',
    updated_at = NOW()
WHERE pl.document_id IN (
    SELECT DISTINCT document_id
    FROM search_index
)
AND pl.processing_status != 'completed';

-- 2. 更新結果の確認
SELECT
    processing_status,
    COUNT(*) as count
FROM process_logs
GROUP BY processing_status
ORDER BY count DESC;

COMMIT;

-- =========================================
-- 確認: 検索可能なドキュメント数
-- =========================================
SELECT
    COUNT(DISTINCT sd.id) as searchable_documents
FROM source_documents sd
INNER JOIN search_index si ON sd.id = si.document_id
INNER JOIN process_logs pl ON sd.id = pl.document_id
WHERE pl.processing_status = 'completed';
