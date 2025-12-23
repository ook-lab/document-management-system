# ネットスーパー横断検索アプリ

3つのネットスーパー（楽天西友・東急ストア・ダイエー）を横断検索し、安い順に商品を表示します。

## 機能

- 🔍 商品名での横断検索
- 💰 安い順に自動ソート
- 🖼️ 商品画像表示
- 🔗 各ストアの商品ページへのリンク
- 📊 最大20件まで表示

## デプロイ方法

### 1. 環境変数設定

```bash
export SUPABASE_URL="your-supabase-url"
export SUPABASE_KEY="your-supabase-key"
```

### 2. デプロイ実行

```bash
cd netsuper_search_app
./deploy.sh
```

## ローカル実行

```bash
cd netsuper_search_app
pip install -r requirements.txt
streamlit run app.py
```

## 技術スタック

- **Frontend**: Streamlit
- **Database**: Supabase (80_rd_products)
- **Deployment**: Google Cloud Run
- **Container**: Docker
