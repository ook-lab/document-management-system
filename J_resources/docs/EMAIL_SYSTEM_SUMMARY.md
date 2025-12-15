# 📧 メールシステム完全ガイド

## 🎯 システム概要

Gmail Vision処理システムは、HTMLメールを自動的に処理し、検索可能な形式でSupabaseに保存するシステムです。**PDFとは完全に分離**されており、既存の機能に一切影響を与えません。

## 📊 システム構成

```
Gmail API
    ↓
メール取得（ラベル: TEST, WORK, DM等）
    ↓
Google Drive保存（HTML + Base64画像埋め込み）
    ↓
Playwright（スクリーンショット生成）
    ↓
Gemini 2.0 Flash-Lite（Vision解析）
    ↓
Supabase（検索可能な形式で保存）
    ↓
メール受信トレイUI（専用表示）
```

## 🔧 主要コンポーネント

### 1. データ取り込み（Gmail → Supabase）

#### `pipelines/gmail_ingestion.py`
- Gmail APIでメール取得
- HTMLに画像をBase64埋め込み
- Google Driveに保存
- Playwrightでスクリーンショット生成
- Gemini 2.0 Flash-LiteでVision解析
- Supabaseに保存

**起動方法**:
```bash
python pipelines/gmail_ingestion.py
```

### 2. Vision処理コア

#### `core/processors/email_vision.py`
- HTMLをスクリーンショット化
- Gemini 2.0 Flash-Liteで解析
- 要約、重要情報を抽出

#### `core/utils/html_screenshot.py`
- Playwright Async APIでスクリーンショット生成
- PNG形式で出力

### 3. Workspace管理

#### `config/workspaces.py`
14種類のWorkspace定義:

**育也関連**:
- `IKUYA_SCHOOL` - 学校関連
- `IKUYA_JUKU` - 塾関連
- `IKUYA_EXAM` - 受験関連

**恵麻関連**:
- `EMA_SCHOOL` - 学校関連

**家庭関連**:
- `HOME_LIVING` - 生活関連
- `HOME_COOKING` - 料理関連

**芳紀個人**:
- `YOSHINORI_PRIVATE_FOLDER`

**仕事**:
- `BUSINESS_WORK`

**メール分類**:
- `IKUYA_MAIL` - 育也宛
- `EMA_MAIL` - 恵麻宛
- `WORK_MAIL` - 仕事
- `DM_MAIL` - DM・広告
- `JOB_MAIL` - 求人
- `MONEY_MAIL` - 金融

### 4. メール表示UI

#### `ui/email_inbox.py`（メインUI）
- メール一覧表示（受信トレイ風）
- メール詳細表示
- Workspaceフィルター
- 期間フィルター
- キーワード検索

#### `ui/components/email_viewer.py`
- メール表示コンポーネント
- ヘッダー、本文、要約、メタデータのタブ表示

**起動方法**:
```bash
./start_email_ui.sh
# または
streamlit run ui/email_inbox.py
```

## 📁 データベーススキーマ

### documentsテーブルの主要カラム

| カラム名 | 役割 | 値の例 |
|---------|------|--------|
| `source_type` | 技術的な出所 | `gmail`, `drive` |
| `file_type` | ファイル形式 | `email`, `pdf`, `excel` |
| `workspace` | **意味的な分類（メイン軸）** | `DM_MAIL`, `WORK_MAIL` |
| `full_text` | メール全文 | テキスト形式 |
| `summary` | AI要約 | テキストまたはJSON |
| `metadata` | メタデータ | JSON形式 |
| `embedding` | ベクトル埋め込み | 1536次元ベクトル |

### メールデータの構造

```json
{
  "source_type": "gmail",
  "file_type": "email",
  "workspace": "DM_MAIL",
  "full_text": "メール情報:\n送信者: ...\n件名: ...\n本文: ...",
  "summary": "AIが生成した要約",
  "metadata": {
    "from": "sender@example.com",
    "to": "recipient@example.com",
    "subject": "件名",
    "date": "2024-12-06",
    "gmail_label": "TEST",
    "workspace": "DM_MAIL",
    "summary": "要約",
    "key_information": ["情報1", "情報2"],
    "has_images": true,
    "links": ["https://..."]
  }
}
```

## 🚀 使い方

### 1. メールを取り込む

```bash
# Gmailから最新メールを取得・処理
python pipelines/gmail_ingestion.py
```

実行内容:
- Gmail APIでメール取得（ラベル: TEST）
- HTMLをGoogle Driveに保存
- Vision処理（Gemini 2.0 Flash-Lite）
- Supabaseに保存

### 2. メールUIで閲覧

```bash
# メール受信トレイUIを起動
./start_email_ui.sh
```

ブラウザで `http://localhost:8501` を開く

### 3. フィルタリング・検索

**Workspaceで絞り込み**:
- サイドバーで「DM_MAIL」を選択
- 広告メールだけを表示

**キーワード検索**:
- サイドバーで「BLACK FRIDAY」と入力
- キャンペーン関連メールを検索

**期間で絞り込み**:
- サイドバーで「今週」を選択
- 今週のメールだけを表示

## 🔒 PDFとの分離（安全性）

### 完全分離の実現方法

1. **データ取得レベル**:
   ```python
   # メールUIでは必ず file_type = 'email' で絞り込み
   query = db.client.table('source_documents').eq('file_type', 'email')
   ```

2. **処理レベル**:
   ```python
   # Gmail取り込みでは source_type = 'gmail' を設定
   email_doc = {
       'source_type': 'gmail',
       'file_type': 'email',
       ...
   }
   ```

3. **UI レベル**:
   - メール専用UI: `ui/email_inbox.py`
   - PDFレビューUI: `ui/review_ui.py`（既存、変更なし）

### 安全性の保証

✅ PDFデータに一切触れない
✅ 既存のPDF処理フローに影響ゼロ
✅ SQLクエリレベルで分離
✅ 別のUIで完全に独立

## 📊 コストと性能

### AI処理コスト

| モデル | 用途 | コスト（1K tokens） |
|-------|------|-------------------|
| Gemini 2.0 Flash-Lite | メールVision処理 | $0.00005 |
| OpenAI text-embedding-3-small | 埋め込み生成 | $0.00002 |

**メール1件あたり**: 約$0.001〜0.01（内容による）

### 処理速度

- メール1件の処理時間: 約10〜20秒
  - スクリーンショット生成: 2〜5秒
  - Vision解析: 5〜10秒
  - 埋め込み生成: 1〜2秒
  - Supabase保存: 1秒

## 🛠️ メンテナンス

### 古いメールのworkspaceを更新

```bash
# マイグレーションスクリプトを実行
python scripts/migrate_email_workspace.py
```

### データベーススキーマ更新

```bash
# Supabase SQL Editorで実行
database/schema_updates/remove_doc_type_column.sql
```

### ログ確認

```bash
# Gmail取り込みログ
tail -f logs/gmail_ingestion.log

# Vision処理ログ
tail -f logs/email_vision.log
```

## 📝 トラブルシューティング

### メールが表示されない
```bash
# 1. データが保存されているか確認
python check_workspace.py

# 2. Gmail取り込みを実行
python pipelines/gmail_ingestion.py
```

### Vision処理がエラーになる
- **原因**: Gemini API keyが未設定
- **解決**: `.env`に`GOOGLE_AI_API_KEY`を設定

### workspaceが "personal" になっている
```bash
# マイグレーションを実行
python scripts/migrate_email_workspace.py
```

## 📚 関連ドキュメント

- [メールUI使用ガイド](./EMAIL_UI_GUIDE.md)
- [Gmail統合セットアップ](./GMAIL_INTEGRATION_SETUP.md)
- [Workspace定義](../config/workspaces.py)

## 🎯 次のステップ

1. **Gmail Labelの設定**:
   - Gmailで実際の分類ラベルを作成（WORK, DM, IKUYA等）
   - `.env`の`GMAIL_LABEL`を変更

2. **自動取り込みの設定**:
   - cronジョブで定期実行
   ```bash
   # 毎時0分に実行
   0 * * * * cd /path/to/project && ./venv/bin/python pipelines/gmail_ingestion.py
   ```

3. **UI のカスタマイズ**:
   - 表示件数の変更
   - フィルター項目の追加
   - カラーテーマの変更

4. **検索機能の強化**:
   - ベクトル検索の実装
   - 類似メール検索
   - カテゴリ自動推薦

---

## ✅ まとめ

- ✅ Gmail → Vision処理 → Supabase の完全自動化
- ✅ PDFとの完全分離（既存機能に影響なし）
- ✅ Workspace軸での柔軟な分類
- ✅ メール専用の見やすいUI
- ✅ 検索・フィルタリング機能
- ✅ 超低コスト（Gemini 2.0 Flash-Lite）

**運用開始準備完了！** 🎉
