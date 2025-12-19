# Stage1/Stage2 残骸ファイル分析

## ファイル分類（39個）

### 【A】確実に削除可能なSQLマイグレーションファイル（既に実行済み）
これらは旧設定からの移行用で、既に実行済みのため不要：

1. `J_resources/sql/schema_updates/remove_stage1_columns.sql` (6箇所参照)
2. `J_resources/sql/schema_updates/rename_stages_to_ABC.sql` (7箇所参照)
3. `J_resources/sql/schema_updates/remove_unused_columns.sql` (8箇所参照)
4. `J_resources/sql/schema_updates/remove_doc_type_column.sql` (2箇所参照)
5. `J_resources/sql/cleanup_remove_columns_step2_drop_columns.sql` (3箇所参照)

### 【B】古いスキーマファイル（参考用として残すか要検討）
6. `J_resources/sql/step1_create_tables.sql` (1箇所参照)
7. `J_resources/sql/schema_v4_unified.sql` (9箇所参照)
8. `J_resources/sql/migration_3tier_structure.sql` (3箇所参照)
9. `J_resources/sql/schema_updates/add_text_extraction_and_vision_model_columns.sql` (3箇所参照)

### 【C】アーカイブ済みドキュメント（既にarchiveフォルダ内）
10. `J_resources/docs/archive/PROJECT_EVALUATION_REPORT_20251212.md` (16箇所参照)
11. `J_resources/docs/archive/PROGRESS_LOG_20251212.md` (2箇所参照)

### 【D】現役ドキュメント（内容更新が必要）
これらは現役の参考ドキュメントですが、stage1/stage2への参照を削除/更新すべき：

12. `DESIGN_REPROCESS_COMPLETE.md` (3箇所参照)
13. `DESIGN_UNIFIED_PIPELINE.md` (1箇所参照)
14. `J_resources/docs/UNIFIED_PROCESSING_FLOW.md` (2箇所参照)
15. `J_resources/docs/TEXT_ONLY_DOCUMENT_SUPPORT.md` (48箇所参照) ⚠️大量
16. `J_resources/docs/TABLE_STRUCTURE_EXTRACTION.md` (5箇所参照)
17. `J_resources/docs/REPROCESSING_QUEUE_GUIDE.md` (1箇所参照)
18. `J_resources/docs/MIGRATION_NOTES.md` (1箇所参照)
19. `J_resources/docs/METADATA_FILTERING_GUIDE.md` (2箇所参照)
20. `J_resources/docs/JSON_SCHEMA_VALIDATION.md` (6箇所参照)
21. `J_resources/docs/INBOX_MONITOR_SETUP.md` (2箇所参照)
22. `J_resources/docs/IMPLEMENTATION_STEPS.md` (7箇所参照)
23. `J_resources/docs/EVENT_DATES_IMPLEMENTATION.md` (6箇所参照)
24. `J_resources/docs/DYNAMIC_SYSTEM.md` (2箇所参照)
25. `J_resources/docs/DUPLICATE_DETECTION.md` (2箇所参照)
26. `J_resources/docs/DATABASE_CLEANUP_GUIDE.md` (1箇所参照)
27. `J_resources/docs/COMPOSITE_CONFIDENCE.md` (5箇所参照)
28. `J_resources/docs/CLASSROOM_REPROCESSING_GUIDE.md` (5箇所参照)
29. `J_resources/docs/CLASSROOM_INTEGRATION_SUMMARY.md` (3箇所参照)
30. `J_resources/docs/50_DOC_TYPE_CLASSIFICATION.md` (6箇所参照)

### 【E】現役Pythonコード（コード修正が必要）
これらは実際に使われているコードで、変数名や関数名の更新が必要：

31. `process_queued_documents.py` (9箇所参照)
32. `A_common/utils/metadata_extractor.py` (2箇所参照)
33. `C_ai_common/llm_client/llm_client.py` (2箇所参照)
34. `H_streamlit/review_ui.py` (9箇所参照)
35. `H_streamlit/utils/stageC_reprocessor.py` (3箇所参照)
36. `H_streamlit/components/manual_text_correction.py` (16箇所参照)
37. `ui/review_ui.py` (16箇所参照)
38. `ui/utils/stageC_reprocessor.py` (3箇所参照)
39. `ui/components/manual_text_correction.py` (14箇所参照)

## 推奨対応

### 即座に削除可能（5ファイル）
- 【A】のSQLマイグレーションファイル全て

### 要確認後削除（4ファイル）
- 【B】の古いスキーマファイル（現在使用されていなければ削除）

### アーカイブ済み（2ファイル）
- 【C】は既にarchiveフォルダ内なので、そのまま保持

### 内容更新が必要（21ファイル）
- 【D】のドキュメントファイル：stage1/stage2の記述をstageE-Kに更新

### コード修正が必要（9ファイル）
- 【E】のPythonファイル：変数名・関数名をリファクタリング

## 合計削減効果
- 削除可能: 5-9ファイル
- 更新必要: 30ファイル
- 参照箇所: 242箇所
