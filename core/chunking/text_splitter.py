"""
テキスト分割モジュール

ドキュメントを小チャンクに分割する機能を提供
"""

from typing import List, Dict
import tiktoken
import re


class TextSplitter:
    """
    テキストを小チャンクに分割するクラス

    Args:
        chunk_size: 1チャンクの文字数（デフォルト300文字）
        overlap: チャンク間のオーバーラップ文字数（デフォルト50文字）
    """

    def __init__(self, chunk_size: int = 300, overlap: int = 50):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if overlap < 0:
            raise ValueError("overlap must be non-negative")
        if overlap >= chunk_size:
            raise ValueError("overlap must be less than chunk_size")

        self.chunk_size = chunk_size
        self.overlap = overlap
        try:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            # tiktokenの初期化に失敗した場合のフォールバック
            print(f"Warning: tiktoken initialization failed: {e}")
            self.encoding = None

    def split_text(self, text: str) -> List[Dict[str, any]]:
        """
        テキストを小チャンクに分割

        Args:
            text: 分割するテキスト

        Returns:
            [
                {
                    "chunk_index": 0,
                    "content": "...",
                    "token_count": 120
                },
                ...
            ]
        """
        if not text or not text.strip():
            return []

        # 改行を正規化
        text = text.replace('\r\n', '\n').replace('\r', '\n')

        chunks = []
        chunk_index = 0
        start = 0
        text_length = len(text)

        while start < text_length:
            # チャンクの終了位置を計算
            end = min(start + self.chunk_size, text_length)

            # 最後のチャンクでない場合、文の区切りを探す
            if end < text_length:
                # 文の終わりを探す（句点、改行など）
                chunk_text = text[start:end]

                # 文の区切り文字で終わる位置を探す
                sentence_end_pattern = r'[。！？\n]'
                matches = list(re.finditer(sentence_end_pattern, chunk_text))

                if matches:
                    # 最後の文の区切りの直後まで含める
                    last_match = matches[-1]
                    end = start + last_match.end()
                else:
                    # 文の区切りがない場合、スペースや句読点で区切る
                    space_pattern = r'[\s、,]'
                    matches = list(re.finditer(space_pattern, chunk_text))
                    if matches:
                        last_match = matches[-1]
                        end = start + last_match.end()

            # チャンクを抽出
            chunk_content = text[start:end].strip()

            if chunk_content:
                # トークン数を計算
                token_count = self._count_tokens(chunk_content)

                chunks.append({
                    "chunk_index": chunk_index,
                    "content": chunk_content,
                    "token_count": token_count
                })
                chunk_index += 1

            # 次のチャンクの開始位置（オーバーラップを考慮）
            start = end - self.overlap

            # オーバーラップ調整後も進んでいない場合は強制的に進める
            if start <= 0 or start >= text_length:
                start = end

        return chunks

    def _count_tokens(self, text: str) -> int:
        """
        テキストのトークン数を計算

        Args:
            text: トークン数を計算するテキスト

        Returns:
            トークン数
        """
        if self.encoding is None:
            # tiktokenが使えない場合は、文字数の1/3を概算値として使用
            return len(text) // 3

        try:
            return len(self.encoding.encode(text))
        except Exception as e:
            print(f"Warning: token counting failed: {e}")
            return len(text) // 3

    def split_by_max_tokens(
        self,
        text: str,
        max_tokens: int = 8000
    ) -> List[Dict[str, any]]:
        """
        最大トークン数を指定してテキストを分割

        長文ドキュメントで元のembedding生成が失敗した場合に使用

        Args:
            text: 分割するテキスト
            max_tokens: 1チャンクの最大トークン数

        Returns:
            チャンクのリスト
        """
        if not text or not text.strip():
            return []

        # まず通常の方法で分割
        chunks = self.split_text(text)

        # トークン数が多すぎるチャンクをさらに分割
        final_chunks = []
        for chunk in chunks:
            if chunk["token_count"] > max_tokens:
                # このチャンクを再分割
                sub_splitter = TextSplitter(
                    chunk_size=len(chunk["content"]) // 2,  # 半分に分割
                    overlap=self.overlap
                )
                sub_chunks = sub_splitter.split_text(chunk["content"])

                # chunk_indexを更新
                for sub_chunk in sub_chunks:
                    sub_chunk["chunk_index"] = len(final_chunks)
                    final_chunks.append(sub_chunk)
            else:
                chunk["chunk_index"] = len(final_chunks)
                final_chunks.append(chunk)

        return final_chunks
