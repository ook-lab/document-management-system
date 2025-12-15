// ============================================================
// Google Classroom → Supabase 3層構造対応版
// 作成日: 2025-12-14
//
// 変更点:
// - テーブル名: documents → source_documents
// - classroom固有フィールドを直接カラムとして送信
// - process_logs への記録機能追加（オプション）
// ============================================================

// ■■■■■■■■■■ メイン実行関数 ■■■■■■■■■■
function syncAllClassroomsToDocuments() {
  const props = PropertiesService.getScriptProperties();

  const SUPABASE_URL          = props.getProperty('SUPABASE_URL');
  const SUPABASE_KEY          = props.getProperty('SUPABASE_KEY');
  const DEST_FOLDER_ID        = props.getProperty('DEST_FOLDER_ID');
  const WORKSPACE_VAL         = props.getProperty('WORKSPACE_NAME');
  const SERVICE_ACCOUNT_EMAIL = props.getProperty('SERVICE_ACCOUNT_EMAIL');

  // 複数のperson/organizationをカンマ区切りで取得して配列化
  const PERSONS_STR           = props.getProperty('PERSONS') || '';
  const ORGANIZATIONS_STR     = props.getProperty('ORGANIZATIONS') || '';

  const PERSONS_ARRAY = PERSONS_STR ? PERSONS_STR.split(',').map(s => s.trim()).filter(s => s) : [];
  const ORGANIZATIONS_ARRAY = ORGANIZATIONS_STR ? ORGANIZATIONS_STR.split(',').map(s => s.trim()).filter(s => s) : [];

  // 3層構造: データ層のテーブル名
  const TABLE_NAME = 'source_documents';

  if (!SUPABASE_URL || !SUPABASE_KEY || !DEST_FOLDER_ID || !WORKSPACE_VAL || !SERVICE_ACCOUNT_EMAIL) {
    console.error("【エラー】スクリプトプロパティが不足しています");
    return;
  }

  const now = new Date();
  const TARGET_START_DATE = new Date();
  TARGET_START_DATE.setDate(now.getDate() - 7);
  const TARGET_END_DATE = new Date();
  TARGET_END_DATE.setDate(now.getDate() + 1);

  const FETCH_LIMIT = 20;

  let destFolder;
  try {
    destFolder = DriveApp.getFolderById(DEST_FOLDER_ID);
  } catch (e) {
    console.error("❌ 保存先フォルダが見つかりません:", e.message);
    return;
  }

  let courses = [];
  try {
    let pageToken = null;
    do {
      const response = Classroom.Courses.list({
        courseStates: ['ACTIVE'],
        pageSize: 50,
        pageToken: pageToken
      });
      if (response.courses) courses = courses.concat(response.courses);
      pageToken = response.nextPageToken;
    } while (pageToken);
  } catch (e) {
    console.error("コース一覧の取得に失敗しました:", e.toString());
    return;
  }

  console.log(`全 ${courses.length} 件のクラスが見つかりました`);

  courses.forEach(course => {
    processCourse(course, TARGET_START_DATE, TARGET_END_DATE, destFolder, {
      SUPABASE_URL, SUPABASE_KEY, TABLE_NAME, WORKSPACE_VAL, SERVICE_ACCOUNT_EMAIL, FETCH_LIMIT,
      PERSONS_ARRAY, ORGANIZATIONS_ARRAY
    });
  });

  console.log("すべてのクラスの同期処理が完了しました");
}

// ■■■■■■■■■■ クラス処理関数 ■■■■■■■■■■
function processCourse(course, startDate, endDate, destFolder, config) {
  const COURSE_ID = course.id;
  const COURSE_NAME = course.name;
  const DOC_TYPE_VAL = COURSE_NAME;

  console.log(`\n========================================`);
  console.log(`処理中クラス: ${COURSE_NAME}`);

  const recordsToInsert = [];
  const insertedSourceIds = new Set();

  // ============ お知らせ ============
  const announcements = listAnnouncements(COURSE_ID, config.FETCH_LIMIT);
  const filteredAnnouncements = announcements.filter(p => isInDateRange(p.creationTime, startDate, endDate));
  filteredAnnouncements.forEach(post => {
    processPost(post, 'お知らせ', COURSE_ID, COURSE_NAME, DOC_TYPE_VAL, destFolder, config, recordsToInsert, insertedSourceIds);
  });

  // ============ 課題 ============
  const courseWork = listCourseWork(COURSE_ID, config.FETCH_LIMIT);
  const filteredCourseWork = courseWork.filter(p => isInDateRange(p.creationTime, startDate, endDate));
  filteredCourseWork.forEach(post => {
    processPost(post, '課題', COURSE_ID, COURSE_NAME, DOC_TYPE_VAL, destFolder, config, recordsToInsert, insertedSourceIds);
  });

  // ============ 資料 ============
  const materials = listCourseWorkMaterials(COURSE_ID, config.FETCH_LIMIT);
  const filteredMaterials = materials.filter(p => isInDateRange(p.creationTime, startDate, endDate));
  filteredMaterials.forEach(post => {
    processPost(post, '資料', COURSE_ID, COURSE_NAME, DOC_TYPE_VAL, destFolder, config, recordsToInsert, insertedSourceIds);
  });

  // Supabaseへ送信
  if (recordsToInsert.length > 0) {
    sendToSupabase(recordsToInsert, COURSE_NAME, config);
  } else {
    console.log(`  [${COURSE_NAME}] 投稿なし。スキップ。`);
  }
}

// ■■■■■■■■■■ 投稿処理関数 ■■■■■■■■■■
function processPost(post, postType, courseId, courseName, docType, destFolder, config, recordsToInsert, insertedSourceIds) {
  const postId = post.id;
  const creatorUserId = post.creatorUserId;
  const creationTime = post.creationTime;
  const materials = post.materials;

  // titleとtextの処理
  let postSubject = "";
  let postText = "";

  if (postType === 'お知らせ') {
    postText = post.text || "";
    postSubject = "";
  } else {
    postSubject = post.title || "";
    postText = post.description || "";
  }

  // 送信者情報取得
  let senderName = 'Unknown';
  let senderEmail = '';
  try {
    const userProfile = Classroom.UserProfiles.get(creatorUserId);
    senderName = userProfile.name.fullName || 'Unknown';
    senderEmail = userProfile.emailAddress || '';
  } catch (e) {}

  // A. 添付ファイルがある場合
  if (materials && materials.length > 0) {
    materials.forEach(material => {
      if (material.driveFile && material.driveFile.driveFile) {
        const originalFileId = material.driveFile.driveFile.id;
        const fileName = material.driveFile.driveFile.title || "無題のファイル";

        let finalUrl = "";
        let finalFileId = null;

        try {
          const existingFiles = destFolder.getFilesByName(fileName);
          let targetFile;

          if (existingFiles.hasNext()) {
            targetFile = existingFiles.next();
          } else {
            const originalFile = DriveApp.getFileById(originalFileId);
            targetFile = originalFile.makeCopy(fileName, destFolder);
          }

          if (targetFile) {
            try {
              targetFile.addViewer(config.SERVICE_ACCOUNT_EMAIL);
            } catch(e) {}
            finalUrl = targetFile.getUrl();
            finalFileId = targetFile.getId();
          }

          const uniqueSourceId = finalFileId || originalFileId;
          if (insertedSourceIds.has(uniqueSourceId)) return;
          insertedSourceIds.add(uniqueSourceId);

          // 3層構造: source_documentsテーブルへの送信データ
          recordsToInsert.push({
            source_type: 'classroom',
            source_id: uniqueSourceId,
            source_url: finalUrl,
            ingestion_route: 'classroom',
            file_name: fileName,
            workspace: config.WORKSPACE_VAL,
            doc_type: docType,

            // 担当者・組織（配列として送信）
            persons: config.PERSONS_ARRAY.length > 0 ? config.PERSONS_ARRAY : null,
            organizations: config.ORGANIZATIONS_ARRAY.length > 0 ? config.ORGANIZATIONS_ARRAY : null,

            // Classroom固有フィールド（直接カラムとして送信）
            display_sender: senderName,
            display_sender_email: senderEmail,
            display_sent_at: creationTime,
            display_subject: postSubject,
            display_post_text: postText,
            display_type: postType,

            // メタデータ（追加情報）
            metadata: {
              'original_classroom_id': originalFileId,
              'post_id': postId,
              'post_type': postType,
              'course_name': courseName,
              'course_id': courseId,
              'sender_name': senderName,
              'sender_email': senderEmail
            }
          });

        } catch (e) {
          console.log('  ➡ ファイル処理エラー: ' + fileName + ' - ' + e.toString());
        }
      }
    });
  }
  // B. テキストのみの場合
  else if (postText) {
    if (insertedSourceIds.has(postId)) return;
    insertedSourceIds.add(postId);

    // 3層構造: source_documentsテーブルへの送信データ
    recordsToInsert.push({
      source_type: 'classroom_text',
      source_id: postId,
      source_url: null,
      ingestion_route: 'classroom',
      file_name: 'text_only',
      workspace: config.WORKSPACE_VAL,
      doc_type: docType,

      // 担当者・組織（配列として送信）
      persons: config.PERSONS_ARRAY.length > 0 ? config.PERSONS_ARRAY : null,
      organizations: config.ORGANIZATIONS_ARRAY.length > 0 ? config.ORGANIZATIONS_ARRAY : null,

      // Classroom固有フィールド（直接カラムとして送信）
      display_sender: senderName,
      display_sender_email: senderEmail,
      display_sent_at: creationTime,
      display_subject: postSubject,
      display_post_text: postText,
      display_type: postType,

      // メタデータ（追加情報）
      metadata: {
        'post_type': postType,
        'course_name': courseName,
        'course_id': courseId,
        'sender_name': senderName,
        'sender_email': senderEmail
      }
    });
  }
}

// ■■■■■■■■■■ Supabase送信関数 ■■■■■■■■■■
function sendToSupabase(records, courseName, config) {
  const options = {
    method: 'post',
    contentType: 'application/json',
    headers: {
      'apikey': config.SUPABASE_KEY,
      'Authorization': 'Bearer ' + config.SUPABASE_KEY,
      'Prefer': 'resolution=merge-duplicates'
    },
    payload: JSON.stringify(records)
  };

  let success = false;
  let retryCount = 0;
  const MAX_RETRIES = 3;

  while (!success && retryCount < MAX_RETRIES) {
    try {
      const res = UrlFetchApp.fetch(config.SUPABASE_URL + '/rest/v1/' + config.TABLE_NAME + '?on_conflict=source_id', options);
      console.log(`  ✅ [${courseName}] 同期完了: ${records.length} 件送信`);
      success = true;

      // オプション: process_logsへの記録
      // recordProcessLog(records, 'completed', null, config);

    } catch (e) {
      retryCount++;
      console.warn(`  ⚠ 送信失敗 (${retryCount}/${MAX_RETRIES}): ${e.message}`);
      if (retryCount < MAX_RETRIES) {
        Utilities.sleep(3000);
      } else {
        console.error(`  ❌ [${courseName}] 送信エラー: ` + e.toString());

        // オプション: process_logsへエラー記録
        // recordProcessLog(records, 'failed', e.toString(), config);
      }
    }
  }
}

// ■■■■■■■■■■ オプション: process_logsへの記録関数 ■■■■■■■■■■
// 必要に応じてコメントアウトを解除して使用
/*
function recordProcessLog(records, status, errorMessage, config) {
  const logsToInsert = records.map(record => ({
    document_id: record.source_id,  // source_idをdocument_idとして使用
    processing_status: status,
    processing_stage: 'gas_ingestion',
    error_message: errorMessage,
    processed_at: new Date().toISOString()
  }));

  const options = {
    method: 'post',
    contentType: 'application/json',
    headers: {
      'apikey': config.SUPABASE_KEY,
      'Authorization': 'Bearer ' + config.SUPABASE_KEY
    },
    payload: JSON.stringify(logsToInsert)
  };

  try {
    UrlFetchApp.fetch(config.SUPABASE_URL + '/rest/v1/process_logs', options);
  } catch (e) {
    console.warn('process_logs記録エラー: ' + e.toString());
  }
}
*/

// ■■■■■■■■■■ ヘルパー関数 ■■■■■■■■■■
function listAnnouncements(courseId, limit) {
  let posts = []; let pageToken = null;
  do {
    const res = Classroom.Courses.Announcements.list(courseId, { pageSize: limit, pageToken: pageToken });
    if (res.announcements) posts = posts.concat(res.announcements);
    pageToken = res.nextPageToken;
  } while (pageToken);
  return posts;
}

function listCourseWork(courseId, limit) {
  let posts = []; let pageToken = null;
  do {
    const res = Classroom.Courses.CourseWork.list(courseId, { pageSize: limit, pageToken: pageToken });
    if (res.courseWork) posts = posts.concat(res.courseWork);
    pageToken = res.nextPageToken;
  } while (pageToken);
  return posts;
}

function listCourseWorkMaterials(courseId, limit) {
  let posts = []; let pageToken = null;
  do {
    const res = Classroom.Courses.CourseWorkMaterials.list(courseId, { pageSize: limit, pageToken: pageToken });
    if (res.courseWorkMaterial) posts = posts.concat(res.courseWorkMaterial);
    pageToken = res.nextPageToken;
  } while (pageToken);
  return posts;
}

function isInDateRange(dateString, startDate, endDate) {
  const d = new Date(dateString);
  return d >= startDate && d <= endDate;
}
