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
from .stage_h_kakeibo import StageHKakeibo
from .stage_i_synthesis import StageISynthesis
from .stage_j_chunking import StageJChunking
from .stage_k_embedding import StageKEmbedding

# 家計簿専用のDB保存ハンドラー
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from K_kakeibo.kakeibo_db_handler import KakeiboDBHandler


class UnifiedDocumentPipeline:
    """統合ドキュメント処理パイプライン (Stage E-K) - 設定ベース版"""

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """
        テキストからnull文字を除去

        Args:
            text: 入力テキスト

        Returns:
            サニタイズ済みテキスト
        """
        if not text:
            return text
        # null文字 (\u0000) を除去
        return text.replace('\u0000', '')

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
        self.db = db_client or DatabaseClient(use_service_role=True)  # RLSバイパスのためService Role使用

        # 設定ローダーを初期化
        self.config = ConfigLoader(config_dir)

        # 各ステージを初期化
        self.stage_e = StageEPreprocessor(self.llm_client)
        self.stage_f = StageFVisualAnalyzer(self.llm_client)
        self.stage_g = StageGTextFormatter(self.llm_client)
        self.stage_h = StageHStructuring(self.llm_client)
        self.stage_h_kakeibo = StageHKakeibo(self.db)  # 家計簿専用Stage H
        self.stage_i = StageISynthesis(self.llm_client)
        self.stage_j = StageJChunking()
        self.stage_k = StageKEmbedding(self.llm_client, self.db)

        # 家計簿専用のDB保存ハンドラー
        self.kakeibo_db_handler = KakeiboDBHandler(self.db)

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
            stage_e_result = self.stage_e.extract_text(file_path, mime_type)

            # Stage E の結果をチェック
            if not stage_e_result.get('success'):
                error_msg = f"Stage E失敗: {stage_e_result.get('error', 'テキスト抽出エラー')}"
                logger.error(f"[Stage E失敗] {error_msg}")
                return {'success': False, 'error': error_msg}

            extracted_text = stage_e_result.get('text', '')
            logger.info(f"[Stage E完了] 抽出テキスト長: {len(extracted_text)}文字")

            # ============================================
            # Stage F: Visual Analysis (全件実行)
            # ============================================
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
            # Stage G: Text Formatting + Integration (全件実行)
            # ============================================
            # 設定から Stage G のプロンプトとモデルを取得
            stage_g_config = self.config.get_stage_config('stage_g', doc_type, workspace)
            prompt_g = stage_g_config['prompt']
            model_g = stage_g_config['model']

            logger.info(f"[Stage G] Text Formatting + Integration開始... (model={model_g})")
            combined_text = self.stage_g.process(
                vision_raw=vision_raw,
                extracted_text=extracted_text,
                prompt_template=prompt_g,
                model=model_g,
                mode="integrate"  # 統合モード
            )

            # Stage G の結果をチェック（空のコンテンツは警告のみ、エラーではない）
            if not combined_text or not combined_text.strip():
                logger.warning(f"[Stage G警告] 統合テキストが空です（テキストのないドキュメントの可能性）")
                combined_text = ""  # 空文字列として継続

            logger.info(f"[Stage G完了] 統合テキスト: {len(combined_text)}文字")

            # ============================================
            # Stage H: Structuring
            # ============================================
            # 設定から Stage H のプロンプトとモデルを取得
            stage_h_config = self.config.get_stage_config('stage_h', doc_type, workspace)
            custom_handler = stage_h_config.get('custom_handler')

            # 家計簿専用処理の場合
            if custom_handler == 'kakeibo':
                logger.info(f"[Stage H] 家計簿構造化開始... (custom_handler=kakeibo)")

                # Stage G の出力を辞書に変換（combined_text が JSON 文字列の場合）
                import json
                import re
                try:
                    # Markdownのコードブロック (```json ... ```) を除去
                    json_text = combined_text.strip()
                    if json_text.startswith('```'):
                        # 最初と最後の```を除去
                        json_text = re.sub(r'^```(?:json)?\s*\n', '', json_text)
                        json_text = re.sub(r'\n```\s*$', '', json_text)

                    logger.debug(f"[Stage H] JSON パース前の最初の500文字:\n{json_text[:500]}")
                    stage_g_output = json.loads(json_text)
                except (json.JSONDecodeError, TypeError) as e:
                    logger.error(f"[Stage H] combined_text が JSON 形式ではありません: {e}")
                    logger.error(f"[Stage H] combined_text の内容:\n{combined_text[:1000]}")
                    raise ValueError("Stage G output must be JSON for kakeibo processing")

                # 家計簿専用 Stage H で処理
                stageH_result = self.stage_h_kakeibo.process(stage_g_output)

                # 家計簿専用のDB保存
                logger.info("[DB保存] 家計簿データをDBに保存...")
                kakeibo_save_result = self.kakeibo_db_handler.save_receipt(
                    stage_h_output=stageH_result,
                    file_name=file_name,
                    drive_file_id=source_id,
                    model_name=stage_h_config['model'],
                    source_folder=workspace
                )
                logger.info(f"[DB保存完了] receipt_id={kakeibo_save_result['receipt_id']}")

                # 家計簿は source_documents に保存せず、ここで終了
                return {
                    'success': True,
                    'receipt_id': kakeibo_save_result['receipt_id'],
                    'transaction_ids': kakeibo_save_result['transaction_ids'],
                    'log_id': kakeibo_save_result['log_id'],
                    'doc_type': 'kakeibo'
                }

            # 通常の Stage H 処理
            else:
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

                # Stage H の結果をチェック
                if not stageH_result or not isinstance(stageH_result, dict):
                    error_msg = "Stage H失敗: 構造化結果が不正です"
                    logger.error(f"[Stage H失敗] {error_msg}")
                    return {'success': False, 'error': error_msg}

                # フォールバック結果をエラーとして検出
                stageH_metadata = stageH_result.get('metadata', {})
                if stageH_metadata.get('extraction_failed'):
                    error_msg = "Stage H失敗: JSON抽出に失敗しました（フォールバック結果）"
                    logger.error(f"[Stage H失敗] {error_msg}")
                    return {'success': False, 'error': error_msg}

                document_date = stageH_result.get('document_date')
                tags = stageH_result.get('tags', [])
                logger.info(f"[Stage H完了]")

            # ============================================
            # Stage I: Synthesis
            # ============================================
            # 設定から Stage I のプロンプトとモデルを取得
            stage_i_config = self.config.get_stage_config('stage_i', doc_type, workspace)

            # skip フラグがある場合はスキップ
            if stage_i_config.get('skip'):
                logger.info("[Stage I] スキップ (skip=true)")
                summary = ""
                relevant_date = None
            else:
                prompt_i = stage_i_config['prompt']
                model_i = stage_i_config['model']

                logger.info(f"[Stage I] 統合・要約開始... (model={model_i})")
                stageI_result = self.stage_i.process(
                    combined_text=combined_text,
                    stageH_result=stageH_result,
                    prompt=prompt_i,
                    model=model_i
                )

                # Stage I の結果をチェック
                if not stageI_result or not isinstance(stageI_result, dict):
                    error_msg = "Stage I失敗: 統合・要約結果が不正です"
                    logger.error(f"[Stage I失敗] {error_msg}")
                    return {'success': False, 'error': error_msg}

                summary = stageI_result.get('summary', '')

                # フォールバック結果をエラーとして検出
                if summary == '処理に失敗しました':
                    error_msg = "Stage I失敗: 要約生成に失敗しました（フォールバック結果）"
                    logger.error(f"[Stage I失敗] {error_msg}")
                    return {'success': False, 'error': error_msg}

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
                # テキストフィールドをサニタイズ（null文字を除去）
                sanitized_combined_text = self._sanitize_text(combined_text)
                sanitized_summary = self._sanitize_text(summary)

                doc_data = {
                    'source_id': source_id,
                    'source_type': 'unified_pipeline',
                    'file_name': file_name,
                    'workspace': workspace,
                    'doc_type': doc_type,
                    'attachment_text': sanitized_combined_text,
                    'summary': sanitized_summary,
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
                    result = self.db.client.table('Rawdata_FILE_AND_MAIL').update(doc_data).eq('id', existing_document_id).execute()
                    if not result.data:
                        logger.error("[DB更新エラー] ドキュメント更新失敗")
                        return {'success': False, 'error': 'Document update failed'}
                else:
                    logger.info("[DB保存] 新規ドキュメント作成")
                    result = self.db.client.table('Rawdata_FILE_AND_MAIL').insert(doc_data).execute()
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
                    self.db.client.table('10_ix_search_index').delete().eq('document_id', document_id).execute()
                except Exception as e:
                    logger.warning(f"[Stage K 警告] 既存チャンク削除エラー（継続）: {e}")

            # 新しいチャンクを保存
            stage_k_result = self.stage_k.embed_and_save(document_id, chunks)

            # Stage K の結果をチェック（厳格モード: 1つでも失敗したら全体失敗）
            if not stage_k_result.get('success'):
                error_msg = f"Stage K失敗: {stage_k_result.get('failed_count', 0)}/{len(chunks)}チャンク保存失敗"
                logger.error(f"[Stage K失敗] {error_msg}")
                return {'success': False, 'error': error_msg}

            # 部分的失敗もエラーとして扱う（厳格モード）
            failed_count = stage_k_result.get('failed_count', 0)
            if failed_count > 0:
                error_msg = f"Stage K部分失敗: {failed_count}/{len(chunks)}チャンク保存失敗"
                logger.error(f"[Stage K失敗] {error_msg}")
                return {'success': False, 'error': error_msg}

            logger.info(f"[Stage K完了] {stage_k_result.get('saved_count', 0)}/{len(chunks)}チャンク保存")

            return {
                'success': True,
                'document_id': document_id,
                'summary': summary,
                'tags': tags,
                'chunks_count': stage_k_result.get('saved_count', 0)
            }

        except Exception as e:
            logger.error(f"[パイプラインエラー] {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
