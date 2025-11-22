"""
マルチLLMクライアント (FINAL_UNIFIED_COMPLETE_v4.md, COMPLETE_IMPLEMENTATION_GUIDE_v3.mdに基づく)
Gemini / Claude / OpenAI を統一インターフェースで利用
"""
import os
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import json

import google.generativeai as genai
from anthropic import Anthropic
from openai import OpenAI
from loguru import logger

# 設定ファイルからインポート
from config.model_tiers import AIProvider, get_model_config

class LLMClient:
    """統合LLMクライアント"""
    
    def __init__(self):
        """環境変数からAPIキーを取得し、各プロバイダーを初期化"""
        
        self.gemini_api_key = os.getenv("GOOGLE_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        # Gemini設定 (FINAL_UNIFIED_COMPLETE_v4.md, 5.1節)
        if self.gemini_api_key:
            genai.configure(api_key=self.gemini_api_key)
        
        # Claude設定 (FINAL_UNIFIED_COMPLETE_v4.md, 5.1節)
        if self.anthropic_api_key:
            self.anthropic_client = Anthropic(api_key=self.anthropic_api_key)
        else:
            self.anthropic_client = None
        
        # OpenAI設定 (FINAL_UNIFIED_COMPLETE_v4.md, 5.1節)
        if self.openai_api_key:
            self.openai_client = OpenAI(api_key=self.openai_api_key)
        else:
            self.openai_client = None
        
        #logger.info("LLMクライアント初期化完了")
    
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
        model_name = config["model"]
        
        if provider == AIProvider.GEMINI:
            if not self.gemini_api_key:
                return {"success": False, "error": "Gemini API key is missing", "model": model_name}
            return self._call_gemini(model_name, prompt, file_path, config, **kwargs)
        
        elif provider == AIProvider.CLAUDE:
            if not self.anthropic_client:
                return {"success": False, "error": "Claude API key is missing", "model": model_name}
            return self._call_claude(model_name, prompt, config, **kwargs)
        
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
        """Gemini API呼び出し (FINAL_UNIFIED_COMPLETE_v4.md, 4.2節を参考に実装)"""
        try:
            model = genai.GenerativeModel(model_name)
            
            content_parts = [prompt]
            
            if file_path and file_path.exists():
                uploaded_file = genai.upload_file(file_path)
                content_parts.append(uploaded_file)
            
            response = model.generate_content(
                content_parts,
                generation_config=genai.GenerationConfig(
                    max_output_tokens=config.get("max_tokens", 1000),
                    temperature=config.get("temperature", 0.1)
                )
            )
            
            # アップロードしたファイルを削除（コスト節約とクリーンアップのため）
            if file_path and file_path.exists():
                 genai.delete_file(uploaded_file.name)
            
            return {
                "success": True,
                "content": response.text,
                "model": model_name,
                "provider": "gemini"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e), "model": model_name, "provider": "gemini"}

    def _call_claude(
        self,
        model_name: str,
        prompt: str,
        config: Dict,
        **kwargs
    ) -> Dict[str, Any]:
        """Claude API呼び出し (FINAL_UNIFIED_COMPLETE_v4.md, 4.3節を参考に実装)"""
        try:
            response = self.anthropic_client.messages.create(
                model=model_name,
                max_tokens=config.get("max_tokens", 4096),
                temperature=config.get("temperature", 0.0),
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            return {
                "success": True,
                "content": response.content[0].text,
                "model": model_name,
                "provider": "claude"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e), "model": model_name, "provider": "claude"}

    def _call_openai(
        self,
        model_name: str,
        prompt: str,
        config: Dict,
        **kwargs
    ) -> Dict[str, Any]:
        """OpenAI API呼び出し (FINAL_UNIFIED_COMPLETE_v4.md, 5.1節を参考に実装)"""
        try:
            # max_tokensをmax_completion_tokensとして渡す（APIの互換性対応）
            max_tokens = config.get("max_tokens", 2048)
            
            response = self.openai_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=max_tokens, # パラメータ名を修正
                temperature=config.get("temperature", 0.7)
            )
            
            return {
                "success": True,
                "content": response.choices[0].message.content,
                "model": model_name,
                "provider": "openai"
            }
            
        except Exception as e:
            # エラーログを改善
            return {"success": False, "error": str(e), "model": model_name, "provider": "openai"}

    def generate_embedding(self, text: str) -> List[float]:
        """Embedding生成 (COMPLETE_IMPLEMENTATION_GUIDE_v3.md, 3.2節を参考に実装)"""
        config = get_model_config("embeddings")
        
        if not self.openai_client:
            raise ConnectionError("OpenAI client not initialized for embedding generation.")
            
        response = self.openai_client.embeddings.create(
            model=config["model"],
            input=text
        )
        
        return response.data[0].embedding