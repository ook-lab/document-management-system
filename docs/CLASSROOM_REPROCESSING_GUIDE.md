# Google Classroom ドキュメント再処理ガイド

## 概要

Google Classroomから取り込まれたドキュメントを、既存の2段階処理パイプライン（Gemini分類 + Claude詳細抽出）で完全に再処理するスクリプトです。

## 背景

Google Classroomから直接取り込まれたドキュメントは、以下の問題がある場合があります：

- ❌ `full_text` が空（PDF/画像からテキスト抽出されていない）
- ❌ `embedding` が空（ベクトル化されていない）
- ❌ `metadata` が簡易的（構造化データがない）
- ❌ `workspace` が `ikuya_classroom`（正しくは `IKUYA_SCHOOL`）
- ❌ `doc_type` が不適切（既存スキーマに存在しない）

このスクリプトは、これらの問題を解決します。

## 処理内容

1. **対象ドキュメントの取得**: `workspace='ikuya_classroom'` のドキュメントを検索
2. **ファイルIDの抽出**: `metadata->original_file_id` からGoogle Drive上のファイルを特定
3. **2段階処理の実行**:
   - **Stage 1**: Gemini 1.5 Flashで文書分類とworkspace判定
   - **Stage 2**: Claude 3.5 Sonnetで詳細なメタデータ抽出
4. **データ生成**:
   - OCRによる `full_text` 抽出
   - YAMLスキーマに基づく構造化 `metadata` 生成
   - Gemini Embeddingによるベクトル化
5. **workspace修正**: `IKUYA_SCHOOL` に変更
6. **古いレコード削除**: 新しいレコードが作成されるため、古いレコードは自動削除

## 使い方

### 1. Dry-run（確認のみ）

実際の処理を行わず、何が処理されるかを確認します。

```bash
python reprocess_classroom_documents.py --dry-run
```

**出力例**:
```
[1/3] 処理中...
  ファイル: 学年通信（30）.pdf
  ファイルID: 1dUiCFI-7nWFF4OUEwo_puAhx6GtZVevU
  現在のworkspace: ikuya_classroom
  現在のdoc_type: 2025_5B
  → 新しいworkspace: IKUYA_SCHOOL
```

### 2. 実際の再処理を実行

```bash
python reprocess_classroom_documents.py
```

確認プロンプトが表示されます：
```
処理を開始しますか？ (y/N):
```

`y` を入力すると処理が開始されます。

### 3. 件数を制限して実行

デフォルトでは最大100件を処理します。制限を変更する場合：

```bash
python reprocess_classroom_documents.py --limit=10
```

### 4. Dry-run + 件数制限

```bash
python reprocess_classroom_documents.py --dry-run --limit=5
```

## オプション

| オプション | 説明 | デフォルト |
|----------|------|----------|
| `--dry-run` または `-n` | 確認のみ（実際の処理は行わない） | False |
| `--limit=N` | 処理する最大件数 | 100 |

## 処理フロー詳細

```
1. Google Classroom ドキュメント取得
   ↓
2. metadata->original_file_id 抽出
   ↓
3. Google Drive からファイルダウンロード
   ↓
4. Stage 1: Gemini 分類
   - doc_type 判定
   - workspace 判定（→ IKUYA_SCHOOL）
   - 要約生成
   ↓
5. Stage 2: Claude 詳細抽出
   - YAMLスキーマに基づくメタデータ抽出
   - weekly_schedule, text_blocks 等の構造化
   ↓
6. テキスト抽出 & ベクトル化
   - full_text 生成
   - Gemini Embedding で embedding 生成
   ↓
7. Supabase に保存
   - 新しいレコード作成
   - 古いレコード削除
```

## 注意事項

### 1. 認証情報の確認

以下のファイルが必要です：
- `.env`: Supabase、Gemini API、Anthropic APIの認証情報
- `./credentials/google_credentials.json`: Google Drive API のサービスアカウントキー

### 2. コスト

各ドキュメントの処理で以下のAPI呼び出しが発生します：
- **Gemini API**: 分類（Flash）+ Embedding
- **Anthropic API**: 詳細抽出（Claude 3.5 Sonnet）

3件のドキュメントなら数円程度ですが、大量に処理する場合はコストに注意してください。

### 3. 処理時間

1件あたり約10〜30秒かかります（ファイルサイズとページ数による）。

### 4. 古いレコードの削除

新しいレコードが作成されると、**古いレコード（`ikuya_classroom`）は自動的に削除**されます。
元に戻すことはできないため、事前に必ずdry-runで確認してください。

## トラブルシューティング

### ファイルIDが見つからない

```
ファイルIDが見つかりません: example.pdf
```

**原因**: `metadata->original_file_id` が設定されていない

**解決策**: 手動でGoogle DriveのファイルIDを`metadata`に追加するか、元のClassroom取り込みスクリプトを修正

### Google Drive API エラー

```
File not found: 1dUiCFI...
```

**原因**: サービスアカウントにファイルへのアクセス権限がない

**解決策**: Google Driveでファイルをサービスアカウントに共有、または共有ドライブに配置

### スキーマ検証エラー

```
スキーマ検証エラー: field 'xxx' is required
```

**原因**: YAMLスキーマに必須フィールドが不足

**解決策**: `config/yaml/DOC_TYPE_SCHEMAS.yaml`を確認し、スキーマを修正

## 実行ログ例

```bash
$ python reprocess_classroom_documents.py --dry-run

[INFO] Google Classroom ドキュメント再処理スクリプト
[WARNING] DRY RUN モード: 実際の処理は行いません
[INFO] Google Classroomドキュメントを取得中...
[INFO] 3件のドキュメントを取得しました

処理予定: 3件
Workspace: ikuya_classroom → IKUYA_SCHOOL

[1/3] 処理中...
  ファイル: 学年通信（30）.pdf
  ファイルID: 1dUiCFI-7nWFF4OUEwo_puAhx6GtZVevU
  現在のworkspace: ikuya_classroom
  現在のdoc_type: 2025_5B
  → 新しいworkspace: IKUYA_SCHOOL

[2/3] 処理中...
  ファイル: 中学受験12月号.pdf
  ファイルID: 16S71tvaoivFmSQifc7bDhIRQI9lePW7s
  現在のworkspace: ikuya_classroom
  現在のdoc_type: 2025_5B
  → 新しいworkspace: IKUYA_SCHOOL

[3/3] 処理中...
  ファイル: IMG_1535.jpg
  ファイルID: 1i7a5KYMcofV1sixY4BYtTMDRKC5b4R3M
  現在のworkspace: ikuya_classroom
  現在のdoc_type: 2025_5B
  → 新しいworkspace: IKUYA_SCHOOL

[INFO] 再処理完了
[INFO] 成功: 0件
[INFO] 失敗: 0件
[INFO] 合計: 3件
```

## 関連ドキュメント

- [Two-Stage Ingestion Pipeline](../pipelines/two_stage_ingestion.py): 既存の処理パイプライン
- [Workspace定義](../config/workspaces.py): Workspace定数の定義
- [DOC_TYPE_SCHEMAS.yaml](../config/yaml/DOC_TYPE_SCHEMAS.yaml): 文書タイプのスキーマ定義
