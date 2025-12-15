# 🚨 緊急デプロイ修正ガイド

検索が動かなくなった問題の解決手順です。

## 問題の原因

Supabaseの検索関数が古い`documents`テーブルを参照しているため、検索が失敗しています。

## 解決手順

### Step 1: Supabase SQL関数を更新 ⚡ **今すぐ実行**

1. Supabaseダッシュボードを開く
2. SQL Editorに移動
3. 以下のSQLファイルを実行：

```bash
# このSQLをコピーしてSupabase SQL Editorで実行
cat database/migrate_all_functions_to_source_documents.sql
```

このSQLは以下の関数を更新します：
- ✅ `search_documents_final` - メイン検索関数
- ✅ `get_active_workspaces` - ワークスペース一覧
- ✅ `get_active_doc_types` - ドキュメントタイプ一覧
- ✅ `hybrid_search` - ハイブリッド検索

**実行後、即座に検索が復旧します！**

### Step 2: アプリのデプロイ状況を確認

現在デプロイされているアプリ：

#### 1. mail-doc-search-system (Cloud Run)
- URL: https://mail-doc-search-system-983922127476.asia-northeast1.run.app/
- コード: `app.py`
- デプロイ方法: Cloud Run (Docker)

#### 2. okubo-review-ui (Streamlit Cloud)
- URL: https://okubo-review-ui.streamlit.app/
- コード: `ui/review_ui.py`
- デプロイ方法: Streamlit Cloud

### Step 3: アプリの再デプロイ（念のため）

アプリのコード自体は既に更新済みですが、念のため再デプロイを推奨します。

#### Cloud Run (mail-doc-search-system) の再デプロイ

```bash
# プロジェクトのルートディレクトリで実行
gcloud run deploy mail-doc-search-system \
  --source . \
  --region asia-northeast1 \
  --allow-unauthenticated
```

または、Cloud Consoleから：
1. Cloud Run → mail-doc-search-system を開く
2. 「新しいリビジョンの編集とデプロイ」をクリック
3. 「デプロイ」をクリック

#### Streamlit Cloud (okubo-review-ui) の再デプロイ

Streamlit Cloudは自動デプロイのため、通常は何もする必要がありません。
もし動作しない場合：

1. https://share.streamlit.io/ にログイン
2. アプリを選択
3. 「Reboot app」をクリック

### Step 4: 動作確認

#### mail-doc-search-system の確認

```bash
# ヘルスチェック
curl https://mail-doc-search-system-983922127476.asia-northeast1.run.app/api/health

# フィルタAPI確認
curl https://mail-doc-search-system-983922127476.asia-northeast1.run.app/api/filters
```

期待される結果：
```json
{
  "status": "ok",
  "message": "Document Q&A System is running"
}
```

#### okubo-review-ui の確認

ブラウザで https://okubo-review-ui.streamlit.app/ を開いて、以下を確認：
- ✅ ページが正常に表示される
- ✅ ドキュメント一覧が表示される
- ✅ エラーメッセージが出ない

## トラブルシューティング

### Q: SQL実行後もまだ検索が動かない

**A:** キャッシュの問題の可能性があります。以下を試してください：

1. ブラウザのキャッシュをクリア
2. シークレットモードで開く
3. 5分待ってから再試行（関数の反映に時間がかかる場合があります）

### Q: Streamlitアプリでエラーが出る

**A:** エラーメッセージを確認：

```
'Node' で 'removeChild' を実行できませんでした
```

これはStreamlit側のUI問題です。以下を試してください：
1. ページをリロード（Cmd+R / Ctrl+R）
2. ブラウザのキャッシュをクリア
3. Streamlit Cloudでアプリを再起動

### Q: Cloud Runアプリがタイムアウトする

**A:** コールドスタートの可能性があります：
1. もう一度アクセス（2回目は速くなります）
2. Cloud Consoleで最小インスタンス数を1に設定

## 完了確認チェックリスト

- [ ] Supabase SQL実行完了
- [ ] mail-doc-search-system で検索が動作
- [ ] okubo-review-ui でドキュメント一覧が表示
- [ ] エラーログがない

全てチェックできたら、修正完了です！🎉

## 技術的な背景

### なぜこの問題が発生したか

1. コードを`table('documents')` → `table('source_documents')`に更新
2. しかし、Supabaseの**SQL関数**は別ファイルで管理されている
3. SQL関数が古い`documents`テーブルを参照していた
4. `documents`ビューを削除したため、関数が動かなくなった

### 修正内容

- **Pythonコード**: 既に全て`source_documents`に更新済み ✅
- **SQL関数**: `migrate_all_functions_to_source_documents.sql`で更新 ✅
- **デプロイ**: 最新コードで再デプロイ ✅

これで3-tier構造への移行が完全に完了します！
