# InBox自動監視システム セットアップガイド

## 概要

InBox自動監視システムは、Google Driveの特定フォルダ（InBox）を毎時監視し、新規追加されたPDFファイルを自動的に検出・処理するシステムです。

## アーキテクチャ

```
Google Drive InBox Folder
         ↓
GitHub Actions (毎時実行)
         ↓
inbox_monitor.py (新規ファイル検出)
         ↓
TwoStageIngestionPipeline (AI処理)
  ├─ Stage 1: Gemini (文書分類)
  └─ Stage 2: Claude (メタデータ抽出)
         ↓
Supabase (データ保存)
         ↓
Google Drive Archive Folder (処理済みファイル移動)
```

## セットアップ手順

### 1. Google Drive フォルダ構造の準備

以下のフォルダ構造を作成してください:

```
DB/
├── InBox/          # 新規ファイルを置くフォルダ
└── Archive/        # 処理済みファイルが移動されるフォルダ
```

### 2. フォルダIDの取得

1. Google Driveで各フォルダを開く
2. URLから フォルダIDをコピー
   - URL形式: `https://drive.google.com/drive/folders/{FOLDER_ID}`
   - `{FOLDER_ID}` の部分をコピー

例:
```
InBox Folder ID: 1aB2cD3eF4gH5iJ6kL7mN8oP9qR0sT1u
Archive Folder ID: 2bC3dE4fG5hI6jK7lM8nO9pQ0rS1tU2v
```

### 3. GitHub Secrets の設定

GitHub リポジトリの Settings → Secrets and variables → Actions で以下を追加:

#### 必須のSecrets

| Secret Name | 説明 | 取得方法 |
|------------|------|---------|
| `INBOX_FOLDER_ID` | InBoxフォルダのID | 手順2で取得 |
| `ARCHIVE_FOLDER_ID` | Archiveフォルダのid | 手順2で取得 |
| `GOOGLE_CREDENTIALS_JSON` | Google Drive API認証情報 | GCPコンソールから取得 |
| `GOOGLE_API_KEY` | Gemini API Key | Google AI Studioから取得 |
| `ANTHROPIC_API_KEY` | Claude API Key | Anthropic Consoleから取得 |
| `SUPABASE_URL` | SupabaseプロジェクトURL | Supabase Dashboardから取得 |
| `SUPABASE_KEY` | Supabase API Key | Supabase Dashboardから取得 |

### 4. Google Drive API 権限の確認

サービスアカウントに以下の権限が必要です:

- ✅ ファイルの読み取り
- ✅ ファイルの移動（削除せずに親フォルダを変更）
- ✅ フォルダ内のファイル一覧取得

**重要**: `core/connectors/google_drive.py` のSCOPESが以下になっていることを確認:
```python
SCOPES = ['https://www.googleapis.com/auth/drive']
```

### 5. ローカル環境での動作確認

GitHub Actionsで実行する前に、ローカルで動作確認を行います:

#### 環境変数の設定

`.env` ファイルに以下を追加:

```bash
# Google Drive
INBOX_FOLDER_ID=your_inbox_folder_id_here
ARCHIVE_FOLDER_ID=your_archive_folder_id_here
GOOGLE_APPLICATION_CREDENTIALS=/path/to/google_credentials.json

# AI APIs
GOOGLE_API_KEY=your_gemini_api_key_here
ANTHROPIC_API_KEY=your_claude_api_key_here

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_key_here
```

#### 実行コマンド

```bash
# 仮想環境をアクティベート
source venv/bin/activate  # Linux/Mac
# または
venv\Scripts\activate  # Windows

# InBox監視スクリプトを実行
python scripts/inbox_monitor.py
```

#### 期待される出力

```
====================================================================
🔍 InBox自動監視システム 開始
実行時刻: 2025-11-27 22:30:00
====================================================================
📊 データベースから処理済みファイルIDを取得中...
✅ 5 件の処理済みファイルIDを取得
📁 InBoxフォルダ [1aB2cD3eF4gH5iJ6kL7mN8oP9qR0sT1u] をスキャン中...
InBox内の全ファイル数: 3, 新規ファイル数: 2
🆕 2 件の新規ファイルを検出:
  - test_document.pdf (ID: 1xY2zW3...)
  - invoice_sample.pdf (ID: 2aB3cD4...)
⚙️  ファイル処理開始: test_document.pdf
✅ ファイル処理成功: test_document.pdf
📦 ファイルをArchiveに移動中: test_document.pdf
✅ ファイル移動成功: test_document.pdf -> Archive
...
====================================================================
📊 InBox自動監視システム 完了サマリー
新規ファイル検出数: 2
処理成功数: 2
処理失敗数: 0
アーカイブ成功数: 2
アーカイブ失敗数: 0
====================================================================
```

## GitHub Actions での自動実行

### ワークフローファイル

`.github/workflows/hourly_monitor.yml` が自動的に以下のスケジュールで実行されます:

```yaml
schedule:
  - cron: '0 * * * *'  # 毎時0分 (UTC)
```

### 実行スケジュール

- **UTC 0:00** → JST 9:00 (午前)
- **UTC 1:00** → JST 10:00
- **UTC 2:00** → JST 11:00
- ...（毎時実行）

### 手動実行

GitHub Actions画面から手動でトリガーすることも可能:

1. GitHub リポジトリ → Actions タブ
2. "02. InBox Hourly Monitor" を選択
3. "Run workflow" ボタンをクリック

## トラブルシューティング

### エラー: "INBOX_FOLDER_ID が環境変数に設定されていません"

**原因**: 環境変数が正しく設定されていない

**解決策**:
- ローカル: `.env` ファイルを確認
- GitHub Actions: Secrets設定を確認

### エラー: "Google Drive認証に失敗しました"

**原因**: 認証情報が無効または権限不足

**解決策**:
1. サービスアカウントのJSON認証情報を再生成
2. Google Drive APIが有効になっているか確認
3. InBoxフォルダがサービスアカウントと共有されているか確認

### エラー: "Permission denied" (ファイル移動時)

**原因**: Google Drive APIのスコープが `readonly` になっている

**解決策**:
`core/connectors/google_drive.py` の17行目を確認:
```python
SCOPES = ['https://www.googleapis.com/auth/drive']  # ← readonlyではない
```

### 新規ファイルが検出されない

**チェックリスト**:
- ✅ InBoxフォルダIDが正しいか
- ✅ ファイルがPDF形式か
- ✅ ファイルが既に処理済み（Supabaseに登録済み）ではないか
- ✅ ファイルがゴミ箱に入っていないか

### 処理が遅い / タイムアウトする

**原因**: 大量のファイルがInBoxに溜まっている

**解決策**:
1. InBox内のファイル数を減らす
2. GitHub Actionsのタイムアウトを延長:
   ```yaml
   timeout-minutes: 60  # デフォルト30分を60分に延長
   ```

## ログの確認

### ローカル環境

```bash
# ログディレクトリを確認
ls logs/

# 最新のログファイルを表示
tail -f logs/inbox_monitor_*.log
```

### GitHub Actions

1. GitHub リポジトリ → Actions タブ
2. 実行履歴から該当のワークフローを選択
3. "Run InBox Monitor" ステップを展開
4. または "inbox-monitor-logs" アーティファクトをダウンロード

## 実装詳細

### 主要ファイル

| ファイル | 説明 |
|---------|------|
| `scripts/inbox_monitor.py` | InBox監視のメインスクリプト |
| `core/connectors/google_drive.py` | Google Drive API連携（拡張済み） |
| `core/database/client.py` | Supabaseデータベースクライアント（拡張済み） |
| `.github/workflows/hourly_monitor.yml` | GitHub Actions定義 |
| `config/settings.py` | 環境変数設定（拡張済み） |

### 追加されたメソッド

#### GoogleDriveConnector

```python
def get_inbox_folder_id() -> Optional[str]
    """環境変数からInBoxフォルダIDを取得"""

def get_archive_folder_id() -> Optional[str]
    """環境変数からArchiveフォルダIDを取得"""

def list_inbox_files(folder_id: str, processed_file_ids: List[str]) -> List[Dict[str, Any]]
    """InBoxフォルダ内の新規ファイルを取得"""

def move_file(file_id: str, new_folder_id: str) -> bool
    """ファイルを別のフォルダに移動"""
```

#### DatabaseClient

```python
def get_processed_file_ids() -> List[str]
    """既に処理済みのファイルIDリストを取得"""
```

## 運用フロー

### 通常運用

1. ユーザーがPDFファイルをInBoxフォルダにアップロード
2. 毎時0分にGitHub Actionsが自動実行
3. 新規ファイルを検出し、AI処理を実行
4. 処理成功したファイルをArchiveフォルダに移動
5. Supabaseに結果を保存

### エラー発生時

1. 処理失敗したファイルはInBoxに残る
2. 次回の実行時に再試行される
3. ログを確認して原因を特定
4. 必要に応じて手動で対応

## セキュリティ考慮事項

### 認証情報の管理

- ✅ `.env` ファイルは `.gitignore` に追加済み
- ✅ GitHub Secretsは暗号化されて保存される
- ✅ 認証情報はワークフロー実行後に自動削除

### アクセス制御

- Google Driveフォルダは必要最小限のアクセス権限で共有
- サービスアカウントのJSONキーは定期的にローテーション推奨

## パフォーマンス最適化

### 推奨設定

- InBox内のファイル数: **最大50件以下**
- 1ファイルの処理時間: **平均2-5分**
- 並列処理: **現在は順次処理（将来的に並列化可能）**

### スケーリング

大量のファイルを処理する場合:
1. InBoxを複数に分割
2. 実行頻度を30分に1回に変更
3. 別途バッチ処理を実装

## まとめ

InBox自動監視システムにより、以下が実現されます:

✅ **完全自動化**: PDFをアップロードするだけで処理開始
✅ **スケジュール実行**: 毎時自動的に新規ファイルをチェック
✅ **ファイル整理**: 処理済みファイルは自動的にArchiveへ移動
✅ **エラーハンドリング**: 失敗したファイルは再試行可能
✅ **透明性**: ログで処理状況を完全に追跡可能

## サポート

問題が発生した場合:
1. ログファイルを確認
2. 環境変数が正しく設定されているか確認
3. Google Drive/Supabaseの接続状態を確認
4. GitHub Issues でサポートを依頼
