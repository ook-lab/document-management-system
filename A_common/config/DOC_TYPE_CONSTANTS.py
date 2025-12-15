"""
文書タイプ定数定義

Phase 2: 50種類の書類タイプ分類体系
8つの主要フォルダに分類された包括的なドキュメント分類システム

Usage:
    from A_common.config.DOC_TYPE_CONSTANTS import ALL_DOC_TYPES, DOC_TYPE_METADATA

    # 全ての分類候補を取得
    types = ALL_DOC_TYPES

    # 特定のdoc_typeの詳細情報を取得
    metadata = DOC_TYPE_METADATA['timetable']
    print(metadata['display_name'])  # "時間割"
    print(metadata['folder'])        # "ikuya_school"
"""

from typing import Dict, List, Any

# ============================================================================
# Folder 1: 育哉-学校 (Ikuya School) - 子どもの学校関連書類
# ============================================================================
IKUYA_SCHOOL_TYPES = [
    "timetable",                    # 時間割
    "school_notice",                # 学校のお知らせ
    "homework",                     # 宿題
    "test_exam",                    # 試験・テスト
    "report_card",                  # 通知表・成績表
    "school_event",                 # 学校行事案内
    "parent_teacher_meeting",       # 保護者面談記録
    "class_newsletter",             # 学級通信
]

# ============================================================================
# Folder 2: 仕事 (Work) - ビジネス関連書類
# ============================================================================
WORK_TYPES = [
    #"meeting_minutes",              # 議事録
    "proposal",                     # 提案書
    "business_report",              # 報告書
    #"contract",                     # 契約書
    "invoice",                      # 請求書
    "receipt",                      # 領収書
    "business_card",                # 名刺
    #"presentation",                 # プレゼン資料
    "memo",                         # 業務メモ
]

# ============================================================================
# Folder 3: 家計・金融 (Household Finance) - 金融・家計管理
# ============================================================================
FINANCE_TYPES = [
    "bank_statement",               # 銀行明細
    "credit_card_statement",        # クレジットカード明細
    "utility_bill",                 # 公共料金請求書
    "tax_document",                 # 税金関連書類
    "insurance_policy",             # 保険証券
    "pension_document",             # 年金関連書類
    "investment_statement",         # 投資明細
]

# ============================================================================
# Folder 4: 医療・健康 (Medical/Health) - 医療・健康管理
# ============================================================================
MEDICAL_TYPES = [
    "medical_record",               # 診療記録
    "prescription",                 # 処方箋
    "health_checkup",               # 健康診断結果
    "vaccination_record",           # 予防接種記録
    "medical_bill",                 # 医療費明細
    "insurance_claim",              # 保険請求書
]

# ============================================================================
# Folder 5: 住まい・不動産 (Housing/Real Estate) - 住宅・不動産関連
# ============================================================================
HOUSING_TYPES = [
    "lease_agreement",              # 賃貸契約書
    "property_deed",                # 不動産登記
    "mortgage_document",            # 住宅ローン書類
    "maintenance_record",           # 修繕記録
    "property_tax",                 # 固定資産税
    "condo_management",             # マンション管理組合
]

# ============================================================================
# Folder 6: 法律・行政 (Legal/Administrative) - 法律・行政手続き
# ============================================================================
LEGAL_ADMIN_TYPES = [
    "government_notice",            # 行政通知
    "resident_certificate",         # 住民票
    "family_register",              # 戸籍謄本
    "permit",                       # 許可証・免許証
    "legal_document",               # 法律文書
    "court_document",               # 裁判所書類
]

# ============================================================================
# Folder 7: 趣味・ライフスタイル (Hobbies/Lifestyle) - 趣味・個人活動
# ============================================================================
LIFESTYLE_TYPES = [
    "travel_document",              # 旅行関連書類
    "event_ticket",                 # イベントチケット
    "membership_card",              # 会員証
    "warranty",                     # 保証書
    "manual",                       # 取扱説明書
    "recipe",                       # レシピ
]

# ============================================================================
# Folder 8: その他 (Other) - 分類不能・その他
# ============================================================================
OTHER_TYPES = [
    "personal_letter",              # 個人的な手紙
    "photo",                        # 写真・画像
    "certificate",                  # 各種証明書
    "id_card",                      # 身分証明書
    "other",                        # その他
]

# ============================================================================
# 全ドキュメントタイプの統合リスト (50種類)
# ============================================================================
ALL_DOC_TYPES: List[str] = (
    IKUYA_SCHOOL_TYPES +
    WORK_TYPES +
    FINANCE_TYPES +
    MEDICAL_TYPES +
    HOUSING_TYPES +
    LEGAL_ADMIN_TYPES +
    LIFESTYLE_TYPES +
    OTHER_TYPES
)

# ============================================================================
# フォルダ別マッピング
# ============================================================================
FOLDER_MAPPINGS: Dict[str, List[str]] = {
    "ikuya_school": IKUYA_SCHOOL_TYPES,
    "work": WORK_TYPES,
    "finance": FINANCE_TYPES,
    "medical": MEDICAL_TYPES,
    "housing": HOUSING_TYPES,
    "legal_admin": LEGAL_ADMIN_TYPES,
    "lifestyle": LIFESTYLE_TYPES,
    "other": OTHER_TYPES,
}

# ============================================================================
# ドキュメントタイプメタデータ（詳細情報）
# ============================================================================
DOC_TYPE_METADATA: Dict[str, Dict[str, Any]] = {
    # Folder 1: 育哉-学校
    "timetable": {
        "display_name": "時間割",
        "folder": "ikuya_school",
        "priority": "high",
        "keywords": ["時間割", "時限", "曜日", "授業"],
    },
    "school_notice": {
        "display_name": "学校のお知らせ",
        "folder": "ikuya_school",
        "priority": "high",
        "keywords": ["お知らせ", "通知", "保護者", "学校"],
    },
    "homework": {
        "display_name": "宿題",
        "folder": "ikuya_school",
        "priority": "high",
        "keywords": ["宿題", "課題", "提出"],
    },
    "test_exam": {
        "display_name": "試験・テスト",
        "folder": "ikuya_school",
        "priority": "high",
        "keywords": ["試験", "テスト", "範囲", "点数"],
    },
    "report_card": {
        "display_name": "通知表・成績表",
        "folder": "ikuya_school",
        "priority": "high",
        "keywords": ["通知表", "成績", "評価", "所見"],
    },
    "school_event": {
        "display_name": "学校行事案内",
        "folder": "ikuya_school",
        "priority": "medium",
        "keywords": ["行事", "運動会", "遠足", "修学旅行"],
    },
    "parent_teacher_meeting": {
        "display_name": "保護者面談記録",
        "folder": "ikuya_school",
        "priority": "medium",
        "keywords": ["面談", "保護者会", "懇談"],
    },
    "class_newsletter": {
        "display_name": "学級通信",
        "folder": "ikuya_school",
        "priority": "medium",
        "keywords": ["学級通信", "クラス便り"],
    },

    # Folder 2: 仕事
    "meeting_minutes": {
        "display_name": "議事録",
        "folder": "work",
        "priority": "high",
        "keywords": ["議事録", "会議", "出席者", "議題"],
    },
    "proposal": {
        "display_name": "提案書",
        "folder": "work",
        "priority": "high",
        "keywords": ["提案", "企画", "プロポーザル"],
    },
    "business_report": {
        "display_name": "報告書",
        "folder": "work",
        "priority": "high",
        "keywords": ["報告", "レポート", "業務"],
    },
    "contract": {
        "display_name": "契約書",
        "folder": "work",
        "priority": "high",
        "keywords": ["契約", "契約書", "契約者", "期間"],
    },
    "invoice": {
        "display_name": "請求書",
        "folder": "work",
        "priority": "high",
        "keywords": ["請求書", "金額", "支払", "請求"],
    },
    "receipt": {
        "display_name": "領収書",
        "folder": "work",
        "priority": "medium",
        "keywords": ["領収書", "レシート", "受領"],
    },
    "business_card": {
        "display_name": "名刺",
        "folder": "work",
        "priority": "low",
        "keywords": ["名刺", "連絡先", "会社名"],
    },
    "presentation": {
        "display_name": "プレゼン資料",
        "folder": "work",
        "priority": "medium",
        "keywords": ["プレゼン", "資料", "説明"],
    },
    "memo": {
        "display_name": "業務メモ",
        "folder": "work",
        "priority": "low",
        "keywords": ["メモ", "覚書", "備忘録"],
    },

    # Folder 3: 家計・金融
    "bank_statement": {
        "display_name": "銀行明細",
        "folder": "finance",
        "priority": "high",
        "keywords": ["銀行", "明細", "口座", "残高"],
    },
    "credit_card_statement": {
        "display_name": "クレジットカード明細",
        "folder": "finance",
        "priority": "high",
        "keywords": ["クレジットカード", "カード明細", "利用"],
    },
    "utility_bill": {
        "display_name": "公共料金請求書",
        "folder": "finance",
        "priority": "medium",
        "keywords": ["電気", "ガス", "水道", "料金"],
    },
    "tax_document": {
        "display_name": "税金関連書類",
        "folder": "finance",
        "priority": "high",
        "keywords": ["税金", "確定申告", "所得税", "住民税"],
    },
    "insurance_policy": {
        "display_name": "保険証券",
        "folder": "finance",
        "priority": "high",
        "keywords": ["保険", "証券", "契約", "保障"],
    },
    "pension_document": {
        "display_name": "年金関連書類",
        "folder": "finance",
        "priority": "high",
        "keywords": ["年金", "ねんきん", "定期便"],
    },
    "investment_statement": {
        "display_name": "投資明細",
        "folder": "finance",
        "priority": "medium",
        "keywords": ["投資", "株式", "運用", "資産"],
    },

    # Folder 4: 医療・健康
    "medical_record": {
        "display_name": "診療記録",
        "folder": "medical",
        "priority": "high",
        "keywords": ["診療", "カルテ", "診察"],
    },
    "prescription": {
        "display_name": "処方箋",
        "folder": "medical",
        "priority": "high",
        "keywords": ["処方箋", "薬", "処方"],
    },
    "health_checkup": {
        "display_name": "健康診断結果",
        "folder": "medical",
        "priority": "high",
        "keywords": ["健康診断", "検診", "人間ドック"],
    },
    "vaccination_record": {
        "display_name": "予防接種記録",
        "folder": "medical",
        "priority": "medium",
        "keywords": ["予防接種", "ワクチン", "接種"],
    },
    "medical_bill": {
        "display_name": "医療費明細",
        "folder": "medical",
        "priority": "medium",
        "keywords": ["医療費", "診療費", "明細"],
    },
    "insurance_claim": {
        "display_name": "保険請求書",
        "folder": "medical",
        "priority": "medium",
        "keywords": ["保険請求", "給付金", "請求"],
    },

    # Folder 5: 住まい・不動産
    "lease_agreement": {
        "display_name": "賃貸契約書",
        "folder": "housing",
        "priority": "high",
        "keywords": ["賃貸", "契約", "賃料", "物件"],
    },
    "property_deed": {
        "display_name": "不動産登記",
        "folder": "housing",
        "priority": "high",
        "keywords": ["登記", "不動産", "権利証"],
    },
    "mortgage_document": {
        "display_name": "住宅ローン書類",
        "folder": "housing",
        "priority": "high",
        "keywords": ["住宅ローン", "ローン", "融資"],
    },
    "maintenance_record": {
        "display_name": "修繕記録",
        "folder": "housing",
        "priority": "medium",
        "keywords": ["修繕", "工事", "メンテナンス"],
    },
    "property_tax": {
        "display_name": "固定資産税",
        "folder": "housing",
        "priority": "high",
        "keywords": ["固定資産税", "都市計画税"],
    },
    "condo_management": {
        "display_name": "マンション管理組合",
        "folder": "housing",
        "priority": "medium",
        "keywords": ["管理組合", "管理費", "修繕積立金"],
    },

    # Folder 6: 法律・行政
    "government_notice": {
        "display_name": "行政通知",
        "folder": "legal_admin",
        "priority": "high",
        "keywords": ["行政", "市役所", "区役所", "通知"],
    },
    "resident_certificate": {
        "display_name": "住民票",
        "folder": "legal_admin",
        "priority": "high",
        "keywords": ["住民票", "住所", "世帯"],
    },
    "family_register": {
        "display_name": "戸籍謄本",
        "folder": "legal_admin",
        "priority": "high",
        "keywords": ["戸籍", "謄本", "抄本"],
    },
    "permit": {
        "display_name": "許可証・免許証",
        "folder": "legal_admin",
        "priority": "medium",
        "keywords": ["許可証", "免許", "資格"],
    },
    "legal_document": {
        "display_name": "法律文書",
        "folder": "legal_admin",
        "priority": "high",
        "keywords": ["法律", "訴訟", "弁護士"],
    },
    "court_document": {
        "display_name": "裁判所書類",
        "folder": "legal_admin",
        "priority": "high",
        "keywords": ["裁判所", "裁判", "訴状"],
    },

    # Folder 7: 趣味・ライフスタイル
    "travel_document": {
        "display_name": "旅行関連書類",
        "folder": "lifestyle",
        "priority": "low",
        "keywords": ["旅行", "予約", "チケット", "ホテル"],
    },
    "event_ticket": {
        "display_name": "イベントチケット",
        "folder": "lifestyle",
        "priority": "low",
        "keywords": ["チケット", "イベント", "コンサート"],
    },
    "membership_card": {
        "display_name": "会員証",
        "folder": "lifestyle",
        "priority": "low",
        "keywords": ["会員", "会員証", "メンバーシップ"],
    },
    "warranty": {
        "display_name": "保証書",
        "folder": "lifestyle",
        "priority": "medium",
        "keywords": ["保証書", "保証", "製品"],
    },
    "manual": {
        "display_name": "取扱説明書",
        "folder": "lifestyle",
        "priority": "low",
        "keywords": ["取扱説明書", "マニュアル", "使い方"],
    },
    "recipe": {
        "display_name": "レシピ",
        "folder": "lifestyle",
        "priority": "low",
        "keywords": ["レシピ", "料理", "材料"],
    },

    # Folder 8: その他
    "personal_letter": {
        "display_name": "個人的な手紙",
        "folder": "other",
        "priority": "low",
        "keywords": ["手紙", "はがき", "年賀状"],
    },
    "photo": {
        "display_name": "写真・画像",
        "folder": "other",
        "priority": "low",
        "keywords": ["写真", "画像", "スキャン"],
    },
    "certificate": {
        "display_name": "各種証明書",
        "folder": "other",
        "priority": "medium",
        "keywords": ["証明書", "認定", "修了"],
    },
    "id_card": {
        "display_name": "身分証明書",
        "folder": "other",
        "priority": "high",
        "keywords": ["身分証", "ID", "本人確認"],
    },
    "other": {
        "display_name": "その他",
        "folder": "other",
        "priority": "low",
        "keywords": [],
    },
}

# ============================================================================
# ユーティリティ関数
# ============================================================================

def get_doc_types_by_folder(folder: str) -> List[str]:
    """
    指定されたフォルダに属するdoc_typeのリストを取得

    Args:
        folder: フォルダ名 (例: "ikuya_school", "work")

    Returns:
        doc_typeのリスト
    """
    return FOLDER_MAPPINGS.get(folder, [])


def get_folder_by_doc_type(doc_type: str) -> str:
    """
    指定されたdoc_typeが属するフォルダを取得

    Args:
        doc_type: ドキュメントタイプ

    Returns:
        フォルダ名、見つからない場合は "other"
    """
    metadata = DOC_TYPE_METADATA.get(doc_type)
    if metadata:
        return metadata['folder']
    return "other"


def get_display_name(doc_type: str) -> str:
    """
    指定されたdoc_typeの表示名を取得

    Args:
        doc_type: ドキュメントタイプ

    Returns:
        表示名、見つからない場合はdoc_type自体
    """
    metadata = DOC_TYPE_METADATA.get(doc_type)
    if metadata:
        return metadata['display_name']
    return doc_type


def get_keywords(doc_type: str) -> List[str]:
    """
    指定されたdoc_typeのキーワードリストを取得

    Args:
        doc_type: ドキュメントタイプ

    Returns:
        キーワードのリスト
    """
    metadata = DOC_TYPE_METADATA.get(doc_type)
    if metadata:
        return metadata.get('keywords', [])
    return []


# ============================================================================
# 検証
# ============================================================================

# 全50種類が定義されているか確認
assert len(ALL_DOC_TYPES) == 50, f"Expected 50 doc types, got {len(ALL_DOC_TYPES)}"

# 重複がないか確認
assert len(ALL_DOC_TYPES) == len(set(ALL_DOC_TYPES)), "Duplicate doc types found"

# 全てのdoc_typeにメタデータが定義されているか確認
for doc_type in ALL_DOC_TYPES:
    assert doc_type in DOC_TYPE_METADATA, f"Metadata missing for {doc_type}"

print(f"[OK] 文書タイプ定数: {len(ALL_DOC_TYPES)}種類のdoc_typeを定義しました")
print(f"[OK] フォルダ: {len(FOLDER_MAPPINGS)}個のフォルダに分類されています")
