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

                # DataFrameに変換（7要素構造）
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
                        "商品名": t["product_name"],
                        "数量": quantity,
                        "表示額": displayed_amount,
                        "外or内": tax_display_type,
                        "税率": f"{std.get('tax_rate', 10)}%",
                        "本体価": base_price_total,  # 税抜総額
                        "税額": tax_amount,
                        "税込価": tax_included_amount,  # 税込総額
                        "単価": tax_included_unit_price,  # 税込単価
                        "正式名": std.get("official_name") or "",
                        "物品名": t.get("item_name") or "",
                        "大分類": std.get("major_category") or "",
                        "小分類": std.get("minor_category") or "",
                        "人物": std.get("person") or "",
                        "名目": std.get("purpose") or "",
                        "要確認": "⚠️" if std.get("needs_review") else ""
                    })

                df = pd.DataFrame(df_data)

                # 金額関連のカラムをフォーマット（None値に対応）
                df["表示額"] = df["表示額"].apply(lambda x: f"¥{x:,}" if x is not None else "—")
                df["本体価"] = df["本体価"].apply(lambda x: f"¥{x:,}" if x is not None else "—")
                df["税額"] = df["税額"].apply(lambda x: f"¥{x:,}" if x is not None else "—")
                df["税込価"] = df["税込価"].apply(lambda x: f"¥{x:,}" if x is not None else "—")
                df["単価"] = df["単価"].apply(lambda x: f"¥{x:,}" if x is not None else "—")

                # データフレームを表示（横スクロール有効、高さ指定）
                st.dataframe(
                    df,
                    hide_index=True,
                    height=400  # 高さを指定して見やすく
                )

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
                    tax_summary = db.table("money_receipt_tax_summary") \
                        .select("*") \
                        .eq("processing_log_id", log["id"]) \
                        .execute()
                except Exception as e:
                    # テーブルが存在しない場合はスキップ
                    tax_summary = None

                # ========================================
                # レシート情報サマリー（詳細版）
                # ========================================
                st.subheader("📊 レシート情報サマリー")

                # 計算値を集計
                calc_subtotal = sum(
                    (t.get("60_rd_standardized_items") or {}).get("std_unit_price", 0) * (t.get("quantity") or 1)
                    for t in transactions.data
                )
                calc_total = sum(
                    (t.get("60_rd_standardized_items") or {}).get("std_amount", 0)
                    for t in transactions.data
                )

                # 基本情報（小計・合計）
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("### 小計（税抜）")
                    receipt_subtotal = receipt.get("subtotal_amount")
                    if receipt_subtotal is not None:
                        st.write(f"**レシート記載**: ¥{receipt_subtotal:,}")
                    else:
                        st.write("**レシート記載**: —")
                    st.write(f"**計算値**: ¥{calc_subtotal:,}")
                    if receipt_subtotal and abs(calc_subtotal - receipt_subtotal) > 5:
                        st.warning(f"⚠️ 差分: ¥{calc_subtotal - receipt_subtotal:+,}")

                with col2:
                    st.markdown("### 税込合計")
                    receipt_total = receipt.get("total_amount_check")
                    if receipt_total is not None:
                        st.write(f"**レシート記載**: ¥{receipt_total:,}")
                    else:
                        st.write("**レシート記載**: —")
                    st.write(f"**計算値**: ¥{calc_total:,}")
                    if receipt_total and abs(calc_total - receipt_total) > 5:
                        st.warning(f"⚠️ 差分: ¥{calc_total - receipt_total:+,}")

                # 税率別の詳細情報
                if tax_summary and tax_summary.data:
                    summary = tax_summary.data[0]

                    st.markdown("---")
                    st.markdown(f"### 税率別詳細（{tax_display_type}レシート）")

                    match_icon = "✅" if summary["calculated_matches_actual"] else "⚠️"
                    st.markdown(f"**整合性**: {match_icon} {'一致' if summary['calculated_matches_actual'] else '不一致'}")

                    # 8%と10%のデータを整理
                    tax_detail_data = {
                        "項目": [
                            f"{tax_display_type}8%対象額（税抜）",
                            f"{tax_display_type}8%税額",
                            f"{tax_display_type}8%対象額（税込）",
                            f"{tax_display_type}10%対象額（税抜）",
                            f"{tax_display_type}10%税額",
                            f"{tax_display_type}10%対象額（税込）"
                        ],
                        "レシート記載": [
                            f"¥{summary['tax_8_subtotal']:,}" if summary.get('tax_8_subtotal') is not None else "—",
                            f"¥{summary['tax_8_amount']:,}" if summary.get('tax_8_amount') is not None else "—",
                            f"¥{(summary.get('tax_8_subtotal', 0) + summary.get('tax_8_amount', 0)):,}" if summary.get('tax_8_subtotal') is not None else "—",
                            f"¥{summary['tax_10_subtotal']:,}" if summary.get('tax_10_subtotal') is not None else "—",
                            f"¥{summary['tax_10_amount']:,}" if summary.get('tax_10_amount') is not None else "—",
                            f"¥{(summary.get('tax_10_subtotal', 0) + summary.get('tax_10_amount', 0)):,}" if summary.get('tax_10_subtotal') is not None else "—"
                        ],
                        "計算値": [
                            "—",  # 税抜は計算しない
                            f"¥{summary['calculated_tax_8_amount']:,}" if summary.get('calculated_tax_8_amount') is not None else "—",
                            f"¥{total_amount_8:,}",  # 8%税込合計（計算値）
                            "—",  # 税抜は計算しない
                            f"¥{summary['calculated_tax_10_amount']:,}" if summary.get('calculated_tax_10_amount') is not None else "—",
                            f"¥{total_amount_10:,}"  # 10%税込合計（計算値）
                        ],
                        "差分": [
                            "—",
                            f"{summary['tax_8_diff']:+d}円" if summary.get('tax_8_diff') is not None else "—",
                            "—",
                            "—",
                            f"{summary['tax_10_diff']:+d}円" if summary.get('tax_10_diff') is not None else "—",
                            "—"
                        ]
                    }

                    st.table(pd.DataFrame(tax_detail_data))
                else:
                    # tax_summaryがない場合は簡易表示
                    st.markdown("---")
                    st.markdown("### 税額サマリー")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**8%税額（計算）**: ¥{total_tax_8:,}")
                    with col2:
                        st.write(f"**10%税額（計算）**: ¥{total_tax_10:,}")

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


if __name__ == "__main__":
    main()
