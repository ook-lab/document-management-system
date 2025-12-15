# Google Classroom投稿表示機能 - 実装ガイド

## 概要

Webアプリケーション（https://mail-doc-search-system-983922127476.asia-northeast1.run.app/）の検索結果に、Google Classroom投稿を専用フォーマットで表示する機能を実装しました。

---

## 実装内容

### 1. **Classroom投稿の特別表示**

検索結果でClassroom投稿（`source_type='classroom'` または `'classroom_text'`）を検出し、以下の情報を表示：

#### 表示項目
- **📘 文書名（件名）**
  - `file_name` フィールドから取得
  - デフォルト: "Google Classroom投稿"

- **👤 送信者**
  - `metadata.author_name` または `metadata.sender` から取得
  - デフォルト: "不明"

- **🕒 送信日時**
  - `created_at` または `metadata.created_time` から取得
  - フォーマット: `YYYY/MM/DD HH:MM`

- **ストリーム本文**
  - `full_text` フィールドを優先的に使用
  - フォールバック: `content` → `summary`
  - 改行を保持（`white-space: pre-wrap`）

- **📎 添付ファイル**
  - `source_url` がある場合、Driveリンクとして表示
  - `metadata.materials` から追加の添付ファイルを取得
  - クリックで新しいタブでDriveファイルを開く

---

## 変更ファイル

### 1. **フロントエンド: `templates/index.html`**

#### A. CSS追加（256-316行）

```css
/* ✅ Classroom投稿専用スタイル */
.classroom-post {
    background: #f8f9ff;
    border-left: 4px solid #4285f4;
    margin-top: 10px;
    padding: 12px;
    border-radius: 6px;
}

.classroom-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    font-size: 0.85em;
    color: #666;
}

.classroom-sender {
    font-weight: 600;
    color: #4285f4;
}

.classroom-date {
    color: #999;
}

.classroom-body {
    color: #333;
    line-height: 1.6;
    margin-bottom: 10px;
    white-space: pre-wrap;
    font-size: 0.9em;
}

.classroom-attachments {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 10px;
}

.attachment-link {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 6px 12px;
    background: #4285f4;
    color: white;
    text-decoration: none;
    border-radius: 6px;
    font-size: 0.85em;
    transition: all 0.3s;
}

.attachment-link:hover {
    background: #3367d6;
    transform: translateY(-1px);
    box-shadow: 0 3px 8px rgba(66, 133, 244, 0.3);
}
```

#### B. JavaScript修正

**`displayDocuments()`関数を拡張:**

```javascript
function displayDocuments(documents) {
    const documentList = document.getElementById('documentList');
    const documentsSection = document.getElementById('documentsSection');

    if (documents.length === 0) {
        documentList.innerHTML = '<div class="empty-state">関連する文書が見つかりませんでした</div>';
    } else {
        documentList.innerHTML = documents.map(doc => {
            // ✅ Classroom投稿かどうかを判定
            const isClassroom = doc.source_type === 'classroom' || doc.source_type === 'classroom_text';

            if (isClassroom) {
                return renderClassroomPost(doc);
            } else {
                return renderRegularDocument(doc);
            }
        }).join('');
    }

    documentsSection.style.display = 'block';
}
```

**新規関数 `renderClassroomPost()`:**

```javascript
function renderClassroomPost(doc) {
    // タイトル（件名）
    const title = doc.file_name || doc.title || 'Google Classroom投稿';

    // 送信者情報（metadataから取得）
    const metadata = doc.metadata || {};
    const sender = metadata.author_name || metadata.sender || '不明';

    // 送信日時（created_atまたはmetadataから）
    const dateStr = doc.created_at || metadata.created_time || '';
    const formattedDate = dateStr ? formatDate(dateStr) : '日時不明';

    // 本文（full_textを優先）
    const bodyText = doc.full_text || doc.content || doc.summary || '';

    // 添付ファイル（source_urlまたはmetadataのmaterialsから）
    const attachments = [];

    // source_urlがある場合（Driveファイルへのリンク）
    if (doc.source_url) {
        const fileName = doc.file_name || 'ファイル';
        attachments.push({
            url: doc.source_url,
            name: fileName,
            type: 'drive'
        });
    }

    // metadataに追加の添付ファイル情報がある場合
    if (metadata.materials && Array.isArray(metadata.materials)) {
        metadata.materials.forEach(material => {
            if (material.driveFile && material.driveFile.url) {
                attachments.push({
                    url: material.driveFile.url,
                    name: material.driveFile.title || 'ファイル',
                    type: 'material'
                });
            }
        });
    }

    // 添付ファイルのHTML
    const attachmentsHtml = attachments.length > 0 ? `
        <div class="classroom-attachments">
            ${attachments.map(att => `
                <a href="${escapeHtml(att.url)}" target="_blank" class="attachment-link">
                    📎 ${escapeHtml(att.name)}
                </a>
            `).join('')}
        </div>
    ` : '';

    return `
        <div class="document-card">
            <div class="document-title">📘 ${escapeHtml(title)}</div>
            <div class="document-meta">
                <span class="similarity-badge">類似度: ${(doc.similarity || 0).toFixed(2)}</span>
                <span style="color: #4285f4; font-weight: 500;">Google Classroom</span>
            </div>
            <div class="classroom-post">
                <div class="classroom-header">
                    <span class="classroom-sender">👤 ${escapeHtml(sender)}</span>
                    <span class="classroom-date">🕒 ${escapeHtml(formattedDate)}</span>
                </div>
                <div class="classroom-body">${escapeHtml(bodyText)}</div>
                ${attachmentsHtml}
            </div>
        </div>
    `;
}
```

**新規関数 `formatDate()`:**

```javascript
function formatDate(dateStr) {
    try {
        const date = new Date(dateStr);
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        return `${year}/${month}/${day} ${hours}:${minutes}`;
    } catch (e) {
        return dateStr;
    }
}
```

---

### 2. **バックエンド: `core/database/client.py`**

#### 検索結果に追加フィールドを含める（219-223行）

```python
doc_result = {
    'id': result.get('document_id'),
    'file_name': result.get('file_name'),
    'doc_type': result.get('doc_type'),
    'document_date': result.get('document_date'),
    'metadata': result.get('metadata'),
    'summary': result.get('summary'),

    # 回答用：大チャンク（全文）
    'content': result.get('large_chunk_text'),
    'large_chunk_id': result.get('large_chunk_id'),

    # 検索スコア：小チャンクの検索スコア
    'similarity': result.get('combined_score', 0),
    'small_chunk_id': result.get('small_chunk_id'),

    'year': result.get('year'),
    'month': result.get('month'),

    # ✅ Classroom表示用の追加フィールド
    'source_type': result.get('source_type'),
    'source_url': result.get('source_url'),
    'full_text': result.get('full_text'),
    'created_at': result.get('created_at')
}
```

---

## 表示例

### 通常のドキュメント

```
┌─────────────────────────────────────────┐
│ 📄 学年通信（29）.pdf                    │
│ 類似度: 0.85                             │
├─────────────────────────────────────────┤
│ 2年A組の学級閉鎖に関するお知らせです...  │
│                                          │
│ [📄 元ファイルを開く]                    │
└─────────────────────────────────────────┘
```

### Google Classroom投稿

```
┌─────────────────────────────────────────┐
│ 📘 【学級閉鎖のご報告】                   │
│ 類似度: 0.92    Google Classroom         │
├─────────────────────────────────────────┤
│ ┌───────────────────────────────────┐   │
│ │ 👤 山田太郎      🕒 2025/12/08 14:30│   │
│ ├───────────────────────────────────┤   │
│ │ 本日2年A組は発熱者、インフルエンザ   │   │
│ │ 罹患者が増加したため学級閉鎖と     │   │
│ │ いたしました。                      │   │
│ │                                    │   │
│ │ 全国的にもインフルエンザが流行して │   │
│ │ おりますのでご家庭でもご留意       │   │
│ │ ください。                          │   │
│ ├───────────────────────────────────┤   │
│ │ [📎 学年通信.pdf]  [📎 保健だより.pdf] │   │
│ └───────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

---

## データフロー

```
Supabase documents テーブル
    │
    ├─ source_type: 'classroom_text' または 'classroom'
    ├─ full_text: 投稿本文
    ├─ source_url: 添付ファイルのDrive URL
    ├─ metadata: { author_name, created_time, materials }
    ├─ created_at: 作成日時
    │
    ↓
search_documents_final() SQL関数
    │
    ↓
DatabaseClient.search_documents() (Python)
    │ (doc_resultに追加フィールドを含める)
    ↓
Flask app.py /api/search エンドポイント
    │
    ↓
フロントエンド index.html
    │
    ├─ displayDocuments()
    │   ├─ source_typeをチェック
    │   └─ isClassroom?
    │       ├─ Yes → renderClassroomPost()
    │       └─ No  → renderRegularDocument()
    │
    └─ レンダリング
```

---

## 必要なデータベースフィールド

Classroom投稿が正しく表示されるために、以下のフィールドが`documents`テーブルに必要です：

| フィールド | 型 | 説明 | 必須 |
|-----------|----|----|------|
| `source_type` | VARCHAR(50) | `'classroom'` または `'classroom_text'` | ✅ |
| `full_text` | TEXT | 投稿の本文 | ✅ |
| `source_url` | TEXT | 添付ファイルのDrive URL | 任意 |
| `metadata` | JSONB | `author_name`, `created_time`, `materials` など | 任意 |
| `created_at` | TIMESTAMP | 作成日時 | 任意 |

---

## デプロイ手順

### 1. ローカルでテスト

```bash
cd document_management_system

# Flaskアプリを起動
python app.py
```

ブラウザで http://localhost:5001 にアクセスして動作確認。

### 2. Cloud Runにデプロイ

```bash
# Dockerイメージをビルド
docker build -t gcr.io/YOUR_PROJECT_ID/mail-doc-search-system .

# Google Container Registryにプッシュ
docker push gcr.io/YOUR_PROJECT_ID/mail-doc-search-system

# Cloud Runにデプロイ
gcloud run deploy mail-doc-search-system \
  --image gcr.io/YOUR_PROJECT_ID/mail-doc-search-system \
  --platform managed \
  --region asia-northeast1 \
  --allow-unauthenticated
```

### 3. 動作確認

https://mail-doc-search-system-983922127476.asia-northeast1.run.app/ にアクセスして、Classroom投稿が正しく表示されることを確認。

---

## トラブルシューティング

### Q1: Classroom投稿が通常の表示になる

**原因:** `source_type` が正しく設定されていない

**解決策:**
```sql
-- documentsテーブルを確認
SELECT source_type, file_name, full_text
FROM documents
WHERE workspace = 'ikuya_classroom'
LIMIT 10;

-- source_typeを修正
UPDATE documents
SET source_type = 'classroom_text'
WHERE workspace = 'ikuya_classroom'
  AND (source_type IS NULL OR source_type = 'drive');
```

### Q2: 送信者が「不明」と表示される

**原因:** `metadata` に `author_name` が含まれていない

**解決策:**
Google Apps Scriptで取り込む際に、author情報を含める：

```javascript
// Google Apps Scriptの修正例
const metadata = {
    author_name: post.creatorUserId.name || '不明',
    created_time: post.creationTime,
    post_type: post._type
};
```

### Q3: 添付ファイルが表示されない

**原因:** `source_url` が空、または `metadata.materials` が設定されていない

**解決策:**
```sql
-- source_urlを確認
SELECT file_name, source_url, metadata
FROM documents
WHERE source_type IN ('classroom', 'classroom_text')
LIMIT 10;
```

---

## まとめ

この機能により、Google Classroom投稿が通常のドキュメントと区別されて表示され、以下の情報が一目で分かるようになりました：

- ✅ **投稿の件名**
- ✅ **送信者名**
- ✅ **送信日時**
- ✅ **本文全文**（改行を保持）
- ✅ **添付ファイル**（クリックでDriveを開く）

これにより、ユーザーはClassroom投稿の内容を検索結果から直接確認でき、必要に応じて添付ファイルにアクセスできます。

---

**作成日:** 2025-12-09
**バージョン:** v1.0
**更新履歴:**
- 2025-12-09: 初版作成
