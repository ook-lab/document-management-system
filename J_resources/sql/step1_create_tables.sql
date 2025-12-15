-- ============================================================
-- ステップ1: 新テーブルとインデックスの作成
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-14
-- ============================================================

BEGIN;

-- 拡張機能の追加
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- 1. source_documents テーブル（データ層）
-- ============================================================
CREATE TABLE IF NOT EXISTS source_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- ソース情報
    source_type VARCHAR(50) NOT NULL,
    source_id VARCHAR(500) NOT NULL UNIQUE,
    source_url TEXT,
    ingestion_route VARCHAR(50),

    -- ファイル情報
    file_name VARCHAR(500),
    file_type VARCHAR(50),
    file_size_bytes BIGINT,

    -- ワークスペース・分類
    workspace VARCHAR(50),
    doc_type VARCHAR(100),

    -- コンテンツ
    full_text TEXT,
    summary TEXT,

    -- Google Classroom固有フィールド
    classroom_sender VARCHAR(500),
    classroom_sender_email VARCHAR(500),
    classroom_sent_at TIMESTAMP WITH TIME ZONE,
    classroom_subject TEXT,
    classroom_post_text TEXT,
    classroom_type VARCHAR(50),

    -- 担当者・組織
    persons TEXT[],
    organizations TEXT[],

    -- メタデータ
    metadata JSONB,
    tags TEXT[],
    document_date DATE,
    content_hash TEXT,

    -- タイムスタンプ
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE source_documents IS
'データ層: GASから送られてきた元データを保管する倉庫';

-- インデックス
CREATE INDEX IF NOT EXISTS idx_source_documents_source ON source_documents(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_source_documents_doc_type ON source_documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_source_documents_workspace ON source_documents(workspace);
CREATE INDEX IF NOT EXISTS idx_source_documents_date ON source_documents(document_date);
CREATE INDEX IF NOT EXISTS idx_source_documents_tags ON source_documents USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_source_documents_metadata ON source_documents USING GIN(metadata);
CREATE INDEX IF NOT EXISTS idx_source_documents_content_hash ON source_documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_source_documents_ingestion_route ON source_documents(ingestion_route);
CREATE INDEX IF NOT EXISTS idx_source_documents_created_at ON source_documents(created_at DESC);

-- ============================================================
-- 2. process_logs テーブル（処理層）
-- ============================================================
CREATE TABLE IF NOT EXISTS process_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,

    -- 処理ステータス
    processing_status VARCHAR(50) DEFAULT 'pending',
    processing_stage TEXT,

    -- AIモデル情報
    stageA_classifier_model TEXT,
    stageB_vision_model TEXT,
    stageC_extractor_model TEXT,
    text_extraction_model TEXT,
    prompt_version TEXT DEFAULT 'v1.0',
    stage1_needs_processing BOOLEAN DEFAULT true,

    -- パフォーマンス
    processing_duration_ms INTEGER,
    inference_time TIMESTAMP WITH TIME ZONE,

    -- エラー情報
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,

    -- バージョン管理
    version INTEGER DEFAULT 1,
    updated_by TEXT,

    -- タイムスタンプ
    processed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE process_logs IS
'処理層: AIやGASの処理履歴を記録';

-- インデックス
CREATE INDEX IF NOT EXISTS idx_process_logs_document_id ON process_logs(document_id);
CREATE INDEX IF NOT EXISTS idx_process_logs_status ON process_logs(processing_status);
CREATE INDEX IF NOT EXISTS idx_process_logs_stage ON process_logs(processing_stage);
CREATE INDEX IF NOT EXISTS idx_process_logs_processed_at ON process_logs(processed_at DESC);
CREATE INDEX IF NOT EXISTS idx_process_logs_created_at ON process_logs(created_at DESC);

-- ============================================================
-- 3. search_index テーブル（検索層）
-- ============================================================
CREATE TABLE IF NOT EXISTS search_index (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,

    -- チャンク情報
    chunk_index INTEGER NOT NULL,
    chunk_content TEXT NOT NULL,
    chunk_size INTEGER NOT NULL,

    -- チャンク種別
    chunk_type VARCHAR(50) DEFAULT 'content_small',
    search_weight FLOAT DEFAULT 1.0,

    -- ベクトル検索
    embedding vector(1536) NOT NULL,

    -- メタデータ
    page_numbers INTEGER[],
    section_title TEXT,

    -- タイムスタンプ
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- 複合ユニーク制約
    UNIQUE(document_id, chunk_index)
);

COMMENT ON TABLE search_index IS
'検索層: ユーザーが検索するときに見る場所';

-- インデックス
CREATE INDEX IF NOT EXISTS idx_search_index_document_id ON search_index(document_id);
CREATE INDEX IF NOT EXISTS idx_search_index_embedding ON search_index USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_search_index_chunk_index ON search_index(chunk_index);
CREATE INDEX IF NOT EXISTS idx_search_index_chunk_type ON search_index(chunk_type);
CREATE INDEX IF NOT EXISTS idx_search_index_doc_type ON search_index(document_id, chunk_type);

-- ============================================================
-- 4. トリガー関数
-- ============================================================
CREATE OR REPLACE FUNCTION refresh_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- トリガー作成
DROP TRIGGER IF EXISTS trigger_source_documents_updated_at ON source_documents;
CREATE TRIGGER trigger_source_documents_updated_at
  BEFORE UPDATE ON source_documents
  FOR EACH ROW
  EXECUTE PROCEDURE refresh_updated_at_column();

DROP TRIGGER IF EXISTS trigger_process_logs_updated_at ON process_logs;
CREATE TRIGGER trigger_process_logs_updated_at
  BEFORE UPDATE ON process_logs
  FOR EACH ROW
  EXECUTE PROCEDURE refresh_updated_at_column();

DROP TRIGGER IF EXISTS trigger_search_index_updated_at ON search_index;
CREATE TRIGGER trigger_search_index_updated_at
  BEFORE UPDATE ON search_index
  FOR EACH ROW
  EXECUTE PROCEDURE refresh_updated_at_column();

COMMIT;

-- ============================================================
-- 完了メッセージ
-- ============================================================
SELECT 'ステップ1完了: 新テーブルとインデックスの作成が成功しました' AS status;
