# ネットスーパースクレイピング - スケジュール管理システム

## 概要

ネットスーパー（楽天西友、東急ストア、ダイエー）の商品データを、**サーバーに負荷をかけずに**定期的に取得するシステムです。

### 主な特徴

1. **カテゴリーごとのスケジュール管理**
   - 実行日とインターバルを個別に設定可能
   - 生鮮食品（肉・魚）など頻繁に更新されるカテゴリーは長めのインターバルに設定

2. **Polite Crawling（礼儀正しいクローリング）**
   - ページ遷移間: 4〜8秒のランダム待機
   - カテゴリー切替時: 15〜30秒のランダム待機
   - 人間らしい挙動でサーバー負荷を最小化

3. **Streamlit管理画面**
   - ブラウザで簡単にスケジュール設定
   - カテゴリーごとの有効/無効切り替え
   - 次回実行日の確認

4. **GitHub Actions自動実行**
   - 毎日午前2時に自動実行
   - 手動実行も可能

---

## セットアップ

### 1. 初回実行（カテゴリー初期化）

最初に、カテゴリー情報を取得して設定ファイルを作成します。

```bash
# 楽天西友の場合
python -m B_ingestion.rakuten_seiyu.process_with_schedule --init

# 東急ストアの場合（実装後）
# python -m B_ingestion.tokyu_store.process_with_schedule --init

# ダイエーの場合（実装後）
# python -m B_ingestion.daiei.process_with_schedule --init
```

これにより、`B_ingestion/common/category_config.json` が作成されます。

### 2. 管理画面でスケジュール設定

Streamlit管理画面を起動します：

```bash
streamlit run B_ingestion/netsuper_category_manager_ui.py
```

ブラウザで `http://localhost:8501` を開き、以下を設定：

- **開始日**: いつから実行を開始するか
- **インターバル（日）**: 何日ごとに実行するか
- **有効/無効**: チェックを外すと実行されない

#### 実行日の計算ルール

1. **開始日が未来の場合**
   - 開始日が1回目の実行日
   - 2回目以降は、前回実行日 + インターバル日数

2. **開始日が今日または過去の場合**
   - まだ一度も実行していない場合: 開始日 + インターバル日数が1回目の実行日
   - すでに実行済みの場合: 前回実行日 + インターバル日数が次回実行日

#### 推奨設定例

| カテゴリー | インターバル | 理由 |
|----------|----------|------|
| 野菜・果物 | 3日 | 価格変動が頻繁 |
| 肉・魚 | 7日 | データ量が多い、商品入れ替わりが激しい |
| 調味料・缶詰 | 30日 | 価格が安定している |
| 日用品 | 14日 | あまり変動しない |

### 3. 通常実行

スケジュールに基づいて実行します：

```bash
python -m B_ingestion.rakuten_seiyu.process_with_schedule
```

### 4. GitHub Actions設定

GitHubリポジトリの `Settings > Secrets and variables > Actions` に以下を追加：

```
RAKUTEN_ID              # 楽天西友のログインID
RAKUTEN_PASSWORD        # 楽天西友のパスワード
TOKYU_STORE_LOGIN_ID    # 東急ストアのログインID（メールアドレス）
TOKYU_STORE_PASSWORD    # 東急ストアのパスワード
DAIEI_LOGIN_ID          # ダイエーのログインID
DAIEI_PASSWORD          # ダイエーのパスワード
SUPABASE_URL            # Supabase URL
SUPABASE_SERVICE_ROLE_KEY  # Supabase Service Role Key
```

設定後、毎日午前2時に自動実行されます。

---

## ファイル構成

```
B_ingestion/
├── common/
│   ├── category_manager.py        # カテゴリースケジュール管理ロジック
│   └── category_config.json       # カテゴリー設定（自動生成）
├── netsuper_category_manager_ui.py # Streamlit管理画面
├── rakuten_seiyu/
│   ├── process_with_schedule.py   # スケジュール対応スクリプト
│   └── ...
├── tokyu_store/
│   └── ...
└── daiei/
    └── ...
```

---

## 待機時間の詳細

### ページ遷移間の待機

```python
wait_time = random.uniform(4.0, 8.0)  # 4〜8秒のランダム
await asyncio.sleep(wait_time)
```

### カテゴリー切替時の待機

```python
wait_time = random.uniform(15.0, 30.0)  # 15〜30秒のランダム
await asyncio.sleep(wait_time)
```

### エラー発生時の待機

```python
await asyncio.sleep(60)  # 1分待機
```

---

## トラブルシューティング

### カテゴリーが設定されていない

```bash
# 初期化コマンドを実行
python -m B_ingestion.rakuten_seiyu.process_with_schedule --init
```

### 設定ファイルを削除したい

管理画面の「設定」タブから「設定ファイルを削除（初期化）」ボタンをクリックするか、
手動で削除：

```bash
rm B_ingestion/common/category_config.json
```

### 特定のカテゴリーだけ無効にしたい

管理画面で該当カテゴリーの「有効」チェックを外して保存してください。

---

## 注意事項

### サーバーへの配慮

- **必ず待機時間を設定する**: 連続アクセスはサーバーに負荷をかけます
- **深夜帯に実行**: アクセスが少ない時間帯（午前2時）に実行
- **エラー時は即座にリトライしない**: 十分な待機時間を確保

### 利用規約の遵守

- スクレイピングは利用規約で禁止されている場合があります
- 私的利用の範囲で、サーバーに負荷をかけないよう注意してください
- データの再配布や商用利用は絶対に行わないでください

---

## 今後の拡張

- [ ] 東急ストア・ダイエーのスケジュール対応スクリプト作成
- [ ] エラー通知機能（LINEやメール）
- [ ] 実行ログの可視化
- [ ] カテゴリーの自動優先度調整（アクセス頻度に基づく）

---

**作成日**: 2025-12-23
**作成者**: Claude Code
