"""
Stage B: Vision処理プロセッサ (ルートタイプ別2段階処理)

HTMLメールやPDFをVision APIで解析
- ルートタイプごとに最適なモデルとプロンプトを使用
- email/file/premium などのルートタイプに対応
旧名: Email Vision Processor
"""
import base64
from typing import Dict, Any, Optional, List
from loguru import logger
from bs4 import BeautifulSoup
import re

from A_common.utils.html_screenshot import HTMLScreenshotGenerator
from C_ai_common.llm_client.llm_client import LLMClient
from A_common.config.model_tiers import ModelTier


class StageBVisionProcessor:
    """Stage B: Vision APIで視覚的コンテンツを解析するプロセッサ"""

    # ルートタイプ別のモデル設定
    ROUTE_CONFIGS = {
        "email": {
            "description": "メールルート（高速・低コスト）",
            "step1": {
                "model": "gemini-2.5-flash-lite",
                "temperature": 0.1,
                "max_tokens": 16384,
                "prompt_key": "email_step1"
            },
            "step2": {
                "model": "gemini-2.5-flash",
                "temperature": 0.0,
                "max_tokens": 8192,
                "prompt_key": "email_step2"
            }
        },
        "file": {
            "description": "ファイルルート（高精度）",
            "step1": {
                "model": "gemini-2.5-pro",
                "temperature": 0.1,
                "max_tokens": 16384,
                "prompt_key": "file_step1"
            },
            "step2": {
                "model": "gemini-2.5-flash",
                "temperature": 0.0,
                "max_tokens": 8192,
                "prompt_key": "file_step2"
            }
        },
        "premium": {
            "description": "プレミアムルート（最高精度）",
            "step1": {
                "model": "gemini-2.5-pro",
                "temperature": 0.1,
                "max_tokens": 16384,
                "prompt_key": "premium_step1"
            },
            "step2": {
                "model": "gemini-2.5-pro",
                "temperature": 0.0,
                "max_tokens": 8192,
                "prompt_key": "premium_step2"
            }
        }
    }

    # プロンプトテンプレート定義
    PROMPTS = {
        # ========================================
        # メールルート用プロンプト
        # ========================================
        "email_step1": """この画像を確認し、読み取れるすべてのテキストを書き出してください。

{metadata_info}

【指示】
- 上から下、左から右の順で、見えるテキストを書き出してください
- 小さな文字も含めてください
- 画像や図がある場合、その説明も含めてください
- JSON形式は不要です。自然なテキストで出力してください

出力形式:
---
[画像内の全テキスト]
---""",

        "email_step2": """以下の【生テキストデータ】を元に、メール情報を抽出してJSON形式で整理してください。

【生テキストデータ】
{raw_text}

【出力形式】
以下のJSON形式で出力してください:
{{
  "extracted_text": "抽出されたテキスト全文",
  "summary": "メールの要約（2-3文）",
  "key_information": ["重要な情報1", "重要な情報2"],
  "has_images": true/false,
  "image_descriptions": ["画像の説明"],
  "tables": ["テーブルの内容"],
  "links": ["リンクURL"]
}}

【注意】
- 生データに含まれていない情報は推測しないでください
- extracted_textには生データをそのまま入れてください""",

        # ========================================
        # ファイルルート用プロンプト（チラシ・フライヤー特化）
        # ========================================
        "file_step1": """あなたはプロのOCRスペシャリストです。この画像を隅々までスキャンし、読み取れるすべてのテキストを1文字も漏らさず書き出してください。

{metadata_info}

【重要な指示】
- 上から下、左から右の順で、見えるすべての文字を書き出してください
- フォントサイズや色に関わらず、小さな注釈、住所、メールアドレス、電話番号もすべて含めてください
- 画像や図表がある場合、その説明も含めてください
- テーブルやリストがある場合、その構造を維持してください
- チラシの隅にある小さな文字（お問い合わせ先、注意事項、アクセス情報など）は特に注意深く読み取ってください
- 解釈や要約は不要です。見えたままを出力してください
- JSON形式は不要です。自然なテキストで出力してください

出力形式:
---
[画像内の全テキストをここに書き出す]
---""",

        "file_step2": """以下の【生テキストデータ】は、画像から抽出されたすべての文字情報です。
このデータを元に、正確な情報を抽出してJSON形式で整理してください。

【生テキストデータ】
{raw_text}

【出力形式】
以下のJSON形式で出力してください:
{{
  "extracted_text": "抽出されたテキスト全文（生データそのままでOK）",
  "summary": "内容の要約（2-3文）",
  "key_information": [
    "重要な情報1（日付、金額、リンク、アクションアイテムなど）",
    "重要な情報2"
  ],
  "has_images": true/false,
  "image_descriptions": ["画像の説明（生データから判断）"],
  "tables": ["テーブルの内容"],
  "links": ["リンクURL"]
}}

【注意】
- 生データに含まれていない情報は推測しないでください
- extracted_textには生データをそのまま入れてください
- 小さな文字で書かれた注釈やお問い合わせ先も key_information に含めてください""",

        # ========================================
        # プレミアムルート用プロンプト（最高精度）
        # ========================================
        "premium_step1": """あなたは最高レベルのOCRスペシャリストであり、プロの校正者です。この画像を極めて注意深くスキャンし、読み取れるすべてのテキストを完璧に書き出してください。

{metadata_info}

【最重要指示】
- 上から下、左から右の順で、見えるすべての文字を書き出してください
- フォントサイズや色に関わらず、極小文字、注釈、住所、メールアドレス、電話番号もすべて含めてください
- 画像や図表がある場合、その詳細な説明も含めてください
- テーブルやリストがある場合、その構造を正確に維持してください
- 特殊なフォント、デザイン文字、装飾文字も文脈から正しく判断してください
- 文字が重なっている、かすれている、背景と同化している場合でも、文脈から推測して書き出してください
- 解釈や要約は不要です。見えたまま、かつ推測も含めて完璧に出力してください
- JSON形式は不要です。自然なテキストで出力してください

出力形式:
---
[画像内の全テキストを完璧に書き出す]
---""",

        "premium_step2": """以下の【生テキストデータ】は、最高精度で抽出されたすべての文字情報です。
このデータを元に、極めて正確な情報を抽出してJSON形式で整理してください。

【生テキストデータ】
{raw_text}

【出力形式】
以下のJSON形式で出力してください:
{{
  "extracted_text": "抽出されたテキスト全文（生データそのままでOK）",
  "summary": "内容の詳細な要約（3-5文）",
  "key_information": [
    "重要な情報1（日付、金額、リンク、アクションアイテムなど、極めて詳細に）",
    "重要な情報2"
  ],
  "has_images": true/false,
  "image_descriptions": ["画像の詳細な説明（生データから判断）"],
  "tables": ["テーブルの内容（完全な形で）"],
  "links": ["リンクURL"]
}}

【注意】
- 生データに含まれていない情報は推測しないでください
- extracted_textには生データをそのまま入れてください
- すべての情報を漏らさず key_information に含めてください
- 最高レベルの精度で構造化してください"""
    }

    def __init__(self, route_type: str = "email"):
        """
        初期化

        Args:
            route_type: 処理ルートタイプ ("email", "file", "premium")
        """
        self.screenshot_generator = HTMLScreenshotGenerator(
            viewport_width=1600,  # 解像度を上げる（細かい文字に対応）
            viewport_height=2400  # A4/B5チラシの縦長比率に対応
        )
        self.llm_client = LLMClient()
        self.model_config = ModelTier.EMAIL_VISION

        # ルートタイプを設定
        self.route_type = route_type
        if route_type not in self.ROUTE_CONFIGS:
            logger.warning(f"未知のルートタイプ: {route_type}. デフォルト'email'を使用します")
            self.route_type = "email"

        self.route_config = self.ROUTE_CONFIGS[self.route_type]

        logger.info(f"StageBVisionProcessor初期化完了")
        logger.info(f"  - ルート: {self.route_type} ({self.route_config['description']})")
        logger.info(f"  - Step 1: {self.route_config['step1']['model']}")
        logger.info(f"  - Step 2: {self.route_config['step2']['model']}")
        logger.info(f"  - 解像度: 1600x2400px")

    def _extract_html_text(self, html_content: str) -> Dict[str, Any]:
        """
        HTMLからテキストとリンクを抽出

        Args:
            html_content: HTML文字列

        Returns:
            {
                'text': str,  # 抽出されたテキスト
                'links': List[str],  # URLリスト
                'has_tables': bool,  # テーブルがあるか
                'has_lists': bool  # リストがあるか
            }
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # スクリプトとスタイルを除去
            for script in soup(['script', 'style']):
                script.decompose()

            # テキストを抽出
            text = soup.get_text(separator='\n', strip=True)

            # 空行を削減（連続する改行を2つまでに）
            text = re.sub(r'\n{3,}', '\n\n', text)

            # リンクを抽出
            links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.startswith('http://') or href.startswith('https://'):
                    links.append(href)

            # テーブルとリストの存在チェック
            has_tables = len(soup.find_all('table')) > 0
            has_lists = len(soup.find_all(['ul', 'ol'])) > 0

            logger.info(f"HTML解析: テキスト={len(text)}文字, リンク={len(links)}個, テーブル={has_tables}, リスト={has_lists}")

            return {
                'text': text,
                'links': links,
                'has_tables': has_tables,
                'has_lists': has_lists
            }

        except Exception as e:
            logger.error(f"HTMLテキスト抽出エラー: {e}")
            return {
                'text': '',
                'links': [],
                'has_tables': False,
                'has_lists': False
            }

    def _merge_vision_and_html(
        self,
        vision_result: Dict[str, Any],
        html_extract: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Vision解析結果とHTML抽出結果をインテリジェントにマージ

        Args:
            vision_result: Vision APIの解析結果
            html_extract: HTMLから抽出したテキスト・リンク

        Returns:
            マージされた結果
        """
        try:
            # Visionのテキストを基本とする（画像説明などを含む）
            vision_text = vision_result.get('extracted_text', '')
            html_text = html_extract.get('text', '')

            # HTMLテキストの方が明らかに長い場合は、両方を組み合わせる
            if len(html_text) > len(vision_text) * 1.5:
                logger.info("HTMLテキストの方が長いため、両方を組み合わせます")

                # Visionの画像説明や特殊情報を抽出
                vision_special_info = []
                if vision_result.get('has_images') and vision_result.get('image_descriptions'):
                    vision_special_info.append("【画像内容】")
                    vision_special_info.extend(vision_result.get('image_descriptions', []))

                # 組み合わせ
                combined_text = f"{html_text}\n\n"
                if vision_special_info:
                    combined_text += "\n".join(vision_special_info)

                final_text = combined_text
            else:
                # Visionのテキストを優先
                final_text = vision_text

            # リンクをマージ（重複排除）
            vision_links = vision_result.get('links', [])
            html_links = html_extract.get('links', [])
            all_links = list(set(vision_links + html_links))

            # 結果をマージ
            merged_result = {
                'extracted_text': final_text,
                'summary': vision_result.get('summary', ''),
                'key_information': vision_result.get('key_information', []),
                'has_images': vision_result.get('has_images', False),
                'image_descriptions': vision_result.get('image_descriptions', []),
                'tables': vision_result.get('tables', []),
                'links': all_links,
                'has_tables': html_extract.get('has_tables', False) or len(vision_result.get('tables', [])) > 0,
                'has_lists': html_extract.get('has_lists', False)
            }

            logger.info(f"マージ完了: 最終テキスト={len(final_text)}文字, リンク={len(all_links)}個")

            return merged_result

        except Exception as e:
            logger.error(f"マージエラー: {e}")
            # エラー時はVisionの結果をそのまま返す
            return vision_result

    async def extract_email_content(
        self,
        html_content: str,
        email_metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        HTMLメールの内容をVision API + HTML解析で抽出

        処理フロー:
        1. Vision解析（画像・レイアウト・表を優先的に取得）
        2. HTMLテキスト抽出（純粋なテキスト部分を取得）
        3. インテリジェントマージ（両方の結果を統合）

        Args:
            html_content: メールのHTML内容
            email_metadata: メールのメタデータ（送信者、件名、日時など）

        Returns:
            抽出された内容
            {
                'extracted_text': str,  # 抽出されたテキスト内容
                'summary': str,  # 要約
                'key_information': list,  # 重要な情報のリスト
                'metadata': dict  # メタデータ
            }
        """
        try:
            logger.info("=" * 60)
            logger.info("メール解析開始: Vision + HTML解析")
            logger.info("=" * 60)
            logger.info("メールスクリーンショット生成中...")

            # HTMLをスクリーンショット化
            screenshot_bytes = await self.screenshot_generator.html_to_screenshot(
                html_content=html_content,
                full_page=True
            )

            # Base64エンコード
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')

            logger.info(f"スクリーンショット生成完了: {len(screenshot_bytes):,} bytes")

            # メタデータからプロンプトを構築
            metadata_info = ""
            if email_metadata:
                metadata_info = f"""
メールメタデータ:
- 送信者: {email_metadata.get('from', 'Unknown')}
- 受信者: {email_metadata.get('to', 'Unknown')}
- 件名: {email_metadata.get('subject', 'No Subject')}
- 日時: {email_metadata.get('date', 'Unknown')}
"""

            # ===================================================================
            # Step 1: 生データ抽出（すべてのテキストを漏れなく書き出し）
            # ===================================================================
            # ルート設定からプロンプトを取得
            step1_config = self.route_config['step1']
            prompt_template = self.PROMPTS[step1_config['prompt_key']]
            prompt_step1 = prompt_template.format(metadata_info=metadata_info)

            logger.info(f"Step 1: 生データ抽出開始（{step1_config['model']}使用）...")

            # Gemini APIを呼び出し（Step 1）
            try:
                raw_text = self.llm_client.generate_with_images(
                    prompt=prompt_step1,
                    image_data=screenshot_base64,
                    model=step1_config['model'],
                    temperature=step1_config['temperature'],
                    max_tokens=step1_config['max_tokens']
                )
                logger.info(f"Step 1完了（{step1_config['model']}）: {len(raw_text)}文字の生データを抽出")
                logger.debug(f"抽出された生データ（最初の500文字）: {raw_text[:500]}")
            except Exception as step1_error:
                # MAX_TOKENSエラーの場合はHTML抽出のみにフォールバック
                error_str = str(step1_error)
                if 'MAX_TOKENS' in error_str or 'max_tokens' in error_str:
                    logger.warning(f"⚠️ Step 1でMAX_TOKENSエラー。HTML抽出のみにフォールバックします: {error_str}")
                    html_extract = self._extract_html_text(html_content)
                    fallback_result = {
                        'extracted_text': html_extract.get('text', ''),
                        'summary': html_extract.get('text', '')[:200] + '...' if len(html_extract.get('text', '')) > 200 else html_extract.get('text', ''),
                        'key_information': ['⚠️ ドキュメントが長すぎるため、Vision解析をスキップしました'],
                        'has_images': False,
                        'image_descriptions': [],
                        'tables': [],
                        'links': html_extract.get('links', []),
                        'has_tables': html_extract.get('has_tables', False),
                        'has_lists': html_extract.get('has_lists', False),
                        'metadata': email_metadata or {}
                    }
                    logger.info(f"HTMLフォールバック完了: テキスト={len(fallback_result['extracted_text'])}文字")
                    return fallback_result
                else:
                    raise

            # ===================================================================
            # Step 2: 構造化（生データをJSON形式に整形）
            # ===================================================================
            # ルート設定からプロンプトを取得
            step2_config = self.route_config['step2']
            prompt_template = self.PROMPTS[step2_config['prompt_key']]
            prompt_step2 = prompt_template.format(raw_text=raw_text)

            logger.info(f"Step 2: 構造化開始（{step2_config['model']}使用）...")

            # Gemini APIを呼び出し（Step 2）
            try:
                response = self.llm_client.generate(
                    prompt=prompt_step2,
                    model=step2_config['model'],
                    temperature=step2_config['temperature'],
                    max_tokens=step2_config['max_tokens']
                )
                logger.info(f"Step 2完了（{step2_config['model']}）: JSON構造化完了")
            except Exception as vision_error:
                # MAX_TOKENSエラーの場合はHTML抽出のみにフォールバック
                error_str = str(vision_error)
                if 'MAX_TOKENS' in error_str or 'max_tokens' in error_str:
                    logger.warning(f"⚠️ MAX_TOKENSエラー検出。HTML抽出のみにフォールバックします: {error_str}")

                    # HTMLテキスト抽出のみを実行
                    html_extract = self._extract_html_text(html_content)

                    # HTML抽出結果を返す（Visionなし）
                    fallback_result = {
                        'extracted_text': html_extract.get('text', ''),
                        'summary': html_extract.get('text', '')[:200] + '...' if len(html_extract.get('text', '')) > 200 else html_extract.get('text', ''),
                        'key_information': ['⚠️ メールが長すぎるため、Vision解析をスキップしました'],
                        'has_images': False,
                        'image_descriptions': [],
                        'tables': [],
                        'links': html_extract.get('links', []),
                        'has_tables': html_extract.get('has_tables', False),
                        'has_lists': html_extract.get('has_lists', False),
                        'metadata': email_metadata or {}
                    }

                    logger.info(f"HTMLフォールバック完了: テキスト={len(fallback_result['extracted_text'])}文字, リンク={len(fallback_result['links'])}個")
                    return fallback_result
                else:
                    # その他のエラーは再raise
                    raise

            # デバッグ: レスポンスの最初の500文字をログ出力
            logger.debug(f"Vision APIレスポンス（最初の500文字）: {response[:500]}")

            # JSONレスポンスをパース
            import json

            # JSONブロックを抽出（非貪欲マッチから貪欲マッチに変更）
            json_match = re.search(r'```json\s*(\{.*\})\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                logger.debug(f"JSONブロック抽出成功。長さ: {len(json_str)} 文字")
            else:
                # JSONブロックがない場合、{ } で囲まれた部分を抽出
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    logger.debug(f"JSON抽出（ブロックなし）。長さ: {len(json_str)} 文字")
                else:
                    json_str = response
                    logger.debug("JSON構造が見つかりません。全体を使用")

            try:
                vision_result = json.loads(json_str)
                logger.info("JSON解析成功")
            except json.JSONDecodeError as e:
                # エスケープシーケンスエラーの場合、修正を試みる
                if 'escape' in str(e).lower():
                    logger.warning(f"エスケープエラー検出。修正を試みます: {str(e)[:100]}")
                    try:
                        # すべてのバックスラッシュを二重エスケープ
                        fixed_str = json_str
                        # 既に正しくエスケープされている部分を保護するため、段階的に処理

                        # Step 1: すべての \ を一時的にプレースホルダーに置き換え
                        fixed_str = fixed_str.replace('\\', '\x00BACKSLASH\x00')

                        # Step 2: プレースホルダーを \\ に置き換え
                        fixed_str = fixed_str.replace('\x00BACKSLASH\x00', '\\\\')

                        # Step 3: 正しいエスケープシーケンスを復元
                        # \\n -> \n, \\t -> \t, \\" -> \", \\\\ -> \\
                        fixed_str = fixed_str.replace('\\\\n', '\\n')
                        fixed_str = fixed_str.replace('\\\\t', '\\t')
                        fixed_str = fixed_str.replace('\\\\r', '\\r')
                        fixed_str = fixed_str.replace('\\\\"', '\\"')
                        fixed_str = fixed_str.replace('\\\\/', '\\/')
                        # Unicode エスケープ: \\uXXXX -> \uXXXX
                        fixed_str = re.sub(r'\\\\u([0-9a-fA-F]{4})', r'\\u\1', fixed_str)
                        # 二重バックスラッシュ: \\\\\\\\ -> \\\\
                        fixed_str = fixed_str.replace('\\\\\\\\', '\\\\')

                        vision_result = json.loads(fixed_str)
                        logger.info("エスケープ修正後、JSON解析成功！")
                    except json.JSONDecodeError as e2:
                        logger.warning(f"修正後もJSON解析失敗: {str(e2)[:100]}")
                        # それでも失敗した場合、テキストとして扱う
                        vision_result = {
                            'extracted_text': response,
                            'summary': response[:200] + '...' if len(response) > 200 else response,
                            'key_information': [],
                            'has_images': False,
                            'image_descriptions': [],
                            'tables': [],
                            'links': []
                        }
                else:
                    # エスケープエラー以外の場合、テキストとして扱う
                    logger.warning(f"JSON解析失敗: {str(e)[:100]}")
                    logger.debug(f"失敗したJSON文字列（最初の500文字）: {json_str[:500]}")
                    vision_result = {
                        'extracted_text': response,
                        'summary': response[:200] + '...' if len(response) > 200 else response,
                        'key_information': [],
                        'has_images': False,
                        'image_descriptions': [],
                        'tables': [],
                        'links': []
                    }

            logger.info(f"Vision解析結果: テキスト={len(vision_result.get('extracted_text', ''))}文字")

            # ステップ2: HTMLからテキストとリンクを抽出
            logger.info("HTMLからテキスト抽出中...")
            html_extract = self._extract_html_text(html_content)

            # ステップ3: Vision結果とHTML抽出結果をマージ
            logger.info("Vision結果とHTML抽出結果をマージ中...")
            merged_result = self._merge_vision_and_html(vision_result, html_extract)

            # メタデータを追加
            merged_result['metadata'] = email_metadata or {}

            logger.info("=" * 60)
            logger.info("メール解析完了")
            logger.info(f"  最終テキスト: {len(merged_result.get('extracted_text', ''))}文字")
            logger.info(f"  リンク: {len(merged_result.get('links', []))}個")
            logger.info(f"  画像: {merged_result.get('has_images', False)}")
            logger.info("=" * 60)

            return merged_result

        except Exception as e:
            logger.error(f"メールVision処理エラー: {e}", exc_info=True)
            raise
