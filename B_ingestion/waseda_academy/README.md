# 早稲田アカデミーOnlineお知らせ取得

このモジュールは、早稲田アカデミーOnlineのお知らせページから新着PDFを自動取得し、Google DriveとSupabaseに保存します。

## 機能

- HTMLファイルから`window.appProps`のJSONデータを抽出
- Supabaseベースの差分検出（新着お知らせのみを処理）
- PDFファイルのダウンロード
- Google Driveへの自動保存
- Supabaseへの基本情報登録（`pending`状態）
- `process_queued_documents.py`による後続処理

## 処理フロー

```
1. HTMLからお知らせ情報を抽出
2. Supabaseで既存データをチェック（差分検出）
3. PDFをダウンロード & Google Driveに保存
4. Supabaseに基本情報を登録（processing_status='pending'）
5. 別途 process_queued_documents.py で処理
   → PDF抽出、Stage A/B/C、embedding生成
```

## セットアップ

### 1. 環境変数の設定

`.env`ファイルに以下の環境変数を設定してください：

```bash
# 早稲田アカデミーOnline設定
WASEDA_PDF_FOLDER_ID=1qe3JsuJB_TKvRZJ9M3bvaqrEk2gsAhJY

# ログイン情報（ブラウザ自動化用）
WASEDA_LOGIN_ID=your_login_id@example.com
WASEDA_PASSWORD=your_password_here
```

### 2. Playwrightのインストール

```bash
# パッケージをインストール
pip install -r requirements.txt

# Playwrightブラウザをインストール
playwright install chromium
```

## 使い方

### ステップ1: お知らせ取得（PDF保存 & Supabase登録）

**推奨: ブラウザ自動化モード（自動ログイン → HTML取得 → PDF取得）**

```bash
cd /Users/ookuboyoshinori/document_management_system
python3 -m B_ingestion.waseda_academy.notice_ingestion --browser
```

**デバッグモード（HTMLファイルから読み込み）**

```bash
# pasted_content.txt をプロジェクトルートに配置してから実行
python3 -m B_ingestion.waseda_academy.notice_ingestion
```

**処理内容**:
- ブラウザ自動化でログイン
- お知らせページのHTMLを取得
- 新着お知らせを検出
- PDFを一括ダウンロード
- Google Driveに保存
- Supabaseに基本情報を登録（`processing_status='pending'`）

### ステップ2: PDF処理（テキスト抽出 & AI処理）

```bash
python3 process_queued_documents.py --workspace=waseda_academy --limit=20
```

**処理内容**:
- PDFからテキストを抽出（`attachment_text`）
- Stage A/B/Cで処理（分類、メタデータ抽出、要約生成）
- embeddingを生成して`search_index`に保存
- `processing_status`を`completed`に更新

## データ構造

### ステップ1で保存される基本情報

```python
{
    'source_type': 'waseda_academy_notice',
    'source_id': '<Google Drive file ID>',
    'file_name': '武蔵小杉校通信12月号',
    'file_type': 'pdf',
    'doc_type': '早稲アカオンライン',  # 固定値
    'workspace': 'waseda_academy',
    'processing_status': 'pending',
    'attachment_text': '',  # 空（ステップ2で抽出）
    'summary': '',  # 空（ステップ2で生成）
    # 表示用フィールド
    'display_subject': '月のお知らせ12月号「武蔵小杉校通信」',
    'display_sent_at': '2025-11-25T00:00:00',
    'display_sender': '武蔵小杉校',
    'display_post_text': '2025年12月の武蔵小杉校通信を公開致します。',
    # メタデータ
    'metadata': {
        'notice_id': 'F2E9401B-4D23-474A-8A27-A843CF1458FA',
        'notice_title': '月のお知らせ12月号「武蔵小杉校通信」',
        'notice_date': '2025.11.25',
        'notice_source': '武蔵小杉校',
        'notice_category': '月のお知らせ',
        'notice_message': '...',
        'pdf_url': 'https://online.waseda-ac.co.jp/notice/.../pdf/0',
        'pdf_title': '武蔵小杉校通信12月号'
    }
}
```

### ステップ2で追加される情報

- `attachment_text`: PDFから抽出されたテキスト全文
- `summary`: AI生成の要約
- `tags`: AI判定のタグ
- `processing_status`: `'completed'`
- `search_index`テーブルにembeddingデータ

## フィールドマッピング

| お知らせ情報 | `source_documents`フィールド | 例 |
|------------|---------------------------|-----|
| タイトル | `display_subject` | "月のお知らせ12月号「武蔵小杉校通信」" |
| 日付 | `display_sent_at` | "2025-11-25T00:00:00" |
| 発信元 | `display_sender` | "武蔵小杉校" |
| 本文 | `display_post_text` | "2025年12月の武蔵小杉校通信を..." |
| PDFタイトル | `file_name` | "武蔵小杉校通信12月号" |
| カテゴリ | `doc_type` | "早稲アカオンライン"（固定） |

## 差分検出

**Supabaseベース**で差分を検出します：

- `source_documents`テーブルの`metadata->notice_id`を検索
- 既に存在するIDはスキップ
- **ファイルベースの管理（`known_waseda_notice_ids.json`）は不要**

## トラブルシューティング

### ログインに失敗する

- `.env`ファイルの`WASEDA_LOGIN_ID`と`WASEDA_PASSWORD`が正しいか確認
- ログインページのHTML構造が変更されていないか確認（セレクタの更新が必要な場合があります）
- `--browser`オプションなしで実行すると、ヘッドレスモードがオフになりブラウザが表示されます（デバッグ用）

### HTMLからデータが抽出できない

- `window.appProps`が含まれているか確認
- ログインページのHTMLと間違えていないか確認（ログイン成功後のページを取得する必要があります）

### PDFダウンロードが失敗する

- ブラウザ自動化を使用している場合、ログインが成功しているか確認
- Playwrightのブラウザがインストールされているか確認（`playwright install chromium`）
- PDFのURLが正しいか確認

### Google Driveへの保存が失敗する

- Google認証情報が正しく設定されているか確認
- フォルダIDが正しいか確認（`.env`の`WASEDA_PDF_FOLDER_ID`）
- サービスアカウントにフォルダへの書き込み権限があるか確認

### Supabaseへの保存が失敗する

- Supabase接続情報（URL、KEY）が正しいか確認（`.env`）
- `source_documents`テーブルが存在するか確認
- テーブルのスキーマが要件を満たしているか確認

## コマンド例

```bash
# 1. お知らせ取得（ブラウザ自動化）
python3 -m B_ingestion.waseda_academy.notice_ingestion --browser

# 1. お知らせ取得（デバッグモード: HTMLファイルから）
python3 -m B_ingestion.waseda_academy.notice_ingestion

# 2. PDF処理（全体）
python3 process_queued_documents.py --workspace=waseda_academy

# 2. PDF処理（制限付き）
python3 process_queued_documents.py --workspace=waseda_academy --limit=10

# 2. ドライラン（確認のみ）
python3 process_queued_documents.py --workspace=waseda_academy --dry-run
```

## ファイル構造

```
document_management_system/
├── B_ingestion/
│   └── waseda_academy/
│       ├── __init__.py
│       ├── browser_automation.py  # Playwrightブラウザ自動化
│       ├── notice_ingestion.py    # メインパイプライン
│       └── README.md              # このファイル
├── pasted_content.txt             # HTMLソースファイル（デバッグ用）
└── process_queued_documents.py    # PDF処理スクリプト
```

## GitHub Actions での自動実行

### GitHub Secrets の設定

GitHub リポジトリの Settings → Secrets and variables → Actions で以下のシークレットを追加：

```
WASEDA_LOGIN_ID=your_login_id@example.com
WASEDA_PASSWORD=your_password_here
```

### ワークフローファイル例

`.github/workflows/waseda_notice.yml`:

```yaml
name: Waseda Academy Notice Ingestion

on:
  schedule:
    - cron: '0 9 * * *'  # 毎日午前9時（JST 18時）に実行
  workflow_dispatch:  # 手動実行も可能

jobs:
  ingest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          playwright install chromium
          playwright install-deps chromium

      - name: Run notice ingestion
        env:
          WASEDA_LOGIN_ID: ${{ secrets.WASEDA_LOGIN_ID }}
          WASEDA_PASSWORD: ${{ secrets.WASEDA_PASSWORD }}
          WASEDA_PDF_FOLDER_ID: ${{ secrets.WASEDA_PDF_FOLDER_ID }}
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
          GOOGLE_APPLICATION_CREDENTIALS: credentials.json
        run: |
          echo "${{ secrets.GOOGLE_CREDENTIALS }}" > credentials.json
          python -m B_ingestion.waseda_academy.notice_ingestion --browser
```

## 今後の拡張

- [x] ログイン自動化（Playwright実装済み）
- [x] PDFダウンロードの一括化（実装済み）
- [ ] GitHub Actionsでのスケジュール実行（手順を記載済み）
- [ ] メール通知機能（新着お知らせの通知）
- [ ] エラーハンドリングとリトライ機能の強化
- [ ] ログイン失敗時の通知機能
