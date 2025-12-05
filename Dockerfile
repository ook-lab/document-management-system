# 1. Python のベースイメージを使う
FROM python:3.12-slim

# 2. 必要なシステムツール（Tesseract, Popplerなど）をインストール
# ここが Buildpacks ではできなかった部分です！
# 修正点: libgl1-mesa-glx は古いので libgl1 に変更しました
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-jpn \
    libtesseract-dev \
    poppler-utils \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# 3. 作業ディレクトリを設定
WORKDIR /app

# 4. ファイルをコピー
COPY . .

# 5. Pythonライブラリをインストール
RUN pip install --no-cache-dir -r requirements.txt

# 6. ポート環境変数を設定（念のため）
ENV PORT=8080

# 7. サーバーを起動
CMD ["python", "app.py"]
