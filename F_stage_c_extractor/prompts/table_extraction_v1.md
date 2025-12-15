# 表構造抽出 プロンプトテンプレート v1.0

## 目的

PDFから抽出されたテキスト内の**複雑な表構造**（時間割のセル結合、議事録の議題グループ化など）を、編集・検索可能なJSON形式で忠実に再現します。

## 表構造抽出の基本原則

### 1. 表の検出

文書内に以下のパターンがあれば表として認識してください:

- **列区切り**: 空白またはタブで区切られた複数の列
- **行区切り**: 改行で区切られた複数の行
- **ヘッダー行**: 1行目または最初の数行が見出し
- **データ行**: ヘッダー以降が実際のデータ

**例**:
```
日付    曜日   1限      2限      3限
11/18   月     国語     算数     理科
11/19   火     算数     国語     社会
```

### 2. セル結合の処理

#### 縦方向の結合 (rowspan)

同じ値が連続する行にまたがる場合、結合されているとみなします。

**元の表**:
```
議題      担当者    期限
予算      田中      11/30
予算      佐藤      11/30
採用      山田      12/15
```

**JSON表現**:
```json
{
  "tables": [
    {
      "table_type": "grouped_data",
      "headers": ["議題", "担当者", "期限"],
      "rows": [
        {
          "cells": [
            {"value": "予算", "rowspan": 2},
            {"value": "田中", "rowspan": 1},
            {"value": "11/30", "rowspan": 1}
          ]
        },
        {
          "cells": [
            {"value": "予算", "merged": true},  // 上のセルに結合
            {"value": "佐藤", "rowspan": 1},
            {"value": "11/30", "rowspan": 1}
          ]
        },
        {
          "cells": [
            {"value": "採用", "rowspan": 1},
            {"value": "山田", "rowspan": 1},
            {"value": "12/15", "rowspan": 1}
          ]
        }
      ]
    }
  ]
}
```

#### 横方向の結合 (colspan)

1つのセルが複数列にまたがる場合。

**元の表**:
```
日付           1-2限        3-4限
11/18 (月)     体育          国語
```

**JSON表現**:
```json
{
  "cells": [
    {"value": "11/18 (月)", "colspan": 1},
    {"value": "体育", "colspan": 2, "description": "1-2限"},
    {"value": "国語", "colspan": 2, "description": "3-4限"}
  ]
}
```

### 3. データの正規化ルール

#### ❌ 誤り: 分解しすぎ

```json
// 間違い: "1-2限" を分解してしまう
{"periods": ["1限", "2限"], "subject": "体育"}
```

#### ✅ 正解: 原文を保持

```json
// 正しい: 原文のまま保持
{"period_range": "1-2限", "subject": "体育"}
```

#### データ正規化の基本ルール

1. **原文尊重**: 文書に記載されている通りに抽出
2. **構造化**: JSON形式で構造を明示
3. **メタデータ付与**: 必要に応じて説明を追加

### 4. 複雑な表の例: クラス別時間割

**元の表** (学級通信など):
```
       5A        5B        5C
月  国語      算数      理科
    算数      国語      算数
    理科      理科      国語

火  社会      音楽      体育
    音楽      体育      社会
```

**JSON表現**:
```json
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
        },
        {
          "class": "5C",
          "periods": [
            {"period": 1, "subject": "理科"},
            {"period": 2, "subject": "算数"},
            {"period": 3, "subject": "国語"}
          ]
        }
      ]
    },
    {
      "day": "火",
      "class_schedules": [
        {
          "class": "5A",
          "periods": [
            {"period": 1, "subject": "社会"},
            {"period": 2, "subject": "音楽"}
          ]
        },
        {
          "class": "5B",
          "periods": [
            {"period": 1, "subject": "音楽"},
            {"period": 2, "subject": "体育"}
          ]
        },
        {
          "class": "5C",
          "periods": [
            {"period": 1, "subject": "体育"},
            {"period": 2, "subject": "社会"}
          ]
        }
      ]
    }
  ]
}
```

### 5. 議事録の表: 議題グループ化

**元の表**:
```
議題           決定事項                    担当者    期限
予算           承認                        田中      -
               来期予算案作成              佐藤      11/30

採用           新規採用2名決定              山田      12/15
               面接スケジュール作成         鈴木      11/25
```

**JSON表現**:
```json
{
  "table_type": "meeting_agenda",
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
          "deadline": "11/30"
        }
      ]
    },
    {
      "topic": "採用",
      "items": [
        {
          "decision": "新規採用2名決定",
          "assignee": "山田",
          "deadline": "12/15"
        },
        {
          "decision": "面接スケジュール作成",
          "assignee": "鈴木",
          "deadline": "11/25"
        }
      ]
    }
  ]
}
```

## 抽出プロンプトへの組み込み方

### メタデータ出力に `tables` フィールドを追加

```json
{
  "doc_type": "timetable",
  "summary": "...",
  "metadata": {
    "school_name": "〇〇小学校",
    "grade": "5年生",
    // 通常のメタデータ
    ...
  },
  "tables": [
    {
      "table_id": "main_timetable",
      "table_type": "daily_schedule",
      "description": "週間授業時間割",
      "headers": ["日付", "曜日", "1限", "2限", "3限", "4限"],
      "rows": [
        {
          "cells": [
            {"value": "11/18", "type": "date"},
            {"value": "月", "type": "day"},
            {"value": "国語", "type": "subject"},
            {"value": "算数", "type": "subject"},
            {"value": "理科", "type": "subject"},
            {"value": "体育", "type": "subject"}
          ]
        },
        ...
      ]
    }
  ]
}
```

## doc_type別の表構造定義

### 1. timetable (時間割)

**表の種類**: `daily_schedule`, `class_timetable`

**構造**:
```json
{
  "tables": [
    {
      "table_type": "daily_schedule",
      "headers": ["日付", "曜日", "時限1", "時限2", ...],
      "rows": [
        {
          "date": "11/18",
          "day": "月",
          "periods": [
            {"period": 1, "subject": "国語", "time": "8:45-9:30"},
            {"period": 2, "subject": "算数", "time": "9:40-10:25"}
          ]
        }
      ]
    }
  ]
}
```

### 2. notice (お知らせ) - 週間予定表

**表の種類**: `weekly_schedule`, `class_schedule`

**構造**:
```json
{
  "tables": [
    {
      "table_type": "weekly_schedule",
      "description": "週間行事予定",
      "rows": [
        {
          "date": "11/18",
          "day": "月",
          "events": ["朝会", "清掃"],
          "class_schedules": [
            {"class": "5A", "subjects": ["国語", "算数", "理科"]},
            {"class": "5B", "subjects": ["算数", "国語", "理科"]}
          ]
        }
      ]
    }
  ]
}
```

### 3. meeting_minutes (議事録)

**表の種類**: `agenda_table`, `action_items_table`

**構造**:
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
              "deadline": "2024-11-30"
            }
          ]
        }
      ]
    }
  ]
}
```

### 4. invoice (請求書) - 明細表

**表の種類**: `line_items`

**構造**:
```json
{
  "tables": [
    {
      "table_type": "line_items",
      "headers": ["項目", "数量", "単価", "金額"],
      "rows": [
        {
          "item": "商品A",
          "quantity": 2,
          "unit_price": 1000,
          "amount": 2000
        }
      ],
      "summary": {
        "subtotal": 2000,
        "tax": 200,
        "total": 2200
      }
    }
  ]
}
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

## JSON Schema検証との連携

抽出された `tables` フィールドは、JSON Schema検証（2.1.2で実装済み）で検証可能です。

**スキーマ例** (timetable.json):
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

## 使用例

### プロンプトへの組み込み

```
あなたは文書分析の専門家です。以下の文書から表構造を忠実に抽出してください。

# 表構造抽出のガイドライン
{table_extraction_v1.mdの内容をここに挿入}

# タスク
1. 文書内の全ての表を検出
2. 各表の構造（ヘッダー、行、セル結合）を分析
3. JSON形式で忠実に再現

# 出力形式
{
  "metadata": { ... },
  "tables": [
    {
      "table_type": "...",
      "headers": [...],
      "rows": [...]
    }
  ]
}
```

## バージョン履歴

- **v1.0** (2024-11-28): 初版リリース
  - 基本的な表構造抽出
  - セル結合対応
  - doc_type別の表定義
