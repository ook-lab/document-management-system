-- ====================================================================
-- 商品名正規化テーブル作成スクリプト
-- ====================================================================
-- 目的: OCRテキストから正式商品名への変換辞書を作成
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-25
-- ====================================================================

BEGIN;

-- ====================================================================
-- 商品名正規化マスタ（OCR → 正式商品名）
-- ====================================================================
-- 例: 「ｻｯﾎﾟﾛ1ﾊﾞﾝ ｼｵﾗ-ﾒﾝ」→「サッポロ一番 塩ラーメン」

CREATE TABLE IF NOT EXISTS "MASTER_Product_normalize" (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ocr_text TEXT NOT NULL,                 -- OCRで読み取った生テキスト
  official_name TEXT NOT NULL,            -- 正規化された正式商品名
  confidence_score FLOAT DEFAULT 1.0,     -- 正規化の信頼度（0.0-1.0）
  source TEXT DEFAULT 'manual',           -- 'manual', 'gemini', 'auto_learning'
  notes TEXT,                             -- 備考
  usage_count INTEGER DEFAULT 0,          -- 使用回数（学習用）
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(ocr_text)                        -- 同じOCRテキストは1つの正式名称のみ
);

CREATE INDEX idx_MASTER_Product_normalize_ocr ON "MASTER_Product_normalize"(ocr_text);
CREATE INDEX idx_MASTER_Product_normalize_official ON "MASTER_Product_normalize"(official_name);
CREATE INDEX idx_MASTER_Product_normalize_usage ON "MASTER_Product_normalize"(usage_count DESC);

COMMENT ON TABLE "MASTER_Product_normalize" IS '商品名正規化辞書 - OCRテキスト→正式商品名のマッピング';

COMMIT;

-- ====================================================================
-- 実行後の確認クエリ
-- ====================================================================

-- テーブル作成確認
-- SELECT table_name
-- FROM information_schema.tables
-- WHERE table_schema = 'public'
-- AND table_name = 'MASTER_Product_normalize';

-- 商品マスター3テーブルの確認
-- SELECT table_name
-- FROM information_schema.tables
-- WHERE table_schema = 'public'
-- AND table_name LIKE 'MASTER_Product_%'
-- ORDER BY table_name;
