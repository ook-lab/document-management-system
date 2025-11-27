-- 【実行場所】: Supabase SQL Editor
-- 【対象】: documents テーブル
-- 【実行方法】: SupabaseダッシュボードでSQL Editorに貼り付け、実行
-- 【目的】: content_hash カラムにインデックスを追加し、重複検知のパフォーマンスを向上

-- Phase 2 (Track 3) - 重複検知機能の実装
-- AUTO_INBOX_COMPLETE_v3.0.md の「2.3.3 重複検知機能（content_hash）」に準拠

BEGIN;

-- content_hash カラムは既に schema_v4_unified.sql で定義済み
-- ここではインデックスのみを追加

-- content_hash カラムへのインデックス作成
-- 重複チェックのパフォーマンスを向上させる
CREATE INDEX IF NOT EXISTS idx_documents_content_hash
ON documents(content_hash)
WHERE content_hash IS NOT NULL;

-- インデックス作成の確認
COMMENT ON INDEX idx_documents_content_hash IS
'content_hashによる重複検知を高速化するためのインデックス。Phase 2で追加。';

-- 統計情報
DO $$
BEGIN
    RAISE NOTICE 'インデックス idx_documents_content_hash が正常に作成されました';
    RAISE NOTICE 'content_hashカラムによる重複検知が高速化されました';
    RAISE NOTICE '重複ファイルはAI処理をスキップし、コストを削減します';
END $$;

COMMIT;

-- 【確認クエリ】インデックスが正しく作成されたか確認
-- SELECT
--     indexname,
--     indexdef
-- FROM pg_indexes
-- WHERE tablename = 'documents'
-- AND indexname = 'idx_documents_content_hash';

-- 【テストクエリ】重複検知のパフォーマンステスト
-- EXPLAIN ANALYZE
-- SELECT id, file_name, content_hash
-- FROM documents
-- WHERE content_hash = 'test_hash_value';
