# 商品自動分類システム

## 概要

埋め込みベクトルを使って商品を自動的に階層分類するシステムです。

## スクリプト

### 1. `migrate_small_category_to_uuid.py`

**目的**: 既存の `small_category`（テキスト）を `category_id`（UUID）にマイグレーション

**処理内容**:
- `Rawdata_NETSUPER_items` の全商品を取得
- `small_category` の値を元に `MASTER_Categories_product` を検索
- 見つかった場合：そのUUIDを `category_id` に設定
- 見つからない場合：新規カテゴリを作成（親なし）してUUIDを設定

**実行方法**:
```bash
cd /Users/ookuboyoshinori/document_management_system
./venv/bin/python L_product_classification/migrate_small_category_to_uuid.py
```

**注意**:
- 実行前に確認プロンプトが表示されます
- バックアップを取ってから実行することを推奨
- 最大10,000件で停止（必要に応じてコード修正）

---

### 2. `auto_classify_with_clustering.py`

**目的**: 埋め込みベクトルを使って階層的に自動分類

**処理フロー**:
1. 全商品の `general_name_embedding` を取得
2. k-meansクラスタリングで小分類を自動生成（150グループ）
3. 各クラスタにAIで命名（GPT-4o-mini）
4. 小分類を再クラスタリングして中分類を生成（30グループ）
5. 中分類を再クラスタリングして大分類を生成（8グループ）
6. 結果をJSONで保存

**実行方法**:
```bash
cd /Users/ookuboyoshinori/document_management_system
./venv/bin/python L_product_classification/auto_classify_with_clustering.py
```

**出力**:
- `L_product_classification/clustering_result.json` - 分類結果

**設定**:
```python
N_SMALL_CATEGORIES = 150  # 小分類の数
N_MEDIUM_CATEGORIES = 30   # 中分類の数
N_LARGE_CATEGORIES = 8     # 大分類の数
```

**推定コスト**（5,000件の場合）:
- AI命名: 150クラスタ × $0.001 ≈ $0.15
- 合計: 約$0.15-0.30

---

## 推奨実行順序

### Phase 1: 5,000件でテスト

1. **マイグレーション実行**:
   ```bash
   ./venv/bin/python L_product_classification/migrate_small_category_to_uuid.py
   ```

2. **クラスタリング実行**:
   ```bash
   ./venv/bin/python L_product_classification/auto_classify_with_clustering.py
   ```

3. **結果確認**:
   ```bash
   cat L_product_classification/clustering_result.json
   ```

4. **UIで確認**:
   - https://netsuper-classification.streamlit.app/
   - 大分類・中分類・小分類が正しく表示されるか確認

### Phase 2: 2万件で本番実行

1. クラスタ数を調整（必要に応じて）
2. 再度実行
3. 最終確認

---

## トラブルシューティング

### エラー: `general_name_embedding` が null

**原因**: 商品の埋め込みベクトルが生成されていない

**解決策**:
1. 埋め込み生成スクリプトを実行
2. または、該当商品をスキップ

### クラスタ数が多すぎる/少なすぎる

**調整方法**:
- `N_SMALL_CATEGORIES` を変更（100-200が推奨）
- `N_MEDIUM_CATEGORIES` を変更（20-40が推奨）
- `N_LARGE_CATEGORIES` を変更（5-10が推奨）

---

## 次のステップ

1. ✅ マイグレーション実行
2. ✅ クラスタリング実行
3. 🔲 結果をMASTER_Categories_productに反映
4. 🔲 商品にcategory_idを自動設定
5. 🔲 UIで手動調整
