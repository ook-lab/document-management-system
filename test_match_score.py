"""
類似度計算のテスト
"""
import re

def _extract_keywords(query: str):
    """クエリからキーワードを抽出"""
    keywords = []

    bracket_matches = re.findall(r'[（(]([^）)]+)[）)]', query)
    keywords.extend(bracket_matches)

    bracket_words = re.findall(r'[\w一-龠ぁ-んァ-ヶー]+[（(][^）)]+[）)]', query)
    keywords.extend(bracket_words)

    words = re.findall(r'[一-龠ぁ-んァ-ヶー]{3,}', query)
    keywords.extend(words)

    return list(set(keywords))

def _calculate_keyword_match_score(file_name: str, keywords: list, query: str) -> float:
    """file_name とクエリの一致度を計算"""
    normalized_query = query.replace('？', '').replace('?', '').replace('の内容は', '').replace('内容', '').strip()

    # 完全一致（括弧付き単語がそのまま含まれる）
    for kw in keywords:
        if '（' in kw or '(' in kw:
            if kw in file_name:
                print(f"  ✅ 完全一致: '{kw}' in '{file_name}' → 1.0")
                return 1.0

    # マッチしたキーワードの数をカウント
    matched_keywords = []
    for kw in keywords:
        if kw in file_name:
            matched_keywords.append(kw)

    if not matched_keywords:
        print(f"  ❌ マッチなし → 0.0")
        return 0.0

    match_count = len(matched_keywords)
    total_keywords = len(keywords)

    print(f"  マッチ: {matched_keywords} ({match_count}/{total_keywords})")

    if match_count == total_keywords:
        return 0.95
    elif match_count >= 2:
        return 0.90
    else:
        return 0.85

# テスト
query = "学年通信（29）の内容は？"
keywords = _extract_keywords(query)
print(f"クエリ: {query}")
print(f"抽出キーワード: {keywords}\n")

test_files = [
    "学年通信 (1).pdf",
    "学年通信（３）.pdf",
    "学年通信（29）.pdf",
]

for file_name in test_files:
    print(f"ファイル: {file_name}")
    score = _calculate_keyword_match_score(file_name, keywords, query)
    print(f"  → スコア: {score}\n")
