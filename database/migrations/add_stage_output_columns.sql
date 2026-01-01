-- マイグレーション: Stage出力保存用カラム追加
-- 作成日: 2026-01-01
-- 目的: E-1~E-5, F (Text OCR/Layout OCR/Visual Elements), H, I, J の各ステージ出力を保存

-- Stage E: PDFテキスト抽出（5種類のエンジン）
ALTER TABLE "Rawdata_FILE_AND_MAIL"
ADD COLUMN IF NOT EXISTS stage_e1_text TEXT,
ADD COLUMN IF NOT EXISTS stage_e2_text TEXT,
ADD COLUMN IF NOT EXISTS stage_e3_text TEXT,
ADD COLUMN IF NOT EXISTS stage_e4_text TEXT,
ADD COLUMN IF NOT EXISTS stage_e5_text TEXT;

-- Stage F: OCR（3種類）
ALTER TABLE "Rawdata_FILE_AND_MAIL"
ADD COLUMN IF NOT EXISTS stage_f_text_ocr TEXT,
ADD COLUMN IF NOT EXISTS stage_f_layout_ocr TEXT,
ADD COLUMN IF NOT EXISTS stage_f_visual_elements TEXT;

-- Stage H: 正規化テキスト
ALTER TABLE "Rawdata_FILE_AND_MAIL"
ADD COLUMN IF NOT EXISTS stage_h_normalized TEXT;

-- Stage I: 構造化テキスト
ALTER TABLE "Rawdata_FILE_AND_MAIL"
ADD COLUMN IF NOT EXISTS stage_i_structured TEXT;

-- Stage J: チャンクJSON（デバッグ用）
ALTER TABLE "Rawdata_FILE_AND_MAIL"
ADD COLUMN IF NOT EXISTS stage_j_chunks_json JSONB;

-- コメント追加
COMMENT ON COLUMN "Rawdata_FILE_AND_MAIL".stage_e1_text IS 'Stage E-1: PyPDF2で抽出したテキスト';
COMMENT ON COLUMN "Rawdata_FILE_AND_MAIL".stage_e2_text IS 'Stage E-2: pdfminerで抽出したテキスト';
COMMENT ON COLUMN "Rawdata_FILE_AND_MAIL".stage_e3_text IS 'Stage E-3: PyMuPDFで抽出したテキスト';
COMMENT ON COLUMN "Rawdata_FILE_AND_MAIL".stage_e4_text IS 'Stage E-4: pdfplumberで抽出したテキスト';
COMMENT ON COLUMN "Rawdata_FILE_AND_MAIL".stage_e5_text IS 'Stage E-5: PDFiumで抽出したテキスト';

COMMENT ON COLUMN "Rawdata_FILE_AND_MAIL".stage_f_text_ocr IS 'Stage F: Text OCR（Tesseract）';
COMMENT ON COLUMN "Rawdata_FILE_AND_MAIL".stage_f_layout_ocr IS 'Stage F: Layout OCR（Tesseract + レイアウト保持）';
COMMENT ON COLUMN "Rawdata_FILE_AND_MAIL".stage_f_visual_elements IS 'Stage F: Visual Elements（視覚要素の説明、Claude 3.5 Sonnet）';

COMMENT ON COLUMN "Rawdata_FILE_AND_MAIL".stage_h_normalized IS 'Stage H: 正規化後のテキスト';
COMMENT ON COLUMN "Rawdata_FILE_AND_MAIL".stage_i_structured IS 'Stage I: 構造化後のテキスト';
COMMENT ON COLUMN "Rawdata_FILE_AND_MAIL".stage_j_chunks_json IS 'Stage J: 生成されたチャンク（JSONB形式、デバッグ用）';
