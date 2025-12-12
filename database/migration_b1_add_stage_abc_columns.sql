-- B1リネーム: Stage ABC命名規則のカラム追加
-- 実行場所: Supabase SQL Editor
-- 実行日: 2025-12-12
-- 設計書: INCREMENTAL_LEARNING_GUIDE_v2.md B1リネームに基づく

BEGIN;

-- 1. Stage ABC命名規則の新カラムを追加
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS stageA_classifier_model TEXT,  -- Stage A分類AIモデル 例: gemini-2.5-flash
ADD COLUMN IF NOT EXISTS stageC_extractor_model TEXT;   -- Stage C詳細抽出AIモデル 例: claude-haiku-4-5

-- 2. 既存のvision_modelをstageB_vision_modelにリネーム
ALTER TABLE documents
RENAME COLUMN vision_model TO stageB_vision_model;

-- 3. コメントの追加（ドキュメント化）
COMMENT ON COLUMN documents.stageA_classifier_model IS 'Stage A分類AIモデル 例: gemini-2.5-flash';
COMMENT ON COLUMN documents.stageB_vision_model IS 'Stage B Vision処理AIモデル（旧: vision_model）例: gemini-2.5-pro';
COMMENT ON COLUMN documents.stageC_extractor_model IS 'Stage C詳細抽出AIモデル 例: claude-haiku-4-5';

COMMIT;

-- 実行確認クエリ
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'documents'
AND column_name IN (
    'stageA_classifier_model',
    'stageB_vision_model',
    'stageC_extractor_model',
    'text_extraction_model'
)
ORDER BY column_name;
