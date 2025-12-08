# フィルタ機能実装ガイド

## 📋 実装完了内容

### ✅ 実装されたフィルタ機能

1. **複数workspace × 複数doc_typeの絞り込み検索**
   - チェックボックスで複数選択可能
   - 「家族全体のスケジュール」など、横断検索に対応

2. **スマホ対応Bottom Sheet UI**
   - 画面下からせり上がるメニュー
   - 親指で操作しやすい配置
   - 検索結果を見ながらフィルタ変更可能

3. **動的フィルタ読み込み**
   - Google Classroomのクラスが増えても自動対応
   - Supabaseから最新のworkspace/doc_type一覧を取得

---

## 🚀 起動手順

### 1. Supabase SQLの実行

まず、Supabaseダッシュボードで以下のSQLを実行してください：

```bash
# ファイルを確認
cat database/add_filter_functions.sql
```

**Supabase SQL Editorでの実行手順:**
1. [Supabaseダッシュボード](https://supabase.com/dashboard) にアクセス
2. プロジェクトを選択
3. 左メニューから「SQL Editor」を選択
4. `database/add_filter_functions.sql` の内容をコピー&ペースト
5. 「Run」ボタンをクリック

### 2. Google Classroom同期スクリプトの実行

提示されたGASコード（`syncAllClassroomsToDocuments`関数）を、Google Apps Scriptエディタに貼り付けて実行してください。

これにより、各クラスルームが動的に`doc_type`として登録されます。

### 3. Flaskアプリケーションの起動

```bash
cd document_management_system
python app.py
```

アプリケーションが起動します（デフォルトポート: 5001）

### 4. ブラウザでアクセス

```
http://localhost:5001
```

---

## 🎨 使い方

### 検索画面での操作

1. **絞り込みボタンをタップ**
   ```
   [検索ボックス]
   [⚙️ 絞り込み] ← ここをタップ
   ```

2. **Bottom Sheetが表示される**
   - 画面下からメニューがせり上がります
   - ワークスペースとドキュメント種別が表示されます

3. **フィルタを選択**
   - 複数選択可能（チェックボックス）
   - 例: 「家族」「仕事」を両方チェック → 横断検索

4. **「決定して検索」ボタンをタップ**
   - Bottom Sheetが閉じます
   - 選択したフィルタがチップとして表示されます
   - 自動的に検索が実行されます

5. **フィルタの削除**
   - チップの「×」ボタンをタップで個別削除
   - または絞り込みメニューで「すべて解除」

---

## 📱 スマホでの表示イメージ

```
┌─────────────────────┐
│ [検索ボックス]       │
│ [⚙️絞り込み] [WS:家族×] [予定×] │
│                     │
│ 検索結果...          │
├─────────────────────┤
│ 背景が暗くなる        │ ← オーバーレイ
├─────────────────────┤
│ 【検索条件を選択】    │ ← Bottom Sheet
│ ───────────────     │
│ ▼ ワークスペース      │
│  [x] 家族            │
│  [ ] 仕事            │
│  [ ] ikuya_classroom │
│                     │
│ ▼ ドキュメント種別    │
│  [x] 予定            │
│  [ ] 議事録          │
│  [ ] 3年B組          │
│                     │
│ [決定して検索]        │
└─────────────────────┘
```

---

## 🔍 動作確認

### テスト1: フィルタ一覧の取得

```bash
curl http://localhost:5001/api/filters
```

**期待される結果:**
```json
{
  "success": true,
  "workspaces": ["ikuya_classroom", "family", "business"],
  "doc_types": ["3年B組", "数学IA", "予定", "議事録", ...]
}
```

### テスト2: 複数フィルタでの検索

```bash
curl -X POST http://localhost:5001/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "今週の予定",
    "limit": 5,
    "workspaces": ["family"],
    "doc_types": ["予定", "スケジュール"]
  }'
```

**期待される結果:**
- `family`ワークスペースかつ
- `doc_type`が「予定」または「スケジュール」
- の文書のみが検索される

---

## 🛠️ トラブルシューティング

### 問題1: フィルタが表示されない

**原因:**
- `/api/filters` エンドポイントがエラーを返している
- Supabaseに接続できていない

**解決策:**
```bash
# ブラウザのコンソールを開いて確認
# 以下のエラーがないか確認
```

### 問題2: Bottom Sheetが開かない

**原因:**
- JavaScriptのエラー

**解決策:**
```bash
# ブラウザのコンソール（F12）でエラーを確認
# HTML/CSSが正しく読み込まれているか確認
```

### 問題3: フィルタが反映されない

**原因:**
- バックエンドのフィルタリングロジックにバグがある

**解決策:**
```bash
# Flaskのログを確認
# [DEBUG] フィルタ後: N 件（workspaces=[...], doc_types=[...]）
# が出力されているか確認
```

---

## 📚 技術詳細

### アーキテクチャ

```
┌─────────────┐
│ フロント    │ index.html
│ (Bottom     │ - フィルタUI
│  Sheet UI)  │ - チェックボックス
└──────┬──────┘
       │ /api/filters (GET)
       │ /api/search (POST)
       ↓
┌─────────────┐
│ Flask API   │ app.py
│             │ - /api/filters: 選択肢取得
│             │ - /api/search: 配列フィルタ対応
└──────┬──────┘
       │ get_available_workspaces()
       │ search_documents()
       ↓
┌─────────────┐
│ Database    │ client.py
│ Client      │ - Pythonレベルフィルタリング
└──────┬──────┘
       │ SQL: SELECT * FROM documents
       ↓
┌─────────────┐
│ Supabase    │
│ (PostgreSQL)│ - documents テーブル
└─────────────┘
```

### データフロー

1. **ページ読み込み時:**
   ```
   Browser → /api/filters → DatabaseClient.get_available_*() → Supabase
   ```

2. **検索時:**
   ```
   Browser → /api/search (workspaces=[], doc_types=[])
         ↓
   app.py: Pythonレベルでフィルタリング
         ↓
   結果を返却
   ```

---

## 🎯 今後の最適化案（オプション）

現在はPythonレベルでフィルタリングしていますが、より効率化するには：

### オプション: Supabase RPC関数を配列対応に

`database/add_filter_functions.sql` にある `hybrid_search` 関数を使うと、
PostgreSQL側で配列フィルタリングを行えます。

**メリット:**
- データベース側でフィルタリング（高速）
- ネットワーク転送量が削減

**デメリット:**
- 既存の `search_documents_final` RPC関数を修正する必要がある
- より複雑な実装

---

## 📝 まとめ

✅ **完成した機能:**
- スマホ対応のBottom Sheet UI
- 複数workspace/doc_typeの横断検索
- Google Classroomの動的クラス対応
- 後方互換性（既存の検索も動作）

✅ **実装ファイル:**
- `database/add_filter_functions.sql` - Supabase SQL関数
- `app.py` - Flask APIエンドポイント
- `templates/index.html` - フロントエンドUI

🎉 **これで「家族全体のスケジュール」など、複数の場所を跨いだ検索が可能になりました！**
