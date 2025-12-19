# G_unified_pipeline: 統合ドキュメント処理パイプライン

設定ベースの柔軟なドキュメント処理フロー（Stage E-K）

## 特徴

- **設定ベース**: doc_type / workspace に応じて自動的にプロンプトとモデルを切り替え
- **YAML + Markdown**: 設定は YAML ファイルと Markdown ファイルで管理
- **柔軟なルーティング**: チラシ、Classroom、家計簿など、ドキュメントタイプごとに最適な処理

## ディレクトリ構造

```
G_unified_pipeline/
├── config/
│   ├── models.yaml                      # AIモデル定義
│   ├── source_documents_routing.yaml    # ルーティング設定
│   └── prompts/
│       ├── stage_f/             # Visual Analysis プロンプト
│       │   ├── default.md
│       │   ├── flyer.md
│       │   └── classroom.md
│       ├── stage_g/             # Text Formatting プロンプト
│       │   ├── default.md
│       │   └── flyer.md
│       ├── stage_h/             # Structuring プロンプト
│       │   ├── default.md
│       │   ├── flyer.md
│       │   └── classroom.md
│       └── stage_i/             # Synthesis プロンプト
│           ├── default.md
│           └── flyer.md
├── config_loader.py             # 設定ローダー
├── pipeline.py                  # 統合パイプライン
├── stage_e_preprocessing.py     # Stage E: Pre-processing
├── stage_f_visual.py            # Stage F: Visual Analysis
├── stage_g_formatting.py        # Stage G: Text Formatting
├── stage_h_structuring.py       # Stage H: Structuring
├── stage_i_synthesis.py         # Stage I: Synthesis
├── stage_j_chunking.py          # Stage J: Chunking
└── stage_k_embedding.py         # Stage K: Embedding
```

## 使い方

```python
from G_unified_pipeline import UnifiedDocumentPipeline

# パイプライン初期化
pipeline = UnifiedDocumentPipeline()

# ドキュメント処理
result = await pipeline.process_document(
    file_path=Path("/path/to/file.pdf"),
    file_name="file.pdf",
    doc_type="flyer",          # ← これで自動的にプロンプト・モデルが切り替わる
    workspace="household",
    mime_type="application/pdf",
    source_id="source_123"
)

if result['success']:
    print(f"✅ 処理成功: {result['document_id']}")
    print(f"   チャンク数: {result['chunks_count']}")
```

## 設定ファイルの編集

### 1. 新しいドキュメントタイプを追加

`config/source_documents_routing.yaml` にルートを追加:

```yaml
routing:
  by_doc_type:
    my_new_type:
      description: "新しいドキュメントタイプ"
      stages:
        stage_f:
          prompt_key: "my_new_type"
          model_key: "default"
        stage_h:
          prompt_key: "my_new_type"
          model_key: "default"
```

### 2. プロンプトを追加

`config/prompts/stage_h/my_new_type.md` を作成:

```markdown
# Stage H: 構造化（新しいドキュメントタイプ）

このドキュメントから以下の情報を抽出してください：
- フィールド1
- フィールド2
...
```

### 3. モデルを変更

`config/models.yaml` でモデルを指定:

```yaml
models:
  stage_h:
    my_new_type: "claude-sonnet-4-5"
```

## 処理フロー

```
Stage E (Pre-processing)
  ↓ pdfplumber, python-docx でテキスト抽出
Stage F (Visual Analysis)  ← 条件付き（画像 or テキスト<100文字）
  ↓ Gemini 2.5 Flash で OCR + レイアウト解析
Stage G (Text Formatting)  ← Stage F の結果がある場合
  ↓ Gemini 2.5 Flash で整形
Stage H (Structuring)
  ↓ Claude Haiku 4.5 で構造化JSON抽出
Stage I (Synthesis)
  ↓ Gemini 2.5 Flash で要約・タグ生成
Stage J (Chunking)
  ↓ メタデータチャンク生成
Stage K (Embedding)
  ↓ OpenAI embedding (text-embedding-3-small) + search_index保存
```

## 既存コードからの移行

```python
# 旧コード（TwoStageIngestionPipeline）
pipeline = TwoStageIngestionPipeline()
result = await pipeline.process_file(file_meta, workspace='inbox')

# 新コード（UnifiedDocumentPipeline）
pipeline = UnifiedDocumentPipeline()
result = await pipeline.process_document(
    file_path=Path(local_path),
    file_name=file_meta['name'],
    doc_type='other',
    workspace='inbox',
    mime_type=file_meta['mimeType'],
    source_id=file_meta['id']
)
```

## トラブルシューティング

### プロンプトが読み込まれない

- ファイル名が正しいか確認: `config/prompts/{stage}/{prompt_key}.md`
- フォールバック: `prompt_key` が見つからない場合、自動的に `default.md` を使用

### モデルが見つからない

- `config/models.yaml` にモデルが定義されているか確認
- フォールバック: `model_key` が見つからない場合、自動的に `default` を使用

### ルーティングが正しく動作しない

- `config/source_documents_routing.yaml` で `doc_type` が正しく定義されているか確認
- 優先順位: `by_workspace` > `by_doc_type` > `default`
