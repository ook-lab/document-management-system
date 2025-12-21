"""
カテゴリツリー編集UI
階層構造のカテゴリを管理
"""

import streamlit as st
import pandas as pd
from typing import List, Dict, Optional

from A_common.database.client import DatabaseClient


class CategoryTreeUI:
    """カテゴリツリー編集画面"""

    def __init__(self):
        self.db = DatabaseClient(use_service_role=True)

    def fetch_categories(self) -> List[Dict]:
        """全カテゴリを取得"""
        result = self.db.client.table('60_ms_categories').select(
            '*'
        ).order('name').execute()

        return result.data

    def build_tree(self, categories: List[Dict], parent_id: Optional[str] = None, level: int = 0) -> List[Dict]:
        """階層構造を構築"""
        tree = []
        for cat in categories:
            if cat.get("parent_id") == parent_id:
                tree.append({
                    "id": cat["id"],
                    "name": cat["name"],
                    "level": level,
                    "is_expense": cat.get("is_expense", True),
                    "parent_id": parent_id
                })
                # 子カテゴリを再帰的に追加
                tree.extend(self.build_tree(categories, cat["id"], level + 1))

        return tree

    def add_category(self, name: str, parent_id: Optional[str], is_expense: bool):
        """新規カテゴリを追加"""
        self.db.client.table('60_ms_categories').insert({
            "name": name,
            "is_expense": is_expense,
            "parent_id": parent_id
        }).execute()

        st.success(f"カテゴリ「{name}」を追加しました")

    def delete_category(self, category_id: str):
        """カテゴリを削除"""
        self.db.client.table('60_ms_categories').delete().eq(
            'id', category_id
        ).execute()

        st.success("カテゴリを削除しました")

    def run(self):
        """UIメイン処理"""
        st.title("🌳 カテゴリツリー編集")
        st.markdown("カテゴリの階層構造を管理します。")

        # カテゴリ取得
        categories = self.fetch_categories()
        tree = self.build_tree(categories)

        # ツリー表示
        st.markdown("### 現在のカテゴリツリー")

        for item in tree:
            indent = "　" * item["level"] * 2
            icon = "📁" if item["level"] == 0 else "📄"
            expense_mark = "💰" if item["is_expense"] else "🔄"

            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"{indent}{icon} {item['name']} {expense_mark}")
            with col2:
                if st.button("🗑️", key=f"del_{item['id']}", help="削除"):
                    self.delete_category(item["id"])
                    st.rerun()

        st.divider()

        # 新規追加フォーム
        st.markdown("### 新規カテゴリ追加")

        col1, col2, col3 = st.columns(3)

        with col1:
            new_name = st.text_input("カテゴリ名")

        with col2:
            parent_options = {"（親なし）": None}
            parent_options.update({cat["name"]: cat["id"] for cat in categories})
            selected_parent = st.selectbox("親カテゴリ", options=list(parent_options.keys()))

        with col3:
            is_expense = st.checkbox("支出カテゴリ", value=True)

        if st.button("追加", type="primary"):
            if new_name:
                parent_id = parent_options[selected_parent]
                self.add_category(new_name, parent_id, is_expense)
                st.rerun()
            else:
                st.warning("カテゴリ名を入力してください")


# Streamlitエントリーポイント
if __name__ == "__main__":
    ui = CategoryTreeUI()
    ui.run()
