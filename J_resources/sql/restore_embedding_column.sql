-- =========================================
-- embeddingカラムの復元
-- 誤って削除された embedding カラムを復元します
-- =========================================

BEGIN;

-- Step 1: embeddingカラムを追加
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS embedding vector(1536);

-- Step 2: インデックスを作成（検索パフォーマンス向上）
CREATE INDEX IF NOT EXISTS documents_embedding_idx
ON documents USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Step 3: 既存ドキュメントのembeddingを再生成する必要があります
-- これはPythonスクリプトで実行する必要があります
-- コメント: 全ドキュメントのembeddingを再生成するには、
-- reprocess_all_documents.py などのスクリプトを使用してください

COMMIT;

-- =========================================
-- 実行後の手順
-- =========================================
-- 1. このSQLを実行してembeddingカラムを復元
-- 2. Pythonスクリプトで全ドキュメントのembeddingを再生成
--    python scripts/regenerate_embeddings.py
-- 3. embedding再生成完了後、元の検索関数に戻す
