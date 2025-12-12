# daily_sync.py - アーカイブ理由

**アーカイブ日**: 2025-12-12
**理由**: Classroom/Driveルート統合により不要になったため

---

## なぜアーカイブされたか

### 統合前の構成

```
【Classroomルート】
GAS → Supabase → reprocess_classroom_documents_v2.py

【ファイルルート】
daily_sync.py → Google Drive → TwoStageIngestionPipeline
```

### 統合後の構成

```
【統一ルート】
GAS (Classroom & Drive監視)
  ↓
Supabase (documents + document_reprocessing_queue)
  ↓
reprocess_classroom_documents_v2.py (定期実行)
```

**結論**: `daily_sync.py` の役割が **GAS** に置き換わったため、不要になりました。

---

## 代替手段

### 以前: daily_sync.py を使う場合

```bash
# Google Driveからファイルを取得して処理
python scripts/daily_sync.py --business-id <FOLDER_ID> --personal-id <FOLDER_ID>
```

### 現在: GASを使う場合（推奨）

1. GASでGoogle Driveを監視
2. 新規ファイルをSupabaseの`documents`テーブルに投入（`processing_status = 'pending'`）
3. Supabase Triggerが自動的に`document_reprocessing_queue`に追加
4. `reprocess_classroom_documents_v2.py`が定期実行で処理

---

## 復元方法（必要な場合）

もし将来的に`daily_sync.py`が必要になった場合：

```bash
# アーカイブから復元
git mv scripts/archive/daily_sync.py scripts/daily_sync.py
```

---

## 関連ドキュメント

- `docs/GAS_INTEGRATION_GUIDE.md`: GAS統合ガイド
- `reprocess_classroom_documents_v2.py`: 統一処理スクリプト
- `database/schema_updates/v10_auto_queue_trigger.sql`: 自動キュー追加トリガー

---

**最終更新**: 2025-12-12
