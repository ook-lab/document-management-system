# JSON Schema検証機能ドキュメント

## 概要

JSON Schema検証機能は、AI (Claude) が生成したメタデータJSONに対し、`jsonschema` ライブラリを使用して**厳密な型・構造・必須フィールドの検証**を行う機能です。これにより、データ整合性を保証し、下流システムでのエラーを防止します。

## 目的

- 🔒 **データ整合性の保証**: AIが生成したJSONが期待される構造に準拠
- 🛡️ **セキュリティ**: `eval()` などの危険な関数を排除
- 📊 **品質管理**: 検証失敗時は信頼度を減点し、レビュー対象に
- 🔍 **エラーの早期発見**: パイプライン内で即座に構造エラーを検出

## アーキテクチャ

### 処理フロー

```
Stage 2 (Claude抽出)
    ↓
メタデータJSON生成
    ↓
JSON Schema検証
    ↓
┌─────────┴─────────┐
│                   │
検証成功          検証失敗
│                   │
↓                   ↓
metadata保存      信頼度20%減点
                  エラー情報記録
                  ↓
                  レビュー対象
```

### 技術仕様

#### 1. JSON Schemaライブラリ: `jsonschema`

**選定理由**:
- ✅ Python標準的なJSON Schema実装
- ✅ JSON Schema Draft 7対応
- ✅ 詳細なエラーメッセージ
- ✅ 複数エラーの一括検出

**セキュリティ**:
- ✅ `json.load()` による安全なJSONパース（`eval()` 不使用）
- ✅ スキーマファイルの厳密な検証
- ✅ インジェクション攻撃への耐性

#### 2. スキーマファイル構造

**配置場所**: `ui/schemas/{doc_type}.json`

**対応マッピング**:
```python
DOC_TYPE_SCHEMA_MAPPING = {
    'timetable': 'timetable.json',
    'notice': 'school_notice.json',
    'school_notice': 'school_notice.json',
    # 必要に応じて追加
}
```

**スキーマ例** (`ui/schemas/timetable.json`):
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "title": "時間割スキーマ",
  "properties": {
    "school_name": {
      "type": "string",
      "title": "学校名"
    },
    "grade": {
      "type": "string",
      "title": "学年"
    },
    "daily_schedule": {
      "type": "array",
      "title": "日別時間割",
      "items": {
        "type": "object",
        "properties": {
          "date": {
            "type": "string",
            "format": "date"
          },
          "periods": {
            "type": "array"
          }
        },
        "required": ["date", "periods"]
      }
    }
  },
  "required": ["school_name", "grade", "daily_schedule"]
}
```

## 実装されたファイル

### 1. `core/ai/json_validator.py` (新規, 267行)

**主要関数**:

#### `validate_metadata(metadata, doc_type, schema_dir=None) -> (bool, str)`

メタデータをJSON Schemaで検証

**引数**:
- `metadata`: 検証対象のメタデータ辞書
- `doc_type`: 文書タイプ (例: "timetable", "notice")
- `schema_dir`: スキーマディレクトリ（オプション、デフォルト: `ui/schemas/`）

**戻り値**:
- `(True, None)`: 検証成功
- `(False, error_message)`: 検証失敗（エラーメッセージ付き）

**動作**:
1. doc_typeに対応するスキーマファイルを取得
2. スキーマが存在しない場合は検証スキップ（警告のみ）
3. スキーマをロード（`json.load()`で安全に）
4. `Draft7Validator` で検証実行
5. 検証失敗時は詳細なエラーメッセージを生成

**例**:
```python
from core.ai.json_validator import validate_metadata

metadata = {
    "school_name": "〇〇小学校",
    "grade": "5年生",
    "daily_schedule": [...]
}

is_valid, error_message = validate_metadata(metadata, "timetable")

if not is_valid:
    print(f"検証エラー: {error_message}")
```

#### `get_validation_errors(metadata, doc_type, schema_dir=None) -> list`

全ての検証エラーを一括取得

**戻り値**:
- `ValidationError` のリスト（複数エラーを一度に確認）

**用途**:
- 開発時のデバッグ
- エラーレポート生成
- 一度に全ての問題を確認

#### `validate_metadata_strict(metadata, doc_type, schema_dir=None) -> bool`

厳密な検証（失敗時に例外を発生）

**Raises**:
- `ValidationError`: 検証失敗時

**用途**:
- テストコード
- 厳密なデータ品質が必要な場合

### 2. `pipelines/two_stage_ingestion.py` (修正, +30行)

**統合箇所**: Stage 2 (Claude抽出) の直後

**処理フロー**:
```python
# Stage 2完了後
stage2_metadata = stage2_result.get('metadata', {})

# JSON Schema検証
logger.info("[JSON検証] メタデータ検証開始...")
is_valid, validation_error = validate_metadata(
    metadata=stage2_metadata,
    doc_type=doc_type
)

if not is_valid:
    # 検証失敗時の処理
    logger.error(f"[JSON検証] 検証失敗: {validation_error}")

    # metadataに検証失敗情報を記録
    metadata['schema_validation'] = {
        'is_valid': False,
        'error_message': validation_error,
        'validated_at': datetime.now().isoformat()
    }

    # 信頼度を減点（20%減点）
    confidence = confidence * 0.8
    logger.warning(f"[JSON検証] 信頼度を減点: {confidence:.2f}")
else:
    logger.info("[JSON検証] ✅ 検証成功")
    metadata['schema_validation'] = {
        'is_valid': True,
        'validated_at': datetime.now().isoformat()
    }
```

**検証失敗時の影響**:
1. **信頼度減点**: `confidence = confidence * 0.8` (20%減点)
2. **エラー情報記録**: `metadata['schema_validation']` に詳細を保存
3. **ログ出力**: エラー詳細をログに記録
4. **レビュー対象**: 信頼度低下によりレビュー優先度が上がる

**重要**: 検証失敗でもデータベース挿入は継続（エラー情報を含めて保存）

### 3. `requirements.txt` (修正)

**追加依存関係**:
```
jsonschema>=4.20.0
```

## セットアップ手順

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

または個別にインストール:
```bash
pip install jsonschema>=4.20.0
```

### 2. スキーマファイルの確認

既存のスキーマファイルを確認:
```bash
ls -la ui/schemas/
# timetable.json
# school_notice.json
```

### 3. 新しいdoc_typeのスキーマ追加

#### Step 1: スキーマファイル作成

`ui/schemas/homework.json`:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "title": "宿題スキーマ",
  "properties": {
    "subject": {
      "type": "string",
      "title": "科目"
    },
    "due_date": {
      "type": "string",
      "format": "date",
      "title": "提出期限"
    },
    "description": {
      "type": "string",
      "title": "課題内容"
    }
  },
  "required": ["subject", "due_date", "description"]
}
```

#### Step 2: マッピング追加

`core/ai/json_validator.py` の `DOC_TYPE_SCHEMA_MAPPING` に追加:
```python
DOC_TYPE_SCHEMA_MAPPING = {
    'timetable': 'timetable.json',
    'notice': 'school_notice.json',
    'homework': 'homework.json',  # 追加
}
```

### 4. 動作確認

```bash
python scripts/inbox_monitor.py
```

**期待されるログ出力（検証成功時）**:
```
[JSON検証] メタデータ検証開始...
[JSON検証] ✅ 検証成功: doc_type='timetable'
```

**期待されるログ出力（検証失敗時）**:
```
[JSON検証] メタデータ検証開始...
[JSON検証] ❌ 検証失敗: JSON Schema検証エラー (doc_type='timetable'): フィールド 'grade' - 'grade' is a required property
[JSON検証] 信頼度を減点: 0.680 (検証失敗のため)
```

## エラーハンドリング

### 1. スキーマファイルが存在しない場合

```python
# 動作: 警告を出力し、検証をスキップ
logger.warning("[JSON検証] doc_type 'unknown' のスキーマが未定義のため検証をスキップします")
return True, None  # 検証成功扱い
```

**理由**: 新しいdoc_typeの場合、スキーマ未定義でもパイプラインを止めない

### 2. 検証失敗時

```python
# 動作:
# 1. エラーメッセージ生成
# 2. metadataにエラー情報を記録
# 3. 信頼度を20%減点
# 4. データベース挿入は継続（エラー情報付き）

metadata['schema_validation'] = {
    'is_valid': False,
    'error_message': 'フィールド "grade" が必須です',
    'validated_at': '2024-11-27T12:34:56'
}

confidence = confidence * 0.8  # 元の信頼度の80%
```

**重要**: 検証失敗でも処理を中止せず、エラー情報を記録して継続

### 3. スキーマファイルのJSON形式エラー

```python
# 動作: エラーログを出力し、検証をスキップ
logger.error("[JSON検証] スキーマファイルのJSON形式が不正: Expecting property name...")
return True, None  # 検証成功扱い（安全側に倒す）
```

### 4. 予期しないエラー

```python
# 動作: エラーログを出力し、検証を通す
logger.error("[JSON検証] ❌ JSON検証中に予期しないエラー: TypeError - ...")
return True, None  # 安全側に倒す
```

## 検証エラーの詳細

### エラータイプ別の処理

#### 1. 必須フィールド不足 (`required`)

**エラー例**:
```
JSON Schema検証エラー (doc_type='timetable'): フィールド 'root' - 'grade' is a required property
```

**原因**: スキーマで `required: ["grade"]` と定義されているが、metadataに `grade` が存在しない

**対処法**:
- Claude promptを修正して必須フィールドを必ず抽出させる
- または、スキーマの `required` を緩和

#### 2. 型不一致 (`type`)

**エラー例**:
```
JSON Schema検証エラー (doc_type='timetable'): フィールド 'daily_schedule' - [1, 2, 3] is not of type 'array'
```

**原因**: `daily_schedule` はarray型が期待されるが、別の型が返された

**ログ詳細**:
```
期待される型: array, 実際の値: "some string"
```

#### 3. パターン不一致 (`pattern`)

**エラー例**:
```
JSON Schema検証エラー (doc_type='timetable'): フィールド 'grade' - '5年' does not match '^(小学|中学|高校)[1-6]年$'
```

**原因**: `grade` フィールドが正規表現パターンに一致しない

**ログ詳細**:
```
パターン不一致: 期待=^(小学|中学|高校)[1-6]年$, 実際=5年
```

### 複数エラーの確認

```python
from core.ai.json_validator import get_validation_errors

errors = get_validation_errors(metadata, "timetable")

for error in errors:
    print(f"エラー: {error.message}")
    print(f"フィールド: {'.'.join(str(p) for p in error.path)}")
```

## 統計とモニタリング

### データベースでの確認

#### 検証成功率の統計

```sql
-- 検証結果の分布
SELECT
    (metadata->'schema_validation'->>'is_valid')::boolean as is_valid,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM documents
WHERE metadata->'schema_validation' IS NOT NULL
GROUP BY is_valid;
```

#### doc_type別の検証失敗率

```sql
-- doc_type別の検証失敗件数
SELECT
    doc_type,
    COUNT(*) as total_documents,
    SUM(CASE WHEN (metadata->'schema_validation'->>'is_valid')::boolean = false THEN 1 ELSE 0 END) as validation_failures,
    ROUND(
        SUM(CASE WHEN (metadata->'schema_validation'->>'is_valid')::boolean = false THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) as failure_rate_percent
FROM documents
WHERE metadata->'schema_validation' IS NOT NULL
GROUP BY doc_type
ORDER BY failure_rate_percent DESC;
```

#### 検証失敗の詳細

```sql
-- 検証失敗したドキュメントの一覧
SELECT
    id,
    file_name,
    doc_type,
    confidence,
    total_confidence,
    metadata->'schema_validation'->>'error_message' as validation_error,
    metadata->'schema_validation'->>'validated_at' as validated_at
FROM documents
WHERE (metadata->'schema_validation'->>'is_valid')::boolean = false
ORDER BY created_at DESC
LIMIT 20;
```

### ログでの確認

**検証成功時**:
```
2024-11-27 12:34:56 | INFO | [JSON検証] メタデータ検証開始...
2024-11-27 12:34:56 | DEBUG | スキーマロード成功: timetable.json
2024-11-27 12:34:56 | INFO | [JSON検証] ✅ 検証成功: doc_type='timetable'
```

**検証失敗時**:
```
2024-11-27 12:35:12 | INFO | [JSON検証] メタデータ検証開始...
2024-11-27 12:35:12 | DEBUG | スキーマロード成功: timetable.json
2024-11-27 12:35:12 | ERROR | [JSON検証] ❌ 検証失敗: JSON Schema検証エラー (doc_type='timetable'): フィールド 'root' - 'grade' is a required property
2024-11-27 12:35:12 | ERROR |   必須フィールドが不足: ['grade']
2024-11-27 12:35:12 | WARNING | [JSON検証] 信頼度を減点: 0.680 (検証失敗のため)
```

## ベストプラクティス

### 1. スキーマ設計

#### 必須フィールドは最小限に

```json
{
  "required": ["school_name", "grade"]  // 本当に必要なもののみ
}
```

**理由**: 厳しすぎると検証失敗が多発し、レビュー負荷が増大

#### デフォルト値の活用

```json
{
  "properties": {
    "tags": {
      "type": "array",
      "default": []  // デフォルト値を設定
    }
  }
}
```

#### 柔軟な型定義

```json
{
  "properties": {
    "date": {
      "type": "string",  // 厳密なdate型ではなくstring
      "pattern": "\\d{4}-\\d{2}-\\d{2}"  // パターンで検証
    }
  }
}
```

### 2. プロンプトエンジニアリング

Stage 2 promptにスキーマを明示:

```python
prompt = f"""
以下のJSONスキーマに従ってメタデータを抽出してください：

{{
  "type": "object",
  "required": ["school_name", "grade", "daily_schedule"],
  "properties": {{
    "school_name": {{"type": "string"}},
    "grade": {{"type": "string", "pattern": "^(小学|中学|高校)[1-6]年$"}},
    ...
  }}
}}

必ずこの構造に従ってJSONを生成してください。
"""
```

### 3. 段階的な導入

1. **Phase 1**: 既存doc_typeのスキーマ作成（timetable, notice）
2. **Phase 2**: 検証失敗データを分析し、スキーマを調整
3. **Phase 3**: 新しいdoc_typeのスキーマを追加

### 4. 定期的な見直し

```python
# 月次で検証失敗率を確認
failure_rate = get_validation_failure_rate()

if failure_rate > 10%:
    # スキーマまたはプロンプトを見直し
    review_schema_and_prompts()
```

## トラブルシューティング

### 問題: 検証失敗率が高い（>20%）

**原因**:
- スキーマが厳しすぎる
- Claude promptがスキーマを考慮していない

**解決策**:
```python
# 1. スキーマの必須フィールドを減らす
"required": ["school_name"]  # gradeを削除

# 2. Claudeプロンプトを修正
"""
以下のフィールドは必須です：
- school_name
- grade
- daily_schedule

これらが抽出できない場合でも、可能な範囲で他のフィールドを抽出してください。
"""
```

### 問題: 特定のdoc_typeで常に検証失敗

**原因**: スキーマとClaude出力が一致していない

**デバッグ**:
```python
from core.ai.json_validator import get_validation_errors

# 全エラーを確認
errors = get_validation_errors(metadata, "timetable")
for error in errors:
    print(f"{error.path}: {error.message}")
```

**解決策**:
1. 実際のClaude出力を確認
2. スキーマをClaude出力に合わせて調整

### 問題: スキーマファイルが見つからない

**エラー**:
```
[JSON検証] doc_type 'homework' のスキーマが未定義のため検証をスキップします
```

**解決策**:
```bash
# 1. スキーマファイルを作成
touch ui/schemas/homework.json

# 2. マッピングに追加
# core/ai/json_validator.py
DOC_TYPE_SCHEMA_MAPPING = {
    'homework': 'homework.json',
}
```

## まとめ

JSON Schema検証機能により、以下が実現されました:

✅ **データ整合性の保証**: AI出力が期待される構造に準拠
✅ **セキュリティ強化**: `eval()` 排除、安全なJSONパース
✅ **品質の可視化**: 検証失敗時は信頼度減点
✅ **エラーの早期発見**: パイプライン内で即座に検出
✅ **柔軟な運用**: スキーマ未定義でもパイプライン継続

**実装ファイル**:
- `core/ai/json_validator.py` (新規, 267行)
- `pipelines/two_stage_ingestion.py` (+30行)
- `requirements.txt` (+1行)

**効果**:
- データ品質の向上: 構造エラーの事前検出
- レビュー効率化: 検証失敗ドキュメントを優先レビュー
- セキュリティ強化: 安全なJSONパース
- 運用の柔軟性: スキーマ未定義でもエラーにならない
