# 実装プラン: 小チャンク検索 + 大チャンク回答アーキテクチャ

## 背景

現在、コードのコメントには「2階層ハイブリッド検索：小チャンク検索 + 大チャンク回答」と記載されているが、実装が存在しない。

### 現状の問題
- `documents`テーブルに1ドキュメント = 1 embeddingのみ
- 小チャンクテーブル、大チャンクテーブルが存在しない
- 長文ドキュメント（16,756トークンなど）でembedding生成が失敗
- 検索精度が低い（全文を1つのembeddingに圧縮するため情報が薄まる）

### 目標アーキテクチャ
1. **小チャンク（300文字）**: ベクトル + 全文検索で関連箇所を発見
2. **大チャンク（全文または大単位）**: 回答生成用のコンテキスト提供
3. **ドキュメント単位で重複排除**: 同じドキュメントから複数の小チャンクがヒットしても1つにまとめる
4. **Rerank対応**: より精度の高いスコアリング

---

## 実装ステップ

### Step 1: データベーススキーマ設計

#### 1.1 小チャンクテーブル作成
```sql
CREATE TABLE small_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    token_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT unique_chunk_per_document UNIQUE (document_id, chunk_index)
);

-- ベクトル検索用インデックス
CREATE INDEX small_chunks_embedding_idx
ON small_chunks USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- ドキュメントID検索用インデックス
CREATE INDEX small_chunks_document_id_idx ON small_chunks(document_id);
```

#### 1.2 大チャンクテーブル作成
大チャンクは現時点では`documents.full_text`をそのまま使用する。
将来的にページ単位などで分割する場合は別テーブルを検討。

**決定**: 当面は`documents`テーブルの`full_text`を大チャンクとして使用

---

### Step 2: チャンク分割ロジック実装

#### 2.1 チャンク分割モジュール作成
ファイル: `core/chunking/text_splitter.py`

```python
from typing import List, Dict
import tiktoken

class TextSplitter:
    def __init__(self, chunk_size: int = 300, overlap: int = 50):
        """
        Args:
            chunk_size: 1チャンクの文字数（デフォルト300文字）
            overlap: チャンク間のオーバーラップ文字数
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.encoding = tiktoken.get_encoding("cl100k_base")

    def split_text(self, text: str) -> List[Dict[str, any]]:
        """
        テキストを小チャンクに分割

        Returns:
            [
                {
                    "chunk_index": 0,
                    "content": "...",
                    "token_count": 120
                },
                ...
            ]
        """
        # 実装: 文字数ベースで分割、オーバーラップ考慮
        pass
```

#### 2.2 チャンク処理の統合
ファイル: `core/processing/chunk_processor.py`

```python
from core.chunking.text_splitter import TextSplitter
from core.embedding.openai_embedder import OpenAIEmbedder

class ChunkProcessor:
    def __init__(self):
        self.splitter = TextSplitter(chunk_size=300, overlap=50)
        self.embedder = OpenAIEmbedder()

    async def process_document(self, document_id: str, full_text: str):
        """
        ドキュメントをチャンク分割してembedding生成

        1. テキストを小チャンクに分割
        2. 各チャンクのembeddingを生成
        3. データベースに保存
        """
        chunks = self.splitter.split_text(full_text)

        for chunk in chunks:
            embedding = await self.embedder.generate(chunk["content"])
            # small_chunksテーブルに保存
```

---

### Step 3: 取り込みパイプラインの更新

#### 3.1 既存パイプラインの確認
- `core/ingestion/document_ingestion.py`: PDFなどの取り込み処理
- ドキュメント保存後にチャンク処理を追加

#### 3.2 パイプライン更新
```python
# document_ingestion.py の更新箇所

async def ingest_document(file_path: str):
    # 既存: PDFからテキスト抽出
    full_text = extract_text(file_path)

    # 既存: documentsテーブルに保存
    document_id = await db.insert_document({
        "full_text": full_text,
        "embedding": None,  # ドキュメントレベルのembeddingは不要に
        ...
    })

    # 新規: チャンク処理
    chunk_processor = ChunkProcessor()
    await chunk_processor.process_document(document_id, full_text)
```

---

### Step 4: 検索関数の更新

#### 4.1 新しい検索関数（Supabase）
ファイル: `database/search_with_small_chunks.sql`

```sql
CREATE OR REPLACE FUNCTION search_documents_with_chunks(
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
    full_text TEXT,
    chunk_content TEXT,
    chunk_score FLOAT,
    combined_score FLOAT,
    source_type VARCHAR,
    source_url TEXT,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    WITH chunk_scores AS (
        -- 小チャンクで検索
        SELECT
            sc.document_id,
            sc.content AS chunk_content,
            (1 - (sc.embedding <=> query_embedding)) AS vector_score,
            ts_rank_cd(
                to_tsvector('simple', sc.content),
                websearch_to_tsquery('simple', query_text)
            ) AS fulltext_score,
            (
                (1 - (sc.embedding <=> query_embedding)) * vector_weight +
                ts_rank_cd(
                    to_tsvector('simple', sc.content),
                    websearch_to_tsquery('simple', query_text)
                ) * fulltext_weight
            ) AS chunk_score
        FROM small_chunks sc
        WHERE sc.embedding IS NOT NULL
          AND (1 - (sc.embedding <=> query_embedding)) >= match_threshold
    ),
    document_best_chunks AS (
        -- ドキュメントごとに最高スコアのチャンクを選択
        SELECT DISTINCT ON (document_id)
            document_id,
            chunk_content,
            chunk_score
        FROM chunk_scores
        ORDER BY document_id, chunk_score DESC
    )
    SELECT
        d.id AS document_id,
        d.file_name,
        d.doc_type,
        d.workspace,
        d.document_date,
        d.metadata,
        d.summary,
        d.full_text,  -- 大チャンク（全文）
        dbc.chunk_content,  -- ヒットした小チャンク
        dbc.chunk_score,
        dbc.chunk_score AS combined_score,
        d.source_type,
        d.source_url,
        d.created_at
    FROM document_best_chunks dbc
    JOIN documents d ON d.id = dbc.document_id
    WHERE
        (filter_doc_types IS NULL
         OR cardinality(filter_doc_types) = 0
         OR d.doc_type = ANY(filter_doc_types))
    ORDER BY combined_score DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;
```

#### 4.2 Pythonクライアントの更新
ファイル: `core/database/client.py`

```python
def search_documents(
    self,
    query: str,
    embedding: List[float],
    limit: int = 10,
    doc_types: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    小チャンク検索 + 大チャンク回答
    """
    rpc_params = {
        "query_text": query,
        "query_embedding": embedding,
        "match_threshold": 0.0,
        "match_count": limit,
        "vector_weight": 0.7,
        "fulltext_weight": 0.3,
        "filter_doc_types": doc_types
    }

    response = self.client.rpc("search_documents_with_chunks", rpc_params).execute()
    return response.data if response.data else []
```

---

### Step 5: 既存ドキュメントの移行

#### 5.1 移行スクリプト作成
ファイル: `migrate_to_chunks.py`

```python
"""
既存の29件のドキュメントを小チャンクに分割
"""
import asyncio
from core.database.client import DatabaseClient
from core.processing.chunk_processor import ChunkProcessor

async def migrate_existing_documents():
    db = DatabaseClient()
    chunk_processor = ChunkProcessor()

    # 既存のドキュメントを全件取得
    documents = db.get_all_documents()

    for doc in documents:
        print(f"Processing: {doc['file_name']}")

        # small_chunksに分割＆embedding生成
        await chunk_processor.process_document(
            document_id=doc['id'],
            full_text=doc['full_text']
        )

        print(f"  -> {len(chunks)} chunks created")

if __name__ == "__main__":
    asyncio.run(migrate_existing_documents())
```

#### 5.2 失敗した2件の再処理
チャンク分割により、以下の2件も処理可能になる：
- 2025年度中1代数Ⅱ期中間試験(配信解答).pdf (16,756トークン)
- 251210図書室お知らせ.pdf (11,863トークン)

---

### Step 6: フロントエンドの調整

#### 6.1 検索結果の表示更新
ファイル: `app.py`

```python
# 検索結果に小チャンクのハイライト表示を追加
for result in search_results:
    st.markdown(f"### {result['file_name']}")

    # ヒットした小チャンクを表示
    st.info(f"関連箇所: {result['chunk_content']}")

    # 全文（大チャンク）はExpander内に
    with st.expander("全文を表示"):
        st.text(result['full_text'])
```

---

## 実装順序

1. **データベーススキーマ作成** (Step 1) - Supabaseで実行
2. **チャンク分割ロジック実装** (Step 2) - Pythonコード
3. **検索関数更新** (Step 4.1) - Supabaseで実行
4. **取り込みパイプライン更新** (Step 3) - Pythonコード
5. **Pythonクライアント更新** (Step 4.2) - Pythonコード
6. **既存ドキュメント移行** (Step 5) - スクリプト実行
7. **フロントエンド調整** (Step 6) - app.py更新
8. **動作確認** - 検索テスト

---

## リスクと対策

### リスク1: embedding生成コスト
- **影響**: 29件 × 平均50チャンク = 約1,450件のembedding生成
- **対策**: バッチ処理、レート制限考慮

### リスク2: データベース容量
- **影響**: small_chunksテーブルが大きくなる
- **対策**: インデックス最適化、古いデータのアーカイブ

### リスク3: 検索速度
- **影響**: チャンク数が増えると検索が遅くなる可能性
- **対策**: IVFFlat インデックスのパラメータチューニング

---

## 完了条件

- [ ] small_chunksテーブルが作成され、インデックスが設定されている
- [ ] 全29件のドキュメントが小チャンクに分割されている
- [ ] 失敗していた2件のドキュメントも処理されている
- [ ] 検索関数が小チャンク検索＋大チャンク回答を返す
- [ ] フロントエンドで小チャンクがハイライト表示される
- [ ] 検索精度が向上している（主観評価）
