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
    stage1_needs_processing BOOLEAN DEFAULT true,
    
    -- Stage 2結果(Claude) / 最終確定
    doc_type VARCHAR(100),  -- 最終確定doc_type
    workspace VARCHAR(50),  -- 最終確定workspace
    
    -- コンテンツ
    full_text TEXT,
    summary TEXT,

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
    
    -- 品質管理・追跡 (v4.0拡張 → v4.1 Stage ABC命名)
    stageA_classifier_model TEXT,   -- Stage A分類AIモデル (旧: stage1_model) 例: gemini-2.5-flash
    stageB_vision_model TEXT,       -- Stage B Vision処理AIモデル (旧: vision_model) 例: gemini-2.5-pro
    stageC_extractor_model TEXT,    -- Stage C詳細抽出AIモデル (旧: stage2_model) 例: claude-haiku-4-5
    text_extraction_model TEXT,     -- テキスト抽出ツール (例: pdfplumber, python-docx, python-pptx)
    prompt_version TEXT DEFAULT 'v1.0',
    content_hash TEXT, -- 重複検知用
    ingestion_route VARCHAR(50),    -- 取り込みルート: 'classroom', 'drive', 'gmail'
    
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

-- ============================================================
-- C2: correction_history テーブル作成 (2025-12-12統合)
-- 目的: ユーザーによるメタデータ修正履歴を記録、ロールバック機能提供
-- ============================================================
CREATE TABLE IF NOT EXISTS correction_history (
    id BIGSERIAL PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    old_metadata JSONB NOT NULL,  -- 修正前のメタデータ
    new_metadata JSONB NOT NULL,  -- 修正後のメタデータ
    corrector_email TEXT,         -- 修正者のメールアドレス
    corrected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    correction_type TEXT DEFAULT 'manual',  -- 'manual' or 'automatic'
    notes TEXT  -- 修正に関するメモ
);

COMMENT ON TABLE correction_history IS
'ユーザーがReview UIで行ったメタデータ修正の履歴を記録';

-- document_chunks テーブル作成（チャンク分割対応）
-- 目的: 1文書複数embeddingによる検索精度向上
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    -- チャンク情報
    chunk_index INTEGER NOT NULL,  -- 0から始まる連番
    chunk_text TEXT NOT NULL,      -- チャンクのテキスト
    chunk_size INTEGER NOT NULL,   -- 文字数

    -- B2: メタデータ別ベクトル化戦略 (2025-12-12追加)
    chunk_type VARCHAR(50) DEFAULT 'content_small',  -- チャンク種別
        -- 'title': タイトル専用 (weight=2.0)
        -- 'summary': サマリー専用 (weight=1.5)
        -- 'date': 日付情報 (weight=1.3)
        -- 'tags': タグ情報 (weight=1.2)
        -- 'content_small': 本文小チャンク (weight=1.0)
        -- 'content_large': 本文大チャンク (weight=1.0)
        -- 'synthetic': 合成チャンク (weight=1.0)
    search_weight FLOAT DEFAULT 1.0,  -- 検索時の重み付け係数

    -- ベクトル検索 (1536次元: OpenAI Embedding)
    embedding vector(1536) NOT NULL,

    -- メタデータ
    page_numbers INTEGER[],        -- このチャンクが含むページ番号（PDFの場合）
    section_title TEXT,            -- セクション見出し（該当する場合）

    -- タイムスタンプ
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- 複合ユニーク制約（同一文書内でchunk_indexは一意）
    UNIQUE(document_id, chunk_index)
);

-- インデックス作成 (COMPLETE_IMPLEMENTATION_GUIDE_v3.md と FINAL_UNIFIED_COMPLETE_v4.md の統合)
CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_documents_doc_type ON documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_documents_workspace ON documents(workspace);
CREATE INDEX IF NOT EXISTS idx_documents_date ON documents(document_date);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(processing_status);
CREATE INDEX IF NOT EXISTS idx_documents_tags ON documents USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_documents_metadata ON documents USING GIN(metadata);
CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON documents (content_hash);
CREATE INDEX IF NOT EXISTS idx_documents_ingestion_route ON documents(ingestion_route);

CREATE INDEX IF NOT EXISTS idx_emails_gmail_id ON emails(gmail_id);
CREATE INDEX IF NOT EXISTS idx_emails_sender ON emails(sender_email);

CREATE INDEX IF NOT EXISTS idx_corrections_document_id ON corrections (document_id);
CREATE INDEX IF NOT EXISTS idx_corrections_status ON corrections (status);

-- C2: correction_history用インデックス
CREATE INDEX IF NOT EXISTS idx_correction_history_document_id
ON correction_history(document_id, corrected_at DESC);
CREATE INDEX IF NOT EXISTS idx_correction_history_corrector
ON correction_history(corrector_email) WHERE corrector_email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_correction_history_corrected_at
ON correction_history(corrected_at DESC);

-- document_chunks用インデックス
CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding ON document_chunks USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_document_chunks_chunk_index ON document_chunks(chunk_index);
-- B2: メタデータ別ベクトル化戦略用インデックス
CREATE INDEX IF NOT EXISTS idx_document_chunks_chunk_type ON document_chunks(chunk_type);
CREATE INDEX IF NOT EXISTS idx_document_chunks_doc_type ON document_chunks(document_id, chunk_type);

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

DROP TRIGGER IF EXISTS trigger_set_updated_at_chunks ON document_chunks;
CREATE TRIGGER trigger_set_updated_at_chunks
  BEFORE UPDATE ON document_chunks
  FOR EACH ROW
  EXECUTE PROCEDURE refresh_updated_at_column();

-- ============================================================
-- C1: 統一検索関数 (2025-12-12)
-- 旧hybrid_searchを廃止し、B2のメタデータ重み付けに対応
-- ============================================================
CREATE OR REPLACE FUNCTION unified_search(
    query_text TEXT,
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.0,
    match_count INT DEFAULT 10,
    vector_weight FLOAT DEFAULT 0.7,
    fulltext_weight FLOAT DEFAULT 0.3,
    filter_doc_types TEXT[] DEFAULT NULL,
    filter_chunk_types TEXT[] DEFAULT NULL,
    filter_workspace TEXT DEFAULT NULL
)
RETURNS TABLE (
    document_id UUID,
    file_name VARCHAR,
    doc_type VARCHAR,
    workspace VARCHAR,
    document_date DATE,
    metadata JSONB,
    summary TEXT,
    full_text TEXT,
    best_chunk_text TEXT,
    best_chunk_type VARCHAR,
    best_chunk_id UUID,
    best_chunk_index INTEGER,
    raw_similarity FLOAT,
    weighted_similarity FLOAT,
    fulltext_score FLOAT,
    combined_score FLOAT,
    title_matched BOOLEAN,
    source_type VARCHAR,
    source_url TEXT,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    WITH chunk_scores AS (
        SELECT
            dc.id AS chunk_id,
            dc.document_id AS doc_id,
            dc.chunk_index,
            dc.chunk_text,
            dc.chunk_type,
            COALESCE(dc.search_weight, 1.0) AS search_weight,
            (1 - (dc.embedding <=> query_embedding)) AS raw_sim,
            (1 - (dc.embedding <=> query_embedding)) * COALESCE(dc.search_weight, 1.0) AS weighted_sim,
            ts_rank_cd(
                to_tsvector('simple', dc.chunk_text),
                websearch_to_tsquery('simple', query_text)
            ) AS ft_score
        FROM document_chunks dc
        JOIN documents d ON dc.document_id = d.id
        WHERE
            dc.embedding IS NOT NULL
            AND (dc.chunk_type IS NULL OR dc.chunk_type != 'content_large')
            AND (1 - (dc.embedding <=> query_embedding)) >= match_threshold
            AND (filter_chunk_types IS NULL OR dc.chunk_type = ANY(filter_chunk_types))
            AND (filter_doc_types IS NULL OR d.doc_type = ANY(filter_doc_types))
            AND (filter_workspace IS NULL OR d.workspace = filter_workspace)
            AND d.processing_status = 'completed'
    ),
    ranked_chunks AS (
        SELECT
            cs.*,
            (cs.weighted_sim * vector_weight + cs.ft_score * fulltext_weight) AS combined,
            (cs.chunk_type = 'title') AS is_title_match
        FROM chunk_scores cs
    ),
    document_best_chunks AS (
        SELECT DISTINCT ON (rc.doc_id)
            rc.chunk_id,
            rc.doc_id,
            rc.chunk_index,
            rc.chunk_text,
            rc.chunk_type,
            rc.raw_sim,
            rc.weighted_sim,
            rc.ft_score,
            rc.combined,
            rc.is_title_match
        FROM ranked_chunks rc
        ORDER BY rc.doc_id, rc.is_title_match DESC, rc.combined DESC
    )
    SELECT
        d.id AS document_id,
        d.file_name,
        d.doc_type,
        d.workspace,
        d.document_date,
        d.metadata,
        d.summary,
        d.full_text,
        dbc.chunk_text AS best_chunk_text,
        dbc.chunk_type::VARCHAR AS best_chunk_type,
        dbc.chunk_id AS best_chunk_id,
        dbc.chunk_index AS best_chunk_index,
        dbc.raw_sim::FLOAT AS raw_similarity,
        dbc.weighted_sim::FLOAT AS weighted_similarity,
        dbc.ft_score::FLOAT AS fulltext_score,
        dbc.combined::FLOAT AS combined_score,
        dbc.is_title_match AS title_matched,
        d.source_type,
        d.source_url,
        d.created_at
    FROM document_best_chunks dbc
    INNER JOIN documents d ON d.id = dbc.doc_id
    ORDER BY dbc.is_title_match DESC, dbc.combined DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION unified_search IS 'C1統一検索: B2メタデータ重み付け対応、タイトルマッチ優先';

-- チャンク検索関数（ベクトル検索）
CREATE OR REPLACE FUNCTION match_document_chunks(
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.0,
    match_count INT DEFAULT 50
)
RETURNS TABLE (
    chunk_id UUID,
    document_id UUID,
    chunk_index INTEGER,
    chunk_text TEXT,
    similarity FLOAT,
    -- 親ドキュメント情報も結合して返す
    file_name VARCHAR,
    doc_type VARCHAR,
    document_date DATE,
    metadata JSONB,
    summary TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id AS chunk_id,
        dc.document_id,
        dc.chunk_index,
        dc.chunk_text,
        1 - (dc.embedding <=> query_embedding) AS similarity,
        d.file_name,
        d.doc_type,
        d.document_date,
        d.metadata,
        d.summary
    FROM document_chunks dc
    JOIN documents d ON dc.document_id = d.id
    WHERE
        d.processing_status = 'completed'
        AND (1 - (dc.embedding <=> query_embedding)) > match_threshold
    ORDER BY similarity DESC
    LIMIT match_count;
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

-- documentsテーブルにchunk統計カラムを追加（add_document_chunks.sqlより）
-- 注: ALTER TABLEは既にカラムが存在する場合はスキップされます
DO $$
BEGIN
    -- chunk_count カラムを追加
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'documents' AND column_name = 'chunk_count'
    ) THEN
        ALTER TABLE documents ADD COLUMN chunk_count INTEGER DEFAULT 0;
    END IF;

    -- chunking_strategy カラムを追加
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'documents' AND column_name = 'chunking_strategy'
    ) THEN
        ALTER TABLE documents ADD COLUMN chunking_strategy VARCHAR(50) DEFAULT 'none';
    END IF;

    -- C2: latest_correction_id カラムを追加
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'documents' AND column_name = 'latest_correction_id'
    ) THEN
        ALTER TABLE documents ADD COLUMN latest_correction_id BIGINT REFERENCES correction_history(id);
    END IF;
END $$;

-- C2: correction_history用ロールバック関数
CREATE OR REPLACE FUNCTION rollback_document_metadata(p_document_id UUID)
RETURNS JSONB AS $$
DECLARE
    v_latest_correction_id BIGINT;
    v_old_metadata JSONB;
BEGIN
    SELECT latest_correction_id INTO v_latest_correction_id
    FROM documents WHERE id = p_document_id;

    IF v_latest_correction_id IS NULL THEN
        RAISE EXCEPTION '修正履歴が存在しません: document_id=%', p_document_id;
    END IF;

    SELECT old_metadata INTO v_old_metadata
    FROM correction_history WHERE id = v_latest_correction_id;

    UPDATE documents
    SET metadata = v_old_metadata,
        latest_correction_id = NULL
    WHERE id = p_document_id;

    RETURN v_old_metadata;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION rollback_document_metadata IS
'C2: 指定ドキュメントのメタデータを最新修正前の状態にロールバック';

COMMIT;