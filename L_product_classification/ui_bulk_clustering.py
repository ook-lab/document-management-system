"""
一括クラスタリング承認UI
Geminiが生成したクラスタを効率的に承認
"""

import streamlit as st
import pandas as pd
from typing import List, Dict

from A_common.database.client import DatabaseClient


class BulkClusteringUI:
    """一括クラスタリング承認画面"""

    def __init__(self):
        self.db = DatabaseClient(use_service_role=True)

    def fetch_pending_clusters(self) -> List[Dict]:
        """承認待ちクラスタを取得"""
        result = self.db.client.table('99_tmp_gemini_clustering').select(
            '*'
        ).eq('approval_status', 'pending').execute()

        return result.data

    def approve_clusters(self, cluster_ids: List[str], category_id: str):
        """
        クラスタを承認し、Tier 1/2辞書に登録

        Args:
            cluster_ids: 承認するクラスタIDリスト
            category_id: カテゴリID（60_ms_categoriesから取得）
        """
        for cluster_id in cluster_ids:
            # クラスタ情報を取得
            cluster = self.db.client.table('99_tmp_gemini_clustering').select(
                '*'
            ).eq('id', cluster_id).single().execute()

            cluster_data = cluster.data
            general_name = cluster_data["general_name"]
            product_ids = cluster_data["product_ids"]
            product_names = cluster_data["product_names"]

            # Tier 1: 各商品名 → general_name のマッピング
            for product_name in set(product_names):  # 重複排除
                self.db.client.table('70_ms_product_normalization').upsert({
                    "raw_keyword": product_name,
                    "general_name": general_name,
                    "confidence_score": cluster_data["confidence_avg"],
                    "source": "gemini_batch"
                }).execute()

            # Tier 2: general_name + context → category_id
            self.db.client.table('70_ms_product_classification').upsert({
                "general_name": general_name,
                "source_type": "online_shop",
                "workspace": "shopping",
                "doc_type": "online shop",
                "organization": None,  # 全組織共通
                "category_id": category_id,
                "approval_status": "approved",
                "confidence_score": cluster_data["confidence_avg"]
            }).execute()

            # 80_rd_productsを更新
            for product_id in product_ids:
                self.db.client.table('80_rd_products').update({
                    "general_name": general_name,
                    "category_id": category_id,
                    "needs_approval": False,
                    "classification_confidence": cluster_data["confidence_avg"]
                }).eq('id', product_id).execute()

            # クラスタのステータスを更新
            self.db.client.table('99_tmp_gemini_clustering').update({
                "approval_status": "approved"
            }).eq('id', cluster_id).execute()

        st.success(f"{len(cluster_ids)}件のクラスタを承認しました")

    def run(self):
        """UIメイン処理"""
        st.title("🎯 一括クラスタリング承認")
        st.markdown("Geminiが自動生成したクラスタを確認・承認します。")

        # カテゴリマスタを取得
        categories_result = self.db.client.table('60_ms_categories').select(
            'id, name, parent_id'
        ).execute()
        categories = {cat["name"]: cat["id"] for cat in categories_result.data}

        # 承認待ちクラスタを取得
        clusters = self.fetch_pending_clusters()

        if not clusters:
            st.info("承認待ちのクラスタはありません")
            return

        # DataFrameに変換
        df_data = []
        for cluster in clusters:
            df_data.append({
                "id": cluster["id"],
                "承認": False,
                "一般名詞": cluster["general_name"],
                "カテゴリ": cluster.get("category_name", "食材"),
                "商品数": len(cluster["product_ids"]),
                "信頼度": f"{cluster['confidence_avg']:.2%}",
                "商品例": ", ".join(cluster["product_names"][:3]) + "..." if len(cluster["product_names"]) > 3 else ", ".join(cluster["product_names"])
            })

        df = pd.DataFrame(df_data).sort_values("商品数", ascending=False)

        st.markdown(f"### 全{len(df)}クラスタ（商品数降順）")

        # データエディタ
        edited_df = st.data_editor(
            df,
            column_config={
                "id": st.column_config.TextColumn("ID", disabled=True, width="small"),
                "承認": st.column_config.CheckboxColumn("承認", default=False),
                "一般名詞": st.column_config.TextColumn("一般名詞", width="medium"),
                "カテゴリ": st.column_config.SelectboxColumn(
                    "カテゴリ",
                    options=list(categories.keys()),
                    width="medium"
                ),
                "商品数": st.column_config.NumberColumn("商品数", format="%d"),
                "信頼度": st.column_config.TextColumn("信頼度", width="small"),
                "商品例": st.column_config.TextColumn("商品例（先頭3件）", width="large")
            },
            hide_index=True,
            use_container_width=True
        )

        # 承認ボタン
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("選択を一括承認", type="primary"):
                approved_rows = edited_df[edited_df["承認"] == True]

                if len(approved_rows) == 0:
                    st.warning("承認する項目を選択してください")
                else:
                    # カテゴリIDを取得
                    cluster_ids = approved_rows["id"].tolist()

                    # カテゴリ名からIDを取得（最初の行のカテゴリを使用）
                    category_name = approved_rows.iloc[0]["カテゴリ"]
                    category_id = categories[category_name]

                    self.approve_clusters(cluster_ids, category_id)
                    st.rerun()


# Streamlitエントリーポイント
if __name__ == "__main__":
    ui = BulkClusteringUI()
    ui.run()
