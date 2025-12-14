-- ============================================================
-- 3層テーブル構造へのマイグレーション
-- 実行場所: Supabase SQL Editor
-- 作成日: 2025-12-14
-- ============================================================
--
-- 設計コンセプト:
--   1. source_documents (データ層): GASから送られてくる元データを保管
--   2. process_logs (処理層): AIやGASの処理履歴・ログを記録
--   3. search_index (検索層): ベクトル検索用の最適化されたデータ
--
-- ============================================================

BEGIN;

-- ============================================================
-- 1. source_documents テーブル（データ層）
-- 目的: GASから送られてきた原本データをそのまま保管
-- ============================================================
CREATE TABLE IF NOT EXISTS source_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- ソース情報
    source_type VARCHAR(50) NOT NULL,  -- 'classroom', 'classroom_text', 'drive', 'email_attachment'
    source_id VARCHAR(500) NOT NULL UNIQUE,  -- Google Drive ID, Classroom Post ID等
    source_url TEXT,
    ingestion_route VARCHAR(50),  -- 'classroom', 'drive', 'gmail'

    -- ファイル情報
    file_name VARCHAR(500),
    file_type VARCHAR(50),  -- 'pdf', 'docx', 'xlsx', etc.
    file_size_bytes BIGINT,

    -- ワークスペース・分類
    workspace VARCHAR(50),
    doc_type VARCHAR(100),

    -- コンテンツ（元データ）
    full_text TEXT,
    summary TEXT,

    -- Google Classroom固有フィールド（GASから送られてくる生データ）
    classroom_sender VARCHAR(500),
    classroom_sender_email VARCHAR(500),
    classroom_sent_at TIMESTAMP WITH TIME ZONE,
    classroom_subject TEXT,
    classroom_post_text TEXT,
    classroom_type VARCHAR(50),  -- 'お知らせ', '課題', '資料'

    -- 担当者・組織（配列）
    persons TEXT[],
    organizations TEXT[],

    -- メタデータ（JSONB: 柔軟な構造）
    metadata JSONB,
    tags TEXT[],
    document_date DATE,

    -- コンテンツハッシュ（重複検知用）
    content_hash TEXT,

    -- タイムスタンプ
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE source_documents IS
'データ層: GASから送られてきた元データを保管する倉庫。150列あっても、空欄だらけでもOK。将来AIモデルを変更する際の原本として使用。';

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

-- updated_at自動更新トリガー
CREATE OR REPLACE FUNCTION refresh_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_source_documents_updated_at ON source_documents;
CREATE TRIGGER trigger_source_documents_updated_at
  BEFORE UPDATE ON source_documents
  FOR EACH ROW
  EXECUTE PROCEDURE refresh_updated_at_column();


-- ============================================================
-- 2. process_logs テーブル（処理層）
-- 目的: AIやGASの処理履歴・エラーログを記録
-- ============================================================
CREATE TABLE IF NOT EXISTS process_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,

    -- 処理ステータス
    processing_status VARCHAR(50) DEFAULT 'pending',  -- 'pending', 'processing', 'completed', 'failed'
    processing_stage TEXT,  -- 'stage1_only', 'stage1_and_stage2', 'chunking', 'embedding'

    -- AIモデル情報
    stageA_classifier_model TEXT,  -- Stage A分類AIモデル (例: gemini-2.5-flash)
    stageB_vision_model TEXT,      -- Stage B Vision処理AIモデル (例: gemini-2.5-pro)
    stageC_extractor_model TEXT,   -- Stage C詳細抽出AIモデル (例: claude-haiku-4-5)
    text_extraction_model TEXT,    -- テキスト抽出ツール (例: pdfplumber)
    prompt_version TEXT DEFAULT 'v1.0',

    -- 処理結果
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
'処理層: AIやGASの処理履歴を記録。いつ、誰が、どのモデルを使って処理したか、エラーは出たかなどを記録。デバッグ用。';

-- インデックス
CREATE INDEX IF NOT EXISTS idx_process_logs_document_id ON process_logs(document_id);
CREATE INDEX IF NOT EXISTS idx_process_logs_status ON process_logs(processing_status);
CREATE INDEX IF NOT EXISTS idx_process_logs_stage ON process_logs(processing_stage);
CREATE INDEX IF NOT EXISTS idx_process_logs_processed_at ON process_logs(processed_at DESC);
CREATE INDEX IF NOT EXISTS idx_process_logs_created_at ON process_logs(created_at DESC);

-- updated_at自動更新トリガー
DROP TRIGGER IF EXISTS trigger_process_logs_updated_at ON process_logs;
CREATE TRIGGER trigger_process_logs_updated_at
  BEFORE UPDATE ON process_logs
  FOR EACH ROW
  EXECUTE PROCEDURE refresh_updated_at_column();


-- ============================================================
-- 3. search_index テーブル（検索層）
-- 目的: ベクトル検索用の最適化されたデータ
-- 備考: 既存のdocument_chunksを改名・拡張
-- ============================================================
CREATE TABLE IF NOT EXISTS search_index (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,

    -- チャンク情報
    chunk_index INTEGER NOT NULL,
    chunk_content TEXT NOT NULL,
    chunk_size INTEGER NOT NULL,

    -- チャンク種別（メタデータ別ベクトル化戦略）
    chunk_type VARCHAR(50) DEFAULT 'content_small',
        -- 'title': タイトル専用 (weight=2.0)
        -- 'summary': サマリー専用 (weight=1.5)
        -- 'date': 日付情報 (weight=1.3)
        -- 'tags': タグ情報 (weight=1.2)
        -- 'content_small': 本文小チャンク (weight=1.0)
        -- 'content_large': 本文大チャンク (weight=1.0)
        -- 'synthetic': 合成チャンク (weight=1.0)
    search_weight FLOAT DEFAULT 1.0,

    -- ベクトル検索（1536次元: OpenAI Embedding）
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
'検索層: ユーザーが検索するときに見る場所。必要な情報だけに絞り込まれた、スリムで高速なテーブル。';

-- インデックス
CREATE INDEX IF NOT EXISTS idx_search_index_document_id ON search_index(document_id);
CREATE INDEX IF NOT EXISTS idx_search_index_embedding ON search_index USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_search_index_chunk_index ON search_index(chunk_index);
CREATE INDEX IF NOT EXISTS idx_search_index_chunk_type ON search_index(chunk_type);
CREATE INDEX IF NOT EXISTS idx_search_index_doc_type ON search_index(document_id, chunk_type);

-- updated_at自動更新トリガー
DROP TRIGGER IF EXISTS trigger_search_index_updated_at ON search_index;
CREATE TRIGGER trigger_search_index_updated_at
  BEFORE UPDATE ON search_index
  FOR EACH ROW
  EXECUTE PROCEDURE refresh_updated_at_column();


-- ============================================================
-- 4. 既存データの移行
-- 既存のdocumentsテーブルからsource_documentsとprocess_logsへ移行
-- ============================================================

-- 4-1. source_documentsへデータ移行
-- 注: 既存のdocumentsテーブルに存在しないカラムは除外
INSERT INTO source_documents (
    id, source_type, source_id, source_url, ingestion_route,
    file_name, file_type,
    -- file_size_bytes は既存テーブルに存在しないため除外
    workspace, doc_type,
    -- full_text は既存テーブルに存在しないため除外
    summary,
    classroom_sender, classroom_sender_email, classroom_sent_at,
    classroom_subject, classroom_post_text, classroom_type,
    metadata, tags, document_date, content_hash,
    created_at, updated_at
)
SELECT
    id, source_type, source_id, source_url, ingestion_route,
    file_name, file_type,
    workspace, doc_type,
    summary,
    classroom_sender,
    classroom_sender_email,
    classroom_sent_at,
    classroom_subject,
    classroom_post_text,
    classroom_type,
    metadata, tags, document_date, content_hash,
    created_at, updated_at
FROM documents
ON CONFLICT (source_id) DO NOTHING;

-- 4-2. process_logsへデータ移行
-- 注: 既存のdocumentsテーブルに存在しないカラムは除外
INSERT INTO process_logs (
    document_id, processing_status, processing_stage,
    -- stageA_classifier_model, stageB_vision_model, stageC_extractor_model は既存テーブルに存在しないため除外
    -- text_extraction_model は既存テーブルに存在しないため除外
    prompt_version,
    -- stage1_needs_processing は既存テーブルに存在しないため除外
    processing_duration_ms, inference_time,
    error_message, version, updated_by,
    processed_at, created_at, updated_at
)
SELECT
    id, processing_status, processing_stage,
    prompt_version,
    processing_duration_ms, inference_time,
    error_message, version, updated_by,
    updated_at, created_at, updated_at
FROM documents;

-- 4-3. search_indexへデータ移行（既存のdocument_chunksから）
INSERT INTO search_index (
    id, document_id, chunk_index, chunk_content, chunk_size,
    chunk_type, search_weight, embedding,
    page_numbers, section_title,
    created_at, updated_at
)
SELECT
    id, document_id, chunk_index, chunk_text, chunk_size,
    chunk_type, search_weight, embedding,
    page_numbers, section_title,
    created_at, updated_at
FROM document_chunks
ON CONFLICT (document_id, chunk_index) DO NOTHING;


-- ============================================================
-- 5. 統一検索関数の更新（3層構造対応）
-- ============================================================
CREATE OR REPLACE FUNCTION unified_search_v2(
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
            si.id AS chunk_id,
            si.document_id AS doc_id,
            si.chunk_index,
            si.chunk_content,
            si.chunk_type,
            COALESCE(si.search_weight, 1.0) AS search_weight,
            (1 - (si.embedding <=> query_embedding)) AS raw_sim,
            (1 - (si.embedding <=> query_embedding)) * COALESCE(si.search_weight, 1.0) AS weighted_sim,
            ts_rank_cd(
                to_tsvector('simple', si.chunk_content),
                websearch_to_tsquery('simple', query_text)
            ) AS ft_score
        FROM search_index si
        JOIN source_documents sd ON si.document_id = sd.id
        WHERE
            si.embedding IS NOT NULL
            AND (si.chunk_type IS NULL OR si.chunk_type != 'content_large')
            AND (1 - (si.embedding <=> query_embedding)) >= match_threshold
            AND (filter_chunk_types IS NULL OR si.chunk_type = ANY(filter_chunk_types))
            AND (filter_doc_types IS NULL OR sd.doc_type = ANY(filter_doc_types))
            AND (filter_workspace IS NULL OR sd.workspace = filter_workspace)
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
            rc.chunk_content,
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
        sd.id AS document_id,
        sd.file_name,
        sd.doc_type,
        sd.workspace,
        sd.document_date,
        sd.metadata,
        sd.summary,
        sd.full_text,
        dbc.chunk_content AS best_chunk_text,
        dbc.chunk_type::VARCHAR AS best_chunk_type,
        dbc.chunk_id AS best_chunk_id,
        dbc.chunk_index AS best_chunk_index,
        dbc.raw_sim::FLOAT AS raw_similarity,
        dbc.weighted_sim::FLOAT AS weighted_similarity,
        dbc.ft_score::FLOAT AS fulltext_score,
        dbc.combined::FLOAT AS combined_score,
        dbc.is_title_match AS title_matched,
        sd.source_type,
        sd.source_url,
        sd.created_at
    FROM document_best_chunks dbc
    INNER JOIN source_documents sd ON sd.id = dbc.doc_id
    ORDER BY dbc.is_title_match DESC, dbc.combined DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION unified_search_v2 IS
'3層構造対応の統一検索関数: source_documents + search_indexを使用';


-- ============================================================
-- 6. 既存テーブルのリネームとビュー作成
-- ============================================================
-- 既存のdocumentsテーブルをdocuments_legacyにリネームしてバックアップ
ALTER TABLE documents RENAME TO documents_legacy;

-- 既存のdocument_chunksテーブルもdocument_chunks_legacyにリネームしてバックアップ
ALTER TABLE document_chunks RENAME TO document_chunks_legacy;

-- 既存のアプリケーションが`documents`テーブルを参照している場合、
-- ビューを作成して互換性を維持
CREATE VIEW documents AS
SELECT
    sd.id,
    sd.source_type,
    sd.source_id,
    sd.source_url,
    sd.ingestion_route,
    sd.file_name,
    sd.file_type,
    sd.file_size_bytes,
    sd.workspace,
    sd.doc_type,
    sd.full_text,
    sd.summary,
    sd.metadata,
    sd.tags,
    sd.document_date,
    sd.content_hash,
    sd.created_at,
    sd.updated_at,
    pl.processing_status,
    pl.processing_stage,
    pl.stageA_classifier_model,
    pl.stageB_vision_model,
    pl.stageC_extractor_model,
    pl.text_extraction_model,
    pl.prompt_version,
    pl.error_message,
    pl.processed_at
FROM source_documents sd
LEFT JOIN LATERAL (
    SELECT *
    FROM process_logs
    WHERE process_logs.document_id = sd.id
    ORDER BY created_at DESC
    LIMIT 1
) pl ON true;

COMMENT ON VIEW documents IS
'互換性ビュー: 既存アプリケーションのためにsource_documentsとprocess_logsを結合';

COMMIT;
