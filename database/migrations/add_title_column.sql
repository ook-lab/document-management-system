-- Rawdata_FILE_AND_MAILテーブルにtitleカラムを追加
-- Stage Iで生成されたタイトルを保存する

ALTER TABLE "Rawdata_FILE_AND_MAIL"
ADD COLUMN IF NOT EXISTS title TEXT;

-- コメント追加
COMMENT ON COLUMN "Rawdata_FILE_AND_MAIL".title IS 'Stage Iで生成されたドキュメントタイトル';
