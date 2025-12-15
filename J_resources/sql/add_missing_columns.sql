-- source_documentsテーブルに不足しているカラムを追加
-- 実行場所: Supabase SQL Editor

BEGIN;

-- 日付関連
ALTER TABLE source_documents
ADD COLUMN IF NOT EXISTS all_mentioned_dates DATE[];

ALTER TABLE source_documents
ADD COLUMN IF NOT EXISTS relevant_date DATE;

-- 処理状態管理
ALTER TABLE source_documents
ADD COLUMN IF NOT EXISTS processing_status VARCHAR(50) DEFAULT 'pending';

ALTER TABLE source_documents
ADD COLUMN IF NOT EXISTS processing_stage TEXT;

ALTER TABLE source_documents
ADD COLUMN IF NOT EXISTS error_message TEXT;

-- AIモデル追跡（Stage A/B/C命名規則）
ALTER TABLE source_documents
ADD COLUMN IF NOT EXISTS stagea_classifier_model TEXT;

ALTER TABLE source_documents
ADD COLUMN IF NOT EXISTS stageb_vision_model TEXT;

ALTER TABLE source_documents
ADD COLUMN IF NOT EXISTS stagec_extractor_model TEXT;

-- その他の品質管理カラム
ALTER TABLE source_documents
ADD COLUMN IF NOT EXISTS text_extraction_model TEXT;

ALTER TABLE source_documents
ADD COLUMN IF NOT EXISTS prompt_version TEXT DEFAULT 'v1.0';

ALTER TABLE source_documents
ADD COLUMN IF NOT EXISTS processing_duration_ms INTEGER;

ALTER TABLE source_documents
ADD COLUMN IF NOT EXISTS inference_time TIMESTAMP WITH TIME ZONE;

-- 既存ドキュメントの処理ステータスを更新
UPDATE source_documents
SET processing_status = 'completed'
WHERE processing_status IS NULL;

COMMIT;

-- 確認クエリ
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'source_documents'
ORDER BY column_name;
