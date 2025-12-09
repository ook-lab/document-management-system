"""
ReactiveDocumentUpdater
元データ（full_text, extracted_tables）を編集したら、
全ての派生データを自動的に再生成するクラス
"""
from typing import Dict, List, Any, Optional
from loguru import logger
from datetime import datetime
import json

from core.database.client import DatabaseClient
from core.ai.llm_client import LLMClient
from core.ai.stage1_classifier import Stage1Classifier
from core.ai.stage2_extractor import Stage2Extractor
from core.utils.chunking import chunk_document_parent_child
from core.utils.hypothetical_questions import HypotheticalQuestionGenerator
from config.yaml_loader import get_classification_yaml_string


class ReactiveDocumentUpdater:
    """
    元データ（full_text）の編集時に全ての派生データを自動再生成

    再生成される派生データ:
    - メタデータ (doc_type, document_date, year, month, summary等)
    - Parent チャンク (1500文字)
    - Child チャンク (300文字)
    - Hypothetical Questions
    - Embeddings (vector(1536))
    """

    def __init__(self, db: DatabaseClient = None, llm: LLMClient = None):
        self.db = db or DatabaseClient()
        self.llm = llm or LLMClient()

        self.yaml_string = get_classification_yaml_string()
        self.stage1_classifier = Stage1Classifier(llm_client=self.llm)
        self.stage2_extractor = Stage2Extractor(llm_client=self.llm)
        self.question_generator = HypotheticalQuestionGenerator(self.llm)

        logger.info("ReactiveDocumentUpdater初期化完了")

    async def update_document_from_source(
        self,
        document_id: str,
        edited_text: str,
        edited_tables: Optional[List] = None
    ) -> Dict[str, Any]:
        """
        元データの編集から全データを再生成

        処理フロー:
        1. full_text/extracted_tables を更新
        2. メタデータ再抽出（Stage 1 + Stage 2）
        3. 既存のチャンク・質問を削除
        4. チャンク再分割
        5. Questions再生成
        6. Embeddings再計算
        7. 全てをトランザクションで保存

        Args:
            document_id: ドキュメントID
            edited_text: 編集後のテキスト
            edited_tables: 編集後のテーブルデータ（任意）

        Returns:
            更新結果
        """

        logger.info(f"[ReactiveUpdate] ドキュメント {document_id} の再生成開始")

        try:
            # ========================================
            # Step 0: 既存ドキュメント情報取得
            # ========================================
            doc = self.db.get_document_by_id(document_id)
            if not doc:
                raise ValueError(f"ドキュメントが見つかりません: {document_id}")

            file_name = doc['file_name']
            workspace = doc.get('workspace', 'personal')

            logger.info(f"[ReactiveUpdate] 対象: {file_name}")

            # ========================================
            # Step 1: メタデータ再抽出（Stage 1）
            # ========================================
            logger.info("[ReactiveUpdate] Stage 1: メタデータ再抽出開始")

            # テキストのみから分類（ファイルなしバージョン）
            stage1_result = await self.stage1_classifier.classify(
                file_path=None,
                doc_types_yaml=self.yaml_string,
                mime_type="text/plain",
                text_content=edited_text
            )

            doc_type = stage1_result.get('doc_type', 'other')
            workspace_detected = stage1_result.get('workspace', workspace)
            summary = stage1_result.get('summary', '')
            confidence = stage1_result.get('confidence', 0.0)

            logger.info(f"[ReactiveUpdate] Stage 1完了: doc_type={doc_type}, confidence={confidence}")

            # ========================================
            # Step 2: Stage 2 構造化抽出
            # ========================================
            metadata = stage1_result.get('metadata', {})

            if len(edited_text.strip()) >= 50:
                logger.info("[ReactiveUpdate] Stage 2: 構造化抽出開始")

                try:
                    stage2_result = await self.stage2_extractor.extract(
                        text=edited_text,
                        doc_type=doc_type,
                        stage1_metadata=stage1_result
                    )

                    # Stage 2のメタデータで上書き
                    if stage2_result:
                        metadata.update(stage2_result.get('metadata', {}))
                        summary = stage2_result.get('summary', summary)

                        logger.info("[ReactiveUpdate] Stage 2完了")

                except Exception as e:
                    logger.warning(f"[ReactiveUpdate] Stage 2失敗（Stage 1の結果を使用）: {e}")

            # ========================================
            # Step 3: チャンク再分割
            # ========================================
            logger.info("[ReactiveUpdate] チャンク再分割開始")

            chunk_result = chunk_document_parent_child(
                text=edited_text,
                parent_size=1500,
                child_size=300
            )

            parent_chunks = chunk_result['parent_chunks']
            child_chunks = chunk_result['child_chunks']

            logger.info(f"[ReactiveUpdate] チャンク再分割完了: 親{len(parent_chunks)}個, 子{len(child_chunks)}個")

            # ========================================
            # Step 4: Embeddings生成
            # ========================================
            logger.info("[ReactiveUpdate] Embeddings生成開始")

            # 子チャンクのEmbedding（バッチ生成）
            child_texts = [c['text'] for c in child_chunks]
            child_embeddings = []

            # OpenAI APIの制限を考慮して、10件ずつバッチ処理
            batch_size = 10
            for i in range(0, len(child_texts), batch_size):
                batch = child_texts[i:i+batch_size]
                batch_embeddings = [self.llm.generate_embedding(text[:8000]) for text in batch]
                child_embeddings.extend(batch_embeddings)

            # 親チャンクのEmbedding
            parent_texts = [p['text'] for p in parent_chunks]
            parent_embeddings = []

            for i in range(0, len(parent_texts), batch_size):
                batch = parent_texts[i:i+batch_size]
                batch_embeddings = [self.llm.generate_embedding(text[:8000]) for text in batch]
                parent_embeddings.extend(batch_embeddings)

            logger.info(f"[ReactiveUpdate] Embeddings生成完了")

            # ========================================
            # Step 5: Hypothetical Questions生成
            # ========================================
            logger.info("[ReactiveUpdate] Hypothetical Questions生成開始")

            all_questions = []
            question_embeddings = []

            # 最初の10チャンクのみ（コスト削減）
            for i, chunk in enumerate(child_chunks[:10]):
                questions = self.question_generator.generate_questions(
                    chunk_text=chunk['text'],
                    num_questions=3,
                    document_metadata=metadata
                )

                for q in questions:
                    q['chunk_index'] = i
                    all_questions.append(q)

                    # 質問のEmbedding生成
                    q_embedding = self.llm.generate_embedding(q['question_text'])
                    question_embeddings.append(q_embedding)

            logger.info(f"[ReactiveUpdate] Questions生成完了: {len(all_questions)}個")

            # ========================================
            # Step 6: データベース更新（トランザクション風）
            # ========================================
            logger.info("[ReactiveUpdate] データベース更新開始")

            # 6-1. 既存データ削除
            self.db.delete_document_chunks_sync(document_id)
            self.db.delete_hypothetical_questions_sync(document_id)

            logger.info("[ReactiveUpdate] 既存チャンク・質問を削除")

            # 6-2. ドキュメント更新
            # year, month, document_dateを抽出
            year = metadata.get('year')
            month = metadata.get('month')
            document_date = metadata.get('document_date')

            update_data = {
                'full_text': edited_text,
                'extracted_tables': json.dumps(edited_tables) if edited_tables else None,
                'doc_type': doc_type,
                'workspace': workspace_detected,
                'summary': summary,
                'metadata': metadata,
                'confidence': confidence,
                'year': year,
                'month': month,
                'document_date': document_date,
                'last_edited_at': datetime.now().isoformat(),
                'processing_status': 'completed',
                'reviewed': False,  # 編集されたのでレビュー済みフラグをリセット
                'review_status': 'pending'
            }

            self.db.update_document_sync(document_id, update_data)

            logger.info("[ReactiveUpdate] ドキュメント更新完了")

            # 6-3. 親チャンク挿入
            parent_chunk_ids = await self.db.insert_parent_child_chunks(
                document_id=document_id,
                parent_chunks=parent_chunks,
                parent_embeddings=parent_embeddings,
                child_chunks=child_chunks,
                child_embeddings=child_embeddings
            )

            logger.info(f"[ReactiveUpdate] チャンク挿入完了: {len(parent_chunk_ids)}個の親チャンク")

            # 6-4. Questions挿入
            if all_questions:
                # chunk_idを解決する必要があるため、挿入されたchild_chunksのIDを取得
                inserted_chunks = await self.db.get_document_chunks(document_id)

                for i, question in enumerate(all_questions):
                    chunk_index = question.get('chunk_index', 0)

                    # chunk_indexに対応するchunk_idを見つける
                    matching_chunk = next(
                        (c for c in inserted_chunks if c.get('chunk_index') == chunk_index and not c.get('is_parent')),
                        None
                    )

                    chunk_id = matching_chunk['id'] if matching_chunk else None

                    await self.db.insert_hypothetical_question(
                        document_id=document_id,
                        chunk_id=chunk_id,
                        question_text=question['question_text'],
                        question_embedding=question_embeddings[i],
                        confidence_score=question.get('confidence_score', 1.0)
                    )

                logger.info(f"[ReactiveUpdate] Questions挿入完了: {len(all_questions)}個")

            logger.info("[ReactiveUpdate] ✅ 全データ更新完了")

            return {
                'success': True,
                'document_id': document_id,
                'doc_type': doc_type,
                'parent_chunks': len(parent_chunks),
                'child_chunks': len(child_chunks),
                'questions': len(all_questions),
                'metadata': metadata
            }

        except Exception as e:
            logger.error(f"[ReactiveUpdate] ❌ エラー: {e}")
            import traceback
            traceback.print_exc()
            raise
