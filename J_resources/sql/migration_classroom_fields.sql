-- Classroom情報とモデル記録用フィールドの追加
-- 実行場所: Supabase SQL Editor
-- 実行日: 2025-12-10

BEGIN;

-- 1. Classroom情報用フィールドの追加
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS classroom_sender VARCHAR(500),      -- Classroom送信者名
ADD COLUMN IF NOT EXISTS classroom_sender_email VARCHAR(500), -- Classroom送信者メールアドレス
ADD COLUMN IF NOT EXISTS classroom_sent_at TIMESTAMP WITH TIME ZONE, -- Classroom送信日時
ADD COLUMN IF NOT EXISTS classroom_subject TEXT,             -- Classroom件名（タイトル）
ADD COLUMN IF NOT EXISTS classroom_course_id VARCHAR(200),   -- ClassroomコースID
ADD COLUMN IF NOT EXISTS classroom_course_name VARCHAR(500); -- Classroomコース名

-- 2. テキスト抽出とVision用の別々のモデルフィールドを追加
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS text_extraction_model TEXT,         -- テキスト抽出に使用したモデル（pdfplumber等）
ADD COLUMN IF NOT EXISTS vision_model TEXT;                  -- Vision処理に使用したモデル（Gemini Vision等）

-- 3. インデックスの追加（検索パフォーマンス向上）
CREATE INDEX IF NOT EXISTS idx_documents_classroom_sender ON documents(classroom_sender_email);
CREATE INDEX IF NOT EXISTS idx_documents_classroom_sent_at ON documents(classroom_sent_at);
CREATE INDEX IF NOT EXISTS idx_documents_classroom_course ON documents(classroom_course_id);

-- 4. コメントの追加（ドキュメント化）
COMMENT ON COLUMN documents.classroom_sender IS 'Google Classroom送信者の表示名';
COMMENT ON COLUMN documents.classroom_sender_email IS 'Google Classroom送信者のメールアドレス';
COMMENT ON COLUMN documents.classroom_sent_at IS 'Google Classroomでの送信日時';
COMMENT ON COLUMN documents.classroom_subject IS 'Google Classroomの投稿件名・タイトル';
COMMENT ON COLUMN documents.classroom_course_id IS 'Google ClassroomのコースID';
COMMENT ON COLUMN documents.classroom_course_name IS 'Google Classroomのコース名';
COMMENT ON COLUMN documents.text_extraction_model IS 'テキスト抽出に使用したモデル（pdfplumber, python-docx等）';
COMMENT ON COLUMN documents.vision_model IS 'Vision処理に使用したAIモデル（Gemini Vision, Claude Vision等）';

COMMIT;

-- 実行確認クエリ
SELECT column_name, data_type, character_maximum_length
FROM information_schema.columns
WHERE table_name = 'documents'
AND column_name IN (
    'classroom_sender',
    'classroom_sender_email',
    'classroom_sent_at',
    'classroom_subject',
    'classroom_course_id',
    'classroom_course_name',
    'text_extraction_model',
    'vision_model'
)
ORDER BY column_name;
