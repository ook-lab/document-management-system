-- Add text_extraction_model and vision_model columns
-- Stage 1では分類用AIとVision用AIの2つを使用しているため、分けて記録します
--
-- 実行方法: Supabase SQL Editor で実行してください
--
-- 追加する列:
-- 1. text_extraction_model: テキスト抽出に使用したツール (pdfplumber, python-docx, python-pptx等)
-- 2. vision_model: Vision処理に使用したAIモデル (gemini-2.0-flash-exp等)

BEGIN;

-- 1. text_extraction_model 列を追加
ALTER TABLE documents ADD COLUMN IF NOT EXISTS text_extraction_model TEXT;

-- 2. vision_model 列を追加
ALTER TABLE documents ADD COLUMN IF NOT EXISTS vision_model TEXT;

-- カラムコメントを追加
COMMENT ON COLUMN documents.stage1_model IS 'Stage 1分類AIモデル (例: gemini-2.5-flash)';
COMMENT ON COLUMN documents.stage2_model IS 'Stage 2詳細抽出AIモデル (例: claude-haiku-4-5-20251001)';
COMMENT ON COLUMN documents.text_extraction_model IS 'テキスト抽出ツール (例: pdfplumber, python-docx, python-pptx)';
COMMENT ON COLUMN documents.vision_model IS 'Vision処理AIモデル (例: gemini-2.5-flash, gemini-2.5-pro)';

COMMIT;
