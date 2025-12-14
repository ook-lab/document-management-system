# 文書検索・質問回答システム

SupabaseとマルチAIモデル（Gemini, Claude, OpenAI）を使用した、ベクトル検索ベースの質問回答システムです。

## 概要

このシステムは、Supabaseに保存された文書に対してベクトル検索を行い、AIで自然な回答を生成するWebアプリケーションです。

### 主な機能

- **ベクトル検索**: OpenAI Embeddingsを使用した高精度な文書検索
- **AI回答生成**: Gemini 2.5 Flash（デフォルト）による高速で自然な回答
- **シンプルなUI**: ブラウザで簡単に操作できる直感的なインターフェース
- **リアルタイム検索**: 質問入力から回答表示まで数秒で完了

## 前提条件

### 必要な環境変数

`.env`ファイルに以下を設定してください：

```bash
# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# OpenAI
OPENAI_API_KEY=your_openai_api_key
```

### データベース準備

1. **Supabaseプロジェクトの作成**
   - [Supabase](https://supabase.com)でプロジェクトを作成

2. **データベーススキーマの実行**
   ```bash
   # Supabase SQL Editorで以下のファイルを順に実行
   database/schema_v4_unified.sql
   database/add_match_documents_function.sql
   ```

3. **文書データの投入**
   - documentsテーブルにembedding（1536次元）を含む文書データを登録
   - 既存のデータ投入パイプラインを使用するか、手動で投入

## インストール手順

### 1. リポジトリのクローンまたは移動

```bash
cd /path/to/document_management_system
```

### 2. 仮想環境のアクティベート

```bash
source venv/bin/activate  # macOS/Linux
# または
venv\Scripts\activate  # Windows
```

### 3. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

## 実行方法

### 開発モード（デバッグ有効）

```bash
python app.py
```

サーバーが起動したら、ブラウザで以下のURLにアクセス：

```
http://localhost:5001
```

### 本番モード（推奨）

Gunicornを使用する場合：

```bash
# Gunicornをインストール（初回のみ）
pip install gunicorn

# サーバー起動
gunicorn -w 4 -b localhost:5001 app:app
```

## 使い方

1. **ブラウザでアクセス**
   - http://localhost:5001 を開く

2. **質問を入力**
   - テキストボックスに質問を入力（例: 「プロジェクトの納期はいつですか？」）

3. **検索・回答ボタンをクリック**
   - 自動的にベクトル検索と回答生成が実行されます

4. **結果を確認**
   - AIによる回答が表示されます
   - 関連する文書のリストが類似度とともに表示されます

## アーキテクチャ

```
┌─────────────┐
│   Browser   │
│  (UI)       │
└──────┬──────┘
       │
       │ HTTP Request
       ▼
┌─────────────┐
│   Flask     │
│   app.py    │
└──────┬──────┘
       │
       ├──────────────────┐
       │                  │
       ▼                  ▼
┌─────────────┐    ┌─────────────┐
│  Supabase   │    │   AI APIs   │
│  (pgvector) │    │  Gemini/GPT │
└─────────────┘    └─────────────┘
```

### 処理フロー

1. **ユーザーが質問を入力**
2. **OpenAI Embeddingsで質問をベクトル化** (1536次元)
3. **Supabaseでベクトル検索** (cosine類似度、上位5件)
4. **検索結果をコンテキストとしてAIモデルに渡す**
5. **AIモデル（Gemini 2.5 Flash）が自然な回答を生成**
6. **ブラウザに回答と関連文書を表示**

## APIエンドポイント

### POST /api/search

ベクトル検索を実行

**リクエスト:**
```json
{
  "query": "プロジェクトの納期はいつですか？",
  "limit": 5,
  "workspace": "personal"  // オプション
}
```

**レスポンス:**
```json
{
  "success": true,
  "results": [
    {
      "id": "uuid",
      "title": "プロジェクト計画書",
      "content": "...",
      "source_type": "drive",
      "file_name": "project_plan.pdf",
      "similarity": 0.85,
      "doc_type": "project_document",
      "workspace": "business"
    }
  ],
  "count": 5
}
```

### POST /api/answer

AIモデルで回答を生成

**リクエスト:**
```json
{
  "query": "プロジェクトの納期はいつですか？",
  "documents": [...]  // /api/searchの結果
}
```

**レスポンス:**
```json
{
  "success": true,
  "answer": "プロジェクトの納期は2024年3月31日です。...",
  "model": "gemini-2.5-flash",
  "provider": "gemini"
}
```

### GET /api/health

ヘルスチェック

**レスポンス:**
```json
{
  "status": "ok",
  "message": "Document Q&A System is running"
}
```

## トラブルシューティング

### ポート5001が既に使用されている

`app.py`の最終行を編集してポート番号を変更：

```python
app.run(host='localhost', port=8080, debug=True)
```

### 環境変数が読み込まれない

`.env`ファイルがプロジェクトルートに存在することを確認：

```bash
ls -la .env
cat .env
```

### Supabaseの接続エラー

1. SUPABASE_URLとSUPABASE_KEYが正しいか確認
2. `match_documents`関数がSupabaseに作成されているか確認：
   ```sql
   SELECT * FROM pg_proc WHERE proname = 'match_documents';
   ```
3. documentsテーブルにデータが存在するか確認：
   ```sql
   SELECT COUNT(*) FROM documents WHERE embedding IS NOT NULL;
   ```

### Embedding生成エラー

OPENAI_API_KEYが正しく設定されているか確認：

```bash
echo $OPENAI_API_KEY
```

### 検索結果が0件

1. documentsテーブルにembeddingが登録されているか確認
2. `processing_status`が`'completed'`になっているか確認：
   ```sql
   SELECT processing_status, COUNT(*)
   FROM documents
   GROUP BY processing_status;
   ```

### `match_documents`関数が見つからない

`database/add_match_documents_function.sql`をSupabaseで実行してください：

```bash
# ファイル内容をコピーして、Supabase SQL Editorに貼り付けて実行
cat database/add_match_documents_function.sql
```

## ファイル構成

```
document_management_system/
├── app.py                              # Flaskアプリケーション
├── templates/
│   └── index.html                      # Webインターフェース
├── core/
│   ├── database/
│   │   └── client.py                   # Supabaseクライアント
│   └── ai/
│       └── llm_client.py              # LLMクライアント
├── database/
│   ├── schema_v4_unified.sql          # メインスキーマ
│   └── add_match_documents_function.sql  # ベクトル検索関数
├── requirements.txt                    # 依存パッケージ
├── .env                               # 環境変数
└── README.md                          # このファイル
```

## 技術スタック

- **バックエンド**: Flask 3.0, Python 3.12
- **フロントエンド**: HTML, CSS, JavaScript（Vanilla JS）
- **AI/ML**:
  - Gemini 2.5 Flash/Pro (分類・Vision・回答生成)
  - Claude Haiku 4.5 (情報抽出)
  - OpenAI GPT-5.1 (高精度回答オプション)
  - OpenAI text-embedding-3-small (1536次元)
- **データベース**: Supabase (PostgreSQL + pgvector)
- **ベクトル検索**: pgvector (cosine類似度)

## セキュリティに関する注意

- 本番環境では`debug=False`に設定してください
- APIキーは必ず環境変数で管理し、コードに直接記述しないでください
- HTTPSを使用することを推奨します
- 適切なCORS設定を行ってください

## 今後の拡張案

- [ ] ユーザー認証機能
- [ ] 検索履歴の保存
- [ ] ワークスペースフィルタのUI追加
- [ ] ドキュメントタイプ別フィルタ
- [ ] 回答の評価機能（フィードバック）
- [ ] マルチモーダル検索（画像対応）

## ライセンス

このプロジェクトは内部使用を目的としています。

## サポート

問題が発生した場合は、以下を確認してください：

1. `.env`ファイルの設定
2. Supabaseのデータベース接続
3. OpenAI APIキーの有効性
4. documentsテーブルのデータ

それでも解決しない場合は、エラーメッセージを確認して対処してください。
