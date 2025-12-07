"""
LLMクライアント（v3.0: マルチプロバイダ対応）
Gemini / Claude / OpenAI を統一インターフェースで利用
"""

import os
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import json
import mimetypes

import google.generativeai as genai
from anthropic import Anthropic, RateLimitError
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, RetryError
from loguru import logger

from config.model_tiers import AIProvider, ModelTier, get_model_config

class LLMClient:
    """統合LLMクライアント"""
    
    def __init__(self):
        """環境変数からAPIキーを取得し、各プロバイダーを初期化"""

        # Gemini APIキーは GOOGLE_AI_API_KEY または GOOGLE_API_KEY から取得
        self.gemini_api_key = os.getenv("GOOGLE_AI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")

        # Gemini設定 (トップレベル関数のみ使用)
        if self.gemini_api_key:
            genai.configure(api_key=self.gemini_api_key)
        else:
            pass

        # Claude設定
        if self.anthropic_api_key:
            self.anthropic_client = Anthropic(api_key=self.anthropic_api_key)
        else:
            self.anthropic_client = None

        # OpenAI設定
        if self.openai_api_key:
            self.openai_client = OpenAI(api_key=self.openai_api_key)
        else:
            self.openai_client = None
    
    def generate_with_images(
        self,
        prompt: str,
        image_data: Union[str, List[str]],
        model: str = "gemini-2.0-flash-lite",
        temperature: float = 0.0,
        max_tokens: int = 2048
    ) -> str:
        """
        画像データを使ってGemini Vision APIを呼び出し

        Args:
            prompt: プロンプト
            image_data: Base64エンコードされた画像データ（単一または複数）
            model: モデル名
            temperature: 温度パラメータ
            max_tokens: 最大トークン数

        Returns:
            生成されたテキスト
        """
        import base64

        if not self.gemini_api_key:
            raise ValueError("Gemini API key is missing")

        try:
            model_obj = genai.GenerativeModel(model)

            # 画像データをリスト化
            if isinstance(image_data, str):
                image_data_list = [image_data]
            else:
                image_data_list = image_data

            # コンテンツパーツを構築
            content_parts = [prompt]

            # 画像を追加
            for img_base64 in image_data_list:
                # Base64をバイトにデコード
                img_bytes = base64.b64decode(img_base64)

                # Geminiの画像形式に変換
                image_part = {
                    'mime_type': 'image/png',
                    'data': img_bytes
                }
                content_parts.append(image_part)

            # 安全フィルター設定
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]

            # APIを呼び出し
            response = model_obj.generate_content(
                content_parts,
                generation_config=genai.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=temperature
                ),
                safety_settings=safety_settings
            )

            # レスポンスの検証
            if not response.candidates:
                raise ValueError("Gemini returned no candidates")

            candidate = response.candidates[0]

            # finish_reason をチェック
            if candidate.finish_reason != 1:  # 1 = STOP (正常終了)
                finish_reason_name = candidate.finish_reason.name if hasattr(candidate.finish_reason, 'name') else str(candidate.finish_reason)
                error_details = {
                    "finish_reason": candidate.finish_reason,
                    "finish_reason_name": finish_reason_name
                }
                if hasattr(candidate, 'safety_ratings') and candidate.safety_ratings:
                    error_details["safety_ratings"] = [
                        {
                            "category": rating.category.name if hasattr(rating.category, 'name') else str(rating.category),
                            "probability": rating.probability.name if hasattr(rating.probability, 'name') else str(rating.probability)
                        }
                        for rating in candidate.safety_ratings
                    ]
                logger.error(f"Gemini Vision失敗: {error_details}")
                raise ValueError(f"Gemini finish_reason: {finish_reason_name} ({candidate.finish_reason})")

            # テキストを取得
            text_content = candidate.content.parts[0].text if candidate.content.parts else ""
            return text_content

        except Exception as e:
            logger.error(f"Gemini Vision API エラー: {e}")
            raise

    def call_model(
        self,
        tier: str,
        prompt: str,
        file_path: Optional[Path] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        指定されたタスクに最適なモデルを呼び出し

        Args:
            tier: モデル階層("stage1_classification", "stage2_extraction", "ui_response")
            prompt: プロンプト
            file_path: ファイルパス (GeminiのStage 1分類用)
            **kwargs: 追加パラメータ

        Returns:
            モデルレスポンス
        """
        config = get_model_config(tier)
        provider = config["provider"]
        # kwargsからmodel_nameが渡されていればそれを優先、なければconfigから取得
        model_name = kwargs.pop('model_name', None) or config["model"]

        if provider == AIProvider.GEMINI:
            if not self.gemini_api_key:
                return {"success": False, "error": "Gemini API key is missing", "model": model_name}
            return self._call_gemini(model_name, prompt, file_path, config, **kwargs)

        elif provider == AIProvider.CLAUDE:
            if not self.anthropic_client:
                return {"success": False, "error": "Claude API key is missing", "model": model_name}
            try:
                return self._call_claude(model_name, prompt, config, **kwargs)
            except RetryError as e:
                # リトライが全て失敗した場合
                original_error = e.last_attempt.exception()
                return {"success": False, "error": str(original_error), "model": model_name, "provider": "claude"}

        elif provider == AIProvider.OPENAI:
            if not self.openai_client:
                return {"success": False, "error": "OpenAI API key is missing", "model": model_name}
            return self._call_openai(model_name, prompt, config, **kwargs)

        else:
            raise ValueError(f"未対応のプロバイダー: {provider}")

    def _call_gemini(
        self,
        model_name: str,
        prompt: str,
        file_path: Optional[Path],
        config: Dict,
        **kwargs
    ) -> Dict[str, Any]:
        """Gemini API呼び出し（トップレベル関数のみ使用）"""
        uploaded_file = None
        try:
            model = genai.GenerativeModel(model_name)

            content_parts = [prompt]

            if file_path and file_path.exists():
                # MIMEタイプを自動判定
                mime_type, _ = mimetypes.guess_type(str(file_path))
                if not mime_type:
                    mime_type = "application/pdf"  # デフォルト

                # ファイルをアップロード（トップレベル関数のみ使用）
                uploaded_file = genai.upload_file(path=str(file_path), mime_type=mime_type)
                content_parts.append(uploaded_file)

            # 安全フィルター設定（finish_reason: 2 対策）
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]

            response = model.generate_content(
                content_parts,
                generation_config=genai.GenerationConfig(
                    max_output_tokens=config.get("max_tokens", 2000),
                    temperature=config.get("temperature", 0.1)
                ),
                safety_settings=safety_settings
            )

            # レスポンスの検証
            if not response.candidates:
                self._cleanup_uploaded_file(uploaded_file)
                return {"success": False, "error": "Gemini returned no candidates", "model": model_name, "provider": "gemini"}

            candidate = response.candidates[0]

            # finish_reason をチェック
            if candidate.finish_reason != 1:  # 1 = STOP (正常終了)
                self._cleanup_uploaded_file(uploaded_file)
                # 詳細なエラー情報を取得
                error_details = {
                    "finish_reason": candidate.finish_reason,
                    "finish_reason_name": candidate.finish_reason.name if hasattr(candidate.finish_reason, 'name') else str(candidate.finish_reason)
                }
                # safety_ratingsがあれば追加
                if hasattr(candidate, 'safety_ratings') and candidate.safety_ratings:
                    error_details["safety_ratings"] = [
                        {
                            "category": rating.category.name if hasattr(rating.category, 'name') else str(rating.category),
                            "probability": rating.probability.name if hasattr(rating.probability, 'name') else str(rating.probability)
                        }
                        for rating in candidate.safety_ratings
                    ]
                logger.error(f"Gemini Vision失敗: {error_details}")
                return {
                    "success": False,
                    "error": f"Gemini finish_reason: {candidate.finish_reason}",
                    "error_details": error_details,
                    "model": model_name,
                    "provider": "gemini"
                }

            # テキストを取得
            text_content = candidate.content.parts[0].text if candidate.content.parts else ""

            # ファイルを削除
            self._cleanup_uploaded_file(uploaded_file)

            return {
                "success": True,
                "content": text_content,
                "model": model_name,
                "provider": "gemini"
            }

        except Exception as e:
            self._cleanup_uploaded_file(uploaded_file)
            return {"success": False, "error": str(e), "model": model_name, "provider": "gemini"}

    def _cleanup_uploaded_file(self, uploaded_file) -> None:
        """
        アップロードされたファイルを削除（トップレベル関数のみ使用）

        Args:
            uploaded_file: アップロードされたファイルオブジェクト
        """
        if not uploaded_file:
            return

        try:
            genai.delete_file(name=uploaded_file.name)
        except Exception:
            # 削除に失敗しても処理は継続
            pass

    @retry(
        retry=retry_if_exception_type(RateLimitError),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60)
    )
    def _call_claude(
        self,
        model_name: str,
        prompt: str,
        config: Dict,
        **kwargs
    ) -> Dict[str, Any]:
        """Claude API呼び出し"""
        try:
            # ✅ DEBUG: 送信するプロンプトの先頭部分をログに出力
            from loguru import logger
            logger.debug(f"[Claude CALL] Model: {model_name}, Prompt start: {prompt[:300]}...")

            response = self.anthropic_client.messages.create(
                model=model_name,
                max_tokens=config.get("max_tokens", 4096),
                temperature=config.get("temperature", 0.0),
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # ✅ DEBUG: Claude からの生の応答コンテンツ全体をログに出力
            raw_content = response.content[0].text
            logger.debug(f"[Claude RAW RESP] Content length: {len(raw_content)} chars")
            # 応答が長すぎる場合があるため、先頭2000文字のみをログに記録
            logger.debug(f"[Claude RAW RESP] Content preview: {raw_content[:2000]}")

            return {
                "success": True,
                "content": raw_content,
                "model": model_name,
                "provider": "claude"
            }

        except RateLimitError:
            # RateLimitErrorは再スローしてtenacityにリトライさせる
            raise
        except Exception as e:
            return {"success": False, "error": str(e), "model": model_name, "provider": "claude"}

    def _call_openai(
        self,
        model_name: str,
        prompt: str,
        config: Dict,
        **kwargs
    ) -> Dict[str, Any]:
        """OpenAI API呼び出し"""
        try:
            # ✅ GPT-5.1では max_completion_tokens を使用、旧モデルでは max_tokens（後方互換性）
            max_completion_tokens = config.get("max_completion_tokens")
            max_tokens = config.get("max_tokens", 2048)

            # パラメータを動的に構築
            api_params = {
                "model": model_name,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }

            # temperatureはGPT-5.1などの一部モデルでサポートされていないため、configに含まれている場合のみ設定
            if "temperature" in config:
                api_params["temperature"] = config["temperature"]

            # max_completion_tokens が設定されていればそれを使用、なければ max_tokens
            if max_completion_tokens:
                api_params["max_completion_tokens"] = max_completion_tokens
            else:
                api_params["max_tokens"] = max_tokens

            response = self.openai_client.chat.completions.create(**api_params)
            
            return {
                "success": True,
                "content": response.choices[0].message.content,
                "model": model_name,
                "provider": "openai"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e), "model": model_name, "provider": "openai"}

    def generate_embedding(self, text: str) -> List[float]:
        """
        Embedding生成

        Args:
            text: Embeddingを生成するテキスト

        Returns:
            1536次元のembeddingベクトル
        """
        config = get_model_config("embeddings")

        if not self.openai_client:
            raise ConnectionError("OpenAI client not initialized for embedding generation.")

        # text-embedding-3-smallモデルで1536次元を明示的に指定
        response = self.openai_client.embeddings.create(
            model=config["model"],
            input=text,
            dimensions=config.get("dimensions", 1536)  # デフォルト1536次元
        )

        return response.data[0].embedding

    def transcribe_image(
        self,
        image_path: Path,
        prompt: str = "この画像内の表組みやリストを、Markdown形式で正確に書き起こしてください。"
    ) -> Dict[str, Any]:
        """
        画像ファイルをGemini Visionで文字起こし

        Args:
            image_path: 画像ファイルのパス（PNG, JPEG等）
            prompt: Geminiに送るプロンプト

        Returns:
            {"success": bool, "content": str, "model": str, "provider": str}
        """
        if not self.gemini_api_key:
            return {"success": False, "error": "Gemini API key is missing", "model": "gemini-2.5-flash"}

        # Gemini Flash を使用（画像処理に最適）
        return self._call_gemini(
            model_name="gemini-2.5-flash",
            prompt=prompt,
            file_path=image_path,
            config={
                "max_tokens": 8192,  # トークン数を増やして長い出力に対応
                "temperature": 0.0
            }
        )