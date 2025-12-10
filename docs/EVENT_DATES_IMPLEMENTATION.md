# イベント日付検索機能の実装

## 実施日: 2025-12-10

## 目的

Classroom投稿などで「明後日日曜日はアドベント...」のような相対的な日付表現を含む文書を、実際の日付（例: 12/7）で検索できるようにする。

## 問題の詳細

### 従来の問題

| 項目 | 説明 |
|------|------|
| **投稿日** | 2025年12月5日 |
| **投稿内容** | 「明後日日曜日はアドベント...」|
| **ユーザーのクエリ** | 「12/7」で検索 |
| **従来の動作** | ヒットしない（「明後日」≠「12/7」） |
| **期待される動作** | ヒットする（明後日 = 12/7と認識） |

## 実装内容

### 1. データベーススキーマの拡張

**ファイル**: `database/migration_event_dates.sql`

```sql
-- event_datesカラムを追加（DATE配列型）
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS event_dates DATE[];

-- GINインデックスを追加（配列検索の高速化）
CREATE INDEX IF NOT EXISTS idx_documents_event_dates
ON documents USING GIN(event_dates);
```

### 2. Stage 2プロンプトの拡張

**ファイル**: `core/ai/stage2_extractor.py`

#### 追加したパラメータ

```python
def extract_metadata(
    ...
    reference_date: str = None  # 基準日（Classroom投稿日など）
) -> Dict:
```

#### プロンプトの変更

```
# 投稿日・基準日
2025-12-05

**重要**: この日付を基準に、相対的な日付表現（「明日」「明後日」「来週」など）を
絶対日付に変換してください。

# タスク
3. **event_dates**: イベントや予定の日付リスト (YYYY-MM-DD形式の配列)
   - 「明日」「明後日」などの相対表現は、上記の基準日から計算して絶対日付に変換
   - 例: 基準日が2025-12-05で「明後日日曜日」→ 2025-12-07
   - 複数の日付がある場合はすべて抽出
```

### 3. SQL検索関数の更新

**ファイル**: `database/update_search_with_event_dates.sql`

#### 変更内容

日付フィルタが `document_date` だけでなく、`event_dates` 配列もチェックするように変更：

```sql
-- 年フィルタ（document_date または event_dates のいずれかにマッチ）
AND (
    filter_year IS NULL
    OR EXTRACT(YEAR FROM d.document_date) = filter_year
    OR EXISTS (
        SELECT 1 FROM unnest(d.event_dates) AS event_date
        WHERE EXTRACT(YEAR FROM event_date) = filter_year
    )
)
```

### 4. Pythonパイプラインの更新

**ファイル**: `pipelines/two_stage_ingestion.py`

#### 変更内容

1. Stage 2から`event_dates`を取得
2. `document_data`に`event_dates`フィールドを追加
3. Supabaseに保存

```python
event_dates = stage2_result.get('event_dates', [])

document_data = {
    ...
    "event_dates": event_dates_array,  # イベント日付配列
    ...
}
```

## 実装手順

### ステップ1: Supabaseでマイグレーションを実行

```sql
-- database/migration_event_dates.sql を実行
```

### ステップ2: Supabase検索関数を更新

```sql
-- database/update_search_with_event_dates.sql を実行
```

### ステップ3: 既存データの再処理

既存のClassroom投稿を再処理して、`event_dates`を抽出します：

```bash
# GASスクリプトを再実行
# または、Pythonスクリプトで再処理
cd /Users/ookuboyoshinori/document_management_system
python scripts/reprocess_documents.py --source_type=classroom
```

### ステップ4: Pythonサーバーを再起動

```bash
pkill -f "python.*app.py"
python app.py
```

## 動作フロー

### 処理の流れ

```
1. Classroom投稿（12月5日）
   ↓
2. GASがSupabaseに保存
   - classroom_sent_at: 2025-12-05
   ↓
3. Pythonパイプラインが処理
   ↓
4. Stage 2でメタデータ抽出
   - reference_date: 2025-12-05 を渡す
   - AIが「明後日日曜日」を認識
   - event_dates: [2025-12-07] を抽出
   ↓
5. Supabaseに保存
   - event_dates: [2025-12-07]
   ↓
6. ユーザーが「12/7」で検索
   ↓
7. SQL関数がevent_dates配列をチェック
   ↓
8. 該当文書がヒット！
```

### データの例

```json
{
  "classroom_sent_at": "2025-12-05T12:00:00Z",
  "classroom_subject": "アドベント第２主日のお知らせ",
  "full_text": "明後日日曜日はアドベント🌲🎄第２主日となります...",
  "document_date": "2025-12-05",
  "event_dates": ["2025-12-07"],
  "metadata": {
    "event_dates": ["2025-12-07"]
  }
}
```

## 検索の動作確認

### テストケース1: 相対日付

**投稿**: 「明後日日曜日はアドベント...」（投稿日: 12月5日）

**検索クエリ**: 「12/7」

**期待結果**: ✅ ヒットする（event_dates に 2025-12-07 が含まれる）

### テストケース2: 明示的な日付

**投稿**: 「12月7日のイベントについて」

**検索クエリ**: 「12/7」

**期待結果**: ✅ ヒットする（全文検索でマッチ）

### テストケース3: 複数の日付

**投稿**: 「明日と明後日にイベントがあります」（投稿日: 12月5日）

**検索クエリ**: 「12/6」または「12/7」

**期待結果**: ✅ 両方でヒットする（event_dates に [2025-12-06, 2025-12-07] が含まれる）

## トラブルシューティング

### 問題1: 既存データで検索がヒットしない

**原因**: まだ再処理されていない

**解決策**:
```bash
# GASスクリプトを再実行して全データを再取得
# または、Pythonで特定のドキュメントを再処理
python scripts/reprocess_documents.py --document_id=XXX
```

### 問題2: event_datesが空になる

**原因**: AIが日付を認識できていない

**解決策**:
1. プロンプトを確認（reference_dateが正しく渡されているか）
2. ログを確認（Stage 2の出力）
3. AIモデルの応答を確認

### 問題3: reference_dateが渡されていない

**原因**: Classroom投稿の処理でreference_dateを渡していない

**解決策**:
- GASスクリプトで`classroom_sent_at`を保存
- Pythonパイプラインで`classroom_sent_at`を取得して`reference_date`として渡す

## 今後の拡張

### 予定している機能

1. **より複雑な相対表現のサポート**
   - 「来週の月曜日」
   - 「月末」
   - 「次の金曜日」

2. **期間の抽出**
   - 「12月10日から15日まで」→ event_dates: [2025-12-10, ..., 2025-12-15]

3. **曜日の検証**
   - 「明後日日曜日」→ 計算結果が日曜日でない場合は警告

4. **日本語の日付表現**
   - 「今月末」
   - 「来月初め」

## 関連ドキュメント

- [Classroom統合まとめ](CLASSROOM_INTEGRATION_SUMMARY.md)
- [実装手順](../IMPLEMENTATION_STEPS.md)
- [データベーススキーマ](../database/schema_v4_unified.sql)

---

**実装完了日**: 2025-12-10
**次回レビュー**: データが再処理された後に動作確認
