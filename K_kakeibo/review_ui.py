"""
家計簿レビューUI (Streamlit)

レシート単位でのレビュー：
- レシート画像プレビュー
- 商品一覧（表形式）
- 合計金額
- レシート単位での承認・編集
"""

import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from PIL import Image
import io

# 設定
try:
    # Streamlit Cloud環境
    from K_kakeibo.config import SUPABASE_URL, SUPABASE_KEY, GOOGLE_DRIVE_CREDENTIALS
except ImportError:
    # ローカル環境
    from config import SUPABASE_URL, SUPABASE_KEY, GOOGLE_DRIVE_CREDENTIALS

# Supabase接続
db = create_client(SUPABASE_URL, SUPABASE_KEY)

# Google Drive接続
@st.cache_resource
def get_drive_service():
    """Google Drive APIサービスを取得"""
    import json
    from pathlib import Path

    # Streamlit Cloudの場合はSecretsから、ローカルの場合はファイルから
    if "gcp_service_account" in st.secrets:
        # Streamlit CloudのSecrets
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
    else:
        # ローカル環境
        cred_path = Path(GOOGLE_DRIVE_CREDENTIALS)
        if not cred_path.exists():
            st.error(f"サービスアカウントファイルが見つかりません: {GOOGLE_DRIVE_CREDENTIALS}")
            st.stop()
        credentials = service_account.Credentials.from_service_account_file(
            GOOGLE_DRIVE_CREDENTIALS,
            scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
    return build("drive", "v3", credentials=credentials)


def get_receipt_image(drive_file_id: str):
    """Google Driveからレシート画像を取得"""
    try:
        service = get_drive_service()
        request = service.files().get_media(
            fileId=drive_file_id,
            supportsAllDrives=True
        )

        file_bytes = io.BytesIO()
        from googleapiclient.http import MediaIoBaseDownload
        downloader = MediaIoBaseDownload(file_bytes, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()

        file_bytes.seek(0)
        return Image.open(file_bytes)
    except Exception as e:
        st.error(f"画像取得エラー: {e}")
        return None


def main():
    st.set_page_config(page_title="家計簿レビュー", layout="wide")
    st.title("📊 家計簿レビューシステム")

    # メインタブ
    tab1, tab2 = st.tabs(["📄 レシートレビュー", "🏷️ 商品分類管理"])

    with tab1:
        show_receipt_review_tab()

    with tab2:
        show_product_classification_tab()


def show_receipt_review_tab():
    """レシートレビュータブ"""
    # サイドバー：Google Driveから取り込み
    st.sidebar.header("📥 レシート取り込み")

    with st.sidebar.expander("Google Driveから取り込む"):
        st.markdown("**00_Inbox_Easy** から最新のレシート画像を取り込みます")

        col1, col2 = st.columns(2)

        with col1:
            limit = st.number_input("取り込み件数", min_value=1, max_value=10, value=3, key="import_limit")

        with col2:
            if st.button("🚀 取り込み開始", key="start_import"):
                with st.spinner("レシート画像を取り込み中..."):
                    import subprocess
                    import sys
                    from pathlib import Path

                    try:
                        # Pythonスクリプトのパスを取得
                        script_path = Path(__file__).parent / "reimport_receipts_from_drive.py"

                        # プロジェクトルートディレクトリを取得
                        project_root = Path(__file__).parent.parent

                        # 環境変数にPYTHONPATHを設定
                        import os
                        env = os.environ.copy()
                        env['PYTHONPATH'] = str(project_root)

                        # Streamlit CloudのSecretsから環境変数を渡す
                        if "KAKEIBO_INBOX_EASY_FOLDER_ID" in st.secrets:
                            env['KAKEIBO_INBOX_EASY_FOLDER_ID'] = st.secrets["KAKEIBO_INBOX_EASY_FOLDER_ID"]
                            st.info(f"✅ INBOX_EASY_FOLDER_ID を設定: {st.secrets['KAKEIBO_INBOX_EASY_FOLDER_ID'][:20]}...")
                        else:
                            st.warning("⚠️ INBOX_EASY_FOLDER_ID がSecretsに見つかりません")

                        if "KAKEIBO_INBOX_HARD_FOLDER_ID" in st.secrets:
                            env['KAKEIBO_INBOX_HARD_FOLDER_ID'] = st.secrets["KAKEIBO_INBOX_HARD_FOLDER_ID"]
                            st.info(f"✅ INBOX_HARD_FOLDER_ID を設定: {st.secrets['KAKEIBO_INBOX_HARD_FOLDER_ID'][:20]}...")
                        else:
                            st.warning("⚠️ INBOX_HARD_FOLDER_ID がSecretsに見つかりません")

                        # subprocess でスクリプトを実行
                        result = subprocess.run(
                            [sys.executable, str(script_path), f"--limit={limit}"],
                            capture_output=True,
                            text=True,
                            timeout=600,
                            env=env,
                            cwd=str(project_root)
                        )

                        # 標準出力を表示
                        if result.stdout:
                            st.text("=== 実行ログ ===")
                            st.code(result.stdout, language="log")

                        # 標準エラー出力を表示
                        if result.stderr:
                            st.warning("=== エラー/警告 ===")
                            st.code(result.stderr, language="log")

                        if result.returncode == 0:
                            st.success(f"✅ 処理が完了しました！（終了コード: {result.returncode}）")
                            st.info("数秒待ってからページをリロードしてください")
                            if st.button("🔄 今すぐリロード"):
                                st.rerun()
                        else:
                            st.error(f"❌ エラーが発生しました（終了コード: {result.returncode}）")

                    except subprocess.TimeoutExpired:
                        st.warning("⏱️ タイムアウトしました。処理に時間がかかっています。")
                    except Exception as e:
                        st.error(f"エラー: {e}")
                        import traceback
                        st.code(traceback.format_exc())

        st.divider()

        if st.button("📊 データ件数を確認"):
            try:
                receipts = db.table("60_rd_receipts").select("*", count="exact").execute()
                transactions = db.table("60_rd_transactions").select("*", count="exact").execute()
                st.success(f"レシート: {receipts.count}件、商品: {transactions.count}件")
            except Exception as e:
                st.error(f"エラー: {e}")

    st.sidebar.divider()

    # サイドバー：レシート一覧
    st.sidebar.header("レシート一覧")

    # 処理ログ取得（レシート単位）
    try:
        logs = db.table("99_lg_image_proc_log") \
            .select("*") \
            .order("processed_at", desc=True) \
            .limit(100) \
            .execute()
    except Exception as e:
        st.error(f"処理ログの取得エラー: {str(e)}")
        st.info("エラー詳細を確認してください")
        import traceback
        st.code(traceback.format_exc())
        return

    if not logs.data:
        st.info("処理済みレシートがありません")
        return

    # フィルター
    status_filter = st.sidebar.selectbox(
        "ステータス",
        ["すべて", "未確認", "確認済み", "エラー"]
    )

    # レシート選択
    receipt_options = []
    for log in logs.data:
        status_icon = {
            "success": "✅",
            "failed": "❌"
        }.get(log["status"], "⚠️")

        label = f"{status_icon} {log['file_name']} ({log['processed_at'][:10]})"
        receipt_options.append((label, log))

    if not receipt_options:
        st.info("表示するレシートがありません")
        return

    selected_label = st.sidebar.radio(
        "レシートを選択",
        [opt[0] for opt in receipt_options],
        key="receipt_selector"
    )

    # 選択されたレシートを取得
    selected_log = next(opt[1] for opt in receipt_options if opt[0] == selected_label)

    # メイン画面：レシート詳細
    show_receipt_detail(selected_log)


def show_receipt_detail(log: dict):
    """レシート詳細表示"""

    st.header(f"📄 {log['file_name']}")

    # 2カラムレイアウト
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("レシート画像")

        if log.get("drive_file_id"):
            with st.spinner("画像を読み込み中..."):
                image = get_receipt_image(log["drive_file_id"])
                if image:
                    st.image(image, use_column_width=True)
                else:
                    st.warning("画像を取得できませんでした")
        else:
            st.info("画像IDがありません")

        # レシート情報
        st.subheader("処理情報")
        info_data = {
            "ファイル名": log["file_name"],
            "処理日時": log["processed_at"],
            "ステータス": log["status"],
            "OCRモデル": log.get("ocr_model", "不明"),
            "エラー": log.get("error_message", "なし")
        }

        for key, value in info_data.items():
            st.text(f"{key}: {value}")

    with col_right:
        st.subheader("取引明細")

        if log["status"] == "success" and log.get("receipt_id"):
            # レシート情報を取得
            receipt_result = db.table("60_rd_receipts") \
                .select("*") \
                .eq("id", log["receipt_id"]) \
                .execute()

            if not receipt_result.data:
                st.warning("レシート情報が見つかりません")
                return

            receipt = receipt_result.data[0]

            # 税表示タイプを判定（レシートレベル）
            # すべてのレシートには小計がある（前提）
            # 合計が省略されている場合は、小計と同じ値とする
            subtotal = receipt.get('subtotal_amount')
            total = receipt.get('total_amount_check')

            # 合計が省略されている場合、小計と同じとする
            if total is None and subtotal is not None:
                total = subtotal
                st.info(f"合計が省略されているため、小計と同じ値（¥{subtotal:,}）を使用")

            # 念のため：小計がない場合のフォールバック
            if subtotal is None and total is not None:
                subtotal = total

            # 判定：小計 < 合計 → 外税、小計 = 合計 → 内税
            if subtotal and total:
                if subtotal < total:
                    tax_display_type = "外税"
                else:
                    tax_display_type = "内税"
            else:
                tax_display_type = "不明"

            # トランザクションを取得（JOINは使わず2段階クエリ）
            try:
                transactions = db.table("60_rd_transactions") \
                    .select("*") \
                    .eq("receipt_id", log["receipt_id"]) \
                    .order("line_number") \
                    .execute()

                # 各transactionに対してstandardized_itemsを取得して結合
                if transactions.data:
                    for t in transactions.data:
                        std_items = db.table("60_rd_standardized_items") \
                            .select("*") \
                            .eq("transaction_id", t["id"]) \
                            .execute()
                        # standardized_itemsデータを配列として追加（最初の1件のみ）
                        t["60_rd_standardized_items"] = std_items.data[0] if std_items.data else None

            except Exception as e:
                st.error(f"トランザクション取得エラー: {str(e)}")
                import traceback
                st.code(traceback.format_exc())
                return

            if transactions.data:
                # 🔍 デバッグ：最初のトランザクションのデータ構造を確認
                if len(transactions.data) > 0:
                    first_t = transactions.data[0]
                    with st.expander("🔍 デバッグ情報（最初の商品）"):
                        # データベースキー情報
                        import os
                        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                        anon_key = os.getenv("SUPABASE_KEY")
                        st.write("**🔑 データベースキー情報**")
                        if service_role_key:
                            st.write(f"SERVICE_ROLE_KEY設定: ✅ あり (...{service_role_key[-4:]})")
                        else:
                            st.write("SERVICE_ROLE_KEY設定: ❌ なし")
                        if anon_key:
                            st.write(f"ANON_KEY設定: ✅ あり (...{anon_key[-4:]})")
                        else:
                            st.write("ANON_KEY設定: ❌ なし")
                        st.write(f"使用中のキー末尾: ...{SUPABASE_KEY[-4:]}")
                        st.write("---")

                        # 生のトランザクションデータを表示
                        st.write("**📦 生のトランザクションデータ（全キー）:**")
                        st.json(first_t)
                        st.write("---")

                        # 直接60_rd_standardized_itemsテーブルをクエリ
                        st.write("**🔍 直接クエリ: 60_rd_standardized_items**")
                        transaction_id = first_t.get('id')
                        if transaction_id:
                            try:
                                std_items = db.table("60_rd_standardized_items") \
                                    .select("*") \
                                    .eq("transaction_id", transaction_id) \
                                    .execute()
                                st.write(f"取得件数: {len(std_items.data) if std_items.data else 0}")
                                if std_items.data and len(std_items.data) > 0:
                                    st.json(std_items.data[0])
                                else:
                                    st.write("⚠️ データが見つかりません")
                            except Exception as e:
                                st.write(f"❌ エラー: {e}")
                        st.write("---")

                        # データ構造情報
                        st.write(f"**商品名**: {first_t.get('product_name')}")
                        st.write(f"**60_rd_standardized_items type**: {type(first_t.get('60_rd_standardized_items'))}")
                        st.write(f"**60_rd_standardized_items value**: {first_t.get('60_rd_standardized_items')}")

                        std_test = first_t.get("60_rd_standardized_items") or {}
                        st.write(f"**std (processed)**: {std_test}")
                        if std_test:
                            st.write(f"**std_unit_price**: {std_test.get('std_unit_price')}")
                            st.write(f"**tax_amount**: {std_test.get('tax_amount')}")
                            st.write(f"**std_amount**: {std_test.get('std_amount')}")
                        else:
                            st.write("⚠️ standardized_itemsデータが空です")

                # DataFrameに変換（7要素構造 + ID情報）
                df_data = []
                for t in transactions.data:
                    # standardized_itemsデータを取得（辞書またはNone）
                    std = t.get("60_rd_standardized_items") or {}

                    # 7要素データを取得
                    quantity = t.get("quantity") or 1
                    std_unit_price = std.get('std_unit_price')  # 本体単価（1個あたりの税抜価格）
                    tax_amount = std.get('tax_amount')  # 税額
                    tax_included_amount = std.get('std_amount')  # 税込価

                    # 本体価を計算（本体単価 × 数量 = 税抜総額）
                    base_price_total = None
                    if std_unit_price is not None and quantity:
                        base_price_total = std_unit_price * quantity

                    # 表示額を計算（内税なら税込価、外税なら本体価）
                    if tax_display_type == "内税":
                        displayed_amount = tax_included_amount
                    elif tax_display_type == "外税":
                        displayed_amount = base_price_total
                    else:
                        displayed_amount = None

                    # 税込単価を計算（税込価 ÷ 数量）
                    tax_included_unit_price = None
                    if tax_included_amount and quantity:
                        tax_included_unit_price = tax_included_amount // quantity

                    df_data.append({
                        "_transaction_id": t["id"],  # 更新用（非表示）
                        "_std_id": std.get("id"),  # 更新用（非表示）
                        "商品名": t["product_name"],
                        "数量": quantity,
                        "表示額": displayed_amount if displayed_amount is not None else 0,
                        "外or内": tax_display_type,
                        "税率": std.get('tax_rate', 10),
                        "本体価": base_price_total if base_price_total is not None else 0,
                        "税額": tax_amount if tax_amount is not None else 0,
                        "税込価": tax_included_amount if tax_included_amount is not None else 0,
                        "単価": tax_included_unit_price if tax_included_unit_price is not None else 0,
                        "正式名": std.get("official_name") or "",
                        "物品名": t.get("item_name") or "",
                        "大分類": std.get("major_category") or "",
                        "小分類": std.get("minor_category") or "",
                        "人物": std.get("person") or "",
                        "名目": std.get("purpose") or "",
                        "要確認": "⚠️" if std.get("needs_review") else ""
                    })

                df = pd.DataFrame(df_data)

                # 編集可能なデータエディタ
                edited_df = st.data_editor(
                    df,
                    hide_index=True,
                    height=400,
                    column_config={
                        "_transaction_id": None,  # 非表示
                        "_std_id": None,  # 非表示
                        "商品名": st.column_config.TextColumn("商品名", disabled=True),
                        "数量": st.column_config.NumberColumn("数量", min_value=1, step=1),
                        "表示額": st.column_config.NumberColumn("表示額", format="¥%d"),
                        "外or内": st.column_config.TextColumn("外or内", disabled=True),
                        "税率": st.column_config.NumberColumn("税率", format="%d%%", disabled=True),
                        "本体価": st.column_config.NumberColumn("本体価", format="¥%d"),
                        "税額": st.column_config.NumberColumn("税額", format="¥%d"),
                        "税込価": st.column_config.NumberColumn("税込価", format="¥%d"),
                        "単価": st.column_config.NumberColumn("単価", format="¥%d", disabled=True),
                    },
                    use_container_width=True
                )

                # 更新ボタン
                if st.button("💾 データを更新", type="primary"):
                    # 変更されたデータをDBに保存
                    updated_count = 0
                    for idx, row in edited_df.iterrows():
                        std_id = row["_std_id"]
                        if std_id:
                            # 本体単価を逆算（本体価 ÷ 数量）
                            quantity = row["数量"]
                            base_price = row["本体価"]
                            std_unit_price = base_price // quantity if quantity > 0 else 0

                            # 60_rd_standardized_itemsを更新
                            try:
                                db.table("60_rd_standardized_items").update({
                                    "std_unit_price": std_unit_price,
                                    "tax_amount": row["税額"],
                                    "std_amount": row["税込価"]
                                }).eq("id", std_id).execute()
                                updated_count += 1
                            except Exception as e:
                                st.error(f"更新エラー ({row['商品名']}): {e}")

                    if updated_count > 0:
                        st.success(f"✅ {updated_count}件のデータを更新しました")
                        st.rerun()  # ページをリロードしてレシート情報サマリーも更新

                # 合計金額・税額サマリー
                total = sum(
                    (t.get("60_rd_standardized_items") or {}).get("std_amount", 0)
                    for t in transactions.data
                )
                # 税率別の集計
                total_tax_8 = sum(
                    (t.get("60_rd_standardized_items") or {}).get("tax_amount", 0)
                    for t in transactions.data
                    if (t.get("60_rd_standardized_items") or {}).get("tax_rate") == 8
                )
                total_tax_10 = sum(
                    (t.get("60_rd_standardized_items") or {}).get("tax_amount", 0)
                    for t in transactions.data
                    if (t.get("60_rd_standardized_items") or {}).get("tax_rate") == 10
                )
                # 税込合計（8%、10%それぞれ）
                total_amount_8 = sum(
                    (t.get("60_rd_standardized_items") or {}).get("std_amount", 0)
                    for t in transactions.data
                    if (t.get("60_rd_standardized_items") or {}).get("tax_rate") == 8
                )
                total_amount_10 = sum(
                    (t.get("60_rd_standardized_items") or {}).get("std_amount", 0)
                    for t in transactions.data
                    if (t.get("60_rd_standardized_items") or {}).get("tax_rate") == 10
                )

                # 税額サマリー取得（レシート記載値との比較）
                try:
                    tax_summary = db.table("60_ag_receipt_summary") \
                        .select("*") \
                        .eq("receipt_id", log["receipt_id"]) \
                        .execute()
                except Exception as e:
                    # テーブルが存在しない場合はスキップ
                    tax_summary = None

                # ========================================
                # レシート情報サマリー（詳細版）
                # ========================================

                # 計算値を集計（税抜・税込両方）
                calc_subtotal_excluding_tax = sum(  # 税抜合計（外税用）
                    (t.get("60_rd_standardized_items") or {}).get("std_unit_price", 0) * (t.get("quantity") or 1)
                    for t in transactions.data
                )
                calc_total = sum(  # 税込合計
                    (t.get("60_rd_standardized_items") or {}).get("std_amount", 0)
                    for t in transactions.data
                )

                # 税率別の対象額（8%, 10%）
                # 10%対象額（税込）- 内税用
                calc_10_amount_including_tax = sum(
                    (t.get("60_rd_standardized_items") or {}).get("std_amount", 0)
                    for t in transactions.data
                    if (t.get("60_rd_standardized_items") or {}).get("tax_rate") == 10
                )
                # 10%対象額（税抜）- 外税用
                calc_10_amount_excluding_tax = sum(
                    (t.get("60_rd_standardized_items") or {}).get("std_unit_price", 0) * (t.get("quantity") or 1)
                    for t in transactions.data
                    if (t.get("60_rd_standardized_items") or {}).get("tax_rate") == 10
                )
                # 8%対象額（税込）- 内税用
                calc_8_amount_including_tax = sum(
                    (t.get("60_rd_standardized_items") or {}).get("std_amount", 0)
                    for t in transactions.data
                    if (t.get("60_rd_standardized_items") or {}).get("tax_rate") == 8
                )
                # 8%対象額（税抜）- 外税用
                calc_8_amount_excluding_tax = sum(
                    (t.get("60_rd_standardized_items") or {}).get("std_unit_price", 0) * (t.get("quantity") or 1)
                    for t in transactions.data
                    if (t.get("60_rd_standardized_items") or {}).get("tax_rate") == 8
                )

                # レシート記載値
                receipt_subtotal = receipt.get("subtotal_amount")
                receipt_total = receipt.get("total_amount_check")

                # 整合性チェック
                if tax_summary and tax_summary.data:
                    summary = tax_summary.data[0]
                    match_icon = "✅" if summary.get("calculated_matches_actual") else "⚠️"
                    st.subheader(f"📊 レシート情報サマリー（{tax_display_type}） {match_icon}")
                else:
                    st.subheader(f"📊 レシート情報サマリー（{tax_display_type}）")
                    summary = None

                # テーブルデータを作成（内税・外税で項目名と計算方法を変える）
                table_data = {
                    "項目": [],
                    "レシート記載": [],
                    "計算値（差分）": []
                }

                # 1. 小計
                if tax_display_type == "内税":
                    # 内税の場合：小計 = 税込合計
                    table_data["項目"].append("小計（税込）")
                    table_data["レシート記載"].append(f"¥{receipt_subtotal:,}" if receipt_subtotal is not None else "—")

                    subtotal_diff = calc_total - receipt_subtotal if receipt_subtotal else 0
                    if subtotal_diff != 0:
                        table_data["計算値（差分）"].append(f"¥{calc_total:,}|{subtotal_diff:+,}円")
                    else:
                        table_data["計算値（差分）"].append(f"¥{calc_total:,}|")
                else:
                    # 外税の場合：小計 = 税抜合計
                    table_data["項目"].append("小計（税抜）")
                    table_data["レシート記載"].append(f"¥{receipt_subtotal:,}" if receipt_subtotal is not None else "—")

                    subtotal_diff = calc_subtotal_excluding_tax - receipt_subtotal if receipt_subtotal else 0
                    if subtotal_diff != 0:
                        table_data["計算値（差分）"].append(f"¥{calc_subtotal_excluding_tax:,}|{subtotal_diff:+,}円")
                    else:
                        table_data["計算値（差分）"].append(f"¥{calc_subtotal_excluding_tax:,}|")

                # 2. 税率別の対象額と税額
                if summary:
                    if tax_display_type == "内税":
                        # 内税10%対象額（税込）
                        table_data["項目"].append("内税10%対象額（税込）")
                        tax_10_subtotal = summary.get('tax_10_subtotal')
                        tax_10_amount = summary.get('tax_10_amount')
                        # レシート記載 = 対象額（税抜） + 税額 = 税込
                        if tax_10_subtotal is not None and tax_10_amount is not None:
                            receipt_10_including = tax_10_subtotal + tax_10_amount
                            table_data["レシート記載"].append(f"¥{receipt_10_including:,}")
                        else:
                            table_data["レシート記載"].append("—")
                            receipt_10_including = None

                        # 計算値 = 10%対象商品の税込価合計
                        amount_diff = calc_10_amount_including_tax - receipt_10_including if receipt_10_including else 0
                        if amount_diff != 0:
                            table_data["計算値（差分）"].append(f"¥{calc_10_amount_including_tax:,}|{amount_diff:+,}円")
                        else:
                            table_data["計算値（差分）"].append(f"¥{calc_10_amount_including_tax:,}|")

                        # 内税10%税額
                        table_data["項目"].append("内税10%税額")
                        table_data["レシート記載"].append(
                            f"¥{tax_10_amount:,}" if tax_10_amount is not None else "—"
                        )
                        # 計算値は total_tax_10 を使う（実際に計算した税額）
                        tax_10_diff = total_tax_10 - tax_10_amount if tax_10_amount else 0
                        if tax_10_diff != 0:
                            table_data["計算値（差分）"].append(f"¥{total_tax_10:,}|{tax_10_diff:+d}円")
                        else:
                            table_data["計算値（差分）"].append(f"¥{total_tax_10:,}|")

                        # 内税8%対象額（税込）
                        if calc_8_amount_including_tax > 0:
                            table_data["項目"].append("内税8%対象額（税込）")
                            tax_8_subtotal = summary.get('tax_8_subtotal')
                            tax_8_amount = summary.get('tax_8_amount')
                            if tax_8_subtotal is not None and tax_8_amount is not None:
                                receipt_8_including = tax_8_subtotal + tax_8_amount
                                table_data["レシート記載"].append(f"¥{receipt_8_including:,}")
                            else:
                                table_data["レシート記載"].append("—")
                                receipt_8_including = None

                            amount_diff = calc_8_amount_including_tax - receipt_8_including if receipt_8_including else 0
                            if amount_diff != 0:
                                table_data["計算値（差分）"].append(f"¥{calc_8_amount_including_tax:,}|{amount_diff:+,}円")
                            else:
                                table_data["計算値（差分）"].append(f"¥{calc_8_amount_including_tax:,}|")

                            # 内税8%税額
                            table_data["項目"].append("内税8%税額")
                            table_data["レシート記載"].append(
                                f"¥{tax_8_amount:,}" if tax_8_amount is not None else "—"
                            )
                            # 計算値は total_tax_8 を使う（実際に計算した税額）
                            tax_8_diff = total_tax_8 - tax_8_amount if tax_8_amount else 0
                            if tax_8_diff != 0:
                                table_data["計算値（差分）"].append(f"¥{total_tax_8:,}|{tax_8_diff:+d}円")
                            else:
                                table_data["計算値（差分）"].append(f"¥{total_tax_8:,}|")

                    else:  # 外税
                        # 外税10%対象額（税抜）
                        table_data["項目"].append("外税10%対象額（税抜）")
                        tax_10_subtotal = summary.get('tax_10_subtotal')
                        table_data["レシート記載"].append(
                            f"¥{tax_10_subtotal:,}" if tax_10_subtotal is not None else "—"
                        )

                        # 計算値 = 10%対象商品の税抜価合計
                        amount_diff = calc_10_amount_excluding_tax - tax_10_subtotal if tax_10_subtotal else 0
                        if amount_diff != 0:
                            table_data["計算値（差分）"].append(f"¥{calc_10_amount_excluding_tax:,}|{amount_diff:+,}円")
                        else:
                            table_data["計算値（差分）"].append(f"¥{calc_10_amount_excluding_tax:,}|")

                        # 外税10%税額
                        table_data["項目"].append("外税10%税額")
                        tax_10_amount = summary.get('tax_10_amount')
                        table_data["レシート記載"].append(
                            f"¥{tax_10_amount:,}" if tax_10_amount is not None else "—"
                        )
                        # 計算値は total_tax_10 を使う（実際に計算した税額）
                        tax_10_diff = total_tax_10 - tax_10_amount if tax_10_amount else 0
                        if tax_10_diff != 0:
                            table_data["計算値（差分）"].append(f"¥{total_tax_10:,}|{tax_10_diff:+d}円")
                        else:
                            table_data["計算値（差分）"].append(f"¥{total_tax_10:,}|")

                        # 外税8%対象額（税抜）
                        if calc_8_amount_excluding_tax > 0:
                            table_data["項目"].append("外税8%対象額（税抜）")
                            tax_8_subtotal = summary.get('tax_8_subtotal')
                            table_data["レシート記載"].append(
                                f"¥{tax_8_subtotal:,}" if tax_8_subtotal is not None else "—"
                            )

                            amount_diff = calc_8_amount_excluding_tax - tax_8_subtotal if tax_8_subtotal else 0
                            if amount_diff != 0:
                                table_data["計算値（差分）"].append(f"¥{calc_8_amount_excluding_tax:,}|{amount_diff:+,}円")
                            else:
                                table_data["計算値（差分）"].append(f"¥{calc_8_amount_excluding_tax:,}|")

                            # 外税8%税額
                            table_data["項目"].append("外税8%税額")
                            tax_8_amount = summary.get('tax_8_amount')
                            table_data["レシート記載"].append(
                                f"¥{tax_8_amount:,}" if tax_8_amount is not None else "—"
                            )
                            # 計算値は total_tax_8 を使う（実際に計算した税額）
                            tax_8_diff = total_tax_8 - tax_8_amount if tax_8_amount else 0
                            if tax_8_diff != 0:
                                table_data["計算値（差分）"].append(f"¥{total_tax_8:,}|{tax_8_diff:+d}円")
                            else:
                                table_data["計算値（差分）"].append(f"¥{total_tax_8:,}|")
                else:
                    # tax_summaryがない場合
                    if tax_display_type == "内税":
                        table_data["項目"].append("内税10%対象額（税込）")
                        table_data["レシート記載"].append("—")
                        table_data["計算値（差分）"].append(f"¥{calc_10_amount_including_tax:,}|")

                        table_data["項目"].append("内税10%税額")
                        table_data["レシート記載"].append("—")
                        table_data["計算値（差分）"].append(f"¥{total_tax_10:,}|")
                    else:
                        table_data["項目"].append("外税10%対象額（税抜）")
                        table_data["レシート記載"].append("—")
                        table_data["計算値（差分）"].append(f"¥{calc_10_amount_excluding_tax:,}|")

                        table_data["項目"].append("外税10%税額")
                        table_data["レシート記載"].append("—")
                        table_data["計算値（差分）"].append(f"¥{total_tax_10:,}|")

                # 3. 税込合計
                table_data["項目"].append("税込合計")
                table_data["レシート記載"].append(f"¥{receipt_total:,}" if receipt_total is not None else "—")

                total_diff = calc_total - receipt_total if receipt_total else 0
                if total_diff != 0:
                    table_data["計算値（差分）"].append(f"¥{calc_total:,}|{total_diff:+,}円")
                else:
                    table_data["計算値（差分）"].append(f"¥{calc_total:,}|")

                # HTMLテーブルを作成（差分を赤字で表示）
                html_table = '<table style="width:100%; border-collapse: collapse;">'
                html_table += '<tr style="background-color: #f0f0f0;"><th style="padding: 8px; text-align: left; border: 1px solid #ddd;">項目</th><th style="padding: 8px; text-align: left; border: 1px solid #ddd;">レシート記載</th><th style="padding: 8px; text-align: left; border: 1px solid #ddd;">計算値（差分）</th></tr>'

                for i in range(len(table_data["項目"])):
                    item = table_data["項目"][i]
                    receipt_text = table_data["レシート記載"][i]
                    calc_val = table_data["計算値（差分）"][i]

                    # "|" で分割して、差分部分を赤字にする
                    if "|" in calc_val:
                        parts = calc_val.split("|")
                        if parts[1]:  # 差分がある場合
                            calc_display = f'{parts[0]} <span style="color: red;">({parts[1]})</span>'
                        else:  # 差分がない場合
                            calc_display = parts[0]
                    else:
                        calc_display = calc_val

                    html_table += f'<tr><td style="padding: 8px; border: 1px solid #ddd;">{item}</td><td style="padding: 8px; border: 1px solid #ddd;">{receipt_text}</td><td style="padding: 8px; border: 1px solid #ddd;">{calc_display}</td></tr>'

                html_table += '</table>'
                st.markdown(html_table, unsafe_allow_html=True)

                # 店名・日付（レシートから取得）
                st.text(f"店名: {receipt['shop_name']}")
                st.text(f"取引日: {receipt['transaction_date']}")
                st.text(f"レシート合計: ¥{receipt.get('total_amount_check', 0):,}")

                # 確認状態（レシート単位）
                if receipt["is_verified"]:
                    st.success("✅ このレシートは確認済みです")
                else:
                    st.warning(f"⏸️ このレシートは未確認です")

                # アクションボタン
                st.divider()

                col1, col2, col3 = st.columns(3)

                with col1:
                    if st.button("✅ 全て承認", key="approve_all"):
                        # レシート単位で承認
                        db.table("60_rd_receipts") \
                            .update({"is_verified": True}) \
                            .eq("id", log["receipt_id"]) \
                            .execute()
                        st.success("承認しました")
                        st.rerun()

                with col2:
                    if st.button("📝 個別編集", key="edit_mode"):
                        st.session_state.edit_mode = True
                        st.rerun()

                with col3:
                    if st.button("🗑️ 全て削除", key="delete_all"):
                        # レシートを削除（CASCADE で子・孫も削除される）
                        db.table("60_rd_receipts") \
                            .delete() \
                            .eq("id", log["receipt_id"]) \
                            .execute()
                        st.warning("削除しました")
                        st.rerun()

                # 個別編集モード
                if st.session_state.get("edit_mode"):
                    st.divider()
                    st.subheader("個別編集")

                    for idx, t in enumerate(transactions.data):
                        std = t.get("60_rd_standardized_items", [{}])[0] if isinstance(t.get("60_rd_standardized_items"), list) else t.get("60_rd_standardized_items", {})
                        amount = std.get('std_amount', 0) or 0
                        with st.expander(f"{t['product_name']} (¥{amount:,})"):
                            col_a, col_b, col_c = st.columns(3)

                            with col_a:
                                new_product = st.text_input(
                                    "商品名",
                                    value=t["product_name"],
                                    key=f"prod_{idx}"
                                )

                                new_amount = st.number_input(
                                    "金額",
                                    value=amount,
                                    key=f"amt_{idx}"
                                )

                                new_tax_included = st.number_input(
                                    "内税額",
                                    value=std.get("tax_amount", 0) or 0,
                                    key=f"tax_{idx}"
                                )

                                new_official_name = st.text_input(
                                    "正式名",
                                    value=std.get("official_name") or "",
                                    key=f"official_{idx}"
                                )

                                new_item_name = st.text_input(
                                    "物品名",
                                    value=t.get("item_name") or "",
                                    key=f"item_{idx}"
                                )

                            with col_b:
                                new_major_category = st.text_input(
                                    "大分類",
                                    value=std.get("major_category") or "",
                                    key=f"major_{idx}"
                                )

                                new_minor_category = st.text_input(
                                    "小分類",
                                    value=std.get("minor_category") or "",
                                    key=f"minor_{idx}"
                                )

                            with col_c:
                                new_person = st.text_input(
                                    "人物",
                                    value=std.get("person") or "",
                                    key=f"person_{idx}"
                                )

                                new_purpose = st.text_input(
                                    "名目",
                                    value=std.get("purpose") or "",
                                    key=f"purpose_{idx}"
                                )

                            if st.button("💾 更新", key=f"update_{idx}"):
                                # 子テーブル（テキスト）の更新
                                db.table("60_rd_transactions").update({
                                    "product_name": new_product,
                                    "item_name": new_item_name
                                }).eq("id", t["id"]).execute()

                                # 孫テーブル（分類・金額）の更新
                                std = t.get("60_rd_standardized_items", [{}])[0] if isinstance(t.get("60_rd_standardized_items"), list) else t.get("60_rd_standardized_items", {})
                                if std and "id" in std:
                                    db.table("60_rd_standardized_items").update({
                                        "std_amount": new_amount,
                                        "tax_amount": new_tax_included,
                                        "official_name": new_official_name,
                                        "major_category": new_major_category,
                                        "minor_category": new_minor_category,
                                        "person": new_person,
                                        "purpose": new_purpose
                                    }).eq("id", std["id"]).execute()

                                # レシート全体を確認済みにマーク
                                db.table("60_rd_receipts").update({
                                    "is_verified": True
                                }).eq("id", log["receipt_id"]).execute()

                                st.success("更新しました")
                                st.rerun()

                    if st.button("編集モード終了", key="exit_edit"):
                        st.session_state.edit_mode = False
                        st.rerun()

            else:
                st.warning("トランザクションデータが見つかりません")

        elif log["status"] == "failed":
            st.error(f"❌ 処理エラー: {log.get('error_message', '不明')}")
            st.info("errorsフォルダを確認してください")

        else:
            st.info("トランザクションデータがありません")


def show_product_classification_tab():
    """商品分類管理タブ"""
    st.header("🏷️ 商品分類管理")

    # サブタブ
    subtab1, subtab2, subtab3 = st.tabs(["📥 日次承認インボックス", "✅ クラスタ承認", "🌳 カテゴリ管理"])

    with subtab1:
        show_daily_inbox()

    with subtab2:
        show_bulk_clustering()

    with subtab3:
        show_category_tree()


def show_daily_inbox():
    """日次承認インボックス（信号機UI）"""
    st.subheader("📥 日次承認インボックス")
    st.info("新規商品の分類結果を確認・承認します")

    # 承認待ち商品を信頼度別に取得
    try:
        high = db.table('80_rd_products').select(
            'id, product_name, general_name, category_id, classification_confidence, organization'
        ).eq('needs_approval', True).gte('classification_confidence', 0.9).execute()

        medium = db.table('80_rd_products').select(
            'id, product_name, general_name, category_id, classification_confidence, organization'
        ).eq('needs_approval', True).gte('classification_confidence', 0.7).lt('classification_confidence', 0.9).execute()

        low = db.table('80_rd_products').select(
            'id, product_name, general_name, category_id, classification_confidence, organization'
        ).eq('needs_approval', True).lt('classification_confidence', 0.7).execute()

        # タブ表示
        tab_high, tab_medium, tab_low = st.tabs([
            f"🟢 高信頼度 ({len(high.data)}件)",
            f"🟡 中信頼度 ({len(medium.data)}件)",
            f"🔴 要確認 ({len(low.data)}件)"
        ])

        with tab_high:
            render_product_approval_table(high.data, "高信頼度", "🟢")

        with tab_medium:
            render_product_approval_table(medium.data, "中信頼度", "🟡")

        with tab_low:
            render_product_approval_table(low.data, "要確認", "🔴")

    except Exception as e:
        st.error(f"データ取得エラー: {e}")


def render_product_approval_table(products, title, icon):
    """商品承認テーブル表示"""
    if not products:
        st.info(f"{title}: 該当なし")
        return

    st.markdown(f"### {icon} {title} ({len(products)}件)")

    df = pd.DataFrame([{
        "id": p["id"],
        "承認": False,
        "商品名": p["product_name"],
        "一般名詞": p.get("general_name", "未設定"),
        "信頼度": f"{p.get('classification_confidence', 0):.1%}" if p.get('classification_confidence') else "—",
        "店舗": p.get("organization", "")
    } for p in products])

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
            for _, row in approved_rows.iterrows():
                db.table('80_rd_products').update({
                    "needs_approval": False
                }).eq('id', row['id']).execute()
            st.success(f"{len(approved_rows)}件の商品を承認しました")
            st.rerun()


def show_bulk_clustering():
    """一括クラスタリング承認"""
    st.subheader("✅ クラスタ一括承認")
    st.info("Geminiが自動生成したクラスタを確認・承認します")

    try:
        # 承認待ちクラスタを取得
        clusters = db.table('99_tmp_gemini_clustering').select(
            '*'
        ).eq('approval_status', 'pending').execute()

        if not clusters.data:
            st.success("承認待ちのクラスタはありません")
            return

        # カテゴリマスタを取得
        categories = db.table('60_ms_categories').select('id, name').execute()
        category_map = {cat["name"]: cat["id"] for cat in categories.data}

        st.markdown(f"### 全{len(clusters.data)}クラスタ")

        df = pd.DataFrame([{
            "id": c["id"],
            "承認": False,
            "一般名詞": c["general_name"],
            "カテゴリ": c.get("category_name", "食材"),
            "商品数": len(c["product_ids"]),
            "信頼度": f"{c['confidence_avg']:.1%}",
            "商品例": ", ".join(c["product_names"][:3]) + "..."
        } for c in clusters.data])

        edited_df = st.data_editor(
            df,
            column_config={
                "id": st.column_config.TextColumn("ID", disabled=True, width="small"),
                "承認": st.column_config.CheckboxColumn("承認", default=False),
                "一般名詞": st.column_config.TextColumn("一般名詞", width="medium"),
                "カテゴリ": st.column_config.SelectboxColumn(
                    "カテゴリ",
                    options=list(category_map.keys()),
                    width="medium"
                ),
                "商品数": st.column_config.NumberColumn("商品数", format="%d"),
                "信頼度": st.column_config.TextColumn("信頼度", width="small"),
                "商品例": st.column_config.TextColumn("商品例（先頭3件）", width="large")
            },
            hide_index=True,
            use_container_width=True
        )

        if st.button("選択を一括承認", type="primary"):
            approved_rows = edited_df[edited_df["承認"] == True]

            if len(approved_rows) == 0:
                st.warning("承認する項目を選択してください")
            else:
                # 最初の行のカテゴリIDを取得
                category_name = approved_rows.iloc[0]["カテゴリ"]
                category_id = category_map[category_name]

                for _, row in approved_rows.iterrows():
                    # クラスタ情報を取得
                    cluster = next(c for c in clusters.data if c["id"] == row["id"])
                    general_name = cluster["general_name"]
                    product_ids = cluster["product_ids"]
                    product_names = cluster["product_names"]
                    confidence = cluster["confidence_avg"]

                    # Tier 1: 各商品名 → general_name のマッピング
                    for product_name in set(product_names):
                        db.table('70_ms_product_normalization').upsert({
                            "raw_keyword": product_name,
                            "general_name": general_name,
                            "confidence_score": confidence,
                            "source": "gemini_batch"
                        }, on_conflict="raw_keyword,general_name").execute()

                    # Tier 2: general_name + context → category_id
                    db.table('70_ms_product_classification').upsert({
                        "general_name": general_name,
                        "source_type": "online_shop",
                        "workspace": "shopping",
                        "doc_type": "online shop",
                        "organization": None,
                        "category_id": category_id,
                        "approval_status": "approved",
                        "confidence_score": confidence
                    }, on_conflict="general_name,source_type,workspace,doc_type,organization").execute()

                    # 80_rd_productsを更新
                    for product_id in product_ids:
                        db.table('80_rd_products').update({
                            "general_name": general_name,
                            "category_id": category_id,
                            "needs_approval": False,
                            "classification_confidence": confidence
                        }).eq('id', product_id).execute()

                    # クラスタのステータスを更新
                    db.table('99_tmp_gemini_clustering').update({
                        "approval_status": "approved"
                    }).eq('id', row["id"]).execute()

                st.success(f"{len(approved_rows)}件のクラスタを承認しました")
                st.rerun()

    except Exception as e:
        st.error(f"エラー: {e}")


def show_category_tree():
    """カテゴリツリー編集"""
    st.subheader("🌳 カテゴリツリー管理")
    st.info("カテゴリの階層構造を管理します")

    try:
        # カテゴリ取得
        categories = db.table('60_ms_categories').select('*').order('name').execute()

        # ツリー構築
        def build_tree(parent_id=None, level=0):
            items = []
            for cat in categories.data:
                if cat.get("parent_id") == parent_id:
                    items.append({
                        "id": cat["id"],
                        "name": cat["name"],
                        "level": level,
                        "is_expense": cat.get("is_expense", True),
                        "parent_id": parent_id
                    })
                    items.extend(build_tree(cat["id"], level + 1))
            return items

        tree = build_tree()

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
                    db.table('60_ms_categories').delete().eq('id', item['id']).execute()
                    st.success("削除しました")
                    st.rerun()

        st.divider()

        # 新規追加フォーム
        st.markdown("### 新規カテゴリ追加")

        col1, col2, col3 = st.columns(3)

        with col1:
            new_name = st.text_input("カテゴリ名")

        with col2:
            parent_options = {"（親なし）": None}
            parent_options.update({cat["name"]: cat["id"] for cat in categories.data})
            selected_parent = st.selectbox("親カテゴリ", options=list(parent_options.keys()))

        with col3:
            is_expense = st.checkbox("支出カテゴリ", value=True)

        if st.button("追加", type="primary"):
            if new_name:
                parent_id = parent_options[selected_parent]
                db.table('60_ms_categories').insert({
                    "name": new_name,
                    "is_expense": is_expense,
                    "parent_id": parent_id
                }).execute()
                st.success(f"カテゴリ「{new_name}」を追加しました")
                st.rerun()
            else:
                st.warning("カテゴリ名を入力してください")

    except Exception as e:
        st.error(f"エラー: {e}")


if __name__ == "__main__":
    main()
