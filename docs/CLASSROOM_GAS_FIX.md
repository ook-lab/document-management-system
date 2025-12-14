# Google Apps Script修正ガイド

## 問題

現在のGASスクリプトは、元のファイルID（お子さんのDrive）を`original_file_id`に保存しています。
しかし、実際にアクセスできるのは、あなたのDriveにコピーされたファイルです。

## 修正方法

### 修正前（現在）

```javascript
const originalFileId = material.driveFile.driveFile.id;
// ...
const copiedFile = originalFile.makeCopy(fileName, destFolder);
finalUrl = copiedFile.getUrl();

// ❌ 元のファイルIDを保存（アクセスできない）
recordsToInsert.push({
  metadata: {
    original_file_id: originalFileId,  // ← これが問題
    material_type: 'driveFile',
    post_type: post._type
  }
});
```

### 修正後（推奨）

```javascript
const originalFileId = material.driveFile.driveFile.id;
let copiedFileId = null;  // ← 追加

try {
  const existingFiles = destFolder.getFilesByName(fileName);
  if (existingFiles.hasNext()) {
    const existingFile = existingFiles.next();
    finalUrl = existingFile.getUrl();
    copiedFileId = existingFile.getId();  // ← 追加
    console.log(`  ➡ [既存あり] ${fileName}`);
  } else {
    const originalFile = DriveApp.getFileById(originalFileId);
    const copiedFile = originalFile.makeCopy(fileName, destFolder);
    finalUrl = copiedFile.getUrl();
    copiedFileId = copiedFile.getId();  // ← 追加
    console.log(`  ➡ [コピー作成] ${fileName}`);
  }

  // ✅ コピーされたファイルIDを保存（アクセス可能）
  recordsToInsert.push({
    source_type: 'classroom',
    source_id:   postId,
    source_url:  finalUrl,
    file_name:   fileName,
    summary:     postText,
    workspace:   WORKSPACE_VAL,
    doc_type:    DOC_TYPE_VAL,
    metadata: {
      original_file_id: copiedFileId,      // ← コピーのID
      classroom_source_id: originalFileId,  // ← 元のIDは別フィールドに保存（参考用）
      material_type: 'driveFile',
      post_type: post._type
    },
    created_at: new Date().toISOString()
  });

} catch (e) {
  console.log(`  ➡ ファイル処理エラー: ${fileName} - ${e.toString()}`);
}
```

## 完全な修正版コード

```javascript
function syncClassroomToDocuments() {
  // ▼▼▼ 設定 ▼▼▼
  const props = PropertiesService.getScriptProperties();

  const COURSE_ID      = props.getProperty('COURSE_ID');
  const SUPABASE_URL   = props.getProperty('SUPABASE_URL');
  const SUPABASE_KEY   = props.getProperty('SUPABASE_KEY');
  const DEST_FOLDER_ID = props.getProperty('DEST_FOLDER_ID');

  const TABLE_NAME     = 'documents';
  const WORKSPACE_VAL  = 'ikuya_classroom';
  const DOC_TYPE_VAL   = '2025_5B';

  if (!COURSE_ID || !SUPABASE_URL || !SUPABASE_KEY || !DEST_FOLDER_ID) {
    console.error("【エラー】スクリプトプロパティ設定を確認してください。");
    return;
  }

  const TARGET_START_DATE = new Date('2025-12-01T00:00:00');
  const TARGET_END_DATE   = new Date('2025-12-31T23:59:59');
  const FETCH_LIMIT = 20;

  const destFolder = DriveApp.getFolderById(DEST_FOLDER_ID);
  let allPosts = [];

  console.log(`収集対象期間: ${TARGET_START_DATE.toISOString()} 〜 ${TARGET_END_DATE.toISOString()}`);

  try {
    // お知らせ
    const resAnnounce = Classroom.Courses.Announcements.list(COURSE_ID, { pageSize: FETCH_LIMIT, orderBy: 'updateTime desc' });
    if (resAnnounce.announcements) {
      resAnnounce.announcements.forEach(p => {
        if (isInDateRange(p.creationTime, TARGET_START_DATE, TARGET_END_DATE)) {
          p._type = 'お知らせ';
          p._text = p.text || "";
          allPosts.push(p);
        }
      });
    }

    // 課題
    const resWork = Classroom.Courses.CourseWork.list(COURSE_ID, { pageSize: FETCH_LIMIT, orderBy: 'updateTime desc' });
    if (resWork.courseWork) {
      resWork.courseWork.forEach(p => {
        if (isInDateRange(p.creationTime, TARGET_START_DATE, TARGET_END_DATE)) {
          p._type = '課題';
          p._text = `【課題】${p.title || ""}\n${p.description || ""}`;
          allPosts.push(p);
        }
      });
    }

    // 資料
    const resMaterial = Classroom.Courses.CourseWorkMaterials.list(COURSE_ID, { pageSize: FETCH_LIMIT, orderBy: 'updateTime dec' });
    if (resMaterial.courseWorkMaterial) {
      resMaterial.courseWorkMaterial.forEach(p => {
        if (isInDateRange(p.creationTime, TARGET_START_DATE, TARGET_END_DATE)) {
          p._type = '資料';
          p._text = `【資料】${p.title || ""}\n${p.description || ""}`;
          allPosts.push(p);
        }
      });
    }

  } catch (e) {
    console.error("Classroom取得エラー: " + e.toString());
    return;
  }

  if (allPosts.length === 0) {
    console.log("指定期間内（12月）の投稿は見つかりませんでした。");
    return;
  }

  console.log(`【確認】12月分の全投稿数: ${allPosts.length}件 を検出しました。`);

  const recordsToInsert = [];

  for (const post of allPosts) {
    const postText = post._text;
    const postId = post.id;
    const materials = post.materials;

    if (materials && materials.length > 0) {
      materials.forEach(material => {
        if (material.driveFile) {
          const classroomFileId = material.driveFile.driveFile.id;  // ← 変数名変更
          const fileName = material.driveFile.driveFile.title;
          let finalUrl = "";
          let copiedFileId = null;  // ← 追加

          try {
            const existingFiles = destFolder.getFilesByName(fileName);
            if (existingFiles.hasNext()) {
              const existingFile = existingFiles.next();
              finalUrl = existingFile.getUrl();
              copiedFileId = existingFile.getId();  // ← 追加
              console.log(`  ➡ [既存あり] ${fileName} (ID: ${copiedFileId})`);
            } else {
              const originalFile = DriveApp.getFileById(classroomFileId);
              const copiedFile = originalFile.makeCopy(fileName, destFolder);
              finalUrl = copiedFile.getUrl();
              copiedFileId = copiedFile.getId();  // ← 追加
              console.log(`  ➡ [コピー作成] ${fileName} (ID: ${copiedFileId})`);
            }

            recordsToInsert.push({
              source_type: 'classroom',
              source_id:   postId,
              source_url:  finalUrl,
              file_name:   fileName,
              summary:     postText,
              workspace:   WORKSPACE_VAL,
              doc_type:    DOC_TYPE_VAL,
              metadata: {
                original_file_id: copiedFileId,        // ← コピーのID（アクセス可能）
                classroom_source_id: classroomFileId,   // ← 元のID（参考用）
                material_type: 'driveFile',
                post_type: post._type
              },
              created_at: new Date().toISOString()
            });

          } catch (e) {
            console.log(`  ➡ ファイル処理エラー: ${fileName} - ${e.toString()}`);
          }
        }
      });
    } else if (postText) {
      recordsToInsert.push({
        source_type: 'classroom_text',
        source_id:   postId,
        source_url:  null,
        file_name:   'text_only',
        summary:     postText,
        workspace:   WORKSPACE_VAL,
        doc_type:    DOC_TYPE_VAL,
        metadata:    { post_type: post._type },
        created_at:  new Date().toISOString()
      });
    }
  }

  if (recordsToInsert.length > 0) {
    const options = {
      method: 'post',
      contentType: 'application/json',
      headers: {
        'apikey': SUPABASE_KEY,
        'Authorization': `Bearer ${SUPABASE_KEY}`,
        'Prefer': 'resolution=ignore-duplicates'
      },
      payload: JSON.stringify(recordsToInsert)
    };

    try {
      const res = UrlFetchApp.fetch(`${SUPABASE_URL}/rest/v1/${TABLE_NAME}?on_conflict=source_id`, options);
      console.log(`同期完了: ${recordsToInsert.length} 件 (Status: ${res.getResponseCode()})`);
    } catch (e) {
      console.error("Supabase送信エラー: " + e.toString());
      if (e.response) console.error(e.response.getContentText());
    }
  }
}

function isInDateRange(dateString, startDate, endDate) {
  const d = new Date(dateString);
  return d >= startDate && d <= endDate;
}
```

## 変更のポイント

1. **`copiedFileId`変数を追加**
   - `existingFile.getId()`または`copiedFile.getId()`で取得

2. **`metadata.original_file_id`にコピーのIDを保存**
   - これでサービスアカウントがアクセス可能

3. **`metadata.classroom_source_id`に元のIDを保存**
   - 参考用として保持（オプション）

## 実行後の対応

### 既存データの修正

GASスクリプトを修正して再実行すると、新しいデータは正しいIDで登録されます。

既存の3件のデータについては、手動で修正するか、以下のスクリプトで更新できます：

```python
# update_existing_classroom_docs.py
from core.database.client import DatabaseClient
import json

db = DatabaseClient()

# コピーされたファイルのIDマッピング
# Google Driveで各ファイルを開いてIDを確認
file_id_mapping = {
    "学年通信（30）.pdf": "NEW_COPIED_FILE_ID_1",
    "洗足学園小保健室山元12月 ほけんだより.pdf": "NEW_COPIED_FILE_ID_2",
    "IMG_1535.jpg": "NEW_COPIED_FILE_ID_3",
}

# 既存データを更新
docs = db.client.table('source_documents').select('*').eq('workspace', 'ikuya_classroom').execute()

for doc in docs.data:
    file_name = doc['file_name']
    if file_name in file_id_mapping:
        new_id = file_id_mapping[file_name]

        metadata = doc.get('metadata', {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        # IDを更新
        old_id = metadata.get('original_file_id')
        metadata['classroom_source_id'] = old_id  # 元のIDを保存
        metadata['original_file_id'] = new_id     # 新しいIDに更新

        # データベース更新
        db.client.table('source_documents').update({
            'metadata': metadata
        }).eq('id', doc['id']).execute()

        print(f"✅ {file_name}: {old_id} → {new_id}")
```

## まとめ

1. ✅ GASスクリプトを上記のように修正
2. ✅ スクリプトを再実行（新しいデータは正しいIDで登録される）
3. ✅ 既存の3件は手動またはスクリプトで更新
4. ✅ 再処理スクリプトを実行

これで全て動作するようになります！
