function syncAllClassroomsToDocuments() {
  // ▼▼▼ 設定 ▼▼▼
  const props = PropertiesService.getScriptProperties();

  const SUPABASE_URL    = props.getProperty('SUPABASE_URL');
  const SUPABASE_KEY    = props.getProperty('SUPABASE_KEY');
  const DEST_FOLDER_ID  = props.getProperty('DEST_FOLDER_ID');

  const SERVICE_ACCOUNT_EMAIL = 'document-management-system@consummate-yew-479020-u2.iam.gserviceaccount.com';

  const TABLE_NAME      = 'documents';
  const WORKSPACE_VAL   = 'ikuya_classroom'; // ワークスペースは固定

  if (!SUPABASE_URL || !SUPABASE_KEY || !DEST_FOLDER_ID) {
    console.error("【エラー】スクリプトプロパティ設定を確認してください (COURSE_IDは不要です)。");
    return;
  }
  // ▲▲▲ 設定ここまで ▲▲▲

  const TARGET_START_DATE = new Date('2025-11-28T00:00:00');
  const TARGET_END_DATE   = new Date('2025-12-31T23:59:59');
  const FETCH_LIMIT = 20;

  const destFolder = DriveApp.getFolderById(DEST_FOLDER_ID);

  // 1. アクティブなコース一覧を取得する
  let courses = [];
  try {
    const response = Classroom.Courses.list({
      courseStates: ['ACTIVE'], // アーカイブされていないクラスのみ
      pageSize: 50
    });
    courses = response.courses || [];
  } catch (e) {
    console.error("コース一覧の取得に失敗しました: " + e.toString());
    return;
  }

  if (courses.length === 0) {
    console.log("アクティブなクラスが見つかりませんでした。");
    return;
  }

  console.log(`全 ${courses.length} 件のクラスが見つかりました。同期を開始します...`);

  // ▼▼▼ クラスごとのループ開始 ▼▼▼
  courses.forEach(course => {
    const COURSE_ID = course.id;
    const COURSE_NAME = course.name;

    // ★ここで doc_type を動的に決定
    // クラス名をそのまま使う場合（例: "5年B組", "数学I" など）
    const DOC_TYPE_VAL = COURSE_NAME;

    console.log(`\n========================================`);
    console.log(`処理中クラス: ${COURSE_NAME} (ID: ${COURSE_ID})`);
    console.log(`設定 doc_type: ${DOC_TYPE_VAL}`);
    console.log(`========================================`);

    let allPosts = [];

    try {
      // 1. お知らせ
      const resAnnounce = Classroom.Courses.Announcements.list(COURSE_ID, { pageSize: FETCH_LIMIT, orderBy: 'updateTime desc' });
      if (resAnnounce.announcements) {
        resAnnounce.announcements.forEach(p => {
          if (isInDateRange(p.creationTime, TARGET_START_DATE, TARGET_END_DATE)) {
            p._type = 'お知らせ';
            p._text = p.text || "";
            p._subject = (p.text || "").substring(0, 100); // 最初の100文字を件名として使用
            allPosts.push(p);
          }
        });
      }

      // 2. 課題
      const resWork = Classroom.Courses.CourseWork.list(COURSE_ID, { pageSize: FETCH_LIMIT, orderBy: 'updateTime desc' });
      if (resWork.courseWork) {
        resWork.courseWork.forEach(p => {
          if (isInDateRange(p.creationTime, TARGET_START_DATE, TARGET_END_DATE)) {
            p._type = '課題';
            p._text = '【課題】' + (p.title || "") + '\n' + (p.description || "");
            p._subject = p.title || "無題の課題"; // タイトルを件名として使用
            allPosts.push(p);
          }
        });
      }

      // 3. 資料
      const resMaterial = Classroom.Courses.CourseWorkMaterials.list(COURSE_ID, { pageSize: FETCH_LIMIT, orderBy: 'updateTime desc' });
      if (resMaterial.courseWorkMaterial) {
        resMaterial.courseWorkMaterial.forEach(p => {
          if (isInDateRange(p.creationTime, TARGET_START_DATE, TARGET_END_DATE)) {
            p._type = '資料';
            p._text = '【資料】' + (p.title || "") + '\n' + (p.description || "");
            p._subject = p.title || "無題の資料"; // タイトルを件名として使用
            allPosts.push(p);
          }
        });
      }

    } catch (e) {
      console.error(`  [${COURSE_NAME}] Classroom取得エラー: ` + e.toString());
      return; // このクラスの処理を中断して次のクラスへ
    }

    if (allPosts.length === 0) {
      console.log(`  [${COURSE_NAME}] 指定期間内の投稿なし。スキップします。`);
      return; // 次のクラスへ
    }

    console.log(`  検出数: ${allPosts.length} 件`);

    const recordsToInsert = [];
    const insertedSourceIds = new Set(); // 重複チェック用

    for (const post of allPosts) {
      const postText = post._text;
      const postId = post.id;
      const postSubject = post._subject;
      const postType = post._type;
      const creatorUserId = post.creatorUserId;
      const creationTime = post.creationTime;
      const materials = post.materials;

      // ★ 送信者情報を取得
      let senderName = 'Unknown';
      let senderEmail = '';

      try {
        const userProfile = Classroom.UserProfiles.get(creatorUserId);
        senderName = userProfile.name.fullName || 'Unknown';
        senderEmail = userProfile.emailAddress || '';
      } catch (e) {
        console.log(`  ⚠ 送信者情報取得エラー (userId: ${creatorUserId}): ${e.toString()}`);
      }

      // A. 添付ファイルがある場合
      if (materials && materials.length > 0) {
        materials.forEach(material => {
          if (material.driveFile) {
            const originalFileId = material.driveFile.driveFile.id;
            const fileName = material.driveFile.driveFile.title;

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
                console.log('  ➡ [コピー作成] ' + fileName);
              }

              // 権限付与
              try {
                targetFile.addViewer(SERVICE_ACCOUNT_EMAIL);
              } catch(e) {}

              finalUrl = targetFile.getUrl();
              finalFileId = targetFile.getId();

              recordsToInsert.push({
                source_type: 'classroom',
                source_id:   finalFileId,
                source_url:  finalUrl,
                file_name:   fileName,
                full_text:   postText,
                summary:     null,
                workspace:   WORKSPACE_VAL,     // 固定: ikuya_classroom
                doc_type:    DOC_TYPE_VAL,      // ★動的: クラス名

                // ★ Classroom固有情報を追加
                classroom_sender: senderName,
                classroom_sender_email: senderEmail,
                classroom_sent_at: creationTime,
                classroom_subject: postSubject,
                classroom_course_id: COURSE_ID,
                classroom_course_name: COURSE_NAME,

                metadata: {
                  'original_classroom_id': originalFileId,
                  'post_id': postId,
                  'post_type': postType,
                  'course_name': COURSE_NAME,
                  'course_id': COURSE_ID,
                  'sender_name': senderName,
                  'sender_email': senderEmail
                },
                created_at: new Date().toISOString()
              });

            } catch (e) {
              console.log('  ➡ ファイル処理エラー: ' + fileName + ' - ' + e.toString());
            }
          }
        });
      }
      // B. テキストのみの場合
      else if (postText) {
         recordsToInsert.push({
            source_type: 'classroom_text',
            source_id:   postId,
            source_url:  null,
            file_name:   'text_only',
            full_text:   postText,
            summary:     null,
            workspace:   WORKSPACE_VAL,     // 固定: ikuya_classroom
            doc_type:    DOC_TYPE_VAL,      // ★動的: クラス名

            // ★ Classroom固有情報を追加
            classroom_sender: senderName,
            classroom_sender_email: senderEmail,
            classroom_sent_at: creationTime,
            classroom_subject: postSubject,
            classroom_course_id: COURSE_ID,
            classroom_course_name: COURSE_NAME,

            metadata: {
              'post_type': postType,
              'course_name': COURSE_NAME,
              'course_id': COURSE_ID,
              'sender_name': senderName,
              'sender_email': senderEmail
            },
            created_at:  new Date().toISOString()
         });
      }
    }

    // Supabaseへ送信 (クラスごとに送信を実行)
    if (recordsToInsert.length > 0) {
      const options = {
        method: 'post',
        contentType: 'application/json',
        headers: {
          'apikey': SUPABASE_KEY,
          'Authorization': 'Bearer ' + SUPABASE_KEY,
          'Prefer': 'resolution=merge-duplicates'
        },
        payload: JSON.stringify(recordsToInsert)
      };

      try {
        const res = UrlFetchApp.fetch(SUPABASE_URL + '/rest/v1/' + TABLE_NAME + '?on_conflict=source_id', options);
        console.log(`  ✅ [${COURSE_NAME}] 同期完了: ${recordsToInsert.length} 件送信 (Status: ${res.getResponseCode()})`);
      } catch (e) {
        console.error(`  ❌ [${COURSE_NAME}] Supabase送信エラー: ` + e.toString());
        if (e.response) console.error(e.response.getContentText());
      }
    }
  }); // ▲▲▲ ループ終了 ▲▲▲

  console.log("すべてのクラスの同期処理が完了しました。");
}

function isInDateRange(dateString, startDate, endDate) {
  const d = new Date(dateString);
  return d >= startDate && d <= endDate;
}
