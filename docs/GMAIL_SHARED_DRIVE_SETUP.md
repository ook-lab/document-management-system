# Gmail統合: 共有ドライブ設定ガイド

## 問題: "Service Accounts do not have storage quota"

### 原因
サービスアカウントは「**マイドライブ**」のフォルダに**書き込みができません**。

- ✅ マイドライブから**読み取り**は可能（PDFシステムで動作中）
- ❌ マイドライブへの**書き込み**は不可（Gmail統合で失敗）

Googleの制限により、サービスアカウントは自分の保存容量を持たないため、**共有ドライブ**を使用する必要があります。

---

## 解決策: 共有ドライブの作成

### ステップ1: 共有ドライブを作成

1. **Google Driveにアクセス**
   ```
   https://drive.google.com/
   ```

2. **共有ドライブを新規作成**
   - 左サイドバーの「**共有ドライブ**」をクリック
   - 画面上部の「**新規**」ボタンをクリック
   - ドロップダウンから「**共有ドライブ**」を選択
   - 名前を入力: 例）`Gmail Integration`
   - 「**作成**」をクリック

### ステップ2: サービスアカウントをメンバーに追加

共有ドライブにサービスアカウントを追加する必要があります：

1. **作成した共有ドライブを開く**
   - 左サイドバーから「Gmail Integration」（作成した共有ドライブ）をクリック

2. **メンバーを管理**
   - 右上の「**メンバーを管理**」（人型アイコン）をクリック

3. **サービスアカウントを追加**
   - 「メンバーを追加」の入力欄に以下を貼り付け:
     ```
     document-management-system@consummate-yew-479020-u2.iam.gserviceaccount.com
     ```
   - 役割を選択: **コンテンツ管理者** または **編集者**
   - 「**送信**」をクリック

   **注意**: 「通知を送信」のチェックは外してOKです（サービスアカウントにはメール通知が不要）

### ステップ3: フォルダを作成

共有ドライブ内に2つのフォルダを作成します：

1. **共有ドライブ内でフォルダを作成**
   - 「Gmail Integration」共有ドライブを開く
   - 「新規」→「フォルダ」をクリック
   - フォルダ1の名前: `Gmail - メール本文`
   - フォルダ2の名前: `Gmail - 添付ファイル`

2. **フォルダIDを取得**
   - 各フォルダを**右クリック** → 「**リンクを取得**」
   - または、フォルダを開いてURLをコピー
   - URLの最後の部分がフォルダIDです:
     ```
     https://drive.google.com/drive/folders/【このIDをコピー】
     ```

   例:
   ```
   https://drive.google.com/drive/folders/1ABC123xyz-DefGhi456JklMno789
                                           ↑
                                    このIDをコピー
   ```

### ステップ4: 環境変数を更新

`.env` ファイルの `GMAIL_EMAIL_FOLDER_ID` と `GMAIL_ATTACHMENT_FOLDER_ID` を、
**新しく作成した共有ドライブ内のフォルダID**に更新してください：

```bash
# 古い値（マイドライブのフォルダ - 書き込み不可）
GMAIL_EMAIL_FOLDER_ID=1SBv0oug4psVJr9G1XS8kGtXmN7Ou9ee8
GMAIL_ATTACHMENT_FOLDER_ID=1nq_KG8rWX859jA_VZAe8b0imgcrWFcS-

# ↓ 新しい値（共有ドライブのフォルダID）に変更してください
GMAIL_EMAIL_FOLDER_ID=【新しいメール本文フォルダのID】
GMAIL_ATTACHMENT_FOLDER_ID=【新しい添付ファイルフォルダのID】
```

---

## 確認方法

設定が完了したら、以下のコマンドで動作確認してください：

```bash
cd /Users/ookuboyoshinori/document_management_system
python pipelines/gmail_ingestion.py
```

### 成功例
```
INFO - メール本文をDriveに保存: 20241206_123456_Subject_abc12345.html
INFO - 添付ファイルをDriveに保存: document.pdf
INFO - ファイルアップロード成功: 20241206_123456_Subject_abc12345.html (ID: 1XYZ...)
```

### エラーが出る場合

- **"File not found"**: フォルダIDが間違っている可能性があります
- **"403 Forbidden"**: サービスアカウントがメンバーに追加されていません
- **"Service Accounts do not have storage quota"**: まだマイドライブのフォルダIDを使用しています

---

## よくある質問

### Q1: なぜPDFシステムは動作してGmail統合は動作しないのか？
**A**: PDFシステムは「読み取り」のみでマイドライブから動作します。Gmail統合は「書き込み」が必要なため、共有ドライブが必要です。

### Q2: 既存のマイドライブフォルダを共有ドライブに移動できますか？
**A**: いいえ、マイドライブと共有ドライブは別の構造です。新しく共有ドライブを作成する必要があります。

### Q3: 他のメンバーもこの共有ドライブにアクセスできますか？
**A**: はい、必要に応じて他のメンバーを追加できます。サービスアカウントと同様に「メンバーを管理」から追加してください。

---

## 参考リンク

- [Google Workspace: 共有ドライブの使い方](https://support.google.com/a/users/answer/9310156)
- [Google Drive API: 共有ドライブのサポート](https://developers.google.com/drive/api/guides/enable-shareddrives)
