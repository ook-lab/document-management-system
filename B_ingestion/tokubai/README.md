# トクバイチラシ取得パイプライン

トクバイのウェブサイトから自動的にチラシ画像を取得し、Google DriveとSupabaseに登録するパイプラインです。

## 概要

このモジュールは、指定されたトクバイの店舗ページから最新のチラシ画像を自動的に取得し、既存のドキュメント管理システムに統合します。

### 処理フロー

1. **チラシ一覧の取得**: トクバイの店舗ページからチラシのリンク一覧を取得
2. **新着チェック**: Supabaseで既存のチラシIDをチェックし、新着のみを抽出
3. **画像ダウンロード**: 各チラシページから画像URLを抽出してダウンロード
4. **Google Drive保存**: ダウンロードした画像をGoogle Driveにアップロード
5. **Supabase登録**: メタデータとともにSupabaseに登録（`processing_status='pending'`）
6. **後続処理**: `process_queued_documents.py`でOCR処理やAI分析を実行

## ファイル構成

```
B_ingestion/tokubai/
├── __init__.py              # モジュール初期化
├── tokubai_scraper.py       # スクレイピング処理
├── flyer_ingestion.py       # メインパイプライン
└── README.md                # このファイル
```

## セットアップ

### 1. 環境変数の設定

`.env`ファイルに以下の環境変数を追加してください:

```env
# Tokubai (トクバイ) Flyer Integration
TOKUBAI_STORE_URL=https://tokubai.co.jp/フーディアム/7978
TOKUBAI_FLYER_FOLDER_ID=1uQEJbV94mBC2y0D0FQztDGrzy6UNgEhv
```

- `TOKUBAI_STORE_URL`: 対象店舗のトクバイURL
- `TOKUBAI_FLYER_FOLDER_ID`: チラシ画像の保存先Google DriveフォルダID

### 2. 必要なライブラリ

以下のライブラリが必要です（`requirements.txt`に含まれています）:

- `requests`: HTTPリクエスト
- `beautifulsoup4`: HTMLパース
- `lxml`: HTML/XMLパーサー
- `google-api-python-client`: Google Drive API
- その他の既存依存関係

インストール:

```bash
pip install -r requirements.txt
```

## 使用方法

### 手動実行

プロジェクトルートから以下のコマンドを実行:

```bash
python -m B_ingestion.tokubai.flyer_ingestion
```

### 実行結果

成功すると以下のような出力が表示されます:

```
🛒 トクバイチラシ取得結果
================================================================================

Flyer ID: 1234567
  Success: True
  Images: 2
    - https://drive.google.com/file/d/xxx/view
    - https://drive.google.com/file/d/yyy/view
  Documents: 2 (pending)

================================================================================
次のステップ:
  python process_queued_documents.py --workspace=household
================================================================================
```

### 後続処理

チラシ画像がSupabaseに登録された後、OCR処理とAI分析を実行します:

```bash
python process_queued_documents.py --workspace=household
```

これにより、以下の処理が実行されます:

- Stage A: ドキュメント分類
- Stage B: Vision API による画像解析（チラシの内容抽出）
- Stage C: テキスト抽出と要約生成

## 定期実行の設定

### GitHub Actions での定期実行

`.github/workflows/tokubai_flyer_sync.yml`を作成:

```yaml
name: Tokubai Flyer Sync

on:
  schedule:
    # 毎日午前9時（JST）に実行
    - cron: '0 0 * * *'
  workflow_dispatch:  # 手動実行も可能

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Run flyer ingestion
        env:
          TOKUBAI_STORE_URL: ${{ secrets.TOKUBAI_STORE_URL }}
          TOKUBAI_FLYER_FOLDER_ID: ${{ secrets.TOKUBAI_FLYER_FOLDER_ID }}
          GOOGLE_APPLICATION_CREDENTIALS: ${{ secrets.GOOGLE_APPLICATION_CREDENTIALS }}
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
        run: |
          python -m B_ingestion.tokubai.flyer_ingestion
```

### ローカル環境での定期実行（cron）

Linux/macOSの場合:

```bash
# crontabを編集
crontab -e

# 毎日午前9時に実行
0 9 * * * cd /path/to/document-management-system && /path/to/python -m B_ingestion.tokubai.flyer_ingestion >> /path/to/logs/tokubai.log 2>&1
```

Windowsの場合:

タスクスケジューラを使用してバッチファイルを定期実行するように設定します。

## データベーススキーマ

チラシデータは`source_documents`テーブルに以下の形式で保存されます:

| フィールド | 値の例 |
|-----------|-------|
| `source_type` | `'tokubai_flyer'` |
| `source_id` | Google DriveファイルID |
| `file_type` | `'image'` |
| `doc_type` | `'トクバイチラシ'` |
| `workspace` | `'household'` |
| `organization` | `'フーディアム'` |
| `processing_status` | `'pending'` → `'completed'` |
| `processing_stage` | `'tokubai_flyer_downloaded'` |

### メタデータ（`metadata`フィールド）

```json
{
  "flyer_id": "1234567",
  "flyer_title": "特売チラシ",
  "flyer_period": "2025.12.18 - 2025.12.20",
  "flyer_url": "https://tokubai.co.jp/フーディアム/7978/1234567",
  "image_url": "https://...",
  "page_number": 1,
  "store_url": "https://tokubai.co.jp/フーディアム/7978"
}
```

## トラブルシューティング

### 403 Forbidden エラー

トクバイのサーバーがボットと判定している可能性があります。`tokubai_scraper.py`の`User-Agent`ヘッダーを調整してください。

### 画像が取得できない

- チラシページのHTML構造が変更された可能性があります
- `tokubai_scraper.py`の`extract_image_urls()`メソッドを確認し、セレクタを修正してください

### 重複データが登録される

- `check_existing_flyers()`でSupabaseの既存チェックが正しく動作しているか確認
- `metadata->flyer_id`が正しく保存されているか確認

## 既存パイプラインとの統合

このモジュールは、既存の`B_ingestion`配下の他のモジュール（`gmail`、`waseda_academy`）と同じパターンで実装されています:

- `A_common/connectors/google_drive.py`を使用してGoogle Driveへアップロード
- `A_common/database/client.py`を使用してSupabaseへ登録
- `process_queued_documents.py`で統一的な後続処理を実行

## 今後の拡張

- [ ] 複数店舗への対応
- [ ] チラシの期間情報の詳細な抽出
- [ ] 商品情報の自動抽出（AI分析）
- [ ] 価格比較機能との連携
- [ ] エラー通知機能（Slack/Email）

## ライセンス

このプロジェクトは既存のdocument-management-systemプロジェクトのライセンスに従います。
