# 🚨 緊急復旧ガイド：ベクトル検索を復活させる

## 問題
- 検索結果が0件
- **embedding カラムが存在しない**
- ベクトル検索が機能していない

## 即座に実行する手順（5分で完了）

### Step 1: embeddingカラムを追加（1分）

**Supabase SQL Editor で実行**:

```sql
BEGIN;

-- embeddingカラムを追加
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS embedding vector(1536);

-- インデックスを作成（検索パフォーマンス向上）
CREATE INDEX IF NOT EXISTS documents_embedding_idx
ON documents USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

COMMIT;
```

### Step 2: 全ドキュメントのembeddingを再生成（3分）

**Windows PowerShell/コマンドプロンプトで実行**:

```bash
cd K:\document-management-system
python regenerate_all_embeddings.py
```

プロンプトが出たら `y` を入力して実行。

### Step 3: ベクトル検索機能を使う検索関数に戻す（1分）

**Supabase SQL Editor で実行**:

```sql
BEGIN;

-- 既存の関数を削除
DROP FUNCTION IF EXISTS search_documents_final(TEXT, vector(1536), FLOAT, INT, FLOAT, FLOAT, TEXT[]);

-- ベクトル検索＋全文検索のハイブリッド検索に戻す
CREATE OR REPLACE FUNCTION search_documents_final(
    query_text TEXT,
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.0,
    match_count INT DEFAULT 10,
    vector_weight FLOAT DEFAULT 0.7,
    fulltext_weight FLOAT DEFAULT 0.3,
    filter_doc_types TEXT[] DEFAULT NULL
)
RETURNS TABLE (
    document_id UUID,
    file_name VARCHAR,
    doc_type VARCHAR,
    workspace VARCHAR,
    document_date DATE,
    metadata JSONB,
    summary TEXT,
    large_chunk_text TEXT,
    large_chunk_id UUID,
    combined_score FLOAT,
    small_chunk_id UUID,
    source_type VARCHAR,
    source_url TEXT,
    full_text TEXT,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id AS document_id,
        d.file_name,
        d.doc_type,
        d.workspace,
        d.document_date,
        d.metadata,
        d.summary,
        d.full_text AS large_chunk_text,
        d.id AS large_chunk_id,
        -- ベクトル検索70% + 全文検索30%
        (
            (1 - (d.embedding <=> query_embedding)) * vector_weight +
            ts_rank_cd(
                to_tsvector('simple', COALESCE(d.full_text, '') || ' ' || COALESCE(d.summary, '')),
                websearch_to_tsquery('simple', query_text)
            ) * fulltext_weight
        )::FLOAT AS combined_score,
        d.id AS small_chunk_id,
        d.source_type,
        d.source_url,
        d.full_text,
        d.created_at
    FROM documents d
    WHERE
        -- embedding が存在するドキュメントのみ
        d.embedding IS NOT NULL
        -- doc_type絞り込み
        AND (filter_doc_types IS NULL
             OR cardinality(filter_doc_types) = 0
             OR d.doc_type = ANY(filter_doc_types))
        -- 類似度フィルタ
        AND (1 - (d.embedding <=> query_embedding)) >= match_threshold
    ORDER BY combined_score DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

COMMIT;
```

### Step 4: 検索をテスト

アプリケーションで検索を実行して、結果が返ってくることを確認。

---

## なぜこうなったか

1. **embedding カラムが元々存在していなかった**可能性
   - または別のマイグレーションで削除された
   - 私が作成した `cleanup_remove_columns_step2_drop_columns.sql` には embedding は含まれていない

2. **検索関数が embedding を参照していた**
   - embedding が存在しないため、検索が動作しなかった

3. **応急措置として全文検索のみにした**
   - しかし、ベクトル検索がないと意味がない

---

## 完了後の確認

```sql
-- embeddingカラムが存在することを確認
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'documents' AND column_name = 'embedding';

-- embeddingが生成されたドキュメント数を確認
SELECT COUNT(*) FROM documents WHERE embedding IS NOT NULL;
```

全ドキュメント（31件）の embedding が生成されていれば成功です！

---

## トラブルシューティング

### エラー: "type vector does not exist"
pgvector拡張がインストールされていません。Supabase SQL Editorで実行：
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### エラー: API key がない
`.env` ファイルに `OPENAI_API_KEY` が設定されているか確認。

### embedding生成が遅い
31件なので3-5分程度かかります。気長に待ってください。
