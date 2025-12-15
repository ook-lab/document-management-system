# Streamlit Cloud デプロイメントガイド

## エラーの原因

Streamlit Cloudでアプリが動作しない主な原因は、**環境変数（シークレット）が設定されていない**ことです。

アプリは以下の環境変数を必要としています：
- API キー（Google AI、Anthropic、OpenAI）
- データベース接続情報（Supabase）
- Google Drive フォルダーID
- Google サービスアカウント認証情報

## 修正手順

### 1. Streamlit Cloudでシークレットを設定

1. **Streamlit Cloud にログイン**
   - https://share.streamlit.io/ にアクセス

2. **アプリの設定画面を開く**
   - デプロイされているアプリ（okubo-review-ui）を選択
   - 右上の「⚙️ Settings」をクリック

3. **Secrets タブを開く**
   - 左メニューから「Secrets」を選択

4. **環境変数を設定**

   以下の形式で、ローカルの `.env` ファイルの内容をコピー＆ペーストします：

   ```toml
   # AI API Keys
   GOOGLE_AI_API_KEY = "your-actual-key"
   ANTHROPIC_API_KEY = "your-actual-key"
   OPENAI_API_KEY = "your-actual-key"

   # Database (Supabase)
   SUPABASE_URL = "your-supabase-url"
   SUPABASE_KEY = "your-supabase-key"

   # Google Drive Folder IDs
   BUSINESS_FOLDER_ID = "your-folder-id"
   PERSONAL_FOLDER_ID = "your-folder-id"
   IKUYA_SCHOOL_FOLDER_ID = "your-folder-id"
   IKUYA_JUKU_FOLDER_ID = "your-folder-id"
   IKUYA_EXAM_FOLDER_ID = "your-folder-id"
   EMA_SCHOOL_FOLDER_ID = "your-folder-id"
   HOME_LIVING_FOLDER_ID = "your-folder-id"
   HOME_COOKING_FOLDER_ID = "your-folder-id"
   YOSHINORI_PRIVATE_FOLDER_ID = "your-folder-id"
   BUSINESS_WORK_FOLDER_ID = "your-folder-id"

   # Model Configuration
   ANSWER_MODEL = "gemini-2.0-flash-exp"
   EMBEDDING_MODEL = "text-embedding-004"

   # Other Settings
   LOG_LEVEL = "INFO"
   RERANK_ENABLED = "true"
   ```

   **重要**: Google認証情報（GOOGLE_APPLICATION_CREDENTIALS）は、JSONファイルの内容全体を文字列として貼り付ける必要があります。

5. **Save をクリック**
   - 変更を保存すると、アプリが自動的に再起動します

### 2. このリポジトリの変更をプッシュ

ローカルで以下のファイルを追加しました：
- `.streamlit/config.toml` - Streamlit設定
- `.streamlit/secrets.toml.example` - シークレットのテンプレート
- `STREAMLIT_DEPLOYMENT.md` - このガイド
- `.gitignore` の更新（secrets.toml を除外）

これらをGitHubにプッシュします：

```bash
cd ~/document_management_system
git add .streamlit/config.toml .streamlit/secrets.toml.example STREAMLIT_DEPLOYMENT.md .gitignore
git commit -m "Add Streamlit Cloud configuration and deployment guide

- Add .streamlit/config.toml for Streamlit settings
- Add .streamlit/secrets.toml.example as template
- Add deployment guide for Streamlit Cloud
- Update .gitignore to exclude secrets.toml

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
git push
```

### 3. アプリが再起動されるのを待つ

Streamlit Cloudでシークレットを設定すると、アプリが自動的に再起動します。
数分待ってから、https://okubo-review-ui.streamlit.app/ にアクセスしてください。

## トラブルシューティング

### エラーログの確認方法

1. Streamlit Cloud のアプリページにアクセス
2. 右下の「Manage app」→「Logs」をクリック
3. エラーメッセージを確認

### よくあるエラー

#### ImportError や ModuleNotFoundError
- `requirements.txt` に必要なパッケージが記載されているか確認
- パッケージバージョンの互換性を確認

#### 認証エラー
- Secrets に正しいAPIキーが設定されているか確認
- Google認証情報のJSONが正しいフォーマットか確認

#### データベース接続エラー
- Supabase の URL と KEY が正しいか確認
- ネットワーク接続を確認

## ローカルでのテスト

Streamlit Cloudにデプロイする前に、ローカルでテストできます：

1. `.env` ファイルから `.streamlit/secrets.toml` を作成：

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# secrets.toml を編集して、実際の値を設定
```

2. Streamlit を起動：

```bash
streamlit run ui/review_ui.py
```

3. ブラウザで http://localhost:8501 を開く

## 参考リンク

- [Streamlit Cloud Documentation](https://docs.streamlit.io/streamlit-community-cloud)
- [Secrets Management](https://docs.streamlit.io/streamlit-community-cloud/deploy-your-app/secrets-management)
