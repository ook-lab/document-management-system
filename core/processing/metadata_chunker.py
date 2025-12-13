"""
メタデータ別ベクトル化戦略

タイトル、サマリー、日付などのメタデータを別々にチャンク化し、
検索時に重み付けを行うことで精度を向上させます。

旧方式: タイトルと本文を混ぜて小チャンク化 → タイトル情報が希釈
新方式: メタデータ種別ごとに独立したチャンクを生成 → 検索精度向上
"""
from typing import List, Dict, Any, Optional
from loguru import logger


class MetadataChunker:
    """
    メタデータを種類別にチャンク化するクラス

    チャンク種別と重み付け:
    - title: タイトル専用チャンク（重み2.0）- 最高優先度
    - persons: 担当者・関係者チャンク（重み1.8）- 高優先度 ★新規
    - organizations: 組織名チャンク（重み1.7）- 高優先度 ★新規
    - summary: サマリー専用チャンク（重み1.5）
    - date: 日付専用チャンク（重み1.3）
    - tags: タグ専用チャンク（重み1.2）
    - people: AI抽出人物チャンク（重み1.2）★新規
    - content_small: 本文小チャンク（重み1.0）- 150文字
    - content_large: 本文大チャンク（重み1.0）- 全文
    - synthetic: 合成チャンク（重み1.0）- 構造化データ
    """

    # チャンク種別と検索重み
    CHUNK_WEIGHTS = {
        'title': 2.0,                    # タイトルマッチは最優先
        'classroom_subject': 2.0,        # Classroom件名（最重要）
        'doc_type': 1.8,                 # 授業名・ドキュメント種別（重要）
        'classroom_post_text': 1.8,      # Classroom投稿本文（重要）
        'persons': 1.8,                  # 担当者・関係者（重要）★新規追加
        'organizations': 1.7,            # 組織名（重要）★新規追加
        'summary': 1.5,                  # サマリーは高優先
        'classroom_type': 1.5,           # Classroom種別（お知らせ/課題/資料）
        'classroom_sender': 1.3,         # Classroom送信者名
        'classroom_sent_at': 1.3,        # Classroom送信日時
        'date': 1.3,                     # 日付検索
        'tags': 1.2,                     # タグ検索
        'people': 1.2,                   # AI抽出人物（やや重要）★新規追加
        'classroom_sender_email': 1.0,   # Classroom送信者メール
        'content_small': 1.0,            # 本文検索（標準）
        'content_large': 1.0,            # 回答生成用
        'synthetic': 1.0,                # 構造化データ
    }

    def __init__(self):
        """初期化"""
        self.chunk_counter = 0

    def create_metadata_chunks(
        self,
        document_data: Dict[str, Any],
        existing_content_chunks: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        ドキュメントデータからメタデータチャンクを生成

        Args:
            document_data: ドキュメント情報
                - file_name: ファイル名（タイトル）
                - summary: AI生成サマリー
                - document_date: 文書日付
                - tags: タグリスト
                - full_text: 全文（オプション）
            existing_content_chunks: 既存の本文チャンク（オプション）
                指定された場合、本文チャンク生成をスキップ

        Returns:
            メタデータチャンクのリスト
            [{
                'chunk_type': 'title',
                'chunk_text': '...',
                'search_weight': 2.0,
                'chunk_index': 0
            }, ...]
        """
        chunks = []
        self.chunk_counter = 0

        # 1. タイトルチャンク（最高優先度）
        title = document_data.get('file_name') or document_data.get('title')
        if title:
            # 拡張子を除去してクリーンなタイトルを作成
            clean_title = self._clean_title(title)
            if clean_title:
                chunks.append(self._create_chunk(
                    chunk_type='title',
                    text=clean_title,
                    metadata={'original_filename': title}
                ))
                logger.debug(f"[MetadataChunker] タイトルチャンク作成: {clean_title[:50]}...")

        # 2. サマリーチャンク
        summary = document_data.get('summary')
        if summary and len(summary.strip()) > 10:
            chunks.append(self._create_chunk(
                chunk_type='summary',
                text=summary.strip()
            ))
            logger.debug(f"[MetadataChunker] サマリーチャンク作成: {len(summary)}文字")

        # 3. 日付チャンク
        date_text = self._format_date_chunk(document_data)
        if date_text:
            chunks.append(self._create_chunk(
                chunk_type='date',
                text=date_text
            ))
            logger.debug(f"[MetadataChunker] 日付チャンク作成: {date_text}")

        # 4. タグチャンク
        tags = document_data.get('tags', [])
        if tags and len(tags) > 0:
            tag_text = self._format_tags_chunk(tags)
            if tag_text:
                chunks.append(self._create_chunk(
                    chunk_type='tags',
                    text=tag_text
                ))
                logger.debug(f"[MetadataChunker] タグチャンク作成: {len(tags)}個のタグ")

        # 5. doc_type（授業名・ドキュメント種別）チャンク（高優先度）
        doc_type = document_data.get('doc_type')
        if doc_type and len(doc_type.strip()) > 0:
            chunks.append(self._create_chunk(
                chunk_type='doc_type',
                text=f"授業名: {doc_type.strip()}"
            ))
            logger.debug(f"[MetadataChunker] doc_typeチャンク作成: {doc_type}")

        # 6. Classroom専用チャンク（Google Classroom投稿情報）
        classroom_subject = document_data.get('classroom_subject')
        if classroom_subject and len(classroom_subject.strip()) > 0:
            chunks.append(self._create_chunk(
                chunk_type='classroom_subject',
                text=f"件名: {classroom_subject.strip()}"
            ))
            logger.debug(f"[MetadataChunker] Classroom件名チャンク作成: {len(classroom_subject)}文字")

        classroom_post_text = document_data.get('classroom_post_text')
        if classroom_post_text and len(classroom_post_text.strip()) > 0:
            chunks.append(self._create_chunk(
                chunk_type='classroom_post_text',
                text=f"投稿本文: {classroom_post_text.strip()}"
            ))
            logger.debug(f"[MetadataChunker] Classroom投稿本文チャンク作成: {len(classroom_post_text)}文字")

        classroom_type = document_data.get('classroom_type')
        if classroom_type:
            chunks.append(self._create_chunk(
                chunk_type='classroom_type',
                text=f"種別: {classroom_type}"
            ))
            logger.debug(f"[MetadataChunker] Classroom種別チャンク作成: {classroom_type}")

        classroom_sender = document_data.get('classroom_sender')
        if classroom_sender:
            chunks.append(self._create_chunk(
                chunk_type='classroom_sender',
                text=f"送信者: {classroom_sender}"
            ))
            logger.debug(f"[MetadataChunker] Classroom送信者チャンク作成: {classroom_sender}")

        classroom_sent_at = document_data.get('classroom_sent_at')
        if classroom_sent_at:
            chunks.append(self._create_chunk(
                chunk_type='classroom_sent_at',
                text=f"送信日時: {classroom_sent_at}"
            ))
            logger.debug(f"[MetadataChunker] Classroom送信日時チャンク作成: {classroom_sent_at}")

        classroom_sender_email = document_data.get('classroom_sender_email')
        if classroom_sender_email:
            chunks.append(self._create_chunk(
                chunk_type='classroom_sender_email',
                text=f"送信者メール: {classroom_sender_email}"
            ))
            logger.debug(f"[MetadataChunker] Classroom送信者メールチャンク作成")

        # 7. persons（担当者・関係者）チャンク（高重要）
        persons = document_data.get('persons', [])
        if persons and len(persons) > 0:
            persons_text = self._format_persons_chunk(persons)
            if persons_text:
                chunks.append(self._create_chunk(
                    chunk_type='persons',
                    text=persons_text
                ))
                logger.debug(f"[MetadataChunker] personsチャンク作成: {len(persons)}名")

        # 8. organizations（組織名）チャンク（高重要）
        organizations = document_data.get('organizations', [])
        if organizations and len(organizations) > 0:
            orgs_text = self._format_organizations_chunk(organizations)
            if orgs_text:
                chunks.append(self._create_chunk(
                    chunk_type='organizations',
                    text=orgs_text
                ))
                logger.debug(f"[MetadataChunker] organizationsチャンク作成: {len(organizations)}組織")

        # 9. people（AI抽出人物）チャンク
        people = document_data.get('people', [])
        if people and len(people) > 0:
            people_text = self._format_people_chunk(people)
            if people_text:
                chunks.append(self._create_chunk(
                    chunk_type='people',
                    text=people_text
                ))
                logger.debug(f"[MetadataChunker] peopleチャンク作成: {len(people)}名")

        logger.info(f"[MetadataChunker] メタデータチャンク生成完了: {len(chunks)}個")
        return chunks

    def _create_chunk(
        self,
        chunk_type: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        チャンクオブジェクトを作成

        Args:
            chunk_type: チャンク種別
            text: チャンクテキスト
            metadata: 追加メタデータ

        Returns:
            チャンクオブジェクト
        """
        chunk = {
            'chunk_type': chunk_type,
            'chunk_text': text,
            'chunk_size': len(text),
            'search_weight': self.CHUNK_WEIGHTS.get(chunk_type, 1.0),
            'chunk_index': self.chunk_counter
        }

        if metadata:
            chunk['metadata'] = metadata

        self.chunk_counter += 1
        return chunk

    def _clean_title(self, title: str) -> str:
        """
        ファイル名からクリーンなタイトルを抽出

        - 拡張子を除去
        - 日付プレフィックスを整形
        - アンダースコアをスペースに変換
        """
        import re

        # 拡張子を除去
        clean = re.sub(r'\.(pdf|docx?|xlsx?|pptx?|txt|html?)$', '', title, flags=re.IGNORECASE)

        # アンダースコアをスペースに変換（ただしスネークケースを考慮）
        # 例: "2024_12_01_会議資料" → "2024年12月01日 会議資料"

        # 日付パターンを検出して整形
        date_pattern = r'^(\d{4})[_\-]?(\d{2})[_\-]?(\d{2})[_\s]*'
        match = re.match(date_pattern, clean)
        if match:
            year, month, day = match.groups()
            date_str = f"{year}年{month}月{day}日"
            rest = clean[match.end():].strip('_- ')
            clean = f"{date_str} {rest}" if rest else date_str

        # 残りのアンダースコアをスペースに
        clean = clean.replace('_', ' ')

        return clean.strip()

    def _format_date_chunk(self, document_data: Dict[str, Any]) -> Optional[str]:
        """
        日付関連情報をチャンク用テキストに整形

        document_date, event_dates, relevant_dateを統合
        """
        parts = []

        # メイン文書日付
        doc_date = document_data.get('document_date')
        if doc_date:
            parts.append(f"文書日付: {doc_date}")

        # イベント日付（複数可）
        event_dates = document_data.get('event_dates', [])
        if event_dates:
            if isinstance(event_dates, list):
                for event in event_dates:
                    if isinstance(event, dict):
                        label = event.get('label', 'イベント')
                        date = event.get('date', '')
                        if date:
                            parts.append(f"{label}: {date}")
                    elif isinstance(event, str):
                        parts.append(f"イベント日: {event}")

        # 関連日付
        relevant_date = document_data.get('relevant_date')
        if relevant_date and relevant_date != doc_date:
            parts.append(f"関連日付: {relevant_date}")

        return '\n'.join(parts) if parts else None

    def _format_tags_chunk(self, tags: List[str]) -> Optional[str]:
        """
        タグリストをチャンク用テキストに整形
        """
        if not tags:
            return None

        # 重複除去と整形
        unique_tags = list(dict.fromkeys(tags))  # 順序を保持して重複除去

        # タグをカンマ区切りとハッシュタグ形式の両方で表現
        tag_text = ', '.join(unique_tags)
        hashtags = ' '.join([f"#{tag}" for tag in unique_tags])

        return f"タグ: {tag_text}\n{hashtags}"

    def _format_persons_chunk(self, persons: List[str]) -> Optional[str]:
        """
        担当者・関係者リストをチャンク用テキストに整形

        配列には複数の表記（漢字、ひらがな、アルファベット）が含まれる想定
        例: ['山田太郎', 'やまだたろう', 'Yamada Taro', '山田']
        """
        if not persons:
            return None

        # 重複除去
        unique_persons = list(dict.fromkeys(persons))

        # スペース区切りで結合（ベクトル化時に全表記が考慮される）
        persons_text = ' '.join(unique_persons)

        return f"担当者: {persons_text}"

    def _format_organizations_chunk(self, organizations: List[str]) -> Optional[str]:
        """
        組織名リストをチャンク用テキストに整形

        配列には複数の表記（正式名称、略称、ひらがな、英語）が含まれる想定
        例: ['東京大学', 'とうきょうだいがく', 'Tokyo University', '東大', 'UTokyo']
        """
        if not organizations:
            return None

        # 重複除去
        unique_orgs = list(dict.fromkeys(organizations))

        # スペース区切りで結合
        orgs_text = ' '.join(unique_orgs)

        return f"組織: {orgs_text}"

    def _format_people_chunk(self, people: List[str]) -> Optional[str]:
        """
        AI抽出人物リストをチャンク用テキストに整形

        Args:
            people: AIが文書から抽出した人物名のリスト
        """
        if not people:
            return None

        # 重複除去
        unique_people = list(dict.fromkeys(people))

        # カンマ区切りとスペース区切りの両方で表現
        people_text = ', '.join(unique_people)
        people_spaced = ' '.join(unique_people)

        return f"関係者: {people_text}\n{people_spaced}"

    def get_weight_for_type(self, chunk_type: str) -> float:
        """
        チャンク種別に対応する検索重みを取得
        """
        return self.CHUNK_WEIGHTS.get(chunk_type, 1.0)

    @staticmethod
    def calculate_weighted_score(
        similarity: float,
        search_weight: float = 1.0
    ) -> float:
        """
        類似度スコアに重みを適用

        Args:
            similarity: ベクトル類似度（0.0-1.0）
            search_weight: 検索重み

        Returns:
            重み付けされたスコア
        """
        return similarity * search_weight


def create_metadata_chunks(document_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    便利関数: ドキュメントデータからメタデータチャンクを生成

    Args:
        document_data: ドキュメント情報

    Returns:
        メタデータチャンクのリスト
    """
    chunker = MetadataChunker()
    return chunker.create_metadata_chunks(document_data)
