/**
 * DualEditor.tsx
 * リアルタイムMarkdown→HTMLプレビューエディタ
 *
 * 機能:
 * - 左パネル: Markdown入力エリア
 * - 右パネル: HTMLプレビュー
 * - リアルタイム同期による一方向データバインディング
 */

import React, { useState, useMemo } from 'react';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import styles from './DualEditor.module.css';

// Markdown初期コンテンツ
const INITIAL_MARKDOWN = `# Welcome to the Dual Editor
- **Input:** Edit this Markdown text here.
- **Output:** See the rendered HTML on the right side.
---
This is a test of **real-time synchronization**.`;

/**
 * DualEditorコンポーネント
 * Markdownエディタとプレビューパネルを提供
 */
const DualEditor: React.FC = () => {
  // Markdownテキストを管理するState
  const [markdown, setMarkdown] = useState<string>(INITIAL_MARKDOWN);

  /**
   * MarkdownをHTMLに変換し、XSS攻撃を防ぐためにサニタイズ
   * useMemoを使用してパフォーマンスを最適化
   *
   * セキュリティ対策:
   * ✅ DOMPurifyを使用してHTMLをサニタイズ
   * - <script>タグなどの危険なコードを自動的に削除
   * - イベントハンドラ属性（onclick等）を無害化
   * - 安全なHTMLのみをレンダリング
   */
  const htmlContent = useMemo(() => {
    try {
      // Step 1: markedでMarkdownをHTMLに変換
      const rawHtml = marked.parse(markdown, {
        breaks: true,        // 改行を<br>に変換
        gfm: true,           // GitHub Flavored Markdown を有効化
        headerIds: true,     // 見出しにIDを自動付与
        mangle: false,       // メールアドレスの難読化を無効化
      });

      // Step 2: DOMPurifyでHTMLをサニタイズ（XSS対策）
      const sanitizedHtml = DOMPurify.sanitize(rawHtml, {
        ALLOWED_TAGS: [
          // テキスト関連
          'p', 'br', 'span', 'div',
          // 見出し
          'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
          // リスト
          'ul', 'ol', 'li',
          // テーブル
          'table', 'thead', 'tbody', 'tr', 'th', 'td',
          // リンク・画像
          'a', 'img',
          // 強調・整形
          'strong', 'em', 'code', 'pre', 'blockquote',
          // 水平線
          'hr'
        ],
        ALLOWED_ATTR: [
          // リンク属性
          'href', 'title', 'target', 'rel',
          // 画像属性
          'src', 'alt', 'width', 'height',
          // ID・クラス（Markdownの見出しIDなど）
          'id', 'class'
        ],
        // プロトコル制限（JavaScriptプロトコルを防ぐ）
        ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|sms|cid|xmpp):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
      });

      return sanitizedHtml;
    } catch (error) {
      console.error('Markdown parsing error:', error);
      // エラー時もサニタイズ
      return DOMPurify.sanitize('<p style="color: red;">Markdown変換エラーが発生しました</p>');
    }
  }, [markdown]);

  /**
   * テキストエリアの入力変更ハンドラ
   * リアルタイムでStateを更新し、プレビューを再レンダリング
   */
  const handleInputChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMarkdown(event.target.value);
  };

  return (
    <div className={styles.container}>
      {/* Editor A: Markdown入力パネル */}
      <div className={styles.editorPanel}>
        <div className={styles.panelHeader}>
          <h2 className={styles.panelTitle}>📝 Markdown Editor</h2>
          <span className={styles.characterCount}>
            {markdown.length} characters
          </span>
        </div>
        <textarea
          className={styles.textarea}
          value={markdown}
          onChange={handleInputChange}
          placeholder="Enter your Markdown here..."
          spellCheck={false}
          autoComplete="off"
        />
      </div>

      {/* Editor B: HTMLプレビューパネル */}
      <div className={styles.previewPanel}>
        <div className={styles.panelHeader}>
          <h2 className={styles.panelTitle}>👁️ Preview</h2>
          <span className={styles.liveIndicator}>● LIVE</span>
        </div>
        <div
          className={styles.previewContent}
          /*
           * XSS警告:
           * dangerouslySetInnerHTMLは信頼できるコンテンツにのみ使用してください。
           * ユーザー入力を直接レンダリングする場合、適切なサニタイゼーションが必要です。
           *
           * 推奨対策:
           * 1. DOMPurify等のライブラリでHTMLをサニタイズ
           * 2. Content Security Policy (CSP) ヘッダーの設定
           * 3. 信頼できないソースからのMarkdownは受け入れない
           */
          dangerouslySetInnerHTML={{ __html: htmlContent }}
        />
      </div>
    </div>
  );
};

export default DualEditor;
