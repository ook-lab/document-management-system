"""
複合信頼度計算モジュール (Confidence Calculator)

目的: AIの確信度に加え、キーワードマッチング、メタデータ充足率、
     データ整合性を組み合わせた総合的な品質スコア (total_confidence) を算出

設計: Phase 2 (Track 1) - 複合指標によるConfidence計算
     AUTO_INBOX_COMPLETE_v3.0.md の「2.1.1 複合指標によるConfidence計算」に準拠

加重平均式:
    total_confidence = (model_confidence * 0.4) +
                      (keyword_match_score * 0.3) +
                      (metadata_completeness * 0.2) +
                      (data_consistency * 0.1)
"""

import re
from typing import Dict, Any, List, Optional
from loguru import logger


# 文書タイプ別の必須キーワード定義
REQUIRED_KEYWORDS = {
    'timetable': ['時間割', '時限', '曜日', '授業', 'クラス', '学年'],
    'notice': ['お知らせ', '通知', '連絡', '保護者', '学校'],
    'homework': ['宿題', '課題', '提出', '期限'],
    'test_exam': ['試験', 'テスト', '範囲', '日程', '点数'],
    'report_card': ['通知表', '成績', '評価', '所見'],
    'invoice': ['請求書', '金額', '合計', '支払'],
    'contract': ['契約', '契約書', '契約者', '期間'],
    'meeting_minutes': ['議事録', '会議', '出席者', '議題'],
    'receipt': ['領収書', 'レシート', '金額', '日付'],
}

# 文書タイプ別の必須メタデータフィールド
REQUIRED_METADATA_FIELDS = {
    'timetable': ['grade', 'period'],
    'notice': ['title', 'date', 'from'],
    'homework': ['subject', 'due_date', 'description'],
    'test_exam': ['subject', 'date', 'scope'],
    'report_card': ['student_name', 'grade', 'semester'],
    'invoice': ['amount', 'due_date', 'invoice_number'],
    'contract': ['party_a', 'party_b', 'start_date', 'end_date'],
    'meeting_minutes': ['meeting_date', 'attendees', 'agenda'],
    'receipt': ['amount', 'date', 'store_name'],
}


def calculate_keyword_match_score(text: str, doc_type: str) -> float:
    """
    テキストと文書タイプに基づき、必須キーワードの一致度を計算

    Args:
        text: 抽出されたテキスト
        doc_type: 文書タイプ

    Returns:
        キーワード一致スコア (0.0 ~ 1.0)
    """
    if not text or not doc_type:
        return 0.0

    # doc_typeに対応するキーワードリストを取得
    required_keywords = REQUIRED_KEYWORDS.get(doc_type, [])

    if not required_keywords:
        # キーワード定義がない場合は中立スコア
        logger.debug(f"doc_type '{doc_type}' にキーワード定義がありません")
        return 0.5

    # テキストを正規化（小文字化、空白除去）
    normalized_text = text.lower()

    # 一致したキーワードの数をカウント
    matched_count = 0
    for keyword in required_keywords:
        if keyword.lower() in normalized_text:
            matched_count += 1

    # 一致率を計算
    match_ratio = matched_count / len(required_keywords)

    logger.debug(f"キーワードマッチ: {matched_count}/{len(required_keywords)} = {match_ratio:.2f}")

    return match_ratio


def calculate_metadata_completeness(metadata: Dict[str, Any], doc_type: str) -> float:
    """
    抽出されたメタデータが、文書タイプごとの必須フィールドをどれだけ満たしているかを計算

    Args:
        metadata: 抽出されたメタデータ
        doc_type: 文書タイプ

    Returns:
        メタデータ充足率 (0.0 ~ 1.0)
    """
    if not metadata or not doc_type:
        return 0.0

    # doc_typeに対応する必須フィールドリストを取得
    required_fields = REQUIRED_METADATA_FIELDS.get(doc_type, [])

    if not required_fields:
        # 必須フィールド定義がない場合は中立スコア
        logger.debug(f"doc_type '{doc_type}' に必須フィールド定義がありません")
        return 0.5

    # 存在するフィールドの数をカウント
    present_count = 0
    for field in required_fields:
        value = metadata.get(field)

        # フィールドが存在し、かつ空でない場合
        if value is not None and value != "" and value != []:
            present_count += 1

    # 充足率を計算
    completeness_ratio = present_count / len(required_fields)

    logger.debug(f"メタデータ充足率: {present_count}/{len(required_fields)} = {completeness_ratio:.2f}")

    return completeness_ratio


def calculate_data_consistency(metadata: Dict[str, Any], doc_type: str) -> float:
    """
    メタデータの整合性をチェック

    Args:
        metadata: 抽出されたメタデータ
        doc_type: 文書タイプ

    Returns:
        データ整合性スコア (0.0 ~ 1.0)
    """
    if not metadata:
        return 0.0

    consistency_score = 1.0
    issues = []

    # 日付フォーマットの整合性チェック
    date_fields = ['date', 'due_date', 'start_date', 'end_date', 'meeting_date', 'document_date']
    for field in date_fields:
        if field in metadata:
            date_value = metadata[field]
            if isinstance(date_value, str) and date_value:
                # 日付フォーマットの簡易チェック (YYYY-MM-DD, YYYY/MM/DD, YYYY年MM月DD日)
                date_patterns = [
                    r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',  # YYYY-MM-DD or YYYY/MM/DD
                    r'\d{4}年\d{1,2}月\d{1,2}日',   # YYYY年MM月DD日
                ]
                if not any(re.search(pattern, date_value) for pattern in date_patterns):
                    issues.append(f"{field}の日付フォーマットが不正: {date_value}")
                    consistency_score -= 0.2

    # 数値フィールドの整合性チェック
    numeric_fields = ['amount', 'score', 'grade_number']
    for field in numeric_fields:
        if field in metadata:
            value = metadata[field]
            if isinstance(value, str):
                # 数値を含むかチェック
                if not re.search(r'\d+', value):
                    issues.append(f"{field}が数値を含んでいない: {value}")
                    consistency_score -= 0.15

    # リスト型フィールドの整合性チェック
    list_fields = ['attendees', 'tags', 'subjects']
    for field in list_fields:
        if field in metadata:
            value = metadata[field]
            if not isinstance(value, list):
                issues.append(f"{field}がリスト型ではない: {type(value)}")
                consistency_score -= 0.15
            elif isinstance(value, list) and len(value) == 0:
                # 空リストは軽微な問題
                consistency_score -= 0.05

    # 学年フォーマットの整合性チェック (timetable, report_card など)
    if 'grade' in metadata:
        grade_value = metadata['grade']
        if isinstance(grade_value, str):
            # "小学X年", "中学X年", "高校X年" のパターンチェック
            if not re.match(r'(小学|中学|高校)[1-6]年', grade_value):
                issues.append(f"学年フォーマットが不正: {grade_value}")
                consistency_score -= 0.2

    # スコアは0.0以下にはならない
    consistency_score = max(0.0, consistency_score)

    if issues:
        logger.debug(f"データ整合性の問題検出: {len(issues)}件")
        for issue in issues:
            logger.debug(f"  - {issue}")

    logger.debug(f"データ整合性スコア: {consistency_score:.2f}")

    return consistency_score


def calculate_total_confidence(
    model_confidence: float,
    text: str,
    metadata: Dict[str, Any],
    doc_type: str
) -> Dict[str, float]:
    """
    複合指標による総合信頼度を計算

    Args:
        model_confidence: AIモデルの確信度 (0.0 ~ 1.0)
        text: 抽出されたテキスト
        metadata: 抽出されたメタデータ
        doc_type: 文書タイプ

    Returns:
        各スコアと総合信頼度を含む辞書:
        {
            'model_confidence': float,
            'keyword_match_score': float,
            'metadata_completeness': float,
            'data_consistency': float,
            'total_confidence': float
        }
    """
    # 各指標を計算
    keyword_score = calculate_keyword_match_score(text, doc_type)
    completeness_score = calculate_metadata_completeness(metadata, doc_type)
    consistency_score = calculate_data_consistency(metadata, doc_type)

    # 加重平均で総合信頼度を計算
    total_confidence = (
        model_confidence * 0.4 +
        keyword_score * 0.3 +
        completeness_score * 0.2 +
        consistency_score * 0.1
    )

    # 結果をログ出力
    logger.info("=" * 60)
    logger.info("📊 複合信頼度計算結果")
    logger.info(f"  モデル確信度 (40%):        {model_confidence:.3f}")
    logger.info(f"  キーワード一致 (30%):      {keyword_score:.3f}")
    logger.info(f"  メタデータ充足率 (20%):    {completeness_score:.3f}")
    logger.info(f"  データ整合性 (10%):        {consistency_score:.3f}")
    logger.info(f"  ─────────────────────────")
    logger.info(f"  総合信頼度:                {total_confidence:.3f}")
    logger.info("=" * 60)

    return {
        'model_confidence': model_confidence,
        'keyword_match_score': keyword_score,
        'metadata_completeness': completeness_score,
        'data_consistency': consistency_score,
        'total_confidence': total_confidence
    }


def get_confidence_level(total_confidence: float) -> str:
    """
    総合信頼度からレベル判定

    Args:
        total_confidence: 総合信頼度 (0.0 ~ 1.0)

    Returns:
        信頼度レベル ("very_high", "high", "medium", "low", "very_low")
    """
    if total_confidence >= 0.9:
        return "very_high"
    elif total_confidence >= 0.75:
        return "high"
    elif total_confidence >= 0.6:
        return "medium"
    elif total_confidence >= 0.4:
        return "low"
    else:
        return "very_low"
