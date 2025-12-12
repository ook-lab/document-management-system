# プロジェクト整理計画 - Document Management System

**作成日**: 2025-12-12
**バージョン**: v1.0
**ステータス**: 承認待ち

---

## 📋 エグゼクティブサマリー

このドキュメントは、document-management-systemプロジェクトの詳細な構造分析と整理計画を記載します。

### 現状の問題点
- ルートディレクトリに11個のファイルが散在（本来はサブディレクトリにあるべき）
- 古いコードベース出力ファイルが8世代分で15MB+を占有
- scripts/archive/に30個以上のファイルが蓄積
- ログファイルの無制限蓄積（43ファイル、1.4MB+）
- 重複ファイルと空ファイルの存在

### 整理による効果
- **ストレージ削減**: 約13MB（Phase 1のみ）
- **可読性向上**: ファイル配置の明確化
- **メンテナンス性向上**: 論理的なディレクトリ構造

---

## 🔍 現在のディレクトリ構造の全体像

```
document-management-system/
├── .claude/                      (Claude実装計画)
├── .devcontainer/               (開発コンテナ設定)
├── .github/                      (GitHub Actions)
├── .env / .env.example          (環境設定)
├── .gitignore
├── app.py                        (Flaskメインアプリ)
├── config/                       (設定ファイル)
├── core/                         (コア処理ロジック - 1.1MB)
│   ├── ai/                       (AI/LLM処理)
│   ├── chunking/                 (テキストチャンキング)
│   ├── connectors/               (Google Drive/Gmail接続)
│   ├── database/                 (Supabase接続)
│   ├── document/                 (ドキュメント処理)
│   ├── processing/               (パイプライン処理)
│   ├── processors/               (PDF/Office処理)
│   ├── search/                   (検索ロジック)
│   └── utils/                    (ユーティリティ)
├── credentials/                  (google_credentials.json)
├── database/                     (SQL スクリプト - 246KB)
│   ├── schema_updates/           (20+ バージョンのスキーマ更新)
│   └── schema_v4_unified.sql    (メインスキーマ)
├── docs/                         (マークダウン文書 - 384KB, 30ファイル)
├── frontend/                     (React/TypeScript UI - 234KB)
│   └── src/                      (Vite + React)
├── gas/                          (Google Apps Script)
│   └── ClassroomToSupabase_updated.gs
├── logs/                         (ログファイル - 1.4MB, 43ファイル)
│   ├── db_errors/               (データベースエラーログ)
│   └── daily_sync_*.log
├── pipelines/                    (データ取込パイプライン)
│   ├── two_stage_ingestion.py
│   └── gmail_ingestion.py
├── scripts/                      (スクリプト類)
│   ├── archive/                  (アーカイブ済み)
│   ├── one_time/                 (ワンタイム実行スクリプト)
│   └── inbox_monitor.py
├── templates/                    (HTMLテンプレート - 44KB)
├── tests/                        (ユニットテスト - 36KB, 3ファイル)
├── ui/                           (Streamlit UI - 374KB)
│   ├── components/
│   ├── schemas/
│   └── utils/
├── temp/                         (一時ファイル)
├── venv/                         (Python仮想環境)
└── ルートレベルのスクリプト/ドキュメント
    ├── reprocess_classroom_documents_v2.py (28KB)
    ├── migrate_to_chunks.py
    ├── regenerate_*.py
    ├── test_*.py
    └── project_codebase_*.md (8ファイル, 計15MB)
```

---

## 🚨 発見された問題点

### 🔴 緊急度: 高

#### 1. ルートディレクトリのファイル散在（11ファイル）

| ファイル | 本来あるべき場所 | 理由 |
|---|---|---|
| `reprocess_classroom_documents_v2.py` | `scripts/` | 定期実行スクリプト |
| `migrate_to_chunks.py` | `scripts/one_time/` | データ移行スクリプト |
| `regenerate_all_embeddings.py` | `scripts/one_time/` | メンテナンススクリプト |
| `regenerate_embeddings_simple.py` | `scripts/one_time/` | メンテナンススクリプト |
| `test_table_parser.py` | `tests/` | テストファイル |
| `test_vision_extraction.py` | `tests/` | テストファイル |
| `collect_codebase.py` | `scripts/` | ユーティリティスクリプト |
| `emergency_diagnose_and_fix.py` | `scripts/one_time/` | 緊急対応スクリプト |
| `fix_sql_function.sql` | `database/schema_updates/` | SQLマイグレーション |
| `start_email_ui.sh` | `scripts/` | 起動スクリプト |

**計**: 11個のファイルが不適切な場所に配置

#### 2. project_codebase_*.md の重複保存（15MB+）

| ファイル | サイズ | 作成日 | アクション |
|---|---|---|---|
| `project_codebase_20251202_105336.md` | 729KB | 12月2日 | 削除候補 |
| `project_codebase_20251202_135845.md` | 1.5MB | 12月2日 | 削除候補 |
| `project_codebase_20251210_094555.md` | 2.1MB | 12月10日 | 削除候補 |
| `project_codebase_20251210_114701.md` | 2.2MB | 12月10日 | 削除候補 |
| `project_codebase_20251210_134757.md` | 2.1MB | 12月10日 | 削除候補 |
| `project_codebase_20251210_165546.md` | 2.1MB | 12月10日 | 削除候補 |
| `project_codebase_20251211_112508.md` | 2.2MB | 12月11日 | 削除候補 |
| `project_codebase_20251211_173313.md` | 2.2MB | 12月11日 | **保持（最新版）** |

**削減容量**: 約13MB

#### 3. 重複ファイル

- `migrate_to_chunks.py` がルートと`scripts/archive/`に存在
- どちらを使用すべきか不明確

#### 4. 空ファイル

- `requirements_full.txt` (0バイト)

### 🟡 中程度

#### 5. scripts/archive/ の過度な蓄積（30+ファイル）

**アーカイブスクリプト群**:

| ファイル | 廃止理由 | 推奨アクション |
|---|---|---|
| `daily_sync.py` | Classroom/Drive統合で不要 | 削除候補 |
| `check_embedding.py` | テスト用 | 削除候補 |
| `check_llm_setup.py` | テスト用 | 削除候補 |
| `test_search_query.py` | テスト用 | 削除候補 |
| その他 `one_time/*` | ワンタイム実行済み | 確認後削除 |

**推定不要ファイル**: archive/配下の約30ファイル

#### 6. database/ のSQLスクリプト過多（42ファイル）

- 30以上のマイグレーションスクリプト
- 実行順序が不明確
- スキーマバージョン管理が曖昧

**問題**:
- どのスクリプトが必須か不明
- 新規環境構築時の手順が複雑

#### 7. ドキュメントの散在

**ルートレベルのドキュメント**（docs/へ移動すべき）:

| ファイル | 用途 | 優先度 |
|---|---|---|
| `DATABASE_CLEANUP_GUIDE.md` | DBクリーンアップ | 参照用 |
| `EMERGENCY_RESTORE_GUIDE.md` | 緊急復旧 | 参照用 |
| `FILTER_FEATURE_GUIDE.md` | フィルタ機能 | 参照用 |
| `IMPLEMENTATION_STEPS.md` | 実装ステップ | 参照用 |
| `METADATA_SEARCH_UPDATE.md` | メタデータ検索 | 参照用 |
| `QUICK_START_FIXES.md` | クイックスタート | 補助 |
| `PROGRESS_LOG_20251212.md` | 進捗記録 | 一時的 |
| `PROJECT_EVALUATION_REPORT_20251212.md` | 評価レポート | 一時的 |

**計**: 8個の補助/参照ドキュメントがルートに配置

#### 8. logs/ の無制限蓄積（43ファイル、1.4MB+）

**構成**:
- `daily_sync_*.log` - 5個の日次ログ
- `db_errors/` - 38個のデータベースエラー JSON（2025-12-08～12-10日付）

**問題**:
- ログローテーション戦略がない
- 古いエラーログが削除されていない

### 🟢 軽微

#### 9. 複数のUI層の並行存在

| ファイル | 用途 | フレームワーク |
|---|---|---|
| `app.py` | Web API | Flask |
| `ui/review_ui.py` | ドキュメントレビュー | Streamlit |
| `ui/email_inbox.py` | メール管理 | Streamlit |
| `frontend/src/App.tsx` | Web UI | React/TypeScript |

**問題**: どれがメインUIか不明確

#### 10. 命名規則の不統一

- `v2.0` vs `_v2` vs `_simple`
- プレフィックスのばらつき

#### 11. macOS ファイルの混在

- `.DS_Store` ファイルが5個存在
- `.gitignore`に追加されていない

---

## 🎯 整理計画

### Phase 1: 即座実施（1日以内）⭐ まずはこれだけ

#### A. ルートレベルのファイル整理

**スクリプトファイルの移動**:
```bash
git mv reprocess_classroom_documents_v2.py scripts/
git mv collect_codebase.py scripts/
git mv emergency_diagnose_and_fix.py scripts/one_time/
git mv migrate_to_chunks.py scripts/one_time/
git mv regenerate_all_embeddings.py scripts/one_time/
git mv regenerate_embeddings_simple.py scripts/one_time/
```

**テストファイルの移動**:
```bash
git mv test_table_parser.py tests/
git mv test_vision_extraction.py tests/
```

**SQLファイルの移動**:
```bash
git mv fix_sql_function.sql database/schema_updates/
```

**起動スクリプトの移動**:
```bash
git mv start_email_ui.sh scripts/
```

**影響**: インポートパスの変更なし（スクリプトは直接実行されるため）

#### B. 重複・不要ファイルの削除

**古いコードベース出力を削除**:
```bash
# 古いバージョンを削除（最新版のみ保持）
rm project_codebase_20251202_105336.md
rm project_codebase_20251202_135845.md
rm project_codebase_20251210_094555.md
rm project_codebase_20251210_114701.md
rm project_codebase_20251210_134757.md
rm project_codebase_20251210_165546.md
rm project_codebase_20251211_112508.md
# 保持: project_codebase_20251211_173313.md (最新版)
```

**重複ファイルの削除**:
```bash
# ルート版を使用し、archive版を削除
rm scripts/archive/migrate_to_chunks.py
```

**空ファイルの削除**:
```bash
rm requirements_full.txt
```

**macOS属性ファイルの削除**:
```bash
# .DS_Storeを全て削除
find . -name ".DS_Store" -delete

# .gitignoreに追加
echo ".DS_Store" >> .gitignore
```

**削減容量**: 約13MB

#### C. ドキュメントの整理

**ルートレベルの補助ドキュメントをdocs/へ移動**:
```bash
git mv DATABASE_CLEANUP_GUIDE.md docs/
git mv EMERGENCY_RESTORE_GUIDE.md docs/
git mv FILTER_FEATURE_GUIDE.md docs/
git mv IMPLEMENTATION_STEPS.md docs/
git mv METADATA_SEARCH_UPDATE.md docs/
git mv QUICK_START_FIXES.md docs/
```

**一時的なドキュメント（アーカイブ）**:
```bash
# docs/archive/ ディレクトリを作成
mkdir -p docs/archive

# 一時的なドキュメントを移動
git mv PROGRESS_LOG_20251212.md docs/archive/
git mv PROJECT_EVALUATION_REPORT_20251212.md docs/archive/
```

---

### Phase 2: 短期実施（1週間以内）

#### D. database/ スキーマの整理

**実行済みマイグレーションを明確化**:

`database/schema_updates/README.md` を作成:

```markdown
# データベーススキーマ更新ガイド

## 実行順序

新規環境構築時は以下の順序で実行：

1. **メインスキーマ**: `../schema_v4_unified.sql`
2. **v5以降の拡張**:
   - v5_add_*.sql
   - v6_add_*.sql
   - v7_add_correction_history.sql
   - v8_add_*.sql
   - v9_add_reprocessing_queue.sql
   - v10_auto_queue_trigger.sql

## 各バージョンの内容

| バージョン | ファイル | 内容 | 必須 |
|---|---|---|---|
| v5 | `v5_add_*.sql` | ... | ✅ |
| v6 | `v6_add_*.sql` | ... | ✅ |
...
```

#### E. logs/ のクリーンアップ

**古いログの削除**:
```bash
# 古いエラーログを削除（12月8日〜10日）
rm -rf logs/db_errors/*.json

# .gitignoreに追加
echo "logs/*.log" >> .gitignore
echo "logs/db_errors/*.json" >> .gitignore
```

**削減容量**: 約500KB

**ログローテーション戦略の追加**:

`scripts/cleanup_old_logs.py` を作成:
```python
# 30日以上古いログを自動削除
```

---

### Phase 3: 中期実施（必要に応じて）

#### F. scripts/archive/ の整理

**削除判定が必要なファイル**:
- 30個以上のアーカイブファイルの確認
- 必要なものはdocs/に移動、不要なものは完全削除

**手順**:
1. 各ファイルの最終実行日を確認
2. 3ヶ月以上使用されていないファイルを削除候補に
3. README.mdに削除理由を記載してから削除

#### G. UI層の統一検討

**現状**:
- Flask (app.py) - Web API
- Streamlit (ui/) - ドキュメントレビュー・メール管理
- React (frontend/) - Web UI

**検討事項**:
- メインUIをどれにするか決定
- 不要なUI層の廃止検討
- フロントエンド・バックエンドの役割分担の明確化

---

## 📊 整理後のディレクトリ構造（Phase 1完了時）

```
document-management-system/
├── .env / .env.example
├── .gitignore                       (📝 .DS_Store追加)
├── README.md                        (メインドキュメント)
├── README_WEBAPP.md
├── app.py                           (Flaskメインアプリ)
├── requirements.txt
├── .claude/
├── .devcontainer/
├── .github/
├── config/                          (設定ファイル)
├── core/                            (コア処理ロジック)
├── credentials/                     (認証情報)
├── database/                        (SQLスクリプト)
│   ├── schema_v4_unified.sql
│   ├── search_documents_with_chunks.sql
│   ├── add_match_documents_function.sql
│   └── schema_updates/
│       ├── README.md               (📝 新規作成 - Phase 2)
│       ├── fix_sql_function.sql    (📝 from root)
│       └── v5〜v10_*.sql
├── docs/                            (📝 統合・整理済み)
│   ├── archive/                    (📝 新規作成)
│   │   ├── PROGRESS_LOG_20251212.md
│   │   └── PROJECT_EVALUATION_REPORT_20251212.md
│   ├── DATABASE_CLEANUP_GUIDE.md   (📝 from root)
│   ├── EMERGENCY_RESTORE_GUIDE.md  (📝 from root)
│   ├── FILTER_FEATURE_GUIDE.md     (📝 from root)
│   ├── GAS_INTEGRATION_GUIDE.md
│   ├── IMPLEMENTATION_STEPS.md     (📝 from root)
│   ├── METADATA_SEARCH_UPDATE.md   (📝 from root)
│   ├── PROJECT_CLEANUP_PLAN_20251212.md (📝 このファイル)
│   ├── QUICK_START_FIXES.md        (📝 from root)
│   ├── UNIFIED_PROCESSING_FLOW.md
│   └── ...（その他30個のガイド）
├── frontend/                        (React UI)
├── gas/                             (Google Apps Script)
├── logs/                            (📝 古いログ削除済み - Phase 2)
├── pipelines/                       (データパイプライン)
├── scripts/                         (📝 整理済み)
│   ├── archive/                    (アーカイブ)
│   │   ├── ARCHIVED_DAILY_SYNC_README.md
│   │   └── ...（30+ファイル）
│   ├── one_time/                   (ワンタイム実行)
│   │   ├── emergency_diagnose_and_fix.py  (📝 from root)
│   │   ├── migrate_to_chunks.py           (📝 from root)
│   │   ├── regenerate_all_embeddings.py   (📝 from root)
│   │   ├── regenerate_embeddings_simple.py (📝 from root)
│   │   └── ...
│   ├── collect_codebase.py                (📝 from root)
│   ├── inbox_monitor.py
│   ├── reprocess_classroom_documents_v2.py (📝 from root)
│   └── start_email_ui.sh                   (📝 from root)
├── templates/
├── tests/                           (📝 テスト統合済み)
│   ├── test_app_table_functions.py
│   ├── test_llm_client_retry.py
│   ├── test_table_parser.py        (📝 from root)
│   ├── test_two_stage_error_handling.py
│   └── test_vision_extraction.py   (📝 from root)
├── ui/                              (Streamlit UI)
├── temp/
├── venv/
└── project_codebase_20251211_173313.md (最新版のみ保持)
```

---

## ✅ チェックリスト

### Phase 1: 即座実施

#### A. ルートレベルのファイル整理
- [ ] `reprocess_classroom_documents_v2.py` → `scripts/`
- [ ] `collect_codebase.py` → `scripts/`
- [ ] `emergency_diagnose_and_fix.py` → `scripts/one_time/`
- [ ] `migrate_to_chunks.py` → `scripts/one_time/`
- [ ] `regenerate_all_embeddings.py` → `scripts/one_time/`
- [ ] `regenerate_embeddings_simple.py` → `scripts/one_time/`
- [ ] `test_table_parser.py` → `tests/`
- [ ] `test_vision_extraction.py` → `tests/`
- [ ] `fix_sql_function.sql` → `database/schema_updates/`
- [ ] `start_email_ui.sh` → `scripts/`

#### B. 重複・不要ファイルの削除
- [ ] 古い `project_codebase_*.md` を削除（7ファイル）
- [ ] `scripts/archive/migrate_to_chunks.py` を削除
- [ ] `requirements_full.txt` を削除
- [ ] `.DS_Store` を全て削除（5個）
- [ ] `.gitignore` に `.DS_Store` を追加

#### C. ドキュメントの整理
- [ ] `DATABASE_CLEANUP_GUIDE.md` → `docs/`
- [ ] `EMERGENCY_RESTORE_GUIDE.md` → `docs/`
- [ ] `FILTER_FEATURE_GUIDE.md` → `docs/`
- [ ] `IMPLEMENTATION_STEPS.md` → `docs/`
- [ ] `METADATA_SEARCH_UPDATE.md` → `docs/`
- [ ] `QUICK_START_FIXES.md` → `docs/`
- [ ] `docs/archive/` ディレクトリを作成
- [ ] `PROGRESS_LOG_20251212.md` → `docs/archive/`
- [ ] `PROJECT_EVALUATION_REPORT_20251212.md` → `docs/archive/`

### Phase 2: 短期実施

#### D. database/ スキーマの整理
- [ ] `database/schema_updates/README.md` を作成
- [ ] 実行順序ガイドを記載
- [ ] 各バージョンの内容を文書化

#### E. logs/ のクリーンアップ
- [ ] `logs/db_errors/*.json` を削除
- [ ] `.gitignore` にログファイルを追加
- [ ] `scripts/cleanup_old_logs.py` を作成（ログローテーション）

### Phase 3: 中期実施

#### F. scripts/archive/ の整理
- [ ] アーカイブファイルの削除判定
- [ ] 不要ファイルの削除
- [ ] 削除理由のドキュメント化

#### G. UI層の統一検討
- [ ] メインUIの決定
- [ ] 不要なUI層の廃止検討

---

## 📈 効果測定

### 定量的効果

| 項目 | 整理前 | 整理後（Phase 1） | 削減 |
|---|---|---|---|
| ルートレベルのファイル数 | 約30個 | 約19個 | -11個 |
| ストレージ使用量 | - | - | -13MB |
| ドキュメントの配置 | ルート8個、docs/30個 | ルート2個、docs/38個 | - |
| テストファイルの配置 | ルート2個、tests/3個 | tests/5個 | 統合 |

### 定性的効果

- **可読性向上**: ファイルが論理的に配置される
- **メンテナンス性向上**: どこに何があるか明確になる
- **新規開発者のオンボーディング**: プロジェクト構造が理解しやすくなる
- **ビルド・デプロイの効率化**: 不要ファイルが減り、処理が高速化

---

## ⚠️ 注意事項

### 実行前の確認

1. **バックアップの作成**
   ```bash
   # Gitコミット
   git add .
   git commit -m "整理前のバックアップ"
   ```

2. **ブランチの作成**
   ```bash
   git checkout -b cleanup/project-reorganization
   ```

3. **重要なファイルの確認**
   - 削除予定のファイルに依存関係がないか確認
   - 移動によりインポートパスが壊れないか確認

### インポートパスへの影響

**影響なし**: ルートレベルのスクリプトは直接実行されるため、移動してもインポートパスは変更不要

**例外**: もし他のファイルから直接インポートされている場合は修正が必要
```python
# 修正が必要な場合の例
# 修正前
from reprocess_classroom_documents_v2 import ClassroomReprocessorV2

# 修正後
from scripts.reprocess_classroom_documents_v2 import ClassroomReprocessorV2
```

### ロールバック手順

整理後に問題が発生した場合：
```bash
# ブランチを元に戻す
git checkout main

# または特定のコミットに戻す
git reset --hard <commit_hash>
```

---

## 🚀 実行手順

### Phase 1の実行（推奨: 一括実行）

```bash
# 1. バックアップ
git add .
git commit -m "整理前のバックアップ - Phase 1開始前"

# 2. ブランチ作成
git checkout -b cleanup/phase1-file-reorganization

# 3. A. ルートファイルの移動
git mv reprocess_classroom_documents_v2.py scripts/
git mv collect_codebase.py scripts/
git mv emergency_diagnose_and_fix.py scripts/one_time/
git mv migrate_to_chunks.py scripts/one_time/
git mv regenerate_all_embeddings.py scripts/one_time/
git mv regenerate_embeddings_simple.py scripts/one_time/
git mv test_table_parser.py tests/
git mv test_vision_extraction.py tests/
git mv fix_sql_function.sql database/schema_updates/
git mv start_email_ui.sh scripts/

# 4. B. 重複・不要ファイルの削除
rm project_codebase_20251202_105336.md
rm project_codebase_20251202_135845.md
rm project_codebase_20251210_094555.md
rm project_codebase_20251210_114701.md
rm project_codebase_20251210_134757.md
rm project_codebase_20251210_165546.md
rm project_codebase_20251211_112508.md
rm scripts/archive/migrate_to_chunks.py
rm requirements_full.txt
find . -name ".DS_Store" -delete
echo ".DS_Store" >> .gitignore

# 5. C. ドキュメントの整理
git mv DATABASE_CLEANUP_GUIDE.md docs/
git mv EMERGENCY_RESTORE_GUIDE.md docs/
git mv FILTER_FEATURE_GUIDE.md docs/
git mv IMPLEMENTATION_STEPS.md docs/
git mv METADATA_SEARCH_UPDATE.md docs/
git mv QUICK_START_FIXES.md docs/
mkdir -p docs/archive
git mv PROGRESS_LOG_20251212.md docs/archive/
git mv PROJECT_EVALUATION_REPORT_20251212.md docs/archive/

# 6. コミット
git add .
git commit -m "Phase 1: プロジェクト整理完了

- ルートファイルを適切なディレクトリに移動（11ファイル）
- 古いコードベース出力を削除（7ファイル、13MB削減）
- 重複ファイルと空ファイルを削除
- ドキュメントをdocs/に集約
- .DS_Storeを削除し.gitignoreに追加"

# 7. 動作確認
# 主要なスクリプトが正常に動作するか確認
python scripts/reprocess_classroom_documents_v2.py --dry-run
python -m pytest tests/

# 8. メインブランチにマージ
git checkout main
git merge cleanup/phase1-file-reorganization
```

---

## 📚 関連ドキュメント

- `docs/GAS_INTEGRATION_GUIDE.md` - GAS統合ガイド
- `docs/UNIFIED_PROCESSING_FLOW.md` - 統合処理フロー
- `docs/archive/PROJECT_EVALUATION_REPORT_20251212.md` - プロジェクト評価レポート
- `README.md` - プロジェクト概要

---

## 🎉 まとめ

### 整理の目的

1. **プロジェクト構造の明確化**: ファイルが論理的に配置される
2. **ストレージの最適化**: 不要ファイルの削除で13MB削減
3. **メンテナンス性の向上**: どこに何があるか一目瞭然
4. **新規開発者のオンボーディング**: プロジェクト理解が容易に

### 次のステップ

1. **Phase 1の承認と実行**（推奨: 今すぐ）
2. **Phase 2の実施**（1週間以内）
3. **Phase 3の検討**（必要に応じて）

---

**最終更新**: 2025-12-12
**作成者**: Claude Code (Sonnet 4.5)
**ステータス**: 承認待ち
