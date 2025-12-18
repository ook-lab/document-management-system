# A_common/config ファイル整理分析

## 📊 使用状況サマリー

| ファイル | 使用状況 | 判定 |
|---------|---------|------|
| `user_context.yaml` | ✅ **使用中** | **保持** |
| `user_context.yaml.example` | ✅ サンプル | **保持** |
| `yaml_loader.py` | ✅ **使用中** | **保持** |
| `settings.py` | ✅ **使用中** | **保持** |
| `model_tiers.py` | ⚠️ **一部使用** | **要確認** |
| `workspaces.py` | ⚠️ **一部使用** | **要確認** |
| `CLASSIFICATION_MAPPING_v2.0.yaml` | ❌ 未使用 | **削除候補** |
| `DOC_TYPE_CONSTANTS.py` | ❌ 未使用 | **削除候補** |

---

## ✅ 保持すべきファイル

### 1. `user_context.yaml` ✅
**使用箇所:**
- `G_cloud_run/app.py` - Cloud Run アプリ
- `A_common/config/workspaces.py` - Workspace管理
- **手修正済み** - ユーザーが直接編集している

**理由:** システム全体の家族情報・ワークスペース設定の中核

---

### 2. `yaml_loader.py` ✅
**使用箇所:**
- `process_queued_documents.py` - `get_classification_yaml_string()`
- `A_common/config/workspaces.py` - `load_user_context()`, `get_family_info()`
- `G_cloud_run/app.py` - `load_user_context()`

**理由:** user_context.yaml を読み込むための必須ユーティリティ

---

### 3. `settings.py` ✅
**使用箇所:**
- `C_ai_common/embeddings/embeddings.py` - `settings`
- `C_ai_common/llm_client/llm_client.py` - `settings`
- `A_common/database/client.py` - `settings`

**理由:** API キー、Supabase接続情報などの環境変数管理

---

## ⚠️ 要確認ファイル

### 4. `model_tiers.py` ⚠️
**使用箇所:**
- `C_ai_common/llm_client/llm_client.py` - `AIProvider`, `get_model_config()`
- `G_cloud_run/app.py` - `ResearchFlow`
- `tests/test_llm_client_retry.py` - テストコード

**現状:**
- Stage A/B/C の旧パイプライン用のモデル定義
- **G_unified_pipeline では config/models.yaml を使用**

**判定:**
- ✅ `AIProvider` enum は LLMClient で使用中 → **保持**
- ❌ 旧パイプライン用の定義は削除可能
- → **リファクタリング推奨**（AIProvider のみ残す）

---

### 5. `workspaces.py` ⚠️
**使用箇所:**
- 直接的なimportは見つからず
- `user_context.yaml` から動的生成する仕組み

**現状:**
- **G_unified_pipeline では source_documents_routing.yaml を使用**
- 旧システムとの互換性のために残っている可能性

**判定:**
- ❌ 使用されていない → **削除候補**
- または、今後 G_cloud_run で使う予定があれば保持

---

## ❌ 削除候補ファイル

### 6. `CLASSIFICATION_MAPPING_v2.0.yaml` ❌
**使用箇所:** **なし**

**内容:**
- 旧文書分類システムのマッピング定義
- 50種類の doc_type 定義（Phase 2 設計）
- JSON Schema 定義

**現状:**
- **G_unified_pipeline の source_documents_routing.yaml に置き換え済み**
- 旧 Stage A/B/C パイプライン用

**判定:** **削除推奨** ✅

---

### 7. `DOC_TYPE_CONSTANTS.py` ❌
**使用箇所:** **なし**

**内容:**
- 50種類の doc_type 定数定義
- フォルダ分類体系（ikuya_school, work など）
- メタデータ辞書

**現状:**
- **G_unified_pipeline の source_documents_routing.yaml に置き換え済み**
- 旧 Stage A/B/C パイプライン用

**判定:** **削除推奨** ✅

---

## 🎯 推奨アクション

### 即座に削除可能
1. ✅ `CLASSIFICATION_MAPPING_v2.0.yaml` - 完全に未使用
2. ✅ `DOC_TYPE_CONSTANTS.py` - 完全に未使用

### リファクタリング推奨
3. ⚠️ `model_tiers.py`
   - `AIProvider` enum のみ抽出して新ファイルに移動
   - 旧パイプライン用の定義を削除
   - または、G_unified_pipeline/config/models.yaml に統合

### 要判断
4. ⚠️ `workspaces.py`
   - G_cloud_run で使用予定があるか確認
   - なければ削除

---

## 📁 整理後の理想的な構成

```
A_common/config/
├── __init__.py
├── settings.py              # ✅ 環境変数管理
├── yaml_loader.py           # ✅ YAML読み込みユーティリティ
├── user_context.yaml        # ✅ 家族情報・ワークスペース設定
├── user_context.yaml.example # ✅ サンプル
└── enums.py                 # 新規: AIProvider などの enum定義
```

---

## 🔄 移行パス

### Step 1: 即座に削除
```bash
rm A_common/config/CLASSIFICATION_MAPPING_v2.0.yaml
rm A_common/config/DOC_TYPE_CONSTANTS.py
```

### Step 2: model_tiers.py のリファクタリング
1. `AIProvider` enum を `A_common/config/enums.py` に移動
2. `C_ai_common/llm_client/llm_client.py` の import を更新
3. `model_tiers.py` を削除

### Step 3: workspaces.py の判断
- G_cloud_run で使用予定があるか確認
- なければ削除

---

## 🚨 削除前の確認事項

- [ ] CLASSIFICATION_MAPPING_v2.0.yaml を参照しているコードがないことを確認
- [ ] DOC_TYPE_CONSTANTS.py を参照しているコードがないことを確認
- [ ] model_tiers.py の AIProvider が他で使われていることを確認
- [ ] workspaces.py が本当に不要か確認
