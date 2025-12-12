# 修正内容のクイックガイド

## 実施した修正

### 問題1: 12/5（金曜日）のスケジュールデータが検索でヒットしない

**根本原因**:
- `weekly_schedule`等のメタデータがembedding生成の対象外だった
- メタデータが全文検索（TSVector）の対象外だった

**修正内容**:

#### 1. Python側（pipelines/two_stage_ingestion.py）
```python
# 新規追加: flatten_metadata_to_text() 関数
# - weekly_scheduleの日付、イベント、科目を平坦化
# - 検索可能なテキストに変換

# Embedding生成を改善
# Before: 本文のみ（8000文字）
# After: 本文（7000文字）+ メタデータ（1000文字）
```

#### 2. データベース側（database/schema_updates/add_metadata_to_search.sql）
```sql
-- 新規カラム: metadata_searchable_text
-- 新規関数: extract_searchable_metadata()
-- トリガー更新: metadataも含めてTSVectorを生成
```

**適用方法**:
1. Supabase SQL Editorで `database/schema_updates/add_metadata_to_search.sql` を実行
2. 既存ドキュメントを再取り込み（オプション、推奨）

---

### 問題2: JSON表示が折りたたまれていて全データが見えない

**修正内容**:

#### ui/review_ui.py (472, 475行目)
```python
# Before
st.json(correction.get('old_metadata', {}), expanded=False)

# After
st.json(correction.get('old_metadata', {}), expanded=True)
```

**効果**:
- 修正履歴のJSON表示がデフォルトで展開される
- weekly_scheduleの全ての日のデータが見える
- 入れ子の配列（periods, subjects）も完全に表示される

---

### 問題3: テーブルエディタの高さが小さくて全データが見えない

**修正内容**:

#### ui/components/table_editor.py (330, 422, 615行目)
```python
# Before
height=400

# After
height=600  # 増加: より多くの行を表示
```

**効果**:
- テーブル表示が50%増加（400px → 600px）
- スクロールせずに見える行数が増える
- weekly_scheduleの全6時限が一度に見える

---

## 即座に適用できる修正

以下はコード変更のみで、データベース更新不要：

✅ **完了**: JSON表示の展開（ui/review_ui.py）
✅ **完了**: テーブル高さの増加（ui/components/table_editor.py）
✅ **完了**: Embedding生成の改善（pipelines/two_stage_ingestion.py）

## データベース更新が必要な修正

⚠️ **要実行**: メタデータ検索の有効化

```bash
# Supabase SQL Editorで実行
cat database/schema_updates/add_metadata_to_search.sql
```

このSQLを実行すると：
- 既存データのメタデータが検索可能になる
- 新規データは自動的にメタデータが検索対象になる

---

## 動作確認手順

### 1. UIの表示確認
```bash
streamlit run ui/review_ui.py
```

以下を確認：
- ✅ JSON表示が展開されているか
- ✅ テーブルが600pxの高さで表示されているか
- ✅ weekly_scheduleの全データが見えるか

### 2. 検索機能の確認（データベース更新後）

#### テスト1: 日付で検索
```
検索ワード: 12月5日
期待結果: 学年通信がヒット
```

#### テスト2: イベント名で検索
```
検索ワード: 委員会活動
期待結果: 該当する学年通信がヒット
```

#### テスト3: 曜日で検索
```
検索ワード: 金曜日
期待結果: 金曜日のスケジュールを含む文書がヒット
```

#### テスト4: 科目名で検索
```
検索ワード: 実験
期待結果: 理科実験が含まれる文書がヒット
```

---

## トラブルシューティング

### Q1: 「12月5日」で検索してもヒットしない

**確認事項**:
1. データベースのSQLマイグレーションを実行したか？
   ```sql
   SELECT metadata_searchable_text FROM documents WHERE file_name LIKE '%学年通信%' LIMIT 1;
   ```
   → NULL以外の値が返ればOK

2. 既存データを再取り込みしたか？
   - 新規データは自動的にメタデータが含まれる
   - 既存データはSQLのUPDATEクエリで更新される

### Q2: JSON表示が折りたたまれたまま

**確認事項**:
1. `ui/review_ui.py` の変更が反映されているか？
   ```bash
   grep "expanded=True" ui/review_ui.py
   ```
   → 2箇所（472, 475行目）にあればOK

2. Streamlitを再起動したか？
   ```bash
   # Ctrl+C で停止後、再起動
   streamlit run ui/review_ui.py
   ```

### Q3: テーブルの高さが変わらない

**確認事項**:
1. `ui/components/table_editor.py` の変更が反映されているか？
   ```bash
   grep "height=600" ui/components/table_editor.py
   ```
   → 3箇所（330, 422, 615行目）にあればOK

2. ブラウザのキャッシュをクリアしたか？
   - Streamlitの右上メニュー → "Clear cache" → "Rerun"

---

## 各ファイルの変更サマリー

| ファイル | 変更内容 | 再起動必要 |
|---------|---------|----------|
| `pipelines/two_stage_ingestion.py` | メタデータ展開関数追加、Embedding生成改善 | なし（新規処理時に適用） |
| `database/schema_updates/add_metadata_to_search.sql` | メタデータ検索用スキーマ追加 | なし（SQL実行のみ） |
| `ui/review_ui.py` | JSON表示を展開 | Streamlit再起動 |
| `ui/components/table_editor.py` | テーブル高さ増加 | Streamlit再起動 |

---

## 次のステップ

1. ✅ **即座に実施可能**: Streamlitを再起動してUI改善を確認
2. ⚠️ **推奨**: データベースのSQLマイグレーションを実行
3. 📝 **オプション**: 重要な文書を再取り込みしてembeddingを更新

---

## 参考資料

詳細な説明は `METADATA_SEARCH_UPDATE.md` を参照してください。
