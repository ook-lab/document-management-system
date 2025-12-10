"""
Workspace定義（意味的な分類） - 動的生成版

user_context.yamlから家族構成に基づいてワークスペースを動的に生成します。
個人名や組織名のハードコードを排除し、完全に汎用化されています。

source_type: 技術的な出所（gmail, drive）
file_type: ファイル形式（pdf, excel, email）
workspace: 意味的な分類（★メインの分類軸）
"""

from typing import List, Dict
from config.yaml_loader import load_user_context, get_family_info


class WorkspaceManager:
    """動的ワークスペース管理クラス"""

    def __init__(self):
        """user_context.yamlからワークスペースを動的生成"""
        self._workspaces = {}
        self._label_mapping = {}
        self._generate_workspaces()

    def _generate_workspaces(self):
        """user_context.yamlからワークスペースを生成"""
        context = load_user_context()
        family = get_family_info()
        workspace_config = context.get("workspaces", {})

        # 子供関連のワークスペースを生成
        for child_ws in workspace_config.get("children", []):
            person = child_ws.get("person", "").upper()
            for category in child_ws.get("categories", []):
                cat_id = category.get("id", "")
                workspace_id = f"{person}_{cat_id}"
                display_name = category.get("display_name", "")

                # ワークスペースを登録
                self._workspaces[workspace_id] = {
                    "id": workspace_id,
                    "display_name": display_name,
                    "person": person.lower(),
                    "category": cat_id
                }

                # ラベルマッピングを登録
                for label in category.get("labels", []):
                    self._label_mapping[label] = workspace_id

                # 「育也/学校」形式のラベルも登録
                person_display = self._get_person_display_name(person.lower(), family)
                if person_display:
                    person_label = f"{person_display}/{display_name.replace('関連', '').replace('メール', '')}"
                    self._label_mapping[person_label] = workspace_id

                # 英字ID形式も登録（例: IKUYA_SCHOOL）
                english_label = f"{person}_{cat_id}"
                self._label_mapping[english_label] = workspace_id

        # 家族共通ワークスペースを生成
        for shared_ws in workspace_config.get("family_shared", []):
            ws_id = shared_ws.get("id", "")
            self._workspaces[ws_id] = {
                "id": ws_id,
                "display_name": shared_ws.get("display_name", ""),
                "category": "family_shared"
            }
            for label in shared_ws.get("labels", []):
                self._label_mapping[label] = ws_id

        # 個人ワークスペースを生成
        for personal_ws in workspace_config.get("personal", []):
            person = personal_ws.get("person", "").upper()
            ws_id_suffix = personal_ws.get("id", "")
            ws_id = f"{person}_{ws_id_suffix}"

            self._workspaces[ws_id] = {
                "id": ws_id,
                "display_name": personal_ws.get("display_name", ""),
                "person": person.lower(),
                "category": "personal"
            }
            for label in personal_ws.get("labels", []):
                self._label_mapping[label] = ws_id

        # 一般ワークスペースを生成
        for general_ws in workspace_config.get("general", []):
            ws_id = general_ws.get("id", "")
            self._workspaces[ws_id] = {
                "id": ws_id,
                "display_name": general_ws.get("display_name", ""),
                "category": "general"
            }
            for label in general_ws.get("labels", []):
                self._label_mapping[label] = ws_id

    def _get_person_display_name(self, person_id: str, family: dict) -> str:
        """人物IDから表示名を取得"""
        # 父親
        if family.get("father", {}).get("name") == person_id:
            return family["father"].get("display_name", "")

        # 母親
        if family.get("mother", {}).get("name") == person_id:
            return family["mother"].get("display_name", "")

        # 子供たち
        for child in family.get("children_list", []):
            if child.get("name") == person_id:
                return child.get("display_name", "")

        return ""

    def all_workspaces(self) -> List[str]:
        """全ワークスペースIDのリストを返す"""
        return list(self._workspaces.keys())

    def get_workspace_from_label(self, label: str) -> str:
        """
        Gmailラベルからワークスペースを判定

        Args:
            label: Gmailのラベル名

        Returns:
            workspace ID（見つからない場合はDM_MAIL）
        """
        return self._label_mapping.get(label, "DM_MAIL")

    def get_workspace_info(self, workspace_id: str) -> Dict:
        """ワークスペース情報を取得"""
        return self._workspaces.get(workspace_id, {})


# グローバルインスタンス（シングルトン）
_workspace_manager = None


def get_workspace_manager() -> WorkspaceManager:
    """WorkspaceManagerのシングルトンインスタンスを取得"""
    global _workspace_manager
    if _workspace_manager is None:
        _workspace_manager = WorkspaceManager()
    return _workspace_manager


# 後方互換性のためのWorkspaceクラス（動的生成）
class Workspace:
    """
    後方互換性のためのWorkspace定数クラス
    実際の値はuser_context.yamlから動的に生成されます
    """

    def __init__(self):
        """動的に属性を生成"""
        manager = get_workspace_manager()
        for ws_id in manager.all_workspaces():
            setattr(self, ws_id, ws_id)

    @classmethod
    def all_workspaces(cls):
        """全workspace一覧を取得"""
        return get_workspace_manager().all_workspaces()


# インスタンス化して動的属性を生成
Workspace = Workspace()


# 後方互換性のための関数
def get_workspace_from_gmail_label(label: str) -> str:
    """
    Gmailラベルからworkspaceを判定

    Args:
        label: Gmailのラベル名

    Returns:
        workspace名
    """
    return get_workspace_manager().get_workspace_from_label(label)


# 後方互換性のための辞書（非推奨、get_workspace_from_gmail_labelを使用してください）
GMAIL_LABEL_TO_WORKSPACE = {}


def _init_legacy_mapping():
    """レガシーマッピング辞書を初期化（後方互換性用）"""
    global GMAIL_LABEL_TO_WORKSPACE
    manager = get_workspace_manager()
    GMAIL_LABEL_TO_WORKSPACE = {
        label: manager.get_workspace_from_label(label)
        for label in manager._label_mapping.keys()
    }


# 初期化
_init_legacy_mapping()
