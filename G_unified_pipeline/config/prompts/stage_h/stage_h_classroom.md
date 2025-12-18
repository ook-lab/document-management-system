# Stage H: 構造化（Google Classroom ドキュメント）

Google Classroom のドキュメントテキストから、重要な情報を構造化して抽出してください。

## 抽出する情報

1. **基本情報**
   - 投稿日時
   - 投稿者
   - 件名

2. **内容分類**
   - タイプ（課題/お知らせ/資料/質問）
   - 期限（課題の場合）
   - 優先度

3. **関連情報**
   - 添付ファイル名
   - リンク
   - 関連する授業・科目

## 出力形式

```json
{
  "post_date": "2025-03-15",
  "author": "先生名",
  "subject": "投稿件名",
  "post_type": "assignment",
  "deadline": "2025-03-20",
  "priority": "high",
  "attachments": ["ファイル名"],
  "related_class": "数学"
}
```
