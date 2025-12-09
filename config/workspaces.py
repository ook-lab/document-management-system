"""
Workspace定義（意味的な分類）

source_type: 技術的な出所（gmail, drive）
file_type: ファイル形式（pdf, excel, email）
workspace: 意味的な分類（★メインの分類軸）
"""

# Workspace定数
class Workspace:
    """Workspace（意味的な分類）の定義"""

    # 育也関連
    IKUYA_SCHOOL = "IKUYA_SCHOOL"       # 育也の学校関連
    IKUYA_JUKU = "IKUYA_JUKU"           # 育也の塾関連
    IKUYA_EXAM = "IKUYA_EXAM"           # 育也の受験関連

    # 恵麻関連
    EMA_SCHOOL = "EMA_SCHOOL"           # 恵麻の学校関連

    # 家庭関連
    HOME_LIVING = "HOME_LIVING"         # 家庭・生活関連
    HOME_COOKING = "HOME_COOKING"       # 料理・レシピ関連

    # 芳紀個人
    YOSHINORI_PRIVATE_FOLDER = "YOSHINORI_PRIVATE_FOLDER"  # 芳紀個人フォルダ

    # 仕事関連
    BUSINESS_WORK = "BUSINESS_WORK"     # 仕事全般

    # メール分類
    IKUYA_MAIL = "IKUYA_MAIL"           # 育也宛メール
    EMA_MAIL = "EMA_MAIL"               # 恵麻宛メール
    WORK_MAIL = "WORK_MAIL"             # 仕事メール
    DM_MAIL = "DM_MAIL"                 # DM・広告メール
    JOB_MAIL = "JOB_MAIL"               # 求人・転職メール
    MONEY_MAIL = "MONEY_MAIL"           # 金融・決済メール

    @classmethod
    def all_workspaces(cls):
        """全workspace一覧を取得"""
        return [
            cls.IKUYA_SCHOOL,
            cls.IKUYA_JUKU,
            cls.IKUYA_EXAM,
            cls.EMA_SCHOOL,
            cls.HOME_LIVING,
            cls.HOME_COOKING,
            cls.YOSHINORI_PRIVATE_FOLDER,
            cls.BUSINESS_WORK,
            cls.IKUYA_MAIL,
            cls.EMA_MAIL,
            cls.WORK_MAIL,
            cls.DM_MAIL,
            cls.JOB_MAIL,
            cls.MONEY_MAIL,
        ]


# Gmailラベル → Workspace マッピング
GMAIL_LABEL_TO_WORKSPACE = {
    # 育也関連
    "IKUYA_SCHOOL": Workspace.IKUYA_SCHOOL,
    "IKUYA_JUKU": Workspace.IKUYA_JUKU,
    "IKUYA_EXAM": Workspace.IKUYA_EXAM,
    "育也/学校": Workspace.IKUYA_SCHOOL,
    "育也/塾": Workspace.IKUYA_JUKU,
    "育也/受験": Workspace.IKUYA_EXAM,

    # 恵麻関連
    "EMA_SCHOOL": Workspace.EMA_SCHOOL,
    "恵麻/学校": Workspace.EMA_SCHOOL,

    # 家庭関連
    "HOME": Workspace.HOME_LIVING,
    "COOKING": Workspace.HOME_COOKING,
    "家庭": Workspace.HOME_LIVING,
    "料理": Workspace.HOME_COOKING,

    # 仕事関連
    "WORK": Workspace.BUSINESS_WORK,
    "仕事": Workspace.BUSINESS_WORK,

    # メール分類
    "DM": Workspace.DM_MAIL,
    "JOB": Workspace.JOB_MAIL,
    "MONEY": Workspace.MONEY_MAIL,
    "広告": Workspace.DM_MAIL,
    "求人": Workspace.JOB_MAIL,
    "金融": Workspace.MONEY_MAIL,

    # デフォルト（TESTラベルなど）
    "TEST": Workspace.DM_MAIL,  # テスト用はDM扱い
}


def get_workspace_from_gmail_label(label: str) -> str:
    """
    Gmailラベルからworkspaceを判定

    Args:
        label: Gmailのラベル名

    Returns:
        workspace名
    """
    return GMAIL_LABEL_TO_WORKSPACE.get(label, Workspace.DM_MAIL)
