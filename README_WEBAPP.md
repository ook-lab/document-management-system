# 文書検索・質問回答システム（Webアプリ版）

Flask製のWebインターフェースで、ベクトル検索とAIによる質問回答機能を提供します。

## 機能

- **ベクトル検索**: ユーザーの質問から関連文書を検索
- **AI回答生成**: GPT-4を使用して自然な回答を生成
- **シンプルなUI**: ブラウザで簡単に操作できる直感的なインターフェース

## 前提条件

以下の環境変数が`.env`ファイルに設定されている必要があります:

```bash
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
OPENAI_API_KEY=your_openai_api_key
```

## インストール

1. 仮想環境をアクティベート:
```bash
source venv/bin/activate  # macOS/Linux
# または
venv\Scripts\activate  # Windows
```

2. 必要なパッケージをインストール:
```bash
pip install -r requirements.txt
```

## 実行方法

### 開発モード

```bash
python app.py
```

サーバーが起動したら、ブラウザで以下のURLにアクセス:
```
http://localhost:5001
```

### 本番モード（推奨）

Gunicornを使用する場合:

```bash
# Gunicornをインストール（まだの場合）
pip install gunicorn

# サーバー起動
gunicorn -w 4 -b 0.0.0.0:5001 app:app
```

## APIエンドポイント

### POST /api/search
ユーザーの質問からベクトル検索を実行

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
      "title": "プロジェクト計画書",
      "content": "...",
      "source": "Google Drive",
      "similarity": 0.85
    }
  ],
  "count": 5
}
```

### POST /api/answer
検索結果を元にAIで回答を生成

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
  "model": "gpt-4o",
  "provider": "openai"
}
```

### GET /api/health
ヘルスチェックエンドポイント

**レスポンス:**
```json
{
  "status": "ok",
  "message": "Document Q&A System is running"
}
```

## 使い方

1. **質問を入力**: テキストボックスに質問を入力
2. **検索・回答ボタンをクリック**: 自動的に検索と回答生成が実行されます
3. **結果を確認**:
   - AIによる回答が表示されます
   - 関連する文書のリストが類似度とともに表示されます

## トラブルシューティング

### ポート5001が既に使用されている

別のポートを使用する場合は、`app.py`の最終行を編集:
```python
app.run(host='localhost', port=8080, debug=True)  # ポート番号を変更
```

### 環境変数が読み込まれない

`.env`ファイルがプロジェクトルートに存在することを確認してください:
```bash
ls -la .env
```

### Supabaseの接続エラー

以下を確認:
- SUPABASE_URLとSUPABASE_KEYが正しいか
- Supabaseのベクトル検索関数`match_documents`が作成されているか
- データベースにドキュメントが登録されているか

### Embedding生成エラー

OPENAI_API_KEYが正しく設定されているか確認:
```bash
echo $OPENAI_API_KEY
```

## 技術スタック

- **バックエンド**: Flask 3.0
- **フロントエンド**: HTML, CSS, JavaScript（Vanilla JS）
- **AI/ML**: OpenAI GPT-4, OpenAI Embeddings
- **データベース**: Supabase（PostgreSQL + pgvector）

## ファイル構成

```
document_management_system/
├── app.py                    # Flaskアプリケーション
├── templates/
│   └── index.html           # Webインターフェース
├── core/
│   ├── database/
│   │   └── client.py        # Supabaseクライアント
│   └── ai/
│       └── llm_client.py    # LLMクライアント
├── requirements.txt         # 依存パッケージ
└── .env                     # 環境変数
```

## セキュリティに関する注意

- 本番環境では`debug=False`に設定してください
- 適切なCORS設定を行ってください
- APIキーは必ず環境変数で管理し、コードに直接記述しないでください
- HTTPSを使用することを推奨します

## ライセンス

このプロジェクトは内部使用を目的としています。
