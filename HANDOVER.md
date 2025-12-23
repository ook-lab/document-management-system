# 作業引き継ぎ書 - 家計簿システム (K_kakeibo)

**作成日:** 2025-12-23
**作業環境:** macOS → Windows
**最終コミット:** ff89432

---

## 📋 プロジェクト概要

家計簿管理システムのStreamlitアプリ (`K_kakeibo/review_ui.py`) の機能拡張を実施しました。

**アプリURL:** https://okubo-kakeibo.streamlit.app/

---

## ✅ 実装完了内容

### 1. カテゴリシステムの2層構造化

商品の分類を以下の2つの独立したシステムに分離:

#### **1次分類 (商品カテゴリー)**
- 商品の物理的なカテゴリー
- 例: 文房具、ゲームソフト、交通費、食材など
- 3階層構造: 大分類 → 中分類 → 小分類
  - 例: 食料品 → 野菜 → 根菜

#### **2次分類 (費目)**
- 家計簿の予算カテゴリー
- 例: 食費、教育費、娯楽費、行楽費など
- **決定ロジック (優先順位):**
  1. **名目** (最優先)
  2. **人物**
  3. **1次分類**

**具体例:**
```
交通費(1次) + 旅行(名目) → 行楽費(2次)
交通費(1次) + 学校行事(名目) → 教育費(2次)
ゲームソフト(1次) + 育哉 + 教育(名目) → 教育費(2次)
ゲームソフト(1次) + 育哉 + 日常(名目) → 娯楽費(2次)
```

### 2. 辞書ベースの自動分類システム

AIトークンを使わず、データベース辞書で自動分類:

**検索優先順位:**
1. 店舗名 + 商品名 (完全一致)
2. 店舗名のみ (例: サイゼリヤ → すべて外食)
3. 商品名のみ
4. 正式名のみ
5. 一般名詞のみ

**フィードバックループ:**
- ユーザーが手動修正した内容を辞書に保存
- 使用回数 (`usage_count`) でルールの信頼度を追跡

### 3. UI改善

#### **取引明細画面**
- ✅ 分類を1列に統合 (最下層のみ表示)
- ✅ 人物ドロップダウン: 家族、パパ、ママ、絵麻、育哉 (デフォルト: 家族)
- ✅ 名目ドロップダウン: データベースから取得、拡張可能 (デフォルト: 日常)
- ✅ 費目 (2次分類) の自動判定表示
- ✅ 一括編集機能 (全行を一括変更)

#### **カテゴリ管理画面 (3タブ)**
1. **📦 1次分類 (商品カテゴリー)**
   - ツリー構造表示
   - 追加・削除機能
2. **💰 2次分類 (費目)**
   - 一覧・追加・削除機能
3. **🎯 名目**
   - 一覧・追加・削除機能

#### **ルール管理画面**
- 2次分類決定ルールの表示・追加・削除
- 優先度の自動計算:
  - 名目 + 人物 + 1次分類: priority=80
  - 名目 + (人物 OR 1次分類): priority=90
  - 名目のみ: priority=100
  - 人物 + 1次分類: priority=50
  - 1次分類のみ: priority=30

---

## 🗄️ データベース変更

### 実行済みSQLファイル

以下のSQLファイルをSupabaseデータベースで実行済み:

```bash
# 1. 中分類カラムの追加
K_kakeibo/add_middle_category.sql

# 2. 一般名詞カラムの追加
K_kakeibo/add_general_name_to_standardized_items.sql

# 3. 取引辞書テーブルの作成
K_kakeibo/create_transaction_dictionary.sql

# 4. 2次分類システム (費目システム) の構築
K_kakeibo/create_expense_category_system.sql
```

### 新規テーブル

1. **60_ms_product_categories** - 1次分類マスタ (階層構造)
2. **60_ms_expense_categories** - 2次分類マスタ (費目)
3. **60_ms_purposes** - 名目マスタ (拡張可能)
4. **60_ms_expense_category_rules** - 2次分類決定ルール
5. **60_ms_transaction_dictionary** - 取引辞書 (自動分類用)

### ビュー

- **v_expense_category_rules** - ルール一覧 (見やすい表示用)

### カラム追加

- **60_rd_standardized_items**:
  - `middle_category` TEXT - 中分類
  - `general_name` TEXT - 一般名詞

---

## 🔧 主要な関数

### `K_kakeibo/review_ui.py`

#### 1. `determine_expense_category(db, product_category, person, purpose)`
2次分類 (費目) を優先順位ベースで自動判定

**優先順位:**
1. 名目 + 人物 + 1次分類
2. 名目 + 1次分類
3. 名目 + 人物
4. 名目のみ
5. 人物 + 1次分類
6. 1次分類のみ

#### 2. `auto_classify_transaction(db, shop_name, product_name, official_name, general_name)`
辞書ベースの自動分類

**検索優先順位:**
1. 店舗名 + 商品名
2. 店舗名のみ
3. 商品名のみ
4. 正式名のみ
5. 一般名詞のみ

#### 3. `save_to_dictionary(db, shop_name, product_name, official_name, general_name, category, person, purpose)`
ユーザーの修正内容を辞書に保存

- 既存エントリは `usage_count` をインクリメント
- 新規エントリは自動的に優先度を計算

#### 4. `show_category_tree()`
カテゴリ管理画面 (3タブ構成)

#### 5. `show_rule_management()`
ルール管理画面 (CRUD操作)

---

## 📁 主要ファイル構成

```
document_management_system/
├── K_kakeibo/
│   ├── review_ui.py                              # メインアプリ (Streamlit)
│   ├── add_middle_category.sql                   # DB変更: 中分類追加
│   ├── add_general_name_to_standardized_items.sql # DB変更: 一般名詞追加
│   ├── create_transaction_dictionary.sql         # DB: 取引辞書テーブル
│   └── create_expense_category_system.sql        # DB: 費目システム構築
├── HANDOVER.md                                    # この引き継ぎ書
└── collect_codebase.py                            # コードベース収集ツール
```

---

## 🚀 次のステップ (未実施項目)

現時点で実装は完了しています。以下は今後の拡張案です:

### 1. データの初期投入
- 取引辞書 (`60_ms_transaction_dictionary`) に既存データからルールを学習
- よく使う店舗・商品の組み合わせを事前登録

### 2. ルールの精度向上
- 辞書の使用回数を活用した信頼度表示
- 低信頼度ルールの警告表示

### 3. レポート機能
- 費目別の集計レポート
- 月次・年次のグラフ表示

### 4. エクスポート機能
- CSV/Excelエクスポート (費目別集計付き)

---

## 💻 環境情報

### macOS環境 (作業完了)
- Python: 3.x
- Streamlit
- Supabase (PostgreSQL)
- Git repository: https://github.com/ook-lab/document-management-system.git

### Windows環境で作業を続ける場合

#### 1. リポジトリのクローン/プル
```bash
git clone https://github.com/ook-lab/document-management-system.git
# または既存リポジトリで
git pull origin main
```

#### 2. 環境変数の設定
以下の環境変数が必要です (`.streamlit/secrets.toml` または環境変数):
```toml
SUPABASE_URL = "your-supabase-url"
SUPABASE_KEY = "your-supabase-anon-key"
```

#### 3. Python依存関係のインストール
```bash
pip install streamlit supabase pandas
```

#### 4. アプリの起動
```bash
streamlit run K_kakeibo/review_ui.py
```

---

## 📝 注意事項

### データベーススキーマキャッシュ
新しいテーブルを作成した後、PostgRESTのスキーマキャッシュをリフレッシュする必要があります:
- Supabase Dashboard → Settings → API → "Reload schema cache"
- または数分待つと自動的にリフレッシュされます

### Git管理
- すべての変更はコミット済み
- 最新のコミット: `ff89432`
- ブランチ: `main`

---

## 🔗 参考リンク

- **Streamlitアプリ:** https://okubo-kakeibo.streamlit.app/
- **GitHubリポジトリ:** https://github.com/ook-lab/document-management-system

---

## ✅ 作業完了チェックリスト

- [x] 1次分類・2次分類システムの実装
- [x] 辞書ベースの自動分類実装
- [x] カテゴリ管理画面 (3タブ) の実装
- [x] ルール管理画面の実装
- [x] データベーススキーマ変更 (4つのSQLファイル実行)
- [x] UI改善 (分類統合、ドロップダウン、一括編集)
- [x] すべての変更をgit commit & push
- [x] 引き継ぎ書の作成

**作業完了日時:** 2025-12-23

---

以上です。Windows環境での作業をスムーズに継続できるようにまとめました。
