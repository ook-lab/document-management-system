# Gmail API統合セットアップガイド

## 概要
Google Workspaceアカウント（ookubo.y@workspace-o.com）で、サービスアカウントを使ってGmail APIにアクセスするための設定手順。

**アプリパスワード不要**の安全な方法です。

---

## 前提条件
- ✅ Google Workspaceの管理者権限
- ✅ サービスアカウント認証済み（既存のgoogle_credentials.json）
- ✅ Google Drive APIは既に有効化済み

---

## ステップ1: Gmail APIを有効化（Google Cloud Console）

1. **Google Cloud Consoleにアクセス**
   - https://console.cloud.google.com/
   - 現在のプロジェクトを選択

2. **Gmail APIを有効化**
   - 左メニュー → 「APIとサービス」 → 「ライブラリ」
   - 検索バーで「Gmail API」を検索
   - 「Gmail API」をクリック
   - 「有効にする」ボタンをクリック

3. **確認**
   - 「APIとサービス」 → 「有効なAPIとサービス」
   - 「Gmail API」がリストに表示されていればOK

---

## ステップ2: サービスアカウントのClient IDを確認

1. **サービスアカウントの詳細を開く**
   - Google Cloud Console → 「IAMと管理」 → 「サービスアカウント」
   - 使用中のサービスアカウントをクリック

2. **Client IDをコピー**
   - 「詳細」タブ内の「クライアントID」（数字の長い文字列）をコピー
   - 例: `123456789012345678901`
   - **このIDを次のステップで使います**

---

## ステップ3: ドメイン全体の委任を設定（Workspace管理コンソール）

この設定により、サービスアカウントが組織内のユーザー（あなた）のGmailにアクセスできるようになります。

1. **Google Workspace管理コンソールにアクセス**
   - https://admin.google.com/
   - ookubo.y@workspace-o.com でログイン

2. **APIの制御を開く**
   - 左メニュー → 「セキュリティ」 → 「アクセスとデータ管理」 → 「APIの制御」

3. **ドメイン全体の委任を管理**
   - 「ドメイン全体の委任を管理」をクリック

4. **新しいクライアントIDを追加**
   - 「新規追加」ボタンをクリック
   - **クライアントID**: ステップ2でコピーしたClient IDを貼り付け
   - **OAuthスコープ**: 以下を**カンマ区切りで**貼り付け
     ```
     https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/gmail.modify,https://www.googleapis.com/auth/drive.file
     ```
   - 「承認」をクリック

5. **確認**
   - リストに追加されたClient IDが表示されればOK

---

## ステップ4: スコープの説明

追加したスコープの意味：

| スコープ | 用途 |
|---------|------|
| `gmail.readonly` | メールの読み取り（件名、本文、添付ファイル取得） |
| `gmail.modify` | ラベル追加・削除（既読マーク、アーカイブなど） |
| `drive.file` | Driveへのファイル保存（アプリが作成したファイルのみ） |

---

## ステップ5: Gmailでラベルを作成

メールを整理するため、専用ラベルを作成します：

1. **Gmailにアクセス**
   - https://mail.google.com/
   - ookubo.y@workspace-o.com でログイン

2. **ラベルを作成**
   - 左サイドバーの「新しいラベルを作成」をクリック
   - ラベル名: `TEST` と入力
   - 「作成」をクリック

3. **処理対象のメールにラベルを付ける**
   - 処理したいメールを選択
   - 上部のラベルアイコンをクリック
   - `TEST` ラベルを選択

これで、`label:TEST` のメールだけが処理対象になります。

---

## ステップ6: Google Driveで共有ドライブを作成（重要）

⚠️ **重要**: サービスアカウントは「マイドライブ」のフォルダに書き込みができません。
必ず**共有ドライブ**を使用してください。

### 6-1. 共有ドライブの作成

1. **Google Driveにアクセス**
   - https://drive.google.com/

2. **共有ドライブを作成**
   - 左サイドバーの「共有ドライブ」をクリック
   - 「新規」ボタン → 「共有ドライブ」を選択
   - 名前: 「Gmail Integration」（または任意の名前）
   - 「作成」をクリック

3. **サービスアカウントをメンバーに追加**
   - 作成した共有ドライブを開く
   - 右上の「メンバーを管理」をクリック
   - サービスアカウントのメールアドレスを追加:
     ```
     document-management-system@consummate-yew-479020-u2.iam.gserviceaccount.com
     ```
   - 役割: **コンテンツ管理者** または **編集者**
   - 「送信」をクリック

### 6-2. フォルダを作成

共有ドライブ内に2つのフォルダを作成します：

1. **共有ドライブ内でフォルダを作成**
   - 先ほど作成した共有ドライブを開く
   - フォルダ1: 「Gmail - メール本文」（または任意の名前）
   - フォルダ2: 「Gmail - 添付ファイル」（または任意の名前）

2. **各フォルダのIDを取得**
   - 各フォルダを開く
   - URLから最後の部分をコピー
   - 例: `https://drive.google.com/drive/folders/1SBv0oug4psVJr9G1XS8kGtXmN7Ou9ee8`
   - → フォルダID: `1SBv0oug4psVJr9G1XS8kGtXmN7Ou9ee8`

---

## ステップ7: 環境変数の設定

既存の `.env` ファイルに、以下を追加：

```bash
# Gmail API設定
GMAIL_USER_EMAIL=ookubo.y@workspace-o.com
GMAIL_LABEL=TEST  # 読み取り対象のラベル
GMAIL_EMAIL_FOLDER_ID=1SBv0oug4psVJr9G1XS8kGtXmN7Ou9ee8  # メール本文(HTML)の保存先
GMAIL_ATTACHMENT_FOLDER_ID=1nq_KG8rWX859jA_VZAe8b0imgcrWFcS-  # 添付ファイルの保存先
```

**各IDの説明:**
- `GMAIL_EMAIL_FOLDER_ID`: メール本文をHTML形式で保存するフォルダ
- `GMAIL_ATTACHMENT_FOLDER_ID`: PDFなどの添付ファイルを保存するフォルダ

---

## トラブルシューティング

### エラー: "domain-wide delegation is not enabled"
- ステップ3の設定が反映されるまで5-10分かかる場合があります
- 待ってから再試行してください

### エラー: "Client is unauthorized to retrieve access tokens"
- ステップ2のClient IDが正しいか確認
- ステップ3のスコープが正確にコピーされているか確認（スペースや改行が入っていないか）

### エラー: "User does not have permission to access this resource"
- サービスアカウントがGmailにアクセスする**ユーザー**（subject）を指定する必要があります
- コード内で `subject='ookubo.y@workspace-o.com'` を設定してください

---

## 次のステップ

設定が完了したら、Pythonコードで以下のように使えます：

```python
from pipelines.gmail_ingestion import GmailIngestionPipeline

# パイプラインの初期化（環境変数から自動取得）
pipeline = GmailIngestionPipeline(gmail_user_email='ookubo.y@workspace-o.com')

# ラベル「TEST」の未読メールを処理（最大10件）
results = pipeline.process_unread_emails(max_emails=10)
```

---

## 参考リンク

- [Google Workspace: ドメイン全体の委任](https://developers.google.com/identity/protocols/oauth2/service-account#delegatingauthority)
- [Gmail API: Python クイックスタート](https://developers.google.com/gmail/api/quickstart/python)
