"""
日次承認インボックスUI
信頼度に基づく3段階（信号機）表示
"""

import streamlit as st
import pandas as pd
from typing import List, Dict, Tuple

from A_common.database.client import DatabaseClient


class DailyInboxUI:
    """日次承認インボックス"""

    def __init__(self):
        self.db = DatabaseClient(use_service_role=True)

    def fetch_pending_products(self) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """
        承認待ち商品を信頼度別に取得

        Returns:
            (high, medium, low)のタプル
        """
        result = self.db.client.table('Rawdata_NETSUPER_items').select(
            'id, product_name, general_name, category_id, classification_confidence, organization'
        ).eq('needs_approval', True).execute()

        high = []
        medium = []
        low = []

        for product in result.data:
            confidence = product.get("classification_confidence", 0.0) or 0.0

            if confidence >= 0.9:
                high.append(product)
            elif confidence >= 0.7:
                medium.append(product)
            else:
                low.append(product)

        return high, medium, low

    def approve_products(self, product_ids: List[str]):
        """商品を承認（needs_approval = False）"""
        for product_id in product_ids:
            self.db.client.table('Rawdata_NETSUPER_items').update({
                "needs_approval": False
            }).eq('id', product_id).execute()

        st.success(f"{len(product_ids)}件の商品を承認しました")

    def render_product_table(self, products: List[Dict], title: str, color: str):
        """商品テーブルを表示"""
        if not products:
            st.info(f"{title}: 該当なし")
            return

        st.markdown(f"### {color} {title} ({len(products)}件)")

        df_data = []
        for product in products:
            df_data.append({
                "id": product["id"],
                "承認": False,
                "商品名": product["product_name"],
                "一般名詞": product.get("general_name", "未設定"),
                "信頼度": f"{product.get('classification_confidence', 0.0):.2%}",
                "店舗": product.get("organization", "")
            })

        df = pd.DataFrame(df_data)

        edited_df = st.data_editor(
            df,
            column_config={
                "id": st.column_config.TextColumn("ID", disabled=True, width="small"),
                "承認": st.column_config.CheckboxColumn("承認", default=False),
                "商品名": st.column_config.TextColumn("商品名", width="large"),
                "一般名詞": st.column_config.TextColumn("一般名詞", width="medium"),
                "信頼度": st.column_config.TextColumn("信頼度", width="small"),
                "店舗": st.column_config.TextColumn("店舗", width="medium")
            },
            hide_index=True,
            use_container_width=True,
            key=f"table_{title}"
        )

        if st.button(f"{title}の選択を承認", key=f"btn_{title}"):
            approved_rows = edited_df[edited_df["承認"] == True]
            if len(approved_rows) > 0:
                self.approve_products(approved_rows["id"].tolist())
                st.rerun()

    def run(self):
        """UIメイン処理"""
        st.title("📥 日次承認インボックス")
        st.markdown("新規商品の分類結果を確認・承認します。")

        # データ取得
        high, medium, low = self.fetch_pending_products()

        # タブ表示
        tab1, tab2, tab3 = st.tabs(["🟢 高信頼度", "🟡 中信頼度", "🔴 要確認"])

        with tab1:
            self.render_product_table(high, "高信頼度 (≥90%)", "🟢")

        with tab2:
            self.render_product_table(medium, "中信頼度 (70-90%)", "🟡")

        with tab3:
            self.render_product_table(low, "要確認 (<70%)", "🔴")


# Streamlitエントリーポイント
if __name__ == "__main__":
    ui = DailyInboxUI()
    ui.run()
