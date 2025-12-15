-- full_text カラムを attachment_text にリネーム
-- 理由: full_textは誤解を招く名前。実際には添付ファイルから抽出したテキストのみを保存
--
-- 設計の明確化:
-- - attachment_text: 添付ファイル（PDF, DOCX等）から抽出したテキスト
-- - classroom_subject: Classroom投稿の件名
-- - classroom_post_text: Classroom投稿の本文
-- - summary: AI生成のサマリー
--
-- 注意: full_textは以下の理由で不要と判明：
-- 1. AI処理の入力ではない（その場で抽出したextracted_textを使用）
-- 2. チャンク化で使われていない（extracted_textを使用）
-- 3. 再処理で使われていない（各要素を個別に使用）
-- 4. UI表示で使われていない（summaryや各要素を個別表示）

-- Step 1: カラムをリネーム
ALTER TABLE documents
RENAME COLUMN full_text TO attachment_text;

-- Step 2: コメントを追加して意味を明確化
COMMENT ON COLUMN documents.attachment_text IS '添付ファイル（PDF, DOCX等）から抽出したテキスト。Classroom投稿本文はclassroom_subject/classroom_post_textに保存される。';

-- Step 3: 確認用クエリ
-- リネーム後のカラムを確認
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'documents'
    AND column_name IN ('attachment_text', 'classroom_subject', 'classroom_post_text', 'summary')
ORDER BY column_name;

-- Step 4: データ確認
-- Classroom投稿（添付ファイルあり）のサンプル
SELECT
    id,
    file_name,
    source_type,
    LENGTH(attachment_text) as attachment_text_length,
    LENGTH(classroom_subject) as classroom_subject_length,
    LENGTH(classroom_post_text) as classroom_post_text_length
FROM documents
WHERE source_type = 'classroom'
    AND attachment_text IS NOT NULL
LIMIT 5;

-- Classroom投稿（添付ファイルなし）のサンプル
SELECT
    id,
    file_name,
    source_type,
    LENGTH(attachment_text) as attachment_text_length,
    LENGTH(classroom_subject) as classroom_subject_length,
    LENGTH(classroom_post_text) as classroom_post_text_length
FROM documents
WHERE source_type = 'classroom_text'
LIMIT 5;
