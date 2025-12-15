-- B1統合マイグレーション: 全てのモデル記録カラムを追加
-- 実行場所: Supabase SQL Editor
-- 実行日: 2025-12-12
-- 設計書: INCREMENTAL_LEARNING_GUIDE_v2.md B1リネームに基づく

BEGIN;

-- 1. Stage ABC命名規則のカラムを追加
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS stageA_classifier_model TEXT,   -- Stage A分類AIモデル 例: gemini-2.5-flash
ADD COLUMN IF NOT EXISTS stageB_vision_model TEXT,       -- Stage B Vision処理AIモデル 例: gemini-2.5-pro
ADD COLUMN IF NOT EXISTS stageC_extractor_model TEXT,    -- Stage C詳細抽出AIモデル 例: claude-haiku-4-5
ADD COLUMN IF NOT EXISTS text_extraction_model TEXT;     -- テキスト抽出ツール 例: pdfplumber, python-docx

-- 2. コメントの追加（ドキュメント化）
COMMENT ON COLUMN documents.stageA_classifier_model IS 'Stage A分類AIモデル 例: gemini-2.5-flash';
COMMENT ON COLUMN documents.stageB_vision_model IS 'Stage B Vision処理AIモデル 例: gemini-2.5-pro';
COMMENT ON COLUMN documents.stageC_extractor_model IS 'Stage C詳細抽出AIモデル 例: claude-haiku-4-5';
COMMENT ON COLUMN documents.text_extraction_model IS 'テキスト抽出ツール 例: pdfplumber, python-docx, python-pptx';

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
