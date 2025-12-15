# メール受信トレイUI 使用ガイド

## 📬 概要

Gmail Vision処理されたメールを、PDFとは完全に分離して表示・管理する専用UIです。

## 🎯 特徴

### PDF処理への影響ゼロ
- **完全分離**: `file_type = 'email'` のデータのみを表示
- **安全設計**: PDFデータには一切触れない
- **独立動作**: 既存のPDFレビューUIと別ページで動作

### メール専用の表示形式
- **受信トレイ風UI**: 送信者、件名、日付で見やすく表示
- **メールらしい詳細表示**: ヘッダー、本文、要約を整理
- **ワンクリック操作**: メールを選択して詳細を即座に表示

## 🚀 起動方法

### 1. メール受信トレイUIを起動

```bash
# プロジェクトディレクトリで実行
cd /Users/ookuboyoshinori/document_management_system
source venv/bin/activate
streamlit run ui/email_inbox.py
```

### 2. PDFレビューUI（既存）を起動

```bash
# 別ターミナルで実行（両方同時に使える）
streamlit run ui/review_ui.py --server.port 8502
```

## 📊 画面構成

### 左カラム: メール一覧
```
📬 受信メール一覧
全 15 件のメール
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【残り3日】BLACKFRIDAY大好評...
👤 OASYS株式会社
📝 BLACK FRIDAYキャンペーン...
                          2024-12-06
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
まもなくクーポン終了です!!対...
👤 京橋ワイン楽天店
📝 ワインセール最終日のご案内
                          2024-12-05
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 右カラム: メール詳細

#### 📄 本文タブ
- メールの全文を表示
- 読みやすい形式で整形

#### 📊 要約タブ
- AI（Gemini 2.0 Flash-Lite）が生成した要約
- 重要ポイントの抽出

#### 🔍 重要情報タブ
- キャンペーン期間
- 金額・ポイント情報
- リンク一覧
- 画像の有無

#### ⚙️ メタデータタブ
- 送信者、宛先、日時
- Gmail Label
- Workspace分類
- その他のメタデータ（JSON形式）

## 🔍 フィルター機能

### Workspaceフィルター
```
すべて
DM_MAIL         ← 広告・キャンペーンメール
WORK_MAIL       ← 仕事関連メール
IKUYA_MAIL      ← 育也宛メール
EMA_MAIL        ← 恵麻宛メール
MONEY_MAIL      ← 金融・決済メール
JOB_MAIL        ← 求人・転職メール
```

### 期間フィルター
- すべて
- 今日
- 今週
- 今月
- カスタム（開始日〜終了日を指定）

### キーワード検索
- 件名、本文、送信者から検索
- 部分一致で検索

## 📋 使用例

### 例1: DM・広告メールだけを見る
1. サイドバーで「Workspace」→「DM_MAIL」を選択
2. 広告メールだけがフィルタリングされて表示

### 例2: 特定のキャンペーンを検索
1. サイドバーで「キーワード検索」→「BLACK FRIDAY」と入力
2. BLACK FRIDAYに関連するメールだけを表示

### 例3: 今週届いたメールを確認
1. サイドバーで「期間」→「今週」を選択
2. 今週のメールだけを表示

## 📊 統計情報

サイドバー下部に表示：
- 総メール数
- Workspace別の件数

```
📊 統計
総メール数: 47

Workspace別:
DM_MAIL: 32件
WORK_MAIL: 10件
MONEY_MAIL: 5件
```

## 🔗 外部リンク

各メール詳細画面の下部に表示：

### 📥 元のHTMLをダウンロード
- Google Driveに保存されたHTMLファイルを直接ダウンロード
- 画像付きの完全なメールを確認可能

### 👁️ Google Driveで表示
- Google Driveのプレビューで確認
- ブラウザで開いて閲覧

## 🛠️ トラブルシューティング

### メールが表示されない
**原因**: データがまだSupabaseに保存されていない
**解決策**:
```bash
# Gmail取り込みを実行
python pipelines/gmail_ingestion.py
```

### 画像が表示されない
**原因**: Google DriveのHTMLプレビューの制限
**解決策**: 「元のHTMLをダウンロード」ボタンからファイルをダウンロードして、ブラウザで開く

### フィルターが効かない
**原因**: Supabaseのworkspaceカラムが未設定
**解決策**: マイグレーションスクリプトを実行
```bash
# Supabase SQL Editorで実行
database/schema_updates/remove_doc_type_column.sql
```

## 📁 関連ファイル

```
ui/
├── email_inbox.py              # メール受信トレイUI（メインファイル）
├── components/
│   └── email_viewer.py         # メール表示コンポーネント
└── review_ui.py                # PDFレビューUI（既存、影響なし）

config/
└── workspaces.py               # Workspace定義とマッピング

pipelines/
└── gmail_ingestion.py          # Gmail取り込みパイプライン
```

## 🎨 カスタマイズ

### 表示件数を変更
`ui/email_inbox.py` の `load_emails()` 関数内:
```python
# 現在: 最大100件
query = query.limit(100)

# 変更例: 最大500件
query = query.limit(500)
```

### Workspaceの追加
`config/workspaces.py` に追加:
```python
class Workspace:
    # 新しいworkspaceを追加
    NEW_CATEGORY = "NEW_CATEGORY"
```

## 📝 まとめ

- ✅ PDFとメールを完全に分離
- ✅ メール専用の見やすいUI
- ✅ Workspace・期間・キーワードで柔軟なフィルタリング
- ✅ AI要約と重要情報の自動抽出
- ✅ Google Driveへの直接リンク
