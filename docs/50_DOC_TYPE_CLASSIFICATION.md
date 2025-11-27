# 50種類書類タイプ分類体系ドキュメント

## 概要

Phase 2で実装された**50種類の詳細な書類タイプ分類体系**は、家庭・個人・ビジネスのあらゆる文書を網羅的にカバーする包括的な分類システムです。8つの主要フォルダに整理され、AI分類器が自動的に最適なタイプを選択します。

## 目的

- 📚 **網羅的な分類**: 50種類の詳細な分類で、あらゆる文書をカバー
- 🗂️ **体系的な整理**: 8つのフォルダで構造的に管理
- 🤖 **AI自動分類**: Gemini/Claudeが自動的に最適なタイプを選択
- 🔍 **高精度な検索**: 詳細な分類により検索精度が向上

## 8つの主要フォルダと50種類の分類

### 📚 Folder 1: 育哉-学校 (Ikuya School) - 8種類

子どもの学校関連書類

| doc_type | 表示名 | 説明 |
|----------|--------|------|
| `timetable` | 時間割 | 週間または月間の授業時間割 |
| `school_notice` | 学校のお知らせ | 学校からの通知・連絡事項 |
| `homework` | 宿題 | 課題・宿題の詳細 |
| `test_exam` | 試験・テスト | テスト範囲・日程 |
| `report_card` | 通知表・成績表 | 学期末の成績評価 |
| `school_event` | 学校行事案内 | 運動会・遠足などの案内 |
| `parent_teacher_meeting` | 保護者面談記録 | 面談・保護者会の記録 |
| `class_newsletter` | 学級通信 | クラスからの便り |

### 💼 Folder 2: 仕事 (Work) - 9種類

ビジネス関連書類

| doc_type | 表示名 | 説明 |
|----------|--------|------|
| `meeting_minutes` | 議事録 | 会議の記録・決定事項 |
| `proposal` | 提案書 | プロジェクト提案・企画書 |
| `business_report` | 報告書 | 業務報告・進捗レポート |
| `contract` | 契約書 | ビジネス契約書類 |
| `invoice` | 請求書 | 取引先への請求書 |
| `receipt` | 領収書 | 支払いの領収証 |
| `business_card` | 名刺 | 取引先の名刺 |
| `presentation` | プレゼン資料 | 説明資料・スライド |
| `memo` | 業務メモ | 業務上のメモ・備忘録 |

### 💰 Folder 3: 家計・金融 (Finance) - 7種類

金融・家計管理書類

| doc_type | 表示名 | 説明 |
|----------|--------|------|
| `bank_statement` | 銀行明細 | 口座の入出金明細 |
| `credit_card_statement` | クレジットカード明細 | カード利用明細 |
| `utility_bill` | 公共料金請求書 | 電気・ガス・水道料金 |
| `tax_document` | 税金関連書類 | 確定申告・納税証明 |
| `insurance_policy` | 保険証券 | 生命保険・損害保険 |
| `pension_document` | 年金関連書類 | 年金定期便・通知 |
| `investment_statement` | 投資明細 | 株式・投資信託の明細 |

### 🏥 Folder 4: 医療・健康 (Medical) - 6種類

医療・健康管理書類

| doc_type | 表示名 | 説明 |
|----------|--------|------|
| `medical_record` | 診療記録 | カルテ・診察記録 |
| `prescription` | 処方箋 | 薬の処方箋 |
| `health_checkup` | 健康診断結果 | 検診・人間ドック結果 |
| `vaccination_record` | 予防接種記録 | ワクチン接種記録 |
| `medical_bill` | 医療費明細 | 診療費・入院費明細 |
| `insurance_claim` | 保険請求書 | 医療保険の請求書類 |

### 🏠 Folder 5: 住まい・不動産 (Housing) - 6種類

住宅・不動産関連書類

| doc_type | 表示名 | 説明 |
|----------|--------|------|
| `lease_agreement` | 賃貸契約書 | 賃貸住宅の契約書 |
| `property_deed` | 不動産登記 | 不動産の権利証 |
| `mortgage_document` | 住宅ローン書類 | ローン契約・返済計画 |
| `maintenance_record` | 修繕記録 | 住宅の修繕・工事記録 |
| `property_tax` | 固定資産税 | 固定資産税・都市計画税 |
| `condo_management` | マンション管理組合 | 管理費・修繕積立金 |

### ⚖️ Folder 6: 法律・行政 (Legal/Admin) - 6種類

法律・行政手続き書類

| doc_type | 表示名 | 説明 |
|----------|--------|------|
| `government_notice` | 行政通知 | 市役所・区役所からの通知 |
| `resident_certificate` | 住民票 | 住民票の写し |
| `family_register` | 戸籍謄本 | 戸籍謄本・抄本 |
| `permit` | 許可証・免許証 | 各種許可証・資格証 |
| `legal_document` | 法律文書 | 契約書・合意書 |
| `court_document` | 裁判所書類 | 訴状・判決書 |

### 🎨 Folder 7: 趣味・ライフスタイル (Lifestyle) - 6種類

趣味・個人活動書類

| doc_type | 表示名 | 説明 |
|----------|--------|------|
| `travel_document` | 旅行関連書類 | 旅行予約・チケット |
| `event_ticket` | イベントチケット | コンサート・イベント券 |
| `membership_card` | 会員証 | 会員証・メンバーシップカード |
| `warranty` | 保証書 | 製品の保証書 |
| `manual` | 取扱説明書 | 製品マニュアル |
| `recipe` | レシピ | 料理レシピ |

### 📁 Folder 8: その他 (Other) - 5種類

分類不能・その他の書類

| doc_type | 表示名 | 説明 |
|----------|--------|------|
| `personal_letter` | 個人的な手紙 | 手紙・はがき・年賀状 |
| `photo` | 写真・画像 | スキャンした写真 |
| `certificate` | 各種証明書 | 修了証・認定証 |
| `id_card` | 身分証明書 | 身分証のコピー |
| `other` | その他 | 上記以外の全て |

**合計: 50種類**

## 実装されたファイル

### 1. `config/DOC_TYPE_CONSTANTS.py` (新規, 650行)

**目的**: 50種類の文書タイプを一元管理

**主要な定数**:

```python
# フォルダ別のリスト
IKUYA_SCHOOL_TYPES = ["timetable", "school_notice", ...]
WORK_TYPES = ["meeting_minutes", "proposal", ...]
FINANCE_TYPES = ["bank_statement", "credit_card_statement", ...]
# ... 8つのフォルダ

# 全50種類の統合リスト
ALL_DOC_TYPES = [...]  # 50種類

# フォルダ別マッピング
FOLDER_MAPPINGS = {
    "ikuya_school": IKUYA_SCHOOL_TYPES,
    "work": WORK_TYPES,
    ...
}

# 詳細メタデータ
DOC_TYPE_METADATA = {
    "timetable": {
        "display_name": "時間割",
        "folder": "ikuya_school",
        "priority": "high",
        "keywords": ["時間割", "時限", "曜日", "授業"],
    },
    ...
}
```

**ユーティリティ関数**:

```python
# フォルダからdoc_typeを取得
get_doc_types_by_folder("ikuya_school")  # → ["timetable", "school_notice", ...]

# doc_typeからフォルダを取得
get_folder_by_doc_type("timetable")  # → "ikuya_school"

# 表示名を取得
get_display_name("timetable")  # → "時間割"

# キーワードを取得
get_keywords("timetable")  # → ["時間割", "時限", "曜日", "授業"]
```

### 2. `core/ai/stage1_classifier.py` (修正, +50行)

**変更内容**:

#### インポート追加
```python
from config.DOC_TYPE_CONSTANTS import (
    ALL_DOC_TYPES,
    DOC_TYPE_METADATA,
    FOLDER_MAPPINGS,
    get_display_name
)
```

#### 動的プロンプト生成
```python
def _generate_doc_types_list(self) -> str:
    """
    50種類の文書タイプをフォルダ別に整理したリストを生成
    """
    doc_types_text = []

    for folder_key, folder_types in FOLDER_MAPPINGS.items():
        folder_names = {
            "ikuya_school": "📚 育哉-学校",
            "work": "💼 仕事",
            ...
        }

        folder_display = folder_names.get(folder_key, folder_key)
        doc_types_text.append(f"\n{folder_display}:")

        for doc_type in folder_types:
            display_name = get_display_name(doc_type)
            doc_types_text.append(f"  - {doc_type}: {display_name}")

    return "\n".join(doc_types_text)
```

#### プロンプト更新
```python
def generate_classification_prompt(self, doc_types_yaml: str = None) -> str:
    doc_types_list = self._generate_doc_types_list()

    return f"""あなたは文書分類の専門家です。
この文書を分析し、以下のJSON形式で回答してください:

{{
  "doc_type": "最適な文書タイプ（下記の50種類から1つ選択）",
  "workspace": "family/personal/work のいずれか",
  "relevant_date": "重要な日付 (YYYY-MM-DD形式、なければnull)",
  "summary": "文書の要約 (100文字以内)",
  "confidence": 0.0から1.0の信頼度スコア
}}

**利用可能な文書タイプ (全50種類):**
{doc_types_list}
...
"""
```

**効果**:
- ✅ 50種類全てがAI分類の候補になる
- ✅ フォルダ別に整理されたプロンプトで精度向上
- ✅ 後方互換性を維持（doc_types_yamlパラメータは残す）

## 使用例

### 例1: 定数の利用

```python
from config.DOC_TYPE_CONSTANTS import ALL_DOC_TYPES, get_display_name

# 全ての分類候補を取得
print(f"利用可能な分類: {len(ALL_DOC_TYPES)}種類")

# 表示名を取得
for doc_type in ALL_DOC_TYPES:
    display_name = get_display_name(doc_type)
    print(f"{doc_type}: {display_name}")
```

### 例2: フォルダ別のフィルタリング

```python
from config.DOC_TYPE_CONSTANTS import get_doc_types_by_folder

# 学校関連の書類タイプのみ取得
school_types = get_doc_types_by_folder("ikuya_school")
print(school_types)
# → ["timetable", "school_notice", "homework", ...]
```

### 例3: AI分類の実行

```python
from core.ai.stage1_classifier import Stage1Classifier
from core.ai.llm_client import LLMClient

classifier = Stage1Classifier(LLMClient())

# 50種類から自動選択
result = await classifier.classify(
    file_path=Path("document.pdf"),
    doc_types_yaml=None  # yamlは不要（内部で自動生成）
)

print(result['doc_type'])  # 例: "timetable"
print(result['confidence'])  # 例: 0.95
```

### 例4: メタデータの活用

```python
from config.DOC_TYPE_CONSTANTS import DOC_TYPE_METADATA

# 特定のdoc_typeの詳細情報を取得
metadata = DOC_TYPE_METADATA['timetable']

print(metadata['display_name'])  # "時間割"
print(metadata['folder'])        # "ikuya_school"
print(metadata['priority'])      # "high"
print(metadata['keywords'])      # ["時間割", "時限", "曜日", "授業"]
```

## 分類精度の向上

### キーワードベースの分類

各doc_typeには分類精度を高めるための**キーワード**が定義されています。

**例: `timetable` のキーワード**:
```python
"keywords": ["時間割", "時限", "曜日", "授業"]
```

これらのキーワードが文書に含まれていると、AI が `timetable` と分類する確率が高まります。

### 優先度の設定

各doc_typeには**優先度**が設定されています:

- `high`: 重要な書類（契約書、成績表など）
- `medium`: 中程度の重要度（お知らせ、領収書など）
- `low`: 低優先度（メモ、写真など）

これにより、レビュー時の優先順位付けが可能です。

## データベース統計

### doc_type別の統計

```sql
-- doc_type別のドキュメント数
SELECT
    doc_type,
    COUNT(*) as document_count,
    ROUND(AVG(confidence), 3) as avg_confidence
FROM documents
GROUP BY doc_type
ORDER BY document_count DESC;
```

### フォルダ別の統計

```python
from config.DOC_TYPE_CONSTANTS import get_folder_by_doc_type

# Pythonで集計
folder_counts = {}
for doc in documents:
    folder = get_folder_by_doc_type(doc['doc_type'])
    folder_counts[folder] = folder_counts.get(folder, 0) + 1
```

### 新しいdoc_typeの追加頻度

```sql
-- 月別のdoc_type利用状況
SELECT
    DATE_TRUNC('month', created_at) as month,
    doc_type,
    COUNT(*) as count
FROM documents
WHERE created_at > NOW() - INTERVAL '6 months'
GROUP BY month, doc_type
ORDER BY month DESC, count DESC;
```

## 新しいdoc_typeの追加方法

### Step 1: `config/DOC_TYPE_CONSTANTS.py` に追加

```python
# 例: 新しいフォルダ "education" を追加
EDUCATION_TYPES = [
    "textbook",          # 教科書
    "study_material",    # 学習教材
]

# ALL_DOC_TYPESに追加
ALL_DOC_TYPES = (
    IKUYA_SCHOOL_TYPES +
    WORK_TYPES +
    ...
    EDUCATION_TYPES  # 新規追加
)

# FOLDER_MAPPINGSに追加
FOLDER_MAPPINGS["education"] = EDUCATION_TYPES

# DOC_TYPE_METADATAに追加
DOC_TYPE_METADATA["textbook"] = {
    "display_name": "教科書",
    "folder": "education",
    "priority": "high",
    "keywords": ["教科書", "テキスト", "科目"],
}
```

### Step 2: `core/ai/stage1_classifier.py` の更新

`_generate_doc_types_list()` のfolder_namesに追加:

```python
folder_names = {
    ...
    "education": "📖 教育教材",  # 新規追加
}
```

### Step 3: スキーマファイルの作成（オプション）

```bash
# ui/schemas/textbook.json を作成
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "title": "教科書スキーマ",
  "properties": {
    "subject": {"type": "string"},
    "grade": {"type": "string"},
    "publisher": {"type": "string"}
  },
  "required": ["subject", "grade"]
}
```

### Step 4: 動作確認

```python
from config.DOC_TYPE_CONSTANTS import ALL_DOC_TYPES

assert "textbook" in ALL_DOC_TYPES
print(f"Total doc types: {len(ALL_DOC_TYPES)}")  # 51種類
```

## ベストプラクティス

### 1. 分類の一貫性

新しいdoc_typeを追加する際は、既存の命名規則に従う:
- 英語の小文字とアンダースコア（例: `school_notice`）
- 日本語の表示名は簡潔に（例: "学校のお知らせ"）

### 2. キーワードの選定

効果的なキーワードの特徴:
- ✅ その書類にほぼ確実に含まれる単語
- ✅ 他のdoc_typeと重複しない独自性
- ✅ 3〜5個程度に絞る

### 3. フォルダの整理

関連する書類は同じフォルダにまとめる:
- 学校関連は `ikuya_school`
- 仕事関連は `work`
- 金融関連は `finance`

### 4. 優先度の活用

priority設定のガイドライン:
- `high`: 法的効力がある、期限がある、重要度が高い
- `medium`: 定期的に確認が必要、保管義務がある
- `low`: 参考情報、一時的なもの

## トラブルシューティング

### 問題: AIが常に "other" と分類する

**原因**: キーワードが不適切、または文書が本当に該当しない

**解決策**:
1. キーワードを見直す
2. 文書の実際の内容を確認
3. 新しいdoc_typeの追加を検討

### 問題: 分類が不安定（同じ文書で異なる結果）

**原因**: 複数のdoc_typeに該当する可能性がある

**解決策**:
1. キーワードをより具体的にする
2. プロンプトに判定基準を明示
3. Stage 2（Claude）で精度を上げる

### 問題: 50種類が多すぎてAIが混乱する

**現状**: Gemini 2.5 Flashは50種類程度なら十分対応可能

**将来の対策**:
1. 2段階分類（まずフォルダ→次にdoc_type）
2. キーワードマッチングで候補を絞る
3. より高性能なモデル（GPT-4など）を使用

## まとめ

50種類書類タイプ分類体系により、以下が実現されました:

✅ **網羅的な分類**: 家庭・個人・ビジネスのあらゆる文書をカバー
✅ **体系的な整理**: 8つのフォルダで構造的に管理
✅ **AI自動分類**: Geminiが自動的に最適なタイプを選択
✅ **高い拡張性**: 新しいdoc_typeの追加が容易
✅ **メタデータ管理**: 表示名・キーワード・優先度を一元管理

**実装ファイル**:
- `config/DOC_TYPE_CONSTANTS.py` (新規, 650行)
- `core/ai/stage1_classifier.py` (修正, +50行)

**効果**:
- 分類精度の向上（詳細な分類により誤分類が減少）
- 検索精度の向上（細かい分類で絞り込みやすい）
- 管理の効率化（フォルダ別に整理）
- 運用の柔軟性（簡単に新しいタイプを追加可能）
