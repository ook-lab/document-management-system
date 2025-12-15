-- 【実行場所】: Supabase SQL Editor
-- 【目的】: Stage命名をstage1/stage2からstageA/B/Cに変更
-- 【実施日】: 2025-12-12
-- 【参考】: PROJECT_EVALUATION_REPORT_20251212.md - B1: Stage命名の再構成

-- 3ルート構成:
-- - Classroom/ファイル: stageA (Flash) → stageB (Pro) → stageC (Haiku)
-- - メール: stageA (Flash-lite) → stageB (Flash) → stageC (Flash)

BEGIN;

-- ============================================
-- documentsテーブルのカラム名変更
-- ============================================

-- stage1_model → stageA_classifier_model
ALTER TABLE documents
RENAME COLUMN stage1_model TO stageA_classifier_model;

-- vision_model → stageB_vision_model（既存のvision_modelカラムがある場合）
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'documents' AND column_name = 'vision_model'
    ) THEN
        ALTER TABLE documents RENAME COLUMN vision_model TO stageB_vision_model;
    ELSE
        -- vision_modelカラムが存在しない場合は新規作成
        ALTER TABLE documents ADD COLUMN stageB_vision_model TEXT;
    END IF;
END $$;

-- stage2_model → stageC_extractor_model
ALTER TABLE documents
RENAME COLUMN stage2_model TO stageC_extractor_model;

-- ============================================
-- 新規カラムの追加: ingestion_route
-- ============================================
-- 'classroom', 'drive', 'gmail' のいずれか

ALTER TABLE documents
ADD COLUMN IF NOT EXISTS ingestion_route VARCHAR(50);

-- 既存データへのingestion_route推定（ベストエフォート）
-- source_typeから推定
UPDATE documents
SET ingestion_route = CASE
    WHEN source_type = 'classroom_attachment' THEN 'classroom'
    WHEN source_type = 'drive' THEN 'drive'
    WHEN source_type = 'email_attachment' THEN 'gmail'
    ELSE 'unknown'
END
WHERE ingestion_route IS NULL;

-- ============================================
-- コメント追加（ドキュメント化）
-- ============================================

COMMENT ON COLUMN documents.stageA_classifier_model IS 'Stage A分類AIモデル（旧: stage1_model）- 例: gemini-2.5-flash, gemini-2.5-flash-lite';
COMMENT ON COLUMN documents.stageB_vision_model IS 'Stage B Vision処理AIモデル（旧: vision_model）- 例: gemini-2.5-pro, gemini-2.5-flash';
COMMENT ON COLUMN documents.stageC_extractor_model IS 'Stage C詳細抽出AIモデル（旧: stage2_model）- 例: claude-haiku-4-5, gemini-2.5-flash';
COMMENT ON COLUMN documents.ingestion_route IS '取り込みルート: classroom（Classroom投稿）, drive（Driveファイル）, gmail（メール）';

-- インデックス作成（ingestion_routeによるフィルタリング用）
CREATE INDEX IF NOT EXISTS idx_documents_ingestion_route ON documents(ingestion_route);

COMMIT;

-- ============================================
-- 確認クエリ
-- ============================================
-- 実行後、以下のクエリで確認してください：
--
-- SELECT
--   stageA_classifier_model,
--   stageB_vision_model,
--   stageC_extractor_model,
--   ingestion_route,
--   COUNT(*) as count
-- FROM documents
-- GROUP BY stageA_classifier_model, stageB_vision_model, stageC_extractor_model, ingestion_route;
