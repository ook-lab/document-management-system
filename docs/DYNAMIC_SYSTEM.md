# 動的システムへの移行ガイド

## 概要

**v2.0の重要な変更**: システムは完全に動的になりました。

これまでの硬直的な制約を排除し、成長段階のプロジェクトに最適化しました。

## 変更内容

### Before（v1.x - 硬直的）

```python
# ❌ workspaceは定義済みのものだけ
if workspace not in Workspace.all_workspaces():
    raise ValueError(f"Invalid workspace: {workspace}")

# ❌ doc_typeはYAMLスキーマに定義されているもののみ
if doc_type not in defined_schemas:
    raise ValidationError(f"Unknown doc_type: {doc_type}")

# ❌ スキーマ検証が必須
is_valid, errors = validate_metadata(schema, metadata)
if not is_valid:
    raise ValidationError(errors)  # 処理中断
```

### After（v2.0 - 動的）

```python
# ✅ どんなworkspaceでも受け入れ
workspace = doc.get('workspace', 'unknown')
# そのままデータベースに保存

# ✅ どんなdoc_typeでも受け入れ
doc_type = stage1_result.get('doc_type', 'other')
# そのままデータベースに保存

# ✅ スキーマ検証は警告のみ
is_valid, errors = validate_metadata(schema, metadata)
if not is_valid:
    logger.warning(f"スキーマ検証失敗: {errors}")
    confidence *= 0.8  # 信頼度を減点
# 処理は継続
```

## メリット

### 1. 柔軟性

- 新しいworkspaceを追加する際、コード変更不要
- 新しいdoc_typeを追加する際、YAML編集不要
- Google Classroomなどの外部ソースから来たデータをそのまま受け入れ

### 2. 成長性

- データベースに存在する値を基準にする
- UIは実際のデータから選択肢を自動生成
- 定義ファイルとDBの同期を気にする必要がない

### 3. エラー回避

- 未定義のworkspace/doc_typeでシステムが停止しない
- スキーマ検証失敗でも処理を継続
- 部分的なデータでも保存される

## 実装詳細

### 1. DatabaseClient - 動的取得メソッド

```python
# workspace一覧を動的に取得
def get_available_workspaces(self) -> List[str]:
    response = self.client.table('documents').select('workspace').execute()
    workspaces = {doc.get('workspace') for doc in response.data if doc.get('workspace')}
    return sorted(list(workspaces))

# doc_type一覧を動的に取得
def get_available_doc_types(self) -> List[str]:
    response = self.client.table('documents').select('doc_type').execute()
    doc_types = {doc.get('doc_type') for doc in response.data if doc.get('doc_type')}
    return sorted(list(doc_types))
```

### 2. UI - 動的な選択肢生成

```python
# review_ui.py
# workspaceの選択肢をSupabaseから動的に取得
available_workspaces = db_client.get_available_workspaces()
workspace_options = ["全て"] + available_workspaces

workspace_filter = st.sidebar.selectbox(
    "Workspace",
    options=workspace_options,  # 動的
    index=0
)
```

### 3. パイプライン - 既存値を尊重

```python
# reprocess_classroom_documents.py
# デフォルトで既存のworkspaceを保持
existing_workspace = doc.get('workspace', 'unknown')

if preserve_workspace:
    workspace_to_use = existing_workspace  # そのまま使う
else:
    workspace_to_use = "unknown"  # AIに判定させる

result = await pipeline.process_file(
    file_meta=file_meta,
    workspace=workspace_to_use
)
```

## 移行ガイド

### 既存のコードへの影響

**影響なし**: 既存のコードはそのまま動作します。

- `config/workspaces.py`は依然として使用可能（Gmail Ingestionで使用中）
- YAMLスキーマも依然として有効（Stage2抽出で使用）
- 検証は継続されますが、失敗しても処理は止まりません

### 新しいworkspace/doc_typeを追加する方法

**方法1: 直接DBに保存**（推奨）

```python
# 新しいworkspaceで保存
db.save_document(
    ...,
    workspace="new_workspace_name"  # 自由に指定
)
```

**方法2: config/workspaces.pyに定義**（オプション）

```python
# config/workspaces.py
class Workspace:
    NEW_WORKSPACE = "new_workspace_name"
```

どちらでもOKです。定義しなくても動作します。

### YAMLスキーマの位置づけ

**推奨事項（ベストプラクティス）**:

- YAMLスキーマは「理想的な構造の定義」として維持
- 検証失敗は「品質の低さ」を示すシグナル
- 強制ではなく、ガイドライン

**検証失敗時の動作**:

```python
if not is_valid:
    # ❌ 処理を中断しない
    # ✅ 警告ログを出す
    logger.warning(f"スキーマ検証失敗: {errors}")

    # ✅ 信頼度を減点
    confidence *= 0.8

    # ✅ メタデータに検証結果を記録
    metadata['schema_validation'] = {
        'is_valid': False,
        'error_message': errors
    }

    # ✅ 処理は継続
```

## 使用例

### Google Classroomからの取り込み

```python
# workspaceとdoc_typeは何でもOK
db.save_document(
    file_name="学年通信（30）.pdf",
    workspace="ikuya_classroom",  # config/workspaces.pyに存在しなくてもOK
    doc_type="2025_5B",  # YAMLスキーマに存在しなくてもOK
    metadata={...}  # スキーマに合わなくてもOK（信頼度減点のみ）
)
```

### 動的UIの実装

```python
# Streamlit UI
# 実際のデータから選択肢を生成
workspaces = db.get_available_workspaces()
# 結果: ["ikuya_classroom", "IKUYA_SCHOOL", "BUSINESS_WORK", ...]

doc_types = db.get_available_doc_types()
# 結果: ["2025_5B", "school_newsletter", "exam_info", ...]

# ユーザーはこれらから選択
```

## まとめ

### キーポイント

1. **workspace/doc_typeは自由**: どんな値でも受け入れる
2. **スキーマは推奨**: 検証は行うが、失敗しても継続
3. **UIは動的**: Supabaseから実際のデータを取得
4. **既存値を尊重**: デフォルトで既存のworkspace/doc_typeを保持
5. **後方互換性**: 既存のコードはそのまま動作

### 開発者へのメッセージ

**自由に追加してください**:

- 新しいworkspaceが必要？ → 直接使ってOK
- 新しいdoc_typeが必要？ → 直接使ってOK
- スキーマ定義が間に合わない？ → 後で追加すればOK

**システムは成長と共に進化します**。
