# 家計簿自動化システム (K_kakeibo)

**「スキャンするだけで、文脈まで理解した家計簿が出来上がる」**

ScanSnap + Google Drive + Gemini API + Supabase を使った、完全自動化家計簿システムです。

---

## 特徴

### ✅ 自動処理フロー
1. **ScanSnap** でレシートをスキャン → **Google Drive** に自動保存
2. Python が定期的に監視 → 新しい画像を検出
3. **Gemini 1.5 Flash** で OCR + 構造化
4. 正規化・税計算 → **Supabase** に保存
5. 処理済み画像を自動アーカイブ

### 🎯 高度な文脈理解
- **イベント期間判定**: 旅行期間中のレシートは自動的に「家族旅行」に分類
- **表記ゆれ吸収**: エイリアステーブルで「ぎゅうにゅう」→「牛乳」に自動変換
- **商品辞書**: レシート表記から正式名称・カテゴリを自動判定
- **内税額自動計算**: 8%/10%の混在レシートも自動計算＋整合性チェック

### 🛠️ 手動修正機能
- Streamlit UI で OCR ミスを簡単修正
- マスタデータ（商品辞書・エイリアス・イベント）をブラウザで管理

---

## システム構成

```
┌─────────────┐
│  ScanSnap   │ (WiFi経由)
└──────┬──────┘
       │ JPG保存
       ▼
┌─────────────┐
│ Google Drive│ (/My_Kakeibo/00_Inbox)
└──────┬──────┘
       │ 監視・ダウンロード
       ▼
┌─────────────┐
│  Python     │ (main.py)
│  - OCR処理  │ ← Gemini API
│  - 正規化   │ ← マスタDB参照
│  - DB登録   │ → Supabase
└──────┬──────┘
       │ 処理後移動
       ▼
┌─────────────┐
│ Archive     │ (/99_Archive/YYYY-MM/)
└─────────────┘
```

---

## 税額自動計算機能

### 特徴
- **税込合計額が絶対に正しい**: 支払い金額（税込合計）を基準に税額を逆算
- **8%/10%の自動判定**: Geminiが商品名から税率を推測（食品=8%、それ以外=10%）
- **商品辞書優先**: 登録済み商品は辞書の税率を使用（確実性重視）
- **按分計算**: グループ単位で税額を計算し、各商品に按分
- **端数処理**: 端数（±1円）は最初の商品に加算

### 仕組み
```
1. 各商品の税率を決定
   ┗ 商品辞書にマッチ → 辞書の税率（確定）
   ┗ 未登録 → Geminiの推測（暫定）

2. 商品を8%/10%にグループ化
   ┗ 8%商品: 牛乳、パン等（食品）
   ┗ 10%商品: 洗剤、雑貨等

3. 各グループの税込合計を計算
   ┗ 8%グループ税込合計 + 10%グループ税込合計 = レシート総額

4. グループごとに税額を逆算
   ┗ 8%税額 = 8%対象税込額 × (8/108)
   ┗ 10%税額 = 10%対象税込額 × (10/110)

5. 各商品に税額を按分
   ┗ 税込額の比率で按分（切り捨て）
   ┗ 端数は最初の商品に加算

例：本体5円×2個（10%税率）
   → 税込合計11円、税額1円
   → 商品1: 内税1円、商品2: 内税0円
```

### 整合性保証
- **税込合計 = 各商品の税込額の合計**（必ず一致）
- **税額合計 = 各商品の内税額の合計**（必ず一致）
- レシート記載の税額との差分は±1円以内

### レビューUIでの表示
- 各商品の税率・内税額を表示
- 8%/10%別の税額合計を表示
- レシート記載値との比較表を表示
- 不一致があれば⚠️マークで警告

---

## セットアップ

### 1. 前提条件
- Python 3.10+
- ScanSnap iX series (WiFi対応モデル)
- Google Cloud アカウント
- Supabase アカウント
- Gemini API キー

### 2. Supabase セットアップ

Supabase の SQL Editor で以下を実行:

```bash
# プロジェクトルートから実行

# 1. 基本スキーマ
cat K_kakeibo/schema.sql | pbcopy  # (Macの場合)
# → Supabase SQL Editor に貼り付けて実行

# 2. 税額フィールド追加（新機能）
cat K_kakeibo/add_tax_fields.sql | pbcopy
# → Supabase SQL Editor に貼り付けて実行
```

### 3. Google Drive セットアップ

#### 3.1 Google Cloud プロジェクト作成
```bash
# 1. https://console.cloud.google.com/ にアクセス
# 2. 新しいプロジェクト作成
# 3. Google Drive API を有効化
# 4. サービスアカウント作成 → JSON キーをダウンロード
# 5. service_account.json としてプロジェクトルートに保存
```

#### 3.2 Google Drive フォルダ作成

**2つのモデルを使い分ける構成:**
```
My_Kakeibo/
├── 00_Inbox_Easy/   ← きれいなレシート（gemini-2.5-flash-lite で処理）
├── 00_Inbox_Hard/   ← 読みづらいレシート（gemini-2.5-flash で処理）
├── 99_Archive/      ← 処理済みファイル
└── errors/          ← エラーファイル
```

**運用方法:**
- **きれいなレシート** → `00_Inbox_Easy/` に保存
  - レジで印刷された鮮明なレシート
  - 文字がはっきり読める
  - シンプルな構成

- **読みづらいレシート** → `00_Inbox_Hard/` に保存
  - かすれている、汚れている
  - 手書きメモあり
  - 複雑なレイアウト
  - 小さい文字・薄い印刷

**セットアップ手順:**

1. Google Drive で上記フォルダ構成を作成
2. 各フォルダを **service_account のメールアドレスと共有**（編集権限）
3. 各フォルダのIDをメモ:
   ```
   https://drive.google.com/drive/folders/[この部分がフォルダID]
   ```
4. `.env` ファイルに設定:
   ```
   KAKEIBO_INBOX_EASY_FOLDER_ID=1AbC...
   KAKEIBO_INBOX_HARD_FOLDER_ID=1XyZ...
   KAKEIBO_ARCHIVE_FOLDER_ID=1DeF...
   KAKEIBO_ERROR_FOLDER_ID=1GhI...
   ```

#### 3.3 ScanSnap Cloud 設定

**2つのプロファイルを作成:**

**プロファイル1: きれいなレシート**
1. ScanSnap の設定画面で「クラウド連携」を選択
2. Google Drive を選択
3. 保存先: `/My_Kakeibo/00_Inbox_Easy`
4. ファイル名: `%Y%m%d_%C3` (日付+連番)
5. 形式: JPG

**プロファイル2: 読みづらいレシート**
1. 別のプロファイルを追加
2. Google Drive を選択
3. 保存先: `/My_Kakeibo/00_Inbox_Hard`
4. ファイル名: `%Y%m%d_%C3` (日付+連番)
5. 形式: JPG

**スキャン時の選択:**
レシートの状態を見て、適切なプロファイルを選んでスキャンします。

### 4. 環境変数設定

`.env` ファイルを作成:

```bash
# Google Drive
INBOX_FOLDER_ID="1AbC..."  # 00_Inbox のフォルダID
ARCHIVE_FOLDER_ID="1XyZ..."  # 99_Archive のフォルダID
ERROR_FOLDER_ID="1ErR..."  # errors のフォルダID

# Gemini API
GEMINI_API_KEY="AIza..."

# Supabase
SUPABASE_URL="https://xxx.supabase.co"
SUPABASE_SERVICE_KEY="eyJ..."  # service_role キー推奨
```

### 5. Python パッケージインストール

```bash
pip install -r requirements.txt
```

`requirements.txt` に追加:
```
google-api-python-client
google-auth
google-auth-oauthlib
google-auth-httplib2
google-generativeai
supabase
loguru
python-dotenv
streamlit
```

---

## 使い方

### 自動処理（定期実行）

#### 1回だけ実行（テスト）
```bash
python -m K_kakeibo.main --once
```

#### 定期実行モード（5分ごと監視）
```bash
python -m K_kakeibo.main
```

#### バックグラウンド実行（推奨）

**Mac/Linux:**
```bash
# cronに登録
crontab -e

# 5分ごとに実行
*/5 * * * * cd /path/to/project && /path/to/venv/bin/python -m K_kakeibo.main --once
```

**Windows:**
```powershell
# タスクスケジューラに登録
# トリガー: 5分ごと
# 操作: python.exe -m K_kakeibo.main --once
```

### 手動レビューUI

```bash
streamlit run K_kakeibo/review_ui.py
```

ブラウザで `http://localhost:8501` を開く

---

## 運用フロー

### 日常使用
1. レシートを ScanSnap でスキャン
2. 自動的に Google Drive に保存
3. Python が定期的に処理
4. 必要に応じて Streamlit UI で確認・修正

### マスタデータ登録

#### イベント期間の登録（例: 旅行）
```bash
# Streamlit UI から登録
# マスタ管理 > イベント期間
# 名前: 沖縄旅行 2024夏
# 期間: 2024-08-01 ~ 2024-08-03
# シチュエーション: 家族旅行
```

→ この期間中のレシートは自動的に「家族旅行」に分類

#### 商品辞書の登録
```bash
# レシート表記: ｷﾞｭｳﾆｭｳ
# 正式名称: 牛乳
# カテゴリ: 食費
```

→ 次回から「ｷﾞｭｳﾆｭｳ」は自動的に「牛乳」（食費）として登録

---

## ファイル構成

```
K_kakeibo/
├── __init__.py
├── config.py                    # 設定ファイル
├── drive_monitor.py             # Google Drive 操作
├── gemini_ocr.py                # Gemini OCR処理
├── transaction_processor.py     # 正規化・DB登録
├── main.py                      # メイン処理
├── review_ui.py                 # Streamlit レビューUI
├── schema.sql                   # Supabase スキーマ
├── temp/                        # 一時ダウンロードフォルダ
└── README.md
```

---

## トラブルシューティング

### OCR が失敗する
- 画像が不鮮明 → ScanSnap の解像度を上げる
- 複数レシートが写っている → 1枚ずつスキャン
- エラーフォルダに移動されたファイルを確認 → 手動で Streamlit UI から登録

### Google Drive にアクセスできない
- service_account.json のパスを確認
- フォルダの共有設定を確認（サービスアカウントに編集権限）

### Supabase に登録されない
- .env の SUPABASE_KEY が service_role キーか確認
- スキーマが正しく作成されているか確認

---

## ライセンス

MIT License

---

## 今後の拡張案

- [ ] LINE 通知（処理完了・エラー時）
- [ ] 月次レポート自動生成
- [ ] 予算管理機能
- [ ] クレジットカード明細との突合
- [ ] 家族間での支出共有

---

**作成者**: Claude Code
**バージョン**: 1.0.0
