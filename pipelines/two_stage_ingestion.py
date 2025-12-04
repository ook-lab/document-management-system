"""
2段階取り込みパイプライン（v4.0: ハイブリッドAI版）
Stage 2（Claude詳細抽出）実装版
"""

import os
import asyncio
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from loguru import logger
import hashlib
import json
import traceback

from core.connectors.google_drive import GoogleDriveConnector
from core.processors.pdf import PDFProcessor
from core.processors.office import OfficeProcessor
from core.ai.stage1_classifier import Stage1Classifier
from core.ai.stage2_extractor import Stage2Extractor
from core.ai.confidence_calculator import calculate_total_confidence
from core.ai.json_validator import validate_metadata
# from core.ai.embeddings import EmbeddingClient  # 768次元 - 使用しない
from core.database.client import DatabaseClient
from core.ai.llm_client import LLMClient
from config.yaml_loader import get_classification_yaml_string

PROCESSING_STATUS = {
    "PENDING": "pending",
    "COMPLETED": "completed",
    "FAILED": "failed",
    "SKIPPED": "skipped"
}

class TwoStageIngestionPipeline:
    """2段階取り込みパイプライン"""
    
    def __init__(self, temp_dir: str = "./temp"):
        
        self.llm_client = LLMClient()
        self.drive = GoogleDriveConnector()
        self.db = DatabaseClient()
        self.yaml_string = get_classification_yaml_string()

        self.pdf_processor = PDFProcessor(llm_client=self.llm_client)
        self.office_processor = OfficeProcessor()

        self.stage1_classifier = Stage1Classifier(llm_client=self.llm_client)
        self.stage2_extractor = Stage2Extractor(llm_client=self.llm_client)
        # EmbeddingはLLMClient経由で生成（1536次元）
        # self.embeddings = EmbeddingClient()  # 削除
        
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # Stage 2は完全リレー方式（判定なし、Stage 1の結果を必ずStage 2へ）

        logger.info("TwoStageIngestionPipeline初期化完了 (完全リレー方式: Gemini→Haiku)")
    
    def _extract_text(self, local_path: str, mime_type: str) -> Dict[str, Any]:
        """ファイルタイプに応じてテキスト抽出をルーティング"""
        
        logger.debug(f"テキスト抽出開始: {local_path}, mime_type={mime_type}")
        logger.debug(f"ファイル存在確認: {Path(local_path).exists()}")
        logger.debug(f"ファイルサイズ: {Path(local_path).stat().st_size if Path(local_path).exists() else 'N/A'} bytes")
        
        mime_map = {
            "application/pdf": self.pdf_processor.extract_text,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": self.office_processor.extract_from_docx,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": self.office_processor.extract_from_xlsx,
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": self.office_processor.extract_from_pptx,
        }
        
        processor = mime_map.get(mime_type)
        if processor:
            result = processor(local_path)
            logger.debug(f"抽出結果: success={result.get('success')}, content_length={len(result.get('content', ''))}")
            return result
        
        return {"content": "", "metadata": {}, "success": False, "error_message": f"Unsupported MIME Type: {mime_type}"}

    def _get_file_type(self, mime_type: str) -> str:
        """MIME Typeからfile_typeを判定"""
        mapping = {
            "application/pdf": "pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
        }
        return mapping.get(mime_type, "other")
    
    def _should_run_stage2(self, stage1_result: Dict[str, Any], extracted_text: str) -> bool:
        """
        Stage 2を実行すべきかどうか判定（完全リレー方式）

        【アーキテクチャ】
        - Stage 1 (Gemini): 文書の分類と基本情報の抽出
        - Stage 2 (Haiku): Stage 1の結果を受けて構造化・意味付け

        テキストが存在する限り、Stage 1の結果は必ずStage 2（Haiku）に渡して構造化する。
        信頼度に関係なく、判定なしの完全リレー方式で動作する。
        """

        # 抽出テキストが空の場合、または極端に短い場合のみスキップ
        if not extracted_text or len(extracted_text.strip()) < 50:
            logger.info("[Stage 2] テキストが短すぎるためスキップ")
            return False

        # テキストがある限り、無条件でStage 2（構造化プロセス）へ
        doc_type = stage1_result.get('doc_type', 'other')
        logger.info(f"[Stage 2] 構造化プロセスへ移行 ({doc_type})")
        return True

    async def process_file(
        self,
        file_meta: Dict[str, Any],
        workspace: str = "personal"
    ) -> Optional[Dict[str, Any]]:
        """単一ファイルを2段階で処理"""
        file_id = file_meta['id']
        file_name = file_meta['name']
        mime_type = file_meta.get('mimeType', 'application/octet-stream')
        
        logger.info(f"=== 2段階処理開始: {file_name} ===")
        
        existing = self.db.get_document_by_source_id(file_id)
        if existing:
            logger.warning(f"既に処理済み (Source ID): {file_name}")
            return existing
        
        local_path = None
        # extraction_resultを初期化（NameError回避）
        extraction_result = {"success": False, "content": "", "metadata": {}, "error_message": "未実行"}

        try:
            # ============================================
            # ファイルダウンロード
            # ============================================
            local_path = self.drive.download_file(file_id, file_name, self.temp_dir)
            logger.debug(f"ダウンロード完了: {local_path}")

            # ============================================
            # テキスト抽出（Stage 1の前に実行）
            # ============================================
            extraction_result = self._extract_text(local_path, mime_type)

            if not extraction_result["success"]:
                logger.warning(f"テキスト抽出失敗: {file_name}")
                logger.warning(f"エラー詳細: {extraction_result.get('error_message')}")
                extracted_text = ""
            else:
                extracted_text = extraction_result["content"]

            base_metadata = extraction_result.get("metadata", {})

            # ============================================
            # Stage 1: Gemini分類（テキストを渡す）
            # ============================================
            logger.info("[Stage 1] Gemini分類開始...")
            stage1_result = await self.stage1_classifier.classify(
                file_path=Path(local_path),
                doc_types_yaml=self.yaml_string,
                mime_type=mime_type,
                text_content=extracted_text
            )

            doc_type = stage1_result.get('doc_type', 'other')
            workspace_detected = stage1_result.get('workspace', workspace)
            summary = stage1_result.get('summary', '')
            relevant_date = stage1_result.get('relevant_date')
            stage1_confidence = stage1_result.get('confidence', 0.0)

            logger.info(f"[Stage 1] 完了: doc_type={doc_type}, workspace={workspace_detected}, confidence={stage1_confidence:.2f}")

            # ============================================
            # テキスト抽出が失敗した場合の処理
            # ============================================
            if not extraction_result["success"]:
                extracted_text = summary
                confidence = stage1_confidence
                processing_stage = 'stage1_only'
                metadata = {}
                stage2_model = None
            else:
                
                # ============================================
                # Stage 2判定・実行
                # ============================================
                if self._should_run_stage2(stage1_result, extracted_text):
                    logger.info("[Stage 2] Claude詳細抽出開始...")
                    try:
                        stage2_result = self.stage2_extractor.extract_metadata(
                            full_text=extracted_text,
                            file_name=file_name,
                            stage1_result=stage1_result,
                            workspace=workspace_detected
                        )
                        
                        # Stage 2の結果を反映
                        doc_type = stage2_result.get('doc_type', doc_type)
                        summary = stage2_result.get('summary', summary)
                        document_date = stage2_result.get('document_date')
                        tags = stage2_result.get('tags', [])
                        tables = stage2_result.get('tables', [])  # 表データを取得
                        stage2_metadata = stage2_result.get('metadata', {})
                        stage2_confidence = stage2_result.get('extraction_confidence', 0.0)

                        # metadataをマージ（Stage 2優先）
                        metadata = {
                            **base_metadata,
                            **stage2_metadata,
                            'stage2_attempted': True
                        }
                        if tags:
                            metadata['tags'] = tags
                        if document_date:
                            metadata['document_date'] = document_date
                        if tables:
                            metadata['tables'] = tables  # 表データをmetadataに追加
                        
                        # 最終的な信頼度（Stage 1とStage 2の加重平均）
                        confidence = (stage1_confidence * 0.3 + stage2_confidence * 0.7)
                        processing_stage = 'stage1_and_stage2'
                        stage2_model = 'claude-haiku-4-5-20251001'  # 最新のHaiku 4.5モデル

                        logger.info(f"[Stage 2] 完了: confidence={stage2_confidence:.2f}, metadata_fields={len(stage2_metadata)}")

                        # ============================================
                        # JSON Schema検証（Phase 2 - Track 1）
                        # ============================================
                        logger.info("[JSON検証] メタデータ検証開始...")
                        is_valid, validation_error = validate_metadata(
                            metadata=stage2_metadata,
                            doc_type=doc_type
                        )

                        if not is_valid:
                            # 検証失敗時の処理
                            # KeyError回避: エラーメッセージを安全に文字列化
                            safe_validation_error = str(validation_error).replace('{', '{{').replace('}', '}}')
                            logger.error(f"[JSON検証] 検証失敗: {safe_validation_error}")

                            # metadataに検証失敗情報を記録
                            metadata['schema_validation'] = {
                                'is_valid': False,
                                'error_message': validation_error,
                                'validated_at': datetime.now().isoformat()
                            }

                            # 信頼度を減点（検証失敗は重大な品質問題）
                            confidence = confidence * 0.8  # 20%減点
                            logger.warning(f"[JSON検証] 信頼度を減点: {confidence:.2f} (検証失敗のため)")
                        else:
                            logger.info("[JSON検証] [OK] 検証成功")
                            metadata['schema_validation'] = {
                                'is_valid': True,
                                'validated_at': datetime.now().isoformat()
                            }

                    except Exception as e:
                        error_msg = str(e)
                        error_traceback = traceback.format_exc()
                        # KeyError回避: エラーメッセージを安全に文字列化
                        safe_error_msg = error_msg.replace('{', '{{').replace('}', '}}')
                        safe_traceback = error_traceback.replace('{', '{{').replace('}', '}}')
                        logger.error(f"[Stage 2] 処理エラー: {safe_error_msg}\n{safe_traceback}")

                        # エラー情報をmetadataに記録
                        metadata = {
                            **base_metadata,
                            'stage2_attempted': True,
                            'stage2_error': str(e),
                            'stage2_error_type': type(e).__name__,
                            'stage2_error_timestamp': datetime.now().isoformat()
                        }

                        confidence = stage1_confidence
                        processing_stage = 'stage2_failed'
                        stage2_model = None
                else:
                    # Stage 1のみで完結
                    confidence = stage1_confidence
                    processing_stage = 'stage1_only'
                    metadata = {**base_metadata, 'stage2_attempted': False}
                    stage2_model = None

            # ============================================
            # 複合信頼度計算（Phase 2 - Track 1）
            # ============================================
            logger.info("[複合信頼度] 総合スコア計算開始...")
            confidence_scores = calculate_total_confidence(
                model_confidence=confidence,
                text=extracted_text,
                metadata=metadata,
                doc_type=doc_type
            )

            total_confidence = confidence_scores['total_confidence']
            keyword_match_score = confidence_scores['keyword_match_score']
            metadata_completeness = confidence_scores['metadata_completeness']
            data_consistency = confidence_scores['data_consistency']

            # メタデータに各スコアを追加（分析用）
            metadata['quality_scores'] = {
                'keyword_match': keyword_match_score,
                'metadata_completeness': metadata_completeness,
                'data_consistency': data_consistency
            }

            logger.info(f"[複合信頼度] 完了: total_confidence={total_confidence:.3f}")

            # ============================================
            # Embedding生成（OpenAI text-embedding-3-small、1536次元）
            # ============================================
            if extracted_text:
                embedding = self.llm_client.generate_embedding(extracted_text[:8000])
            else:
                embedding = None
            
            # ============================================
            # コンテンツハッシュ生成
            # ============================================
            content_hash = hashlib.sha256(extracted_text.encode('utf-8')).hexdigest() if extracted_text else None
            
            # ============================================
            # データベース保存（Null文字除去 + 重複エラーハンドリング）
            # ============================================
            # Null文字を除去
            if extracted_text:
                extracted_text = extracted_text.replace('\x00', '')
            if summary:
                summary = summary.replace('\x00', '')

            # metadata.tables から extracted_tables を抽出
            extracted_tables = None
            if 'tables' in metadata and metadata['tables']:
                extracted_tables = metadata['tables']

            document_data = {
                "source_type": "drive",
                "source_id": file_id,
                "source_url": f"https://drive.google.com/file/d/{file_id}/view",
                "drive_file_id": file_id,
                "file_name": file_name,
                "file_type": self._get_file_type(mime_type),
                "doc_type": doc_type,
                "workspace": workspace_detected,
                "full_text": extracted_text,
                "summary": summary,
                "embedding": embedding,
                "metadata": metadata,
                "extracted_tables": extracted_tables,  # UIでの表表示用
                "content_hash": content_hash,
                "confidence": confidence,  # AIモデルの確信度
                "total_confidence": total_confidence,  # 複合信頼度スコア
                "processing_status": PROCESSING_STATUS["COMPLETED"],
                "processing_stage": processing_stage,
                "stage1_model": "gemini-2.5-flash",
                "stage2_model": stage2_model,
                "relevant_date": relevant_date,
            }

            try:
                result = await self.db.insert_document('documents', document_data)
                logger.info(f"=== 処理完了: {file_name} ({doc_type}, {processing_stage}) ===")
                return result
            except Exception as db_error:
                # 重複エラー（23505）の場合はスキップ
                error_str = str(db_error)
                if '23505' in error_str or 'duplicate' in error_str.lower():
                    logger.warning(f"重複エラー検出（スキップ）: {file_name} - {error_str}")
                    return {"status": "skipped", "reason": "duplicate"}
                else:
                    # その他のDBエラーは再スロー
                    raise
            
        except Exception as e:
            error_msg = str(e)
            error_traceback = traceback.format_exc()
            # KeyError回避: エラーメッセージを安全に文字列化
            safe_error_msg = error_msg.replace('{', '{{').replace('}', '}}')
            safe_traceback = error_traceback.replace('{', '{{').replace('}', '}}')
            logger.error(f"処理エラー: {file_name} - {safe_error_msg}\n{safe_traceback}")
            
            error_data = {
                "source_type": "drive",
                "source_id": file_id,
                "file_name": file_name,
                "workspace": workspace,
                "processing_status": PROCESSING_STATUS["FAILED"],
                "error_message": str(e),
                "file_type": self._get_file_type(mime_type),
            }

            try:
                await self.db.insert_document('documents', error_data)
            except Exception as db_error:
                db_error_traceback = traceback.format_exc()
                # KeyError回避: エラーメッセージを安全に文字列化
                safe_db_error = str(db_error).replace('{', '{{').replace('}', '}}')
                safe_db_traceback = db_error_traceback.replace('{', '{{').replace('}', '}}')
                logger.critical(f"DB保存失敗（エラーレコード）: {file_name} - DB Error: {safe_db_error}\n{safe_db_traceback}")

                # ファイルシステムフォールバック
                fallback_dir = Path('logs/db_errors')
                fallback_dir.mkdir(parents=True, exist_ok=True)

                fallback_file = fallback_dir / f"db_error_{datetime.now():%Y%m%d_%H%M%S}_{file_id}.json"

                try:
                    with open(fallback_file, 'w', encoding='utf-8') as f:
                        json.dump({
                            'error_data': error_data,
                            'db_error': str(db_error),
                            'db_error_traceback': traceback.format_exc(),
                            'timestamp': datetime.now().isoformat()
                        }, f, ensure_ascii=False, indent=2)
                    logger.warning(f"エラー情報をファイルに保存: {fallback_file}")
                except Exception as file_error:
                    # KeyError回避: エラーメッセージを安全に文字列化
                    safe_file_error = str(file_error).replace('{', '{{').replace('}', '}}')
                    logger.critical(f"ファイルシステムへの保存も失敗: {safe_file_error}") 
                
            return None
            
        finally:
            if local_path and Path(local_path).exists():
                os.remove(local_path)
                logger.debug(f"一時ファイル削除: {local_path}")