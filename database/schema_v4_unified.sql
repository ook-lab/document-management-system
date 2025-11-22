-- 【実行場所】: Supabase SQL Editor
-- 【対象ファイル】: 新規SQL実行
-- 【実行方法】: SupabaseダッシュボードでSQL Editorに貼り付け、実行

-- 設計書: FINAL_UNIFIED_COMPLETE_v4.md の「3.2 完全なSQLパッチ」に基づく

BEGIN;

-- 拡張機能の追加（pgcryptoはUUID生成、vectorはベクトル検索用）
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

-- documents テーブル作成 (v4.0統合スキーマ)
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type VARCHAR(50) NOT NULL,  -- 'drive', 'email_attachment'
    source_id VARCHAR(500) NOT NULL UNIQUE,  -- Google Drive ID等
    source_url TEXT,
    
    -- ファイル情報
    file_name VARCHAR(500),
    file_type VARCHAR(50),  -- 'pdf', 'docx', 'xlsx', etc.
    file_size_bytes BIGINT,
    
    -- Stage 1結果(Gemini)
    stage1_doc_type VARCHAR(100),
    stage1_workspace VARCHAR(50),  -- 'business', 'personal'
    stage1_confidence FLOAT,
    stage1_needs_processing BOOLEAN DEFAULT true,
    
    -- Stage 2結果(Claude) / 最終確定
    doc_type VARCHAR(100),  -- 最終確定doc_type
    workspace VARCHAR(50),  -- 最終確定workspace
    
    -- コンテンツ
    full_text TEXT,
    summary TEXT,
    
    -- ベクトル検索 (1536次元: OpenAI Embeddingの標準)
    embedding vector(1536),
    
    -- メタデータ
    metadata JSONB,
    tags TEXT[],
    document_date DATE,
    
    -- ステータス管理 (v4.0拡張)
    processing_status VARCHAR(50) DEFAULT 'pending',
    processing_stage TEXT,      -- 'stage1_only'/'stage1_and_stage2'
    inference_time TIMESTAMP WITH TIME ZONE,
    processing_duration_ms INTEGER,
    error_message TEXT,
    
    -- 品質管理・追跡 (v4.0拡張)
    extraction_confidence FLOAT,
    llm_provider TEXT,
    stage1_model TEXT,
    stage2_model TEXT,
    prompt_version TEXT DEFAULT 'v1.0',
    content_hash TEXT, -- 重複検知用
    
    -- 監査・バージョン管理 (QUALITY_CHECK_GUIDE_v2.mdより)
    version INTEGER DEFAULT 1,
    updated_by TEXT,
    update_tx_id UUID,
    
    -- タイムスタンプ
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_accessed_at TIMESTAMP
);

-- emails テーブル作成
CREATE TABLE IF NOT EXISTS emails (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gmail_id VARCHAR(500) NOT NULL UNIQUE,
    thread_id VARCHAR(500),
    
    -- Stage 1結果
    stage1_importance VARCHAR(50),
    stage1_category VARCHAR(100),
    stage1_confidence FLOAT,
    
    -- メール情報
    subject TEXT,
    sender_email VARCHAR(500),
    sender_name VARCHAR(500),
    recipients TEXT[],
    cc TEXT[],
    bcc TEXT[],
    
    -- コンテンツ
    body_text TEXT,
    body_html TEXT,
    snippet TEXT,
    
    -- ベクトル検索
    embedding vector(1536),
    
    -- メタデータ
    labels TEXT[],
    metadata JSONB,
    tags TEXT[],
    
    -- 日時
    email_date TIMESTAMP,
    received_at TIMESTAMP,
    
    -- ステータス
    is_read BOOLEAN DEFAULT false,
    is_starred BOOLEAN DEFAULT false,
    processing_status VARCHAR(50) DEFAULT 'pending',
    
    -- タイムスタンプ
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- attachments テーブル作成
CREATE TABLE IF NOT EXISTS attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_id UUID REFERENCES emails(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    
    file_name VARCHAR(500),
    mime_type VARCHAR(200),
    size_bytes BIGINT,
    
    attachment_id VARCHAR(500),
    
    is_processed BOOLEAN DEFAULT false,
    processed_at TIMESTAMP,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- corrections テーブル作成 (QUALITY_CHECK_GUIDE_v2.mdより)
CREATE TABLE IF NOT EXISTS corrections (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  original_doc_type TEXT,
  corrected_doc_type TEXT,
  original_metadata JSONB,
  corrected_metadata JSONB,
  correction_reason TEXT,
  corrected_at TIMESTAMP WITH TIME ZONE,
  corrected_by TEXT,
  status TEXT DEFAULT 'pending',  -- pending/completed/failed/rolled_back
  tx_id UUID,
  error TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- インデックス作成 (COMPLETE_IMPLEMENTATION_GUIDE_v3.md と FINAL_UNIFIED_COMPLETE_v4.md の統合)
CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_documents_doc_type ON documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_documents_workspace ON documents(workspace);
CREATE INDEX IF NOT EXISTS idx_documents_date ON documents(document_date);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(processing_status);
CREATE INDEX IF NOT EXISTS idx_documents_tags ON documents USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_documents_metadata ON documents USING GIN(metadata);
CREATE INDEX IF NOT EXISTS idx_documents_embedding ON documents USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON documents (content_hash);

CREATE INDEX IF NOT EXISTS idx_emails_gmail_id ON emails(gmail_id);
CREATE INDEX IF NOT EXISTS idx_emails_sender ON emails(sender_email);

CREATE INDEX IF NOT EXISTS idx_corrections_document_id ON corrections (document_id);
CREATE INDEX IF NOT EXISTS idx_corrections_status ON corrections (status);

-- updated_at 自動更新トリガー (FINAL_UNIFIED_COMPLETE_v4.mdより)
CREATE OR REPLACE FUNCTION refresh_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_set_updated_at ON documents;
CREATE TRIGGER trigger_set_updated_at
  BEFORE UPDATE ON documents
  FOR EACH ROW
  EXECUTE PROCEDURE refresh_updated_at_column();

-- ハイブリッド検索関数 (COMPLETE_IMPLEMENTATION_GUIDE_v3.mdより)
CREATE OR REPLACE FUNCTION hybrid_search(
    query_text TEXT,
    query_embedding vector(1536),
    target_workspace TEXT DEFAULT NULL,
    target_type TEXT DEFAULT NULL,
    limit_results INT DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    source_type VARCHAR,
    file_name VARCHAR,
    doc_type VARCHAR,
    summary TEXT,
    document_date DATE,
    similarity_score FLOAT,
    text_rank FLOAT,
    combined_score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        d.id,
        d.source_type,
        d.file_name,
        d.doc_type,
        d.summary,
        d.document_date,
        1 - (d.embedding <=> query_embedding) AS similarity_score,
        ts_rank(to_tsvector('japanese', d.full_text), plainto_tsquery('japanese', query_text)) AS text_rank,
        (1 - (d.embedding <=> query_embedding)) * 0.7 + 
        ts_rank(to_tsvector('japanese', d.full_text), plainto_tsquery('japanese', query_text)) * 0.3 AS combined_score
    FROM documents d
    WHERE 
        (target_workspace IS NULL OR d.workspace = target_workspace)
        AND (target_type IS NULL OR d.doc_type = target_type)
        AND d.processing_status = 'completed'
    ORDER BY combined_score DESC
    LIMIT limit_results;
END;
$$ LANGUAGE plpgsql;

-- ロールバック関数 (QUALITY_CHECK_GUIDE_v2.mdより)
CREATE OR REPLACE FUNCTION rollback_correction(correction_uuid UUID)
RETURNS TEXT LANGUAGE plpgsql AS $$
DECLARE
  corr RECORD;
BEGIN
  SELECT * INTO corr FROM corrections WHERE id = correction_uuid;
  IF NOT FOUND THEN
    RETURN 'correction not found';
  END IF;

  -- documents を元の状態に戻す
  UPDATE documents
  SET doc_type = corr.original_doc_type,
      metadata = corr.original_metadata,
      version = documents.version + 1,
      updated_at = now(),
      updated_by = 'system_rollback'
  WHERE id = corr.document_id;

  -- corrections を rolled_back に
  UPDATE corrections SET status = 'rolled_back' WHERE id = correction_uuid;

  RETURN 'rollback completed';
END;
$$;


COMMIT;