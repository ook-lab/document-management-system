# プロジェクト修正 進捗記録

**開始日時**: 2025-12-12
**基準レポート**: PROJECT_EVALUATION_REPORT_20251212.md
**作業ディレクトリ**: K:\document-management-system

---

## 進捗サマリー

| カテゴリ | 完了 | 未完了 | 状態 |
|---------|------|--------|------|
| 優先度A（即座対応） | 0 | 2 | 未開始 |
| 優先度B（順次対応） | 0 | 2 | 未開始 |
| 優先度C（将来対応） | 0 | 2 | 未開始 |
| **合計** | **0** | **6** | **0%** |

---

## 優先度A（即座対応 - データ損失リスクあり）

### ✅ Step 0: バックアップ（必須）
- **状態**: 未開始
- **開始時刻**: -
- **完了時刻**: -
- **実施内容**:
  - [ ] Supabaseスナップショット作成確認
  - [ ] PostgreSQL dumpバックアップ作成（オプション）
- **備考**:

---

### ✅ A1: スキーマの統合と修正
- **状態**: 未開始
- **開始時刻**: -
- **完了時刻**: -
- **対象ファイル**:
  - `database/schema_v4_unified.sql`
  - `database/schema_updates/add_document_chunks.sql`
- **実施内容**:
  - [ ] schema_v4_unified.sqlにdocument_chunks定義を追加
  - [ ] documents.embeddingカラムをDEPRECATEDコメント化
  - [ ] 本番DBでdocument_chunksテーブル存在確認
  - [ ] 未使用のhybrid_search関数を削除またはコメント化
- **備考**:

---

### ✅ A2: パイプラインのバグ修正
- **状態**: 未開始
- **開始時刻**: -
- **完了時刻**: -
- **対象ファイル**: `pipelines/two_stage_ingestion.py`
- **修正箇所**:
  - [ ] 464行目付近: `full_text_embedding = self.llm_client.generate_embedding(chunk_target_text)` を追加
  - [ ] 525行目: `'embedding': embedding` → `'embedding': full_text_embedding` に修正
- **備考**:

---

### ✅ Step 4: 検証テスト
- **状態**: 未開始
- **開始時刻**: -
- **完了時刻**: -
- **実施内容**:
  - [ ] 検索機能テスト（Pythonスクリプト実行）
  - [ ] チャンク生成テスト（test_single_file.py）
  - [ ] 既存データ整合性確認（check_table_structure.py）
- **備考**:

---

## 優先度B（順次対応 - 機能改善）

### ✅ B1: Stage命名の再構成と3ルート管理
- **状態**: 未開始
- **開始時刻**: -
- **完了時刻**: -
- **対象ファイル**:
  - `core/ai/stage1_classifier.py` → `core/ai/stageA_classifier.py`
  - `core/ai/stage2_extractor.py` → `core/ai/stageC_extractor.py`
  - Vision処理 → `core/ai/stageB_vision.py`（新規統合）
  - `pipelines/gmail_ingestion.py`
  - `pipelines/two_stage_ingestion.py`
- **実施内容**:
  - [ ] ファイル名変更
  - [ ] データベーススキーマ更新（ALTER TABLE）
  - [ ] ingestion_routeカラム追加
- **備考**:

---

### ✅ B2: メタデータ別ベクトル化戦略
- **状態**: 未開始
- **開始時刻**: -
- **完了時刻**: -
- **対象ファイル**:
  - `core/processing/metadata_chunker.py`（新規作成）
  - `database/schema_updates/add_metadata_chunk_columns.sql`（新規作成）
- **実施内容**:
  - [ ] MetadataChunkerクラス作成
  - [ ] document_chunksテーブルにchunk_type, search_weightカラム追加
  - [ ] search_documents_with_chunks関数更新（ウェイト計算）
- **備考**:

---

### ✅ 未使用ファイルのアーカイブ
- **状態**: 未開始
- **開始時刻**: -
- **完了時刻**: -
- **対象ディレクトリ**: `scripts/one_time/`
- **実施内容**:
  - [ ] `scripts/archive/one_time/`ディレクトリ作成
  - [ ] check_*.py（10個）を移動
  - [ ] test_*.py（12個）を移動
  - [ ] delete_price_list.pyを移動
  - [ ] 必要なスクリプトのみルートに残す
- **備考**:

---

## 優先度C（将来対応 - アーキテクチャ改善）

### ✅ C1: 検索関数の完全統一
- **状態**: 未開始
- **開始時刻**: -
- **完了時刻**: -
- **実施内容**:
  - [ ] unified_search関数の設計
  - [ ] hybrid_search, match_documentsの統合
- **備考**: （オプション）

---

### ✅ C2: correction_history テーブルの統合
- **状態**: 未開始
- **開始時刻**: -
- **完了時刻**: -
- **実施内容**:
  - [ ] v7_add_correction_history.sql作成
  - [ ] schema_v4_unified.sqlに統合
- **備考**: （オプション）

---

## エラー・問題ログ

### 発生したエラー
（なし）

---

## 備考・メモ

- このログファイルは各タスク完了時に自動更新されます
- 各セクションの状態は「未開始」「進行中」「完了」「スキップ」のいずれか
- エラーが発生した場合は「エラー・問題ログ」セクションに記録

---

**最終更新**: 2025-12-12（作成時）
