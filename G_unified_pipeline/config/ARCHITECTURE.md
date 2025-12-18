# G_unified_pipeline アーキテクチャ

## 概要

G_unified_pipelineは、ドキュメント処理を**Stage E から Stage K**までの7つのステージで行う統合パイプラインです。各ステージは明確な責任を持ち、**config-based設計**により、ドキュメントタイプやワークスペースに応じて柔軟にAIモデルとプロンプトを切り替えることができます。

---

## 🔄 Stage E から K までの処理フロー

```
┌─────────────┐
│   Stage E   │  前処理（Pre-processing）
│  Preprocessing │
└──────┬──────┘
       ↓
┌─────────────┐
│   Stage F   │  視覚解析（Visual Analysis）
│   Vision    │  ← Gemini 2.5 Flash
└──────┬──────┘
       ↓
┌─────────────┐
│   Stage G   │  テキスト整形（Text Formatting）
│  Formatting │  ← Gemini 2.5 Flash
└──────┬──────┘
       ↓
┌─────────────┐
│   Stage H   │  構造化（Structuring）
│ Structuring │  ← Claude Haiku 4.5
└──────┬──────┘
       ↓
┌─────────────┐
│   Stage I   │  統合・要約（Synthesis）
│  Synthesis  │  ← Gemini 2.5 Flash
└──────┬──────┘
       ↓
┌─────────────┐
│   Stage J   │  チャンク化（Chunking）
│  Chunking   │
└──────┬──────┘
       ↓
┌─────────────┐
│   Stage K   │  埋め込み（Embedding）
│  Embedding  │  ← OpenAI text-embedding-3-small
└─────────────┘
```

---

## 📝 各Stageの詳細

### Stage E: Pre-processing（前処理）

**役割:**
- ファイルの読み込み
- MIME typeの判定
- ファイル形式に応じた初期処理
- メタデータの初期化

**処理内容:**
- 画像ファイル（JPEG, PNG）、PDFファイル、テキストファイルの識別
- 一時ファイルの管理
- エラーハンドリング

**使用モデル:** なし（純粋な前処理）

---

### Stage F: Visual Analysis（視覚解析）

**役割:**
- 画像・PDFからのOCR（光学文字認識）
- レイアウト情報の抽出
- 視覚的構造の理解（見出し、箇条書き、表など）

**処理内容:**
- Gemini 2.5 Flashを使用した視覚解析
- 画像/PDFを Base64 エンコードして送信
- テキストとレイアウト情報を JSON 形式で取得

**使用モデル:**
- デフォルト: `gemini-2.5-flash`
- チラシ: `gemini-2.5-flash`（商品情報抽出に最適化）

**プロンプト例:**
- `config/prompts/stage_f/default.md` - 一般文書用
- `config/prompts/stage_f/flyer.md` - チラシ専用（商品名、価格、カテゴリに特化）

**スキップ条件:**
- `mime_type='text/plain'` の場合（既にテキストがある場合）

---

### Stage G: Text Formatting（テキスト整形）

**役割:**
- Stage F で抽出したテキストの整形
- レイアウト情報を保持しながら読みやすい形式に変換
- 不要な空白・改行の除去

**処理内容:**
- Gemini 2.5 Flashを使用したテキスト整形
- Markdown形式での出力
- 表やリストの構造化

**使用モデル:**
- デフォルト: `gemini-2.5-flash`

**プロンプト例:**
- `config/prompts/stage_g/default.md` - 一般文書用
- `config/prompts/stage_g/flyer.md` - チラシ専用（商品リストを表形式に整形）

**スキップ条件:**
- `mime_type='text/plain'` の場合（テキストファイルは整形不要）

---

### Stage H: Structuring（構造化）

**役割:**
- テキストから構造化データを抽出
- メタデータの生成（日付、金額、人物、組織など）
- ドキュメントタイプ固有のスキーマに基づいた抽出

**処理内容:**
- Claude Haiku 4.5 を使用した高精度な構造化
- JSON形式でメタデータを出力
- 自動リトライ機能（JSONパースエラー時）

**使用モデル:**
- デフォルト: `claude-haiku-4-5-20251001`（高精度・高速）

**プロンプト例:**
- `config/prompts/stage_h/default.md` - 一般文書用（テンプレート変数対応）
- `config/prompts/stage_h/flyer.md` - チラシ専用（商品情報抽出）
- `config/prompts/stage_h/classroom.md` - Classroom文書専用（課題情報抽出）

**重要な機能:**
- **テンプレート変数:** `{doc_type}`, `{workspace}`, `{file_name}` などをプロンプトに埋め込み可能
- **JSONリトライ:** パースエラー時に `json_repair` で自動修復
- **スキーマ検証:** 出力形式の厳密なチェック

---

### Stage I: Synthesis（統合・要約）

**役割:**
- ドキュメント全体の要約生成
- タグの自動生成
- Stage H の結果とテキストを統合

**処理内容:**
- Gemini 2.5 Flashを使用した要約生成
- Stage H の構造化データを参照
- ドキュメントタイプ固有のタグ付け

**使用モデル:**
- デフォルト: `gemini-2.5-flash`

**プロンプト例:**
- `config/prompts/stage_i/default.md` - 一般文書用
- `config/prompts/stage_i/flyer.md` - チラシ専用（商品カテゴリベースのタグ生成）

**出力:**
- `summary`: ドキュメント要約（1-3文）
- `tags`: タグリスト（Stage H のタグとマージ）

---

### Stage J: Chunking（チャンク化）

**役割:**
- ドキュメントを検索用チャンクに分割
- メタデータを各チャンクに付与
- 検索最適化

**処理内容:**
- 文単位でのチャンク分割
- チャンクサイズ: 300-1000文字
- オーバーラップ: 100文字

**使用モデル:** なし（ルールベース処理）

**出力:**
- チャンクID
- チャンクテキスト
- メタデータ（日付、タグ、ファイル名など）

---

### Stage K: Embedding（埋め込み）

**役割:**
- チャンクをベクトル化
- 検索インデックスへの保存
- セマンティック検索の実現

**処理内容:**
- OpenAI text-embedding-3-small でベクトル化
- Supabase の `search_index` テーブルに保存
- 既存チャンクの削除・更新処理

**使用モデル:**
- デフォルト: `text-embedding-3-small`（1536次元）

**出力:**
- ベクトル埋め込み
- search_index への保存

---

## ⚙️ models.yaml の役割

`config/models.yaml` は、各ステージで使用するAIモデルを定義します。

### 構造

```yaml
models:
  stage_f:
    default: "gemini-2.5-flash"
    flyer: "gemini-2.5-flash"

  stage_g:
    default: "gemini-2.5-flash"

  stage_h:
    default: "claude-haiku-4-5-20251001"

  stage_i:
    default: "gemini-2.5-flash"

  stage_k:
    default: "text-embedding-3-small"
```

### 特徴

1. **ステージごとのモデル指定**
   - 各ステージで最適なモデルを選択
   - 視覚解析には Gemini 2.5 Flash（マルチモーダル）
   - 構造化には Claude Haiku 4.5（高精度JSON生成）

2. **doc_typeごとのモデル切り替え**
   - `flyer` の場合は Stage F で専用モデルを使用可能
   - 将来的に新しいドキュメントタイプを追加しやすい

3. **モデルバージョン管理**
   - モデル名を一箇所で管理
   - バージョンアップ時の変更が容易

---

## 📄 prompts/ の役割

`config/prompts/` ディレクトリは、各ステージのプロンプトを Markdown ファイルとして管理します。

### ディレクトリ構造

```
config/prompts/
├── stage_f/
│   ├── default.md       # 一般文書用の視覚解析プロンプト
│   └── flyer.md         # チラシ専用の視覚解析プロンプト
├── stage_g/
│   ├── default.md       # 一般文書用の整形プロンプト
│   └── flyer.md         # チラシ専用の整形プロンプト
├── stage_h/
│   ├── default.md       # 一般文書用の構造化プロンプト
│   ├── flyer.md         # チラシ専用の構造化プロンプト
│   └── classroom.md     # Classroom文書専用の構造化プロンプト
└── stage_i/
    ├── default.md       # 一般文書用の要約プロンプト
    └── flyer.md         # チラシ専用の要約プロンプト
```

### 特徴

1. **doc_typeごとのプロンプト切り替え**
   - `flyer` の場合は `stage_h/flyer.md` を使用
   - `classroom_document` の場合は `stage_h/classroom.md` を使用

2. **テンプレート変数**
   - プロンプト内で `{doc_type}`, `{workspace}`, `{file_name}` などを使用可能
   - 実行時に動的に置換される

3. **Markdown形式**
   - 読みやすく、編集しやすい
   - バージョン管理が容易
   - コメントや説明を追加可能

4. **プロンプトエンジニアリングの分離**
   - コードからプロンプトを分離
   - プロンプトのみの変更でAI出力を調整可能
   - チーム内でのプロンプト共有が容易

---

## 🎯 Config-based設計の利点

### 1. 柔軟性
- ドキュメントタイプに応じた最適なモデル・プロンプトの選択
- コード変更なしでモデル・プロンプトを変更可能

### 2. 保守性
- プロンプトとコードの分離
- 各ステージの責任が明確
- テストしやすい構造

### 3. 拡張性
- 新しいドキュメントタイプの追加が容易
- 新しいステージの追加が容易
- 新しいAIモデルへの切り替えが容易

### 4. 再現性
- 全ての設定がYAML/Markdownで管理
- バージョン管理で履歴追跡が可能
- 環境間での一貫性が保証される

---

## 📊 使用例

### チラシ処理の場合

```python
pipeline = UnifiedDocumentPipeline(db_client=db_client)

result = await pipeline.process_document(
    file_path=Path("flyer.jpg"),
    file_name="supermarket_flyer.jpg",
    doc_type="flyer",           # ← これで自動的にチラシ用の設定が選択される
    workspace="shopping",
    mime_type="image/jpeg",
    source_id="drive_file_id"
)
```

**自動的に適用される設定:**
- Stage F: `gemini-2.5-flash` + `prompts/stage_f/flyer.md`
- Stage G: `gemini-2.5-flash` + `prompts/stage_g/flyer.md`
- Stage H: `claude-haiku-4-5-20251001` + `prompts/stage_h/flyer.md`
- Stage I: `gemini-2.5-flash` + `prompts/stage_i/flyer.md`

---

## 🔧 設定ファイルの編集

### 新しいドキュメントタイプを追加する場合

1. **models.yaml に追加**
```yaml
models:
  stage_h:
    default: "claude-haiku-4-5-20251001"
    invoice: "claude-haiku-4-5-20251001"  # ← 新規追加
```

2. **pipeline_routes.yaml に追加**
```yaml
routing:
  by_doc_type:
    invoice:  # ← 新規追加
      stages:
        stage_h:
          prompt_key: "invoice"
          model_key: "invoice"
```

3. **プロンプトファイルを追加**
```bash
config/prompts/stage_h/invoice.md  # ← 新規作成
```

---

## 📚 まとめ

G_unified_pipelineは、**Stage E から K までの明確な責任分離**と**config-based設計**により、以下を実現しています：

✅ **マルチモーダル処理**: 画像・PDF・テキストを統一的に処理
✅ **柔軟な設定**: ドキュメントタイプごとに最適なAIモデル・プロンプトを選択
✅ **高い保守性**: コードとプロンプトの分離による変更の容易さ
✅ **拡張性**: 新しいドキュメントタイプの追加が容易
✅ **再現性**: 全ての設定をYAML/Markdownで管理

この設計により、システム全体の品質向上とメンテナンス負荷の軽減を実現しています。
