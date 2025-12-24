-- ============================================
-- pgvector拡張を有効化
-- ベクトル検索を使用するために必要
-- ============================================

-- pgvector拡張を有効化
CREATE EXTENSION IF NOT EXISTS vector;

-- 確認
SELECT * FROM pg_extension WHERE extname = 'vector';
