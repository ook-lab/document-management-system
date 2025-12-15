# 表構造抽出 (Table Structure Extraction)

**Phase 2 - Track 2 - Task 2.2.2**
**実装日**: 2024-11-28
**バージョン**: v1.0

## 概要

PDFから抽出されたテキスト内の**複雑な表構造**を、編集・検索可能なJSON形式で忠実に再現する機能を実装しました。

時間割のセル結合、議事録の議題グループ化、クラス別授業スケジュールなど、複雑な表形式のデータを構造化して抽出します。

## 目的

- **検索性の向上**: 表内のデータを構造化し、特定の情報を高速に検索可能にする
- **編集可能性**: JSON形式で抽出することで、後からの編集・加工を容易にする
- **忠実な再現**: セル結合（rowspan/colspan）や階層構造を含む複雑な表を正確に再現する
- **データ分析**: 抽出された構造化データを分析・可視化に活用可能にする

## 実装内容

### 1. 表構造抽出プロンプトテンプレート (`core/ai/prompts/table_extraction_v1.md`)

470行の詳細なプロンプトテンプレートを作成しました。

#### 主要機能

**表の検出**:
- 列区切り・行区切りのパターン認識
- ヘッダー行とデータ行の識別
- 表形式データの自動検出

**セル結合の処理**:
- **縦方向の結合 (rowspan)**: 同じ値が連続する行にまたがる場合
- **横方向の結合 (colspan)**: 1つのセルが複数列にまたがる場合
- セル結合情報をJSON形式で明示的に記録

**データ正規化ルール**:
```json
// ❌ 誤り: 分解しすぎ
{"periods": ["1限", "2限"], "subject": "体育"}

// ✅ 正解: 原文を保持
{"period_range": "1-2限", "subject": "体育"}
```

#### doc_type別の表構造定義

1. **timetable (時間割)**
   - `daily_schedule`: 日別時間割
   - `class_timetable`: クラス別時間割

2. **notice (お知らせ)**
   - `weekly_schedule`: 週間予定表
   - `class_schedule`: クラス別授業スケジュール

3. **meeting_minutes (議事録)**
   - `agenda_table`: 議題表
   - `action_items_table`: アクションアイテム表

4. **invoice (請求書)**
   - `line_items`: 明細表

### 2. Stage 2 抽出器の修正 (`core/ai/stage2_extractor.py`)

#### 追加機能

**テンプレート読み込み**:
```python
def _load_table_extraction_template(self) -> str:
    """表構造抽出プロンプトテンプレートをロード"""
    template_path = Path(__file__).parent / "prompts" / "table_extraction_v1.md"

    if not template_path.exists():
        logger.warning(f"表抽出テンプレートが見つかりません: {template_path}")
        return ""

    with open(template_path, 'r', encoding='utf-8') as f:
        self._table_extraction_template = f.read()

    return self._table_extraction_template
```

**プロンプトへの統合**:
```python
# 表構造抽出テンプレートをロード (Phase 2.2.2)
table_extraction_guidelines = self._load_table_extraction_template()

prompt = f"""
# 表構造抽出ガイドライン (Phase 2.2.2)
{table_extraction_guidelines}
"""
```

**出力形式の拡張**:
```json
{
  "doc_type": "timetable",
  "summary": "文書の要約",
  "document_date": "2024-11-18",
  "tags": ["tag1", "tag2"],
  "metadata": {
    // doc_typeに応じたカスタムフィールド
  },
  "tables": [
    {
      "table_type": "daily_schedule",
      "headers": ["日付", "曜日", "1限", "2限"],
      "rows": [...]
    }
  ],
  "extraction_confidence": 0.95
}
```

**JSON抽出の改善**:
```python
# Phase 2.2.2: 表構造対応
if "tables" not in result:
    result["tables"] = []
```

**フォールバック結果の更新**:
```python
return {
    "doc_type": doc_type,
    "summary": summary,
    "tables": [],  # Phase 2.2.2
    "extraction_confidence": 0.2,
    ...
}
```

## 使用例

### 1. クラス別時間割の抽出

**元の表**:
```
       5A        5B        5C
月  国語      算数      理科
    算数      国語      算数
    理科      理科      国語
```

**抽出結果**:
```json
{
  "tables": [
    {
      "table_type": "class_timetable",
      "headers": {
        "classes": ["5A", "5B", "5C"]
      },
      "daily_schedule": [
        {
          "day": "月",
          "class_schedules": [
            {
              "class": "5A",
              "periods": [
                {"period": 1, "subject": "国語"},
                {"period": 2, "subject": "算数"},
                {"period": 3, "subject": "理科"}
              ]
            },
            {
              "class": "5B",
              "periods": [
                {"period": 1, "subject": "算数"},
                {"period": 2, "subject": "国語"},
                {"period": 3, "subject": "理科"}
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

### 2. 議事録の議題グループ化

**元の表**:
```
議題      決定事項                 担当者    期限
予算      承認                     田中      -
          来期予算案作成           佐藤      11/30

採用      新規採用2名決定          山田      12/15
```

**抽出結果**:
```json
{
  "tables": [
    {
      "table_type": "agenda_table",
      "headers": ["議題", "決定事項", "担当者", "期限"],
      "agenda_groups": [
        {
          "topic": "予算",
          "items": [
            {
              "decision": "承認",
              "assignee": "田中",
              "deadline": null
            },
            {
              "decision": "来期予算案作成",
              "assignee": "佐藤",
              "deadline": "2024-11-30"
            }
          ]
        },
        {
          "topic": "採用",
          "items": [
            {
              "decision": "新規採用2名決定",
              "assignee": "山田",
              "deadline": "2024-12-15"
            }
          ]
        }
      ]
    }
  ]
}
```

### 3. セル結合の処理

**縦方向の結合 (rowspan)**:
```json
{
  "cells": [
    {"value": "予算", "rowspan": 2},
    {"value": "田中", "rowspan": 1}
  ]
}
```

**横方向の結合 (colspan)**:
```json
{
  "cells": [
    {"value": "体育", "colspan": 2, "description": "1-2限"}
  ]
}
```

## JSON Schema検証との連携

抽出された `tables` フィールドは、JSON Schema検証（Phase 2.1.2で実装済み）で検証可能です。

**スキーマ例** (`ui/schemas/timetable_tables.json`):
```json
{
  "properties": {
    "tables": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "table_type": {"type": "string"},
          "headers": {"type": "array"},
          "rows": {"type": "array"}
        },
        "required": ["table_type", "rows"]
      }
    }
  }
}
```

## データフロー

```
┌─────────────────────┐
│  PDF Document       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Text Extraction    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│  Stage 1: Document Classification       │
│  (Gemini 2.5 Flash)                     │
└──────────┬──────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│  Stage 2: Metadata Extraction           │
│  (Claude 4.5 Sonnet)                    │
│                                          │
│  1. Load table_extraction_v1.md         │
│  2. Build extraction prompt             │
│  3. Call Claude API                     │
│  4. Parse JSON response                 │
│     - metadata: カスタムフィールド       │
│     - tables: 表構造データ              │
└──────────┬──────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│  JSON Schema Validation                 │
│  (Phase 2.1.2)                          │
│                                          │
│  - Validate metadata structure          │
│  - Validate tables structure (optional) │
└──────────┬──────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│  Database Storage                       │
│  - metadata: JSONB                      │
│  - tables: 含まれる                     │
└─────────────────────────────────────────┘
```

## 重要な注意事項

### ✅ すべきこと

1. **原文を尊重**: 文書に書かれている通りに抽出
2. **構造を明示**: JSON形式でセル結合・グループ化を表現
3. **型を指定**: 日付・数値・文字列などの型情報を付与
4. **説明を追加**: table_typeやdescriptionで表の用途を明示

### ❌ してはいけないこと

1. **推測**: 記載されていない情報を補完しない
2. **分解**: "1-2限" を "1限", "2限" に分けない
3. **省略**: セル結合や空セルを無視しない
4. **変更**: 元のデータ形式を勝手に変えない

## ファイル構成

```
core/ai/
├── prompts/
│   └── table_extraction_v1.md      # 表構造抽出プロンプトテンプレート (新規)
├── stage2_extractor.py             # Stage 2抽出器 (修正)
└── llm_client.py

ui/schemas/
├── timetable.json                  # 時間割スキーマ (既存)
└── school_notice.json              # 学校通知スキーマ (既存)

docs/
├── TABLE_STRUCTURE_EXTRACTION.md   # 本ドキュメント (新規)
├── JSON_SCHEMA_VALIDATION.md       # Phase 2.1.2
└── 50_DOC_TYPE_CLASSIFICATION.md   # Phase 2.2.1
```

## 技術的な実装の詳細

### キャッシング

テンプレートファイルは初回読み込み時にキャッシュされ、2回目以降は再読み込みしません:

```python
self._table_extraction_template = None  # 初期化

if self._table_extraction_template is not None:
    return self._table_extraction_template  # キャッシュから返す
```

### エラーハンドリング

テンプレートファイルが見つからない場合でも、処理は継続します:

```python
if not template_path.exists():
    logger.warning(f"表抽出テンプレートが見つかりません: {template_path}")
    return ""  # 空文字列を返して処理継続
```

### JSON解析の堅牢性

`tables` フィールドが存在しない場合、空のリストを自動で設定します:

```python
if "tables" not in result:
    result["tables"] = []
```

## 今後の拡張予定

1. **表構造専用のJSON Schema定義**
   - `ui/schemas/tables/` ディレクトリを作成
   - 各doc_typeに対応する表構造スキーマを定義

2. **表データの検索機能強化**
   - PostgreSQLのJSONB演算子を活用した高速検索
   - 表内の特定セル値での絞り込み

3. **表データの可視化**
   - Review UIで表データをテーブル形式で表示
   - CSVエクスポート機能

4. **複雑な表構造の対応拡張**
   - 入れ子構造の表
   - マージされたヘッダー行
   - 複数ページにまたがる表

## 関連ドキュメント

- [JSON Schema検証](./JSON_SCHEMA_VALIDATION.md) - Phase 2.1.2
- [50種類の書類タイプ分類](./50_DOC_TYPE_CLASSIFICATION.md) - Phase 2.2.1
- [プログレストラッカー](./PROGRESS_TRACKER.md) - 全体の進捗管理

## バージョン履歴

- **v1.0** (2024-11-28): 初版リリース
  - 基本的な表構造抽出
  - セル結合対応 (rowspan/colspan)
  - doc_type別の表定義
  - Stage 2抽出器への統合
