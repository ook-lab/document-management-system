"""
キーワード抽出のテスト
"""
import re

def _extract_keywords(query: str):
    """
    クエリから重要なキーワードを抽出
    """
    keywords = []

    # 括弧内の文字を抽出（例：「学年通信（29）」→「29」「学年通信」）
    bracket_matches = re.findall(r'[（(]([^）)]+)[）)]', query)
    keywords.extend(bracket_matches)

    # 括弧を含む単語全体を抽出（例：「学年通信（29）」）
    bracket_words = re.findall(r'[\w一-龠ぁ-んァ-ヶー]+[（(][^）)]+[）)]', query)
    keywords.extend(bracket_words)

    # 名詞的な単語を抽出（ひらがな・カタカナ・漢字が3文字以上）
    words = re.findall(r'[一-龠ぁ-んァ-ヶー]{3,}', query)
    keywords.extend(words)

    # 重複削除して返す
    return list(set(keywords))

# テスト
test_queries = [
    "学年通信（29）の内容は？",
    "12/4の時間割は？",
    "今週の予定を教えて"
]

for query in test_queries:
    keywords = _extract_keywords(query)
    print(f"\nクエリ: {query}")
    print(f"抽出キーワード: {keywords}")
