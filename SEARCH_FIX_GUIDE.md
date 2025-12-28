# 検索システム修正ガイド

## 問題の概要

検索システムで「検索に何も引っかからない」問題が発生しています。

### 原因

データベースのテーブル名変更後、`unified_search_v2` 関数が古いテーブル名を参照していたため、検索が失敗していました。

**テーブル名の変更:**
- `source_documents` → `Rawdata_FILE_AND_MAIL` (133件のデータあり)
- `search_index` → `10_ix_search_index` (402件のインデックスあり)

## 修正方法

### ステップ1: Supabaseダッシュボードにアクセス

1. ブラウザで以下のURLを開く:
   ```
   https://supabase.com/dashboard/project/hjkcgulxddtwlljhbocb/sql/new
   ```

2. Supabaseにログインしていない場合はログイン

### ステップ2: SQL Editorで修正SQLを実行

SQL Editorで以下のSQLを実行してください:

```sql
-- =====================================================
-- unified_search_v2 関数のテーブル名を修正
-- 作成日: 2025-12-28
-- =====================================================

DROP FUNCTION IF EXISTS unified_search_v2(TEXT, vector, FLOAT, INT, FLOAT, FLOAT, TEXT[], TEXT[], TEXT);

CREATE OR REPLACE FUNCTION unified_search_v2(
    query_text TEXT,
    query_embedding vector,
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
    attachment_text TEXT,
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
    created_at TIMESTAMPTZ,
    display_subject TEXT,
    display_sender VARCHAR,
    display_sent_at TIMESTAMPTZ,
    display_post_text TEXT,
    display_type VARCHAR
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
        FROM "10_ix_search_index" si
        JOIN "Rawdata_FILE_AND_MAIL" sd ON si.document_id = sd.id
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
        sd.attachment_text,
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
        sd.created_at,
        sd.display_subject,
        sd.display_sender,
        sd.display_sent_at,
        sd.display_post_text,
        sd.display_type
    FROM document_best_chunks dbc
    INNER JOIN "Rawdata_FILE_AND_MAIL" sd ON sd.id = dbc.doc_id
    ORDER BY dbc.is_title_match DESC, dbc.combined DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;
```

### ステップ3: 実行の確認

1. SQL Editorで `Run` ボタンをクリック
2. 成功メッセージが表示されることを確認

### ステップ4: 検索システムのテスト

修正後、以下のURLで検索が動作するか確認してください:

```
https://mail-doc-search-system-983922127476.asia-northeast1.run.app/
```

## 確認事項

### データベースの状態
- ✅ `Rawdata_FILE_AND_MAIL` テーブル: **133件**のドキュメント
- ✅ `10_ix_search_index` テーブル: **402件**の検索インデックス
- ✅ 3つのワークスペース: `ema_classroom`, `ikuya_classroom`, `waseda_academy`

### 修正内容
- ✅ `unified_search_v2` 関数のテーブル参照を修正
  - `search_index` → `"10_ix_search_index"`
  - `source_documents` → `"Rawdata_FILE_AND_MAIL"`

## トラブルシューティング

### SQLの実行に失敗する場合

1. Supabaseダッシュボードで **Settings** > **Database** を確認
2. データベースのステータスが正常であることを確認
3. 上記のSQLを再度コピー&ペーストして実行

### 修正後も検索が動作しない場合

1. ブラウザのキャッシュをクリア（Ctrl+Shift+R または Cmd+Shift+R）
2. Cloud Runのサービスを再起動（Googleコンソールから）
3. 以下のデバッグエンドポイントで確認:
   ```
   https://mail-doc-search-system-983922127476.asia-northeast1.run.app/api/debug/database
   ```

## 関連ファイル

- 修正SQL: `database/migrations/fix_unified_search_v2_table_names.sql`
- バックエンド: `G_cloud_run/app.py`
- データベースクライアント: `A_common/database/client.py`

## 問題が解決しない場合

以下の情報を確認してください:

1. Supabase SQL Editorでクエリを直接実行:
   ```sql
   SELECT * FROM "10_ix_search_index" LIMIT 5;
   SELECT * FROM "Rawdata_FILE_AND_MAIL" LIMIT 5;
   ```

2. `unified_search_v2` 関数が正しく作成されているか確認:
   ```sql
   SELECT proname, prokind FROM pg_proc WHERE proname = 'unified_search_v2';
   ```

---

**作成日**: 2025-12-28
**問題**: 検索に何も引っかからない
**原因**: テーブル名の不一致
**解決**: unified_search_v2 関数のテーブル参照を修正
