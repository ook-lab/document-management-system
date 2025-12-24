# ネットスーパー横断検索アプリ

3つのネットスーパー（楽天西友・東急ストア・ダイエー）を横断検索し、安い順に商品を表示します。

## 機能

- 🔍 **ベクトル検索**: OpenAI Embeddingを使用した意味的な商品検索
- 🎯 **複数キーワード対応**: スペース区切りで複数キーワード検索可能
- 💰 **価格順ソート**: 検索結果を安い順に自動ソート（200件から上位20件を表示）
- 🖼️ **商品画像表示**: 各商品の画像を表示
- 🔗 **商品ページリンク**: 各ストアの商品ページへ直接アクセス

## セットアップ

### 1. データベースのセットアップ

以下のSQLファイルをSupabaseで順番に実行してください：

```bash
# 1. pgvector拡張を有効化
database/migrations/enable_pgvector.sql

# 2. embeddingカラムを追加
database/migrations/add_embedding_to_products.sql

# 3. ベクトル検索関数を作成
database/migrations/create_vector_search_function.sql
```

### 2. 環境変数設定

```bash
export SUPABASE_URL="your-supabase-url"
export SUPABASE_KEY="your-supabase-key"
export OPENAI_API_KEY="your-openai-api-key"
```

### 3. 既存商品データのベクトル化

```bash
cd netsuper_search_app
python generate_embeddings.py
```

オプション：
- `--limit 100`: 処理する最大件数を指定
- `--delay 0.2`: API呼び出し間の待機時間（秒）

### 4. アプリ実行

**ローカル実行:**
```bash
pip install -r requirements.txt
streamlit run app.py
```

**デプロイ:**
```bash
./deploy.sh
```

## 技術スタック

- **Frontend**: Streamlit
- **Database**: Supabase (PostgreSQL + pgvector)
- **AI**: OpenAI text-embedding-3-small (1536次元)
- **Deployment**: Google Cloud Run
- **Container**: Docker

## ベクトル検索のメリット

従来のキーワード検索では「卵」で検索すると「うずら卵」「たまごサラダ」など、文字列に「卵」を含む商品しか検索できませんでした。

ベクトル検索では、商品名の意味を理解して検索するため：
- 「卵」→ 鶏卵、生卵などダイレクトな商品が上位表示
- 「牛乳 パン」→ 両方のキーワードに関連する商品を検索
- 表記ゆれに強い（例：「トマト」と「tomato」）
