/**
 * DualEditor.test.tsx
 * XSSサニタイズ機能の検証テスト
 */

import { describe, it, expect } from 'vitest';
import DOMPurify from 'dompurify';
import { marked } from 'marked';

describe('DualEditor XSS Sanitization Tests', () => {
  /**
   * テストヘルパー: MarkdownをHTMLに変換してサニタイズ
   * 実際のDualEditorと同じロジック
   */
  const convertAndSanitize = (markdown: string): string => {
    const rawHtml = marked.parse(markdown, {
      breaks: true,
      gfm: true,
      headerIds: true,
      mangle: false,
    });

    return DOMPurify.sanitize(rawHtml, {
      ALLOWED_TAGS: [
        'p', 'br', 'span', 'div',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li',
        'table', 'thead', 'tbody', 'tr', 'th', 'td',
        'a', 'img',
        'strong', 'em', 'code', 'pre', 'blockquote',
        'hr'
      ],
      ALLOWED_ATTR: [
        'href', 'title', 'target', 'rel',
        'src', 'alt', 'width', 'height',
        'id', 'class'
      ],
      ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|sms|cid|xmpp):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
    });
  };

  it('✅ 通常のMarkdownは正しくHTMLに変換される', () => {
    const markdown = '# Hello World\n\nThis is **bold** text.';
    const result = convertAndSanitize(markdown);

    expect(result).toContain('<h1');
    expect(result).toContain('Hello World');
    expect(result).toContain('<strong>bold</strong>');
  });

  it('🔒 <script>タグは削除される', () => {
    const maliciousMarkdown = `
# Test
<script>alert('XSS Attack!')</script>
Normal text
    `.trim();

    const result = convertAndSanitize(maliciousMarkdown);

    // <script>タグが除去されていることを確認
    expect(result).not.toContain('<script>');
    expect(result).not.toContain('alert');
    // 通常のテキストは残る
    expect(result).toContain('Normal text');
  });

  it('🔒 onclick属性は削除される', () => {
    const maliciousMarkdown = '<a href="#" onclick="alert(\'XSS\')">Click me</a>';
    const result = convertAndSanitize(maliciousMarkdown);

    // onclick属性が除去されていることを確認
    expect(result).not.toContain('onclick');
    expect(result).not.toContain('alert');
    // リンクテキストは残る
    expect(result).toContain('Click me');
  });

  it('🔒 javascript:プロトコルのURLは無害化される', () => {
    const maliciousMarkdown = '<a href="javascript:alert(\'XSS\')">Dangerous Link</a>';
    const result = convertAndSanitize(maliciousMarkdown);

    // javascript:プロトコルが除去されていることを確認
    expect(result).not.toContain('javascript:');
    expect(result).not.toContain('alert');
  });

  it('🔒 <iframe>タグは削除される', () => {
    const maliciousMarkdown = '<iframe src="http://evil.com"></iframe>';
    const result = convertAndSanitize(maliciousMarkdown);

    // <iframe>タグが除去されていることを確認
    expect(result).not.toContain('<iframe');
    expect(result).not.toContain('evil.com');
  });

  it('🔒 onerror属性を持つ画像は無害化される', () => {
    const maliciousMarkdown = '<img src="x" onerror="alert(\'XSS\')">';
    const result = convertAndSanitize(maliciousMarkdown);

    // onerror属性が除去されていることを確認
    expect(result).not.toContain('onerror');
    expect(result).not.toContain('alert');
  });

  it('✅ 安全なリンクは保持される', () => {
    const markdown = '[Google](https://www.google.com)';
    const result = convertAndSanitize(markdown);

    // 安全なリンクは保持される
    expect(result).toContain('href="https://www.google.com"');
    expect(result).toContain('Google');
  });

  it('✅ 安全な画像は保持される', () => {
    const markdown = '![Alt Text](https://example.com/image.png)';
    const result = convertAndSanitize(markdown);

    // 安全な画像は保持される
    expect(result).toContain('src="https://example.com/image.png"');
    expect(result).toContain('alt="Alt Text"');
  });

  it('🔒 複数のXSS攻撃パターンが同時に無害化される', () => {
    const maliciousMarkdown = `
# XSS Test
<script>alert('XSS1')</script>
<a href="javascript:alert('XSS2')">Link</a>
<img src="x" onerror="alert('XSS3')">
<iframe src="http://evil.com"></iframe>

Normal **safe** content with proper formatting.
    `.trim();

    const result = convertAndSanitize(maliciousMarkdown);

    // すべての攻撃パターンが除去されていることを確認
    expect(result).not.toContain('<script>');
    expect(result).not.toContain('javascript:');
    expect(result).not.toContain('onerror');
    expect(result).not.toContain('<iframe');
    expect(result).not.toContain('alert');

    // 安全なコンテンツは保持される
    expect(result).toContain('Normal');
    expect(result).toContain('<strong>safe</strong>');
  });

  it('✅ Markdownの高度な機能も正しく動作する', () => {
    const markdown = `
# Heading 1
## Heading 2

- List item 1
- List item 2

| Column 1 | Column 2 |
|----------|----------|
| Data 1   | Data 2   |

\`\`\`javascript
const x = 1;
\`\`\`

> Blockquote

---
    `.trim();

    const result = convertAndSanitize(markdown);

    // 各要素が正しく変換されていることを確認
    expect(result).toContain('<h1');
    expect(result).toContain('<h2');
    expect(result).toContain('<ul');
    expect(result).toContain('<li');
    expect(result).toContain('<table');
    expect(result).toContain('<code');
    expect(result).toContain('<blockquote');
    expect(result).toContain('<hr');
  });
});
