// ■■■■■■■■■■ メイン実行関数 ■■■■■■■■■■
function syncAllClassroomsToDocuments() {
  // ▼▼▼ 設定読み込み ▼▼▼
  const props = PropertiesService.getScriptProperties();

  const SUPABASE_URL          = props.getProperty('SUPABASE_URL');
  const SUPABASE_KEY          = props.getProperty('SUPABASE_KEY');
  const DEST_FOLDER_ID        = props.getProperty('DEST_FOLDER_ID');

  // プロパティから取得
  const WORKSPACE_VAL         = props.getProperty('WORKSPACE_NAME');
  const SERVICE_ACCOUNT_EMAIL = props.getProperty('SERVICE_ACCOUNT_EMAIL');

  const TABLE_NAME = 'documents';

  // 設定漏れチェック
  if (!SUPABASE_URL || !SUPABASE_KEY || !DEST_FOLDER_ID || !WORKSPACE_VAL || !SERVICE_ACCOUNT_EMAIL) {
    console.error("【エラー】スクリプトプロパティが不足しています。以下を確認してください:\n" +
      "- SUPABASE_URL\n- SUPABASE_KEY\n- DEST_FOLDER_ID\n- WORKSPACE_NAME\n- SERVICE_ACCOUNT_EMAIL");
    return;
  }
  // ▲▲▲ 設定ここまで ▲▲▲

  // 日付設定：今日から過去7日間を対象（毎日自動実行用）
  const now = new Date();
  const TARGET_START_DATE = new Date();
  TARGET_START_DATE.setDate(now.getDate() - 7);
  const TARGET_END_DATE = new Date();
  TARGET_END_DATE.setDate(now.getDate() + 1);

  const FETCH_LIMIT = 20;

  // 保存先フォルダ取得
  let destFolder;
  try {
    destFolder = DriveApp.getFolderById(DEST_FOLDER_ID);
  } catch (e) {
    console.error("❌ 保存先フォルダが見つかりません。IDを確認してください:", e.message);
    return;
  }

  // 1. アクティブなコース一覧を取得
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
    console.error("コース一覧の取得に失敗しました: " + e.toString());
    return;
  }

  console.log(`全 ${courses.length} 件のクラスが見つかりました。フォルダ「${destFolder.getName()}」を使用して同期を開始します...`);

  // ▼▼▼ クラスごとの処理 ▼▼▼
  courses.forEach(course => {
    processCourse(course, TARGET_START_DATE, TARGET_END_DATE, destFolder, {
      SUPABASE_URL, SUPABASE_KEY, TABLE_NAME, WORKSPACE_VAL, SERVICE_ACCOUNT_EMAIL, FETCH_LIMIT
    });
  });

  console.log("すべてのクラスの同期処理が完了しました。");
}

// ■■■■■■■■■■ クラス処理関数 ■■■■■■■■■■
function processCourse(course, startDate, endDate, destFolder, config) {
  const COURSE_ID = course.id;
  const COURSE_NAME = course.name;

  // doc_type はクラス名を使用
  const DOC_TYPE_VAL = COURSE_NAME;

  console.log(`\n========================================`);
  console.log(`処理中クラス: ${COURSE_NAME}`);

  let allPosts = [];

  try {
    // 1. お知らせ
    const resAnnounce = listAnnouncements(COURSE_ID, config.FETCH_LIMIT);
    resAnnounce.forEach(p => {
      if (isInDateRange(p.creationTime, startDate, endDate)) {
        p._type = 'お知らせ';
        allPosts.push(p);
      }
    });

    // 2. 課題
    const resWork = listCourseWork(COURSE_ID, config.FETCH_LIMIT);
    resWork.forEach(p => {
      if (isInDateRange(p.creationTime, startDate, endDate)) {
        p._type = '課題';
        allPosts.push(p);
      }
    });

    // 3. 資料
    try {
       let pageToken = null;
       do {
          const resMaterial = Classroom.Courses.CourseWorkMaterials.list(COURSE_ID, { pageSize: config.FETCH_LIMIT, orderBy: 'updateTime desc', pageToken: pageToken });
          if (resMaterial.courseWorkMaterial) {
            resMaterial.courseWorkMaterial.forEach(p => {
              if (isInDateRange(p.creationTime, startDate, endDate)) {
                p._type = '資料';
                allPosts.push(p);
              }
            });
          }
          pageToken = resMaterial.nextPageToken;
       } while(pageToken);
    } catch(e) { /* 資料取得エラーは無視 */ }

  } catch (e) {
    console.error(`  [${COURSE_NAME}] Classroom取得エラー: ` + e.toString());
    return;
  }

  if (allPosts.length === 0) {
    console.log(`  [${COURSE_NAME}] 投稿なし。スキップ。`);
    return;
  }

  console.log(`  検出数: ${allPosts.length} 件`);

  const recordsToInsert = [];
  const insertedSourceIds = new Set();

  for (const post of allPosts) {
    // ★★★ 統一的なマッピング処理 ★★★
    const postType = post._type;
    const postId = post.id;
    const creatorUserId = post.creatorUserId;
    const creationTime = post.creationTime;
    const materials = post.materials;

    // titleの処理パート（統一）
    const postSubject = post.title || post.text || "";

    // textの処理パート（統一）
    const postText = post.description || post.text || "";

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

          // ★★★ ファイルコピー & 権限付与ロジック ★★★
          try {
            const existingFiles = destFolder.getFilesByName(fileName);
            let targetFile;

            if (existingFiles.hasNext()) {
              console.log(`  ⏭ [既存利用] ${fileName}`);
              targetFile = existingFiles.next();
            } else {
              // 親フォルダへコピー
              const originalFile = DriveApp.getFileById(originalFileId);
              targetFile = originalFile.makeCopy(fileName, destFolder);
              console.log(`  ⬇️ [コピー作成] ${fileName}`);
            }

            if (targetFile) {
              // サービスアカウントへ権限付与
              try {
                targetFile.addViewer(config.SERVICE_ACCOUNT_EMAIL);
              } catch(e) {
                console.log(`  ⚠ 権限付与失敗: ${e.message}`);
              }
              finalUrl = targetFile.getUrl();
              finalFileId = targetFile.getId();
            }

            // 重複チェック
            const uniqueSourceId = finalFileId || originalFileId;
            if (insertedSourceIds.has(uniqueSourceId)) return;
            insertedSourceIds.add(uniqueSourceId);

            // ✅ 修正: 6個のclassroomカラムに送信
            recordsToInsert.push({
              source_type: 'classroom',
              source_id:   uniqueSourceId,
              source_url:  finalUrl,
              file_name:   fileName,
              workspace:   config.WORKSPACE_VAL,
              doc_type:    DOC_TYPE_VAL, // コース名

              // ★★★ 必須の6個のclassroomカラム ★★★
              display_sender: senderName,
              display_sender_email: senderEmail,
              display_sent_at: creationTime,
              display_subject: postSubject,
              display_post_text: postText,
              display_type: postType, // ✅ 新規追加: お知らせ/課題/資料

              metadata: {
                'original_classroom_id': originalFileId,
                'post_id': postId,
                'post_type': postType,
                'course_name': COURSE_NAME,
                'course_id': COURSE_ID,
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
      if (insertedSourceIds.has(postId)) continue;
      insertedSourceIds.add(postId);

      // ✅ 修正: 6個のclassroomカラムに送信
      recordsToInsert.push({
        source_type: 'classroom_text',
        source_id:   postId,
        source_url:  null,
        file_name:   'text_only',
        workspace:   config.WORKSPACE_VAL,
        doc_type:    DOC_TYPE_VAL, // コース名

        // ★★★ 必須の6個のclassroomカラム ★★★
        display_sender: senderName,
        display_sender_email: senderEmail,
        display_sent_at: creationTime,
        display_subject: postSubject,
        display_post_text: postText,
        display_type: postType, // ✅ 新規追加: お知らせ/課題/資料

        metadata: {
          'post_type': postType,
          'course_name': COURSE_NAME,
          'course_id': COURSE_ID,
          'sender_name': senderName,
          'sender_email': senderEmail
        }
      });
    }
  }

  // Supabaseへ送信 (リトライ機能付き)
  if (recordsToInsert.length > 0) {
    const options = {
      method: 'post',
      contentType: 'application/json',
      headers: {
        'apikey': config.SUPABASE_KEY,
        'Authorization': 'Bearer ' + config.SUPABASE_KEY,
        'Prefer': 'resolution=merge-duplicates'
      },
      payload: JSON.stringify(recordsToInsert)
    };

    let success = false;
    let retryCount = 0;
    const MAX_RETRIES = 3;

    while (!success && retryCount < MAX_RETRIES) {
      try {
        const res = UrlFetchApp.fetch(config.SUPABASE_URL + '/rest/v1/' + config.TABLE_NAME + '?on_conflict=source_id', options);
        console.log(`  ✅ [${COURSE_NAME}] 同期完了: ${recordsToInsert.length} 件送信`);
        success = true;
      } catch (e) {
        retryCount++;
        console.warn(`  ⚠ 送信失敗 (${retryCount}/${MAX_RETRIES}): ${e.message}`);
        if (retryCount < MAX_RETRIES) Utilities.sleep(3000);
        else console.error(`  ❌ [${COURSE_NAME}] 送信エラー: ` + e.toString());
      }
    }
  }
}

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

function isInDateRange(dateString, startDate, endDate) {
  const d = new Date(dateString);
  return d >= startDate && d <= endDate;
}
