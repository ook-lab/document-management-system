"""
Database Client
Supabaseデータベースへの接続と操作を管理
"""
from typing import Dict, Any, List, Optional
from supabase import create_client, Client
from config.settings import settings
from core.utils.reranker import Reranker, RerankConfig


class DatabaseClient:
    """Supabaseデータベースクライアント"""

    def __init__(self):
        """Supabaseクライアントの初期化"""
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            raise ValueError("SUPABASE_URL と SUPABASE_KEY が設定されていません")

        self.client: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY
        )

        # Rerankerの初期化（Cohere優先、フォールバックでHugging Face）
        self.reranker = None
        if RerankConfig.ENABLED:
            try:
                self.reranker = Reranker(provider=RerankConfig.PROVIDER)
                print(f"[Reranker] 初期化成功: {RerankConfig.PROVIDER}")
            except Exception as e:
                print(f"[Reranker] 初期化失敗: {e}")
                self.reranker = None
    
    def get_document_by_source_id(self, source_id: str) -> Optional[Dict[str, Any]]:
        """
        source_id で文書を検索
        
        Args:
            source_id: Google Drive のファイルID
        
        Returns:
            既存の文書レコード、存在しない場合は None
        """
        try:
            response = self.client.table('documents').select('*').eq('source_id', source_id).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            print(f"Error getting document by source_id: {e}")
            return None
    
    async def insert_document(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        文書をデータベースに挿入

        Args:
            table: テーブル名
            data: 挿入するデータ

        Returns:
            挿入されたレコード
        """
        # embeddingをPostgreSQLのvector型形式に変換
        if 'embedding' in data and data['embedding'] is not None:
            embedding_list = data['embedding']
            if isinstance(embedding_list, list):
                # ベクトル形式の文字列に変換: [0.1,0.2,0.3]
                data = data.copy()  # 元のdataを変更しないようにコピー
                data['embedding'] = '[' + ','.join(str(x) for x in embedding_list) + ']'

        response = self.client.table(table).insert(data).execute()
        return response.data[0] if response.data else {}

    async def upsert_document(
        self,
        table: str,
        data: Dict[str, Any],
        conflict_column: str = 'source_id',
        force_update: bool = False,
        preserve_fields: List[str] = None
    ) -> Dict[str, Any]:
        """
        ドキュメントをupsert（既存レコードがあれば更新、なければ挿入）

        Args:
            table: テーブル名
            data: 挿入・更新するデータ
            conflict_column: 重複判定に使うカラム名（デフォルト: source_id）
            force_update: Trueの場合、全てのフィールドを強制的に更新（再処理時用）
            preserve_fields: force_update=Trueの時でも既存値を保持するフィールドのリスト

        Returns:
            挿入・更新されたレコード
        """
        # embeddingをPostgreSQLのvector型形式に変換
        if 'embedding' in data and data['embedding'] is not None:
            embedding_list = data['embedding']
            if isinstance(embedding_list, list):
                data = data.copy()
                data['embedding'] = '[' + ','.join(str(x) for x in embedding_list) + ']'

        # 既存レコードを取得
        existing = self.client.table(table).select('*').eq(conflict_column, data[conflict_column]).execute()

        if existing.data and len(existing.data) > 0:
            # 既存レコードがある場合
            existing_record = existing.data[0]
            update_data = {}

            if force_update:
                # 再処理モード：基本的に全て更新するが、preserve_fieldsは既存値を保持
                preserve_fields = preserve_fields or []

                for key, value in data.items():
                    if key in preserve_fields:
                        # 保持対象フィールドは既存値が有効な場合のみ保持
                        if existing_record.get(key) not in [None, '', [], {}]:
                            continue  # 既存値を保持（更新しない）
                    update_data[key] = value
            else:
                # 通常モード：空欄・nullの項目のみ更新
                for key, value in data.items():
                    if existing_record.get(key) in [None, '', [], {}]:
                        update_data[key] = value

            if update_data:
                # 更新するデータがある場合のみUPDATE
                response = self.client.table(table).update(update_data).eq(conflict_column, data[conflict_column]).execute()
                return response.data[0] if response.data else {}
            else:
                # 更新不要の場合は既存レコードを返す
                return existing_record
        else:
            # 既存レコードがない場合：新規挿入
            response = self.client.table(table).insert(data).execute()
            return response.data[0] if response.data else {}

    async def search_documents(
        self,
        query: str,
        embedding: List[float],
        limit: int = 50,
        doc_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        2階層ハイブリッド検索：小チャンク検索 + 大チャンク回答（重複排除＆Rerank対応）

        【検索フロー】
        1. 小チャンク（300文字）でベクトル + 全文検索 → 関連ドキュメントを検出
        2. ドキュメント単位で重複排除（最高スコアのみ） → 重複を削減
        3. 大チャンク（全文）で回答生成 → 最も詳細な情報を使用

        【フィルタの考え方】
        - 階層構造（workspace > doc_type）はフロントエンドで維持
        - データベース検索はdoc_typeのみで絞り込み
        - 理由: workspace内の全doc_typeがON = workspaceがON（冗長なため）

        Args:
            query: 検索クエリ
            embedding: クエリのembeddingベクトル
            limit: 取得する最大件数
            doc_types: ドキュメントタイプフィルタ（配列、複数選択可能）

        Returns:
            検索結果のリスト（小チャンク検索スコア順、回答は大チャンク）
        """
        try:
            # クエリから日付を抽出
            target_date = self._extract_date(query)
            filter_year = None
            filter_month = None

            if target_date:
                try:
                    parts = target_date.split('-')
                    filter_year = int(parts[0])
                    filter_month = int(parts[1])
                    print(f"[DEBUG] 日付フィルタ: {filter_year}年{filter_month}月")
                except:
                    pass

            # DB関数を呼び出し（小チャンク検索＋重複排除＋大チャンク取得）
            rpc_params = {
                "query_text": query,
                "query_embedding": embedding,
                "match_threshold": 0.0,
                "match_count": limit,  # 指定された件数を取得
                "vector_weight": 0.7,  # ベクトル検索70%
                "fulltext_weight": 0.3,  # キーワード検索30%
                "filter_year": filter_year,
                "filter_month": filter_month,
                "filter_doc_types": doc_types  # doc_typeのみで絞り込み
            }

            print(f"[DEBUG] search_documents_final 呼び出し: query='{query}', doc_types={doc_types}")
            response = self.client.rpc("search_documents_final", rpc_params).execute()
            results = response.data if response.data else []

            print(f"[DEBUG] search_documents_final 結果: {len(results)} 件")

            # 結果を整形（既に重複排除済みだが、確認用）
            final_results = []
            for result in results:
                doc_result = {
                    'id': result.get('document_id'),
                    'file_name': result.get('file_name'),
                    'doc_type': result.get('doc_type'),
                    'workspace': result.get('workspace'),
                    'document_date': result.get('document_date'),
                    'metadata': result.get('metadata'),
                    'summary': result.get('summary'),

                    # 回答用：大チャンク（全文）
                    'content': result.get('large_chunk_text'),
                    'large_chunk_id': result.get('large_chunk_id'),

                    # 検索スコア：小チャンクの検索スコア
                    'similarity': result.get('combined_score', 0),
                    'small_chunk_id': result.get('small_chunk_id'),

                    'year': result.get('year'),
                    'month': result.get('month')
                }

                # ✅ Classroom表示用の追加フィールド（存在する場合のみ追加）
                if 'source_type' in result:
                    doc_result['source_type'] = result.get('source_type')
                if 'source_url' in result:
                    doc_result['source_url'] = result.get('source_url')
                if 'full_text' in result:
                    doc_result['full_text'] = result.get('full_text')
                if 'created_at' in result:
                    doc_result['created_at'] = result.get('created_at')

                final_results.append(doc_result)

            print(f"[DEBUG] 初期検索結果: {len(final_results)} 件（2階層検索）")
            print(f"[DEBUG] 検索戦略: 小チャンク検索 + 重複排除 + 大チャンク回答")

            # ============================================
            # Reranking（再ランク付け）
            # ============================================
            if self.reranker and RerankConfig.should_rerank(len(final_results)):
                print(f"[DEBUG] Reranking開始: {len(final_results)} 件 → {RerankConfig.FINAL_RESULT_COUNT} 件")
                try:
                    # Rerankingを実行
                    # text_key は 'content' を使用（大チャンクのテキスト）
                    reranked_results = self.reranker.rerank(
                        query=query,
                        documents=final_results,
                        top_k=RerankConfig.FINAL_RESULT_COUNT,
                        text_key='content'  # 大チャンクのテキストで再評価
                    )

                    print(f"[DEBUG] Reranking完了: {len(reranked_results)} 件")

                    # Rerankスコアをログ出力（デバッグ用）
                    for idx, doc in enumerate(reranked_results[:3], 1):  # 上位3件のみ
                        rerank_score = doc.get('rerank_score', 0)
                        original_score = doc.get('similarity', 0)
                        file_name = doc.get('file_name', 'Unknown')
                        print(f"  [{idx}] {file_name}: original={original_score:.3f}, rerank={rerank_score:.3f}")

                    final_results = reranked_results

                except Exception as rerank_error:
                    print(f"[WARNING] Reranking失敗: {rerank_error}")
                    # エラー時は元の結果をそのまま使用
                    print(f"[DEBUG] 元の検索結果を使用: {len(final_results)} 件")
            else:
                if not self.reranker:
                    print("[DEBUG] Reranking無効: Rerankerが初期化されていません")
                else:
                    print(f"[DEBUG] Reranking不要: 検索結果が少ない（{len(final_results)} 件）")

            print(f"[DEBUG] 最終結果: {len(final_results)} 件")

            return final_results

        except Exception as e:
            print(f"2-tier hybrid search error: {e}")
            import traceback
            traceback.print_exc()

            # フォールバック: 従来のベクトル検索（workspaceフィルタなし）
            print("[WARNING] フォールバックモード: match_documents を使用")
            return await self._fallback_vector_search(embedding, limit, None)

    async def _fallback_vector_search(
        self,
        embedding: List[float],
        limit: int,
        workspace: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        フォールバック用のベクトル検索（エラー時に使用）

        Args:
            embedding: クエリのembeddingベクトル
            limit: 取得する最大件数
            workspace: ワークスペースフィルタ

        Returns:
            検索結果のリスト
        """
        try:
            rpc_params = {
                "query_embedding": embedding,
                "match_threshold": 0.0,
                "match_count": min(limit, 5)
            }
            if workspace:
                rpc_params["filter_workspace"] = workspace

            response = self.client.rpc("match_documents", rpc_params).execute()
            results = response.data if response.data else []

            print(f"[DEBUG] フォールバック検索結果: {len(results)} 件")
            return results

        except Exception as e:
            print(f"Fallback search error: {e}")
            return []

    def _check_date_match(self, doc: Dict[str, Any], target_date: str) -> float:
        """
        ドキュメントのメタデータと本文から target_date を検索
        年を無視して、月・日だけでマッチング（例：12-04）

        Args:
            doc: ドキュメント
            target_date: ターゲット日付（YYYY-MM-DD形式、例：2025-12-04）

        Returns:
            マッチスコア（0.0～0.5）
        """
        import re

        # 年を除いた月・日のみを抽出（例：2025-12-04 → 12-04）
        try:
            parts = target_date.split('-')
            month = int(parts[1])
            day = int(parts[2])
        except:
            return 0.0

        # 検索パターン：「12/4」「12月4日」「12-04」など
        date_patterns = [
            f"{month}/{day}",           # 12/4
            f"{month:02d}/{day:02d}",   # 12/04
            f"{month}月{day}日",         # 12月4日
            f"{month:02d}-{day:02d}",   # 12-04
        ]

        # 1. 本文（content, summary, full_text）を検索 - 最優先
        text_fields = ['content', 'summary', 'full_text']
        for field in text_fields:
            text = doc.get(field, '')
            if text:
                for pattern in date_patterns:
                    if pattern in text:
                        print(f"[DEBUG] 本文で日付マッチ: {doc.get('file_name')} に '{pattern}' が含まれる")
                        return 0.5  # 本文マッチで +0.5 ブースト（最優先）

        # 2. メタデータの weekly_schedule をチェック
        metadata = doc.get('metadata', {})
        weekly_schedule = metadata.get('weekly_schedule', [])
        if isinstance(weekly_schedule, list):
            for day_item in weekly_schedule:
                if isinstance(day_item, dict):
                    date = day_item.get('date', '')
                    if date:
                        try:
                            doc_month = int(date.split('-')[1])
                            doc_day = int(date.split('-')[2])
                            if month == doc_month and day == doc_day:
                                return 0.3  # メタデータマッチで +0.3 ブースト
                        except:
                            pass

        # 3. document_date をチェック
        document_date = doc.get('document_date', '')
        if document_date:
            try:
                doc_month = int(str(document_date).split('-')[1])
                doc_day = int(str(document_date).split('-')[2])
                if month == doc_month and day == doc_day:
                    return 0.2
            except:
                pass

        return 0.0

    def _calculate_keyword_match_score(
        self,
        file_name: str,
        keywords: List[str],
        query: str
    ) -> float:
        """
        file_name とクエリの一致度を計算

        Args:
            file_name: ファイル名
            keywords: 抽出されたキーワードのリスト
            query: 元のクエリ

        Returns:
            一致度スコア（0.0～1.0）
        """
        # クエリから記号を除去して正規化
        normalized_query = query.replace('？', '').replace('?', '').replace('の内容は', '').replace('内容', '').strip()

        # 完全一致（括弧付き単語がそのまま含まれる）
        for kw in keywords:
            if '（' in kw or '(' in kw:
                if kw in file_name:
                    return 1.0  # 「学年通信（29）」が完全一致

        # マッチしたキーワードの数をカウント
        matched_keywords = []
        for kw in keywords:
            if kw in file_name:
                matched_keywords.append(kw)

        if not matched_keywords:
            return 0.0

        # マッチ数に応じてスコアを設定
        match_count = len(matched_keywords)
        total_keywords = len(keywords)

        if match_count == total_keywords:
            # すべてのキーワードがマッチ（ただし完全一致ではない）
            return 0.95
        elif match_count >= 2:
            # 2つ以上マッチ
            return 0.90
        else:
            # 1つだけマッチ
            return 0.85

    def _extract_date(self, query: str) -> Optional[str]:
        """
        クエリから日付を抽出（YYYY-MM-DD形式に正規化）

        Args:
            query: 検索クエリ

        Returns:
            正規化された日付文字列（YYYY-MM-DD）、または None
        """
        import re
        from datetime import datetime

        # 現在の年を取得
        current_year = datetime.now().year

        # パターン1: MM/DD形式（例：12/4）
        match = re.search(r'(\d{1,2})/(\d{1,2})', query)
        if match:
            month = int(match.group(1))
            day = int(match.group(2))
            try:
                date_obj = datetime(current_year, month, day)
                return date_obj.strftime('%Y-%m-%d')
            except ValueError:
                pass

        # パターン2: MM月DD日形式（例：12月4日）
        match = re.search(r'(\d{1,2})月(\d{1,2})日', query)
        if match:
            month = int(match.group(1))
            day = int(match.group(2))
            try:
                date_obj = datetime(current_year, month, day)
                return date_obj.strftime('%Y-%m-%d')
            except ValueError:
                pass

        return None

    def _extract_keywords(self, query: str) -> List[str]:
        """
        クエリから重要なキーワードを抽出

        Args:
            query: 検索クエリ

        Returns:
            抽出されたキーワードのリスト
        """
        import re
        keywords = []

        # 括弧内の文字を抽出（例：「学年通信（29）」→「29」「学年通信」）
        bracket_matches = re.findall(r'[（(]([^）)]+)[）)]', query)
        keywords.extend(bracket_matches)

        # 括弧を含む単語全体を抽出（例：「学年通信（29）」）
        bracket_words = re.findall(r'[\w一-龠ぁ-んァ-ヶー]+[（(][^）)]+[）)]', query)
        keywords.extend(bracket_words)

        # 助詞を除去してクリーニング
        cleaned_query = query
        particles = ['の', 'は', 'を', 'が', 'に', 'へ', 'と', 'から', 'まで', 'で', '？', '?']
        for particle in particles:
            cleaned_query = cleaned_query.replace(particle, ' ')

        # 名詞的な単語を抽出（漢字・カタカナが2文字以上）
        words = re.findall(r'[一-龠ァ-ヶー]{2,}', cleaned_query)
        keywords.extend(words)

        # 重複削除・空白除去して返す
        keywords = [kw.strip() for kw in keywords if kw.strip()]
        return list(set(keywords))

    def get_documents_for_review(
        self,
        limit: int = 100,
        search_query: Optional[str] = None,
        workspace: Optional[str] = None,
        file_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        レビュー対象のドキュメントを取得

        通常モード（search_query=None）: 未レビューのドキュメントのみ取得
        検索モード（search_query指定）: レビュー状態に関係なく全件から検索

        Args:
            limit: 取得する最大件数
            search_query: 検索クエリ（IDまたはファイル名で部分一致）
            workspace: ワークスペースフィルタ（'business', 'personal', またはNone）
            file_type: ファイルタイプフィルタ（'pdf', 'email', またはNone）

        Returns:
            ドキュメントのリスト（更新日時降順）
        """
        try:
            query = self.client.table('documents').select('*')

            # File typeフィルタを適用
            if file_type:
                query = query.eq('file_type', file_type)

            # Workspaceフィルタを適用
            if workspace:
                query = query.eq('workspace', workspace)

            if search_query:
                # 検索モード: レビュー状態に関係なく検索
                # IDでの完全一致検索を試みる
                if len(search_query) == 36 or len(search_query) == 8:  # UUID形式またはID先頭8文字
                    # IDで検索（部分一致）
                    response_id = query.ilike('id', f'{search_query}%').limit(limit).execute()
                    if response_id.data:
                        return response_id.data

                # ファイル名で部分一致検索
                response = (
                    query
                    .ilike('file_name', f'%{search_query}%')
                    .order('updated_at', desc=True)
                    .limit(limit)
                    .execute()
                )
                return response.data if response.data else []
            else:
                # 通常モード: 未レビューのドキュメントのみ取得
                response = (
                    query
                    .eq('is_reviewed', False)
                    .order('updated_at', desc=True)
                    .limit(limit)
                    .execute()
                )
                return response.data if response.data else []

        except Exception as e:
            print(f"Error getting documents for review: {e}")
            return []

    def mark_document_reviewed(
        self,
        doc_id: str,
        reviewed_by: Optional[str] = None
    ) -> bool:
        """
        ドキュメントをレビュー済みとしてマークする

        Args:
            doc_id: ドキュメントID
            reviewed_by: レビュー担当者のメールアドレス（オプション）

        Returns:
            成功したかどうか
        """
        try:
            from datetime import datetime

            update_data = {
                'is_reviewed': True,
                'reviewed_at': datetime.utcnow().isoformat()
            }
            if reviewed_by:
                update_data['reviewed_by'] = reviewed_by

            response = (
                self.client.table('documents')
                .update(update_data)
                .eq('id', doc_id)
                .execute()
            )
            return bool(response.data)
        except Exception as e:
            print(f"Error marking document as reviewed: {e}")
            return False

    def mark_document_unreviewed(
        self,
        doc_id: str
    ) -> bool:
        """
        ドキュメントを未レビュー状態に戻す

        Args:
            doc_id: ドキュメントID

        Returns:
            成功したかどうか
        """
        try:
            update_data = {
                'is_reviewed': False,
                'reviewed_at': None,
                'reviewed_by': None
            }

            response = (
                self.client.table('documents')
                .update(update_data)
                .eq('id', doc_id)
                .execute()
            )
            return bool(response.data)
        except Exception as e:
            print(f"Error marking document as unreviewed: {e}")
            return False

    def get_review_progress(self) -> Dict[str, Any]:
        """
        レビュー進捗状況を取得

        Returns:
            進捗情報の辞書
        """
        try:
            # 未レビューの件数
            unreviewed_response = (
                self.client.table('documents')
                .select('*', count='exact')
                .eq('is_reviewed', False)
                .execute()
            )
            unreviewed_count = unreviewed_response.count if unreviewed_response else 0

            # レビュー済みの件数
            reviewed_response = (
                self.client.table('documents')
                .select('*', count='exact')
                .eq('is_reviewed', True)
                .execute()
            )
            reviewed_count = reviewed_response.count if reviewed_response else 0

            # 総件数
            total_count = unreviewed_count + reviewed_count

            # 進捗率
            progress_percent = (reviewed_count / total_count * 100) if total_count > 0 else 0

            return {
                'total': total_count,
                'reviewed': reviewed_count,
                'unreviewed': unreviewed_count,
                'progress_percent': round(progress_percent, 2)
            }
        except Exception as e:
            print(f"Error getting review progress: {e}")
            return {
                'total': 0,
                'reviewed': 0,
                'unreviewed': 0,
                'progress_percent': 0
            }

    def get_available_workspaces(self) -> List[str]:
        """
        データベース内の利用可能なワークスペース一覧を取得

        Returns:
            ワークスペース名のリスト（重複なし、ソート済み）
        """
        try:
            # 全ドキュメントからworkspaceを取得
            response = self.client.table('documents').select('workspace').execute()

            workspaces = set()
            for doc in response.data:
                ws = doc.get('workspace')
                if ws:  # NoneやNULLを除外
                    workspaces.add(ws)

            return sorted(list(workspaces))
        except Exception as e:
            print(f"Error getting available workspaces: {e}")
            return []

    def get_available_doc_types(self) -> List[str]:
        """
        データベース内の利用可能なドキュメントタイプ一覧を取得

        Returns:
            ドキュメントタイプ名のリスト（重複なし、ソート済み）
        """
        try:
            # 全ドキュメントからdoc_typeを取得
            response = self.client.table('documents').select('doc_type').execute()

            doc_types = set()
            for doc in response.data:
                dt = doc.get('doc_type')
                if dt:  # NoneやNULLを除外
                    doc_types.add(dt)

            return sorted(list(doc_types))
        except Exception as e:
            print(f"Error getting available doc_types: {e}")
            return []

    def get_workspace_hierarchy(self) -> Dict[str, List[str]]:
        """
        workspace別のdoc_type階層構造を取得

        Returns:
            {workspace: [doc_type1, doc_type2, ...]} の辞書
        """
        try:
            # workspaceとdoc_typeの組み合わせを取得
            response = self.client.table('documents').select('workspace, doc_type').execute()

            hierarchy = {}
            for doc in response.data:
                workspace = doc.get('workspace')
                doc_type = doc.get('doc_type')

                if workspace and doc_type:
                    if workspace not in hierarchy:
                        hierarchy[workspace] = set()
                    hierarchy[workspace].add(doc_type)

            # setをソート済みリストに変換
            result = {ws: sorted(list(types)) for ws, types in hierarchy.items()}

            # workspaceもソート
            result = dict(sorted(result.items()))

            print(f"[DEBUG] workspace階層構造: {len(result)} workspaces")
            return result

        except Exception as e:
            print(f"Error getting workspace hierarchy: {e}")
            return {}

    def get_document_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        IDでドキュメントを取得

        Args:
            doc_id: ドキュメントID

        Returns:
            ドキュメント、存在しない場合は None
        """
        try:
            response = self.client.table('documents').select('*').eq('id', doc_id).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            print(f"Error getting document by id: {e}")
            return None

    def update_document_metadata(
        self,
        doc_id: str,
        new_metadata: Dict[str, Any],
        new_doc_type: Optional[str] = None
    ) -> bool:
        """
        ドキュメントのメタデータと文書タイプを更新

        注意: この関数は修正履歴を記録しません。
        修正履歴を記録する場合は record_correction() を使用してください。

        Args:
            doc_id: ドキュメントID
            new_metadata: 新しいメタデータ
            new_doc_type: 新しい文書タイプ（オプション）

        Returns:
            成功したかどうか
        """
        try:
            update_data = {'metadata': new_metadata}
            if new_doc_type:
                update_data['doc_type'] = new_doc_type

            response = (
                self.client.table('documents')
                .update(update_data)
                .eq('id', doc_id)
                .execute()
            )
            return bool(response.data)
        except Exception as e:
            print(f"Error updating document metadata: {e}")
            return False

    def record_correction(
        self,
        doc_id: str,
        new_metadata: Dict[str, Any],
        new_doc_type: Optional[str] = None,
        corrector_email: Optional[str] = None,
        notes: Optional[str] = None
    ) -> bool:
        """
        ドキュメントのメタデータを更新し、修正履歴を記録

        Phase 2: トランザクション管理・ロールバック機能

        Args:
            doc_id: ドキュメントID
            new_metadata: 新しいメタデータ
            new_doc_type: 新しい文書タイプ（オプション）
            corrector_email: 修正者のメールアドレス（オプション）
            notes: 修正に関するメモ（オプション）

        Returns:
            成功したかどうか
        """
        try:
            # Step 1: 現在のドキュメントを取得
            current_doc = self.get_document_by_id(doc_id)
            if not current_doc:
                print(f"Error: Document not found: {doc_id}")
                return False

            old_metadata = current_doc.get('metadata', {})
            old_doc_type = current_doc.get('doc_type')

            # Step 2: correction_history に修正履歴を記録
            correction_data = {
                'document_id': doc_id,
                'old_metadata': old_metadata,
                'new_metadata': new_metadata,
                'corrector_email': corrector_email,
                'correction_type': 'manual',
                'notes': notes
            }

            correction_response = (
                self.client.table('correction_history')
                .insert(correction_data)
                .execute()
            )

            if not correction_response.data:
                print("Error: Failed to insert correction history")
                return False

            correction_id = correction_response.data[0]['id']
            print(f"✅ 修正履歴を記録: correction_id={correction_id}")

            # Step 3: documents テーブルを更新
            update_data = {
                'metadata': new_metadata,
                'latest_correction_id': correction_id
            }
            if new_doc_type and new_doc_type != old_doc_type:
                update_data['doc_type'] = new_doc_type

            document_response = (
                self.client.table('documents')
                .update(update_data)
                .eq('id', doc_id)
                .execute()
            )

            if not document_response.data:
                print("Error: Failed to update document")
                return False

            print(f"✅ ドキュメント更新成功: doc_id={doc_id}")
            return True

        except Exception as e:
            print(f"Error recording correction: {e}")
            import traceback
            traceback.print_exc()
            return False

    def rollback_document(self, doc_id: str) -> bool:
        """
        ドキュメントのメタデータを最新の修正前の状態にロールバック

        Phase 2: トランザクション管理・ロールバック機能

        Args:
            doc_id: ドキュメントID

        Returns:
            成功したかどうか
        """
        try:
            # Step 1: 現在のドキュメントを取得
            current_doc = self.get_document_by_id(doc_id)
            if not current_doc:
                print(f"Error: Document not found: {doc_id}")
                return False

            latest_correction_id = current_doc.get('latest_correction_id')
            if not latest_correction_id:
                print(f"Error: No correction history found for document: {doc_id}")
                return False

            # Step 2: 最新の修正履歴を取得
            correction_response = (
                self.client.table('correction_history')
                .select('*')
                .eq('id', latest_correction_id)
                .execute()
            )

            if not correction_response.data:
                print(f"Error: Correction history not found: {latest_correction_id}")
                return False

            correction = correction_response.data[0]
            old_metadata = correction['old_metadata']

            # Step 3: documentsテーブルを修正前の状態に戻す
            update_data = {
                'metadata': old_metadata,
                'latest_correction_id': None  # ロールバック後は修正履歴をクリア
            }

            document_response = (
                self.client.table('documents')
                .update(update_data)
                .eq('id', doc_id)
                .execute()
            )

            if not document_response.data:
                print("Error: Failed to rollback document")
                return False

            print(f"✅ ロールバック成功: doc_id={doc_id}, correction_id={latest_correction_id}")
            return True

        except Exception as e:
            print(f"Error rolling back document: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_correction_history(
        self,
        doc_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        ドキュメントの修正履歴を取得

        Phase 2: トランザクション管理・ロールバック機能

        Args:
            doc_id: ドキュメントID
            limit: 取得する最大件数

        Returns:
            修正履歴のリスト（新しい順）
        """
        try:
            response = (
                self.client.table('correction_history')
                .select('*')
                .eq('document_id', doc_id)
                .order('corrected_at', desc=True)
                .limit(limit)
                .execute()
            )
            return response.data if response.data else []
        except Exception as e:
            print(f"Error getting correction history: {e}")
            return []

    def get_processed_file_ids(self) -> List[str]:
        """
        既に処理済みのファイルIDリストを取得

        Returns:
            処理済みファイルのsource_id（Google Drive file ID）のリスト
        """
        try:
            # source_idが存在するすべてのドキュメントを取得
            response = (
                self.client.table('documents')
                .select('source_id')
                .not_.is_('source_id', 'null')
                .execute()
            )

            # source_idのリストを抽出
            if response.data:
                file_ids = [doc['source_id'] for doc in response.data if doc.get('source_id')]
                print(f"Supabaseから {len(file_ids)} 件の処理済みファイルIDを取得しました")
                return file_ids
            return []

        except Exception as e:
            print(f"Error getting processed file IDs: {e}")
            return []

    def check_duplicate_hash(self, content_hash: str) -> bool:
        """
        content_hashが既にデータベースに存在するかチェック

        Args:
            content_hash: SHA256ハッシュ値

        Returns:
            True: 重複あり（既に存在する）
            False: 重複なし（新規）
        """
        try:
            # content_hashが一致するドキュメントを検索
            response = (
                self.client.table('documents')
                .select('id, file_name, content_hash')
                .eq('content_hash', content_hash)
                .limit(1)
                .execute()
            )

            if response.data and len(response.data) > 0:
                # 重複が見つかった
                existing_doc = response.data[0]
                print(f"⚠️  重複検知: content_hash={content_hash[:16]}... は既に存在します")
                print(f"   既存ファイル: {existing_doc.get('file_name', 'Unknown')}")
                return True

            # 重複なし
            return False

        except Exception as e:
            print(f"Error checking duplicate hash: {e}")
            # エラー時は安全側に倒して重複なしとして扱う
            return False

    def delete_document(self, doc_id: str) -> bool:
        """
        ドキュメントをデータベースから削除

        Args:
            doc_id: 削除するドキュメントのID

        Returns:
            True: 削除成功
            False: 削除失敗
        """
        try:
            # ドキュメントを削除（ON DELETE CASCADEにより関連データも削除される）
            response = (
                self.client.table('documents')
                .delete()
                .eq('id', doc_id)
                .execute()
            )

            if response.data:
                print(f"✅ ドキュメントを削除しました: {doc_id}")
                return True
            else:
                print(f"⚠️  ドキュメントが見つかりませんでした: {doc_id}")
                return False

        except Exception as e:
            print(f"❌ ドキュメント削除エラー: {e}")
            return False