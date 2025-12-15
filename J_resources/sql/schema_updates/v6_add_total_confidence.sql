-- 【実行場所】: Supabase SQL Editor
-- 【対象】: documents テーブル
-- 【実行方法】: SupabaseダッシュボードでSQL Editorに貼り付け、実行
-- 【目的】: total_confidence カラムを追加し、複合信頼度スコアを保存

-- Phase 2 (Track 1) - 複合指標によるConfidence計算
-- AUTO_INBOX_COMPLETE_v3.0.md の「2.1.1 複合指標によるConfidence計算」に準拠

BEGIN;

-- total_confidence カラムの追加
-- 複合信頼度スコア = (model_confidence * 0.4) + (keyword_match * 0.3) +
--                    (metadata_completeness * 0.2) + (data_consistency * 0.1)
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS total_confidence FLOAT;

-- カラムの説明
COMMENT ON COLUMN documents.total_confidence IS
'複合信頼度スコア。AIモデルの確信度、キーワード一致、メタデータ充足率、データ整合性の加重平均。Phase 2で追加。';

-- インデックスの追加（total_confidenceでの検索・ソートを高速化）
CREATE INDEX IF NOT EXISTS idx_documents_total_confidence
ON documents(total_confidence DESC NULLS LAST)
WHERE total_confidence IS NOT NULL;

-- 統計情報
DO $$
BEGIN
    RAISE NOTICE 'カラム total_confidence が正常に追加されました';
    RAISE NOTICE '複合信頼度スコアにより、AI処理の品質を多角的に評価できます';
    RAISE NOTICE 'インデックス idx_documents_total_confidence が作成されました';
END $$;

COMMIT;

-- 【確認クエリ】カラムが正しく追加されたか確認
-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'documents'
-- AND column_name = 'total_confidence';

-- 【確認クエリ】インデックスが正しく作成されたか確認
-- SELECT
--     indexname,
--     indexdef
-- FROM pg_indexes
-- WHERE tablename = 'documents'
-- AND indexname = 'idx_documents_total_confidence';

-- 【サンプルクエリ】total_confidenceでソート
-- SELECT
--     id,
--     file_name,
--     doc_type,
--     confidence as model_confidence,
--     total_confidence,
--     created_at
-- FROM documents
-- WHERE total_confidence IS NOT NULL
-- ORDER BY total_confidence DESC
-- LIMIT 10;

-- 【分析クエリ】信頼度レベル別の統計
-- SELECT
--     CASE
--         WHEN total_confidence >= 0.9 THEN 'very_high'
--         WHEN total_confidence >= 0.75 THEN 'high'
--         WHEN total_confidence >= 0.6 THEN 'medium'
--         WHEN total_confidence >= 0.4 THEN 'low'
--         ELSE 'very_low'
--     END as confidence_level,
--     COUNT(*) as count,
--     ROUND(AVG(total_confidence)::numeric, 3) as avg_confidence,
--     ROUND(MIN(total_confidence)::numeric, 3) as min_confidence,
--     ROUND(MAX(total_confidence)::numeric, 3) as max_confidence
-- FROM documents
-- WHERE total_confidence IS NOT NULL
-- GROUP BY confidence_level
-- ORDER BY avg_confidence DESC;
