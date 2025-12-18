"""
統合ドキュメント処理パイプライン (Stage E-K) - 設定ベース版

設計書: DESIGN_UNIFIED_PIPELINE.md v2.0 に準拠
処理順序: Stage E → F → G → H → I → J → K

特徴:
- doc_type / workspace に応じて自動的にプロンプトとモデルを切り替え
- config/ 内の YAML と Markdown ファイルで設定管理
"""
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger

from C_ai_common.llm_client.llm_client import LLMClient
from A_common.database.client import DatabaseClient

from .config_loader import ConfigLoader
from .stage_e_preprocessing import StageEPreprocessor
from .stage_f_visual import StageFVisualAnalyzer
from .stage_g_formatting import StageGTextFormatter
from .stage_h_structuring import StageHStructuring
from .stage_i_synthesis import StageISynthesis
from .stage_j_chunking import StageJChunking
from .stage_k_embedding import StageKEmbedding


class UnifiedDocumentPipeline:
    """統合ドキュメント処理パイプライン (Stage E-K) - 設定ベース版"""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        db_client: Optional[DatabaseClient] = None,
        config_dir: Optional[Path] = None
    ):
        """
        Args:
            llm_client: LLMクライアント（Noneの場合は新規作成）
            db_client: データベースクライアント（Noneの場合は新規作成）
            config_dir: 設定ディレクトリ（デフォルト: G_unified_pipeline/config/）
        """
        self.llm_client = llm_client or LLMClient()
        self.db = db_client or DatabaseClient()

        # 設定ローダーを初期化
        self.config = ConfigLoader(config_dir)

        # 各ステージを初期化
        self.stage_e = StageEPreprocessor(self.llm_client)
        self.stage_f = StageFVisualAnalyzer(self.llm_client)
        self.stage_g = StageGTextFormatter(self.llm_client)
        self.stage_h = StageHStructuring(self.llm_client)
        self.stage_i = StageISynthesis(self.llm_client)
        self.stage_j = StageJChunking()
        self.stage_k = StageKEmbedding(self.llm_client, self.db)

        logger.info("✅ UnifiedDocumentPipeline 初期化完了（設定ベース）")

    async def process_document(
        self,
        file_path: Path,
        file_name: str,
        doc_type: str,
        workspace: str,
        mime_type: str,
        source_id: str,
        existing_document_id: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        ドキュメントを処理（Stage E-K）

        Args:
            file_path: ファイルパス
            file_name: ファイル名
            doc_type: ドキュメントタイプ（設定ルーティングに使用）
            workspace: ワークスペース
            mime_type: MIMEタイプ
            source_id: ソースID
            existing_document_id: 更新する既存ドキュメントID（Noneの場合は新規作成）
            extra_metadata: 追加メタデータ（Classroom固有フィールドなど）

        Returns:
            処理結果 {'success': bool, 'document_id': str, ...}
        """
        try:
            logger.info(f"📄 ドキュメント処理開始: {file_name} (doc_type={doc_type}, workspace={workspace})")

            # ============================================
            # Stage E: Pre-processing
            # ============================================
            logger.info("[Stage E] Pre-processing開始...")
            extracted_text = self.stage_e.process(file_path, mime_type)
            logger.info(f"[Stage E完了] 抽出テキスト長: {len(extracted_text)}文字")

            # ============================================
            # Stage F: Visual Analysis (条件付き)
            # ============================================
            vision_raw = ""
            needs_vision = self._should_run_vision(mime_type, extracted_text)

            if needs_vision and file_path.exists():
                # 設定から Stage F のプロンプトとモデルを取得
                stage_f_config = self.config.get_stage_config('stage_f', doc_type, workspace)
                prompt_f = stage_f_config['prompt']
                model_f = stage_f_config['model']

                logger.info(f"[Stage F] Visual Analysis開始... (model={model_f})")
                vision_raw = self.stage_f.process(
                    file_path=file_path,
                    prompt=prompt_f,
                    model=model_f
                )
                logger.info(f"[Stage F完了] Vision結果: {len(vision_raw)}文字")

            # ============================================
            # Stage G: Text Formatting (条件付き)
            # ============================================
            vision_formatted = ""
            if vision_raw:
                # 設定から Stage G のプロンプトとモデルを取得
                stage_g_config = self.config.get_stage_config('stage_g', doc_type, workspace)
                prompt_g = stage_g_config['prompt']
                model_g = stage_g_config['model']

                logger.info(f"[Stage G] Text Formatting開始... (model={model_g})")
                vision_formatted = self.stage_g.process(
                    vision_raw=vision_raw,
                    prompt_template=prompt_g,
                    model=model_g
                )
                logger.info(f"[Stage G完了] 整形テキスト: {len(vision_formatted)}文字")

            # 統合テキスト
            combined_text = f"{extracted_text}\n\n{vision_formatted}".strip()

            # ============================================
            # Stage H: Structuring
            # ============================================
            # 設定から Stage H のプロンプトとモデルを取得
            stage_h_config = self.config.get_stage_config('stage_h', doc_type, workspace)
            prompt_h = stage_h_config['prompt']
            model_h = stage_h_config['model']

            logger.info(f"[Stage H] 構造化開始... (model={model_h})")
            stageH_result = self.stage_h.process(
                file_name=file_name,
                doc_type=doc_type,
                workspace=workspace,
                combined_text=combined_text,
                prompt=prompt_h,
                model=model_h
            )

            document_date = stageH_result.get('document_date')
            tags = stageH_result.get('tags', [])
            stageH_metadata = stageH_result.get('metadata', {})
            logger.info(f"[Stage H完了]")

            # ============================================
            # Stage I: Synthesis
            # ============================================
            # 設定から Stage I のプロンプトとモデルを取得
            stage_i_config = self.config.get_stage_config('stage_i', doc_type, workspace)
            prompt_i = stage_i_config['prompt']
            model_i = stage_i_config['model']

            logger.info(f"[Stage I] 統合・要約開始... (model={model_i})")
            stageI_result = self.stage_i.process(
                combined_text=combined_text,
                stageH_result=stageH_result,
                prompt=prompt_i,
                model=model_i
            )

            summary = stageI_result.get('summary', '')
            relevant_date = stageI_result.get('relevant_date')
            logger.info(f"[Stage I完了]")

            # ============================================
            # Stage J: Chunking
            # ============================================
            logger.info("[Stage J] チャンク化開始...")
            chunks = self.stage_j.process(
                display_subject=extra_metadata.get('display_subject', file_name) if extra_metadata else file_name,
                summary=summary,
                tags=tags,
                document_date=document_date,
                metadata=stageH_metadata
            )
            logger.info(f"[Stage J完了] チャンク数: {len(chunks)}")

            # ============================================
            # DB保存: source_documents
            # ============================================
            document_id = existing_document_id
            try:
                doc_data = {
                    'source_id': source_id,
                    'source_type': 'unified_pipeline',
                    'file_name': file_name,
                    'workspace': workspace,
                    'doc_type': doc_type,
                    'attachment_text': combined_text,
                    'summary': summary,
                    'tags': tags,
                    'document_date': document_date,
                    'metadata': stageH_metadata,
                    'processing_status': 'completed'
                }

                # extra_metadata をマージ
                if extra_metadata:
                    if isinstance(doc_data['metadata'], dict):
                        doc_data['metadata'].update(extra_metadata)
                    else:
                        doc_data['metadata'] = extra_metadata

                # 既存ドキュメントを更新 or 新規作成
                if existing_document_id:
                    logger.info(f"[DB更新] 既存ドキュメント更新: {existing_document_id}")
                    result = self.db.client.table('source_documents').update(doc_data).eq('id', existing_document_id).execute()
                    if not result.data:
                        logger.error("[DB更新エラー] ドキュメント更新失敗")
                        return {'success': False, 'error': 'Document update failed'}
                else:
                    logger.info("[DB保存] 新規ドキュメント作成")
                    result = self.db.client.table('source_documents').insert(doc_data).execute()
                    if result.data and len(result.data) > 0:
                        document_id = result.data[0]['id']
                        logger.info(f"[DB保存] source_documents ID: {document_id}")
                    else:
                        logger.error("[DB保存エラー] ドキュメント作成失敗")
                        return {'success': False, 'error': 'Document creation failed'}

            except Exception as e:
                logger.error(f"[DB保存エラー] {e}")
                return {'success': False, 'error': str(e)}

            # ============================================
            # Stage K: Embedding
            # ============================================
            logger.info("[Stage K] ベクトル化開始...")

            # 既存ドキュメントの場合は、古いチャンクを削除
            if existing_document_id:
                try:
                    logger.info(f"[Stage K] 既存チャンク削除: document_id={document_id}")
                    self.db.client.table('search_index').delete().eq('document_id', document_id).execute()
                except Exception as e:
                    logger.warning(f"[Stage K 警告] 既存チャンク削除エラー（継続）: {e}")

            # 新しいチャンクを保存
            self.stage_k.process(chunks, document_id)
            logger.info(f"[Stage K完了] {len(chunks)}チャンク保存")

            return {
                'success': True,
                'document_id': document_id,
                'summary': summary,
                'tags': tags,
                'chunks_count': len(chunks)
            }

        except Exception as e:
            logger.error(f"[パイプラインエラー] {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def _should_run_vision(self, mime_type: str, extracted_text: str) -> bool:
        """Stage F (Vision) を実行すべきか判定"""
        # 条件1: 画像ファイル
        if mime_type and mime_type.startswith('image/'):
            return True

        # 条件2: Pre-processingでテキストがほとんど抽出できなかった（100文字未満）
        if len(extracted_text.strip()) < 100:
            return True

        return False
