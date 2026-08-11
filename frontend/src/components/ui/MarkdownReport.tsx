/**
 * MarkdownReport — renders LLM-generated Markdown with full sanitization.
 * Uses react-markdown + remark-gfm + rehype-sanitize.
 * rehype-sanitize strips disallowed HTML (XSS prevention).
 */

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';

interface MarkdownReportProps {
  markdown: string;
}

export default function MarkdownReport({ markdown }: MarkdownReportProps) {
  if (!markdown) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '14px' }}>
        No report available. The report is generated after LLM triage completes.
      </div>
    );
  }

  return (
    <div className="markdown-report">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize]}
      >
        {markdown}
      </ReactMarkdown>

      <style>{`
        .markdown-report {
          font-size: 14px;
          line-height: 1.7;
          color: var(--text-primary);
        }
        .markdown-report h1 { font-size: 22px; font-weight: 700; margin: 0 0 16px 0; letter-spacing: -0.02em; }
        .markdown-report h2 { font-size: 17px; font-weight: 600; margin: 24px 0 12px 0; border-bottom: 1px solid var(--border-color); padding-bottom: 8px; }
        .markdown-report h3 { font-size: 15px; font-weight: 600; margin: 16px 0 8px 0; }
        .markdown-report p { margin: 0 0 12px 0; }
        .markdown-report ul, .markdown-report ol { margin: 0 0 12px 1.5rem; }
        .markdown-report li { margin-bottom: 4px; }
        .markdown-report code {
          font-family: 'Fira Code', 'Cascadia Code', monospace;
          font-size: 12px;
          background: var(--bg-surface);
          border: 1px solid var(--border-color);
          border-radius: 4px;
          padding: 2px 6px;
        }
        .markdown-report pre {
          background: var(--bg-base);
          border: 1px solid var(--border-color);
          border-radius: var(--radius-md);
          padding: 16px;
          overflow-x: auto;
          margin: 12px 0;
        }
        .markdown-report pre code {
          background: none;
          border: none;
          padding: 0;
          font-size: 12px;
        }
        .markdown-report table {
          width: 100%;
          border-collapse: collapse;
          margin: 12px 0;
          font-size: 13px;
        }
        .markdown-report th {
          text-align: left;
          padding: 10px 12px;
          background: var(--bg-surface);
          border-bottom: 1px solid var(--border-color);
          font-weight: 600;
          font-size: 11px;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--text-muted);
        }
        .markdown-report td {
          padding: 10px 12px;
          border-bottom: 1px solid var(--border-color);
        }
        .markdown-report blockquote {
          border-left: 3px solid var(--color-primary);
          padding: 8px 16px;
          margin: 12px 0;
          color: var(--text-secondary);
          background: rgba(59,130,246,0.05);
          border-radius: 0 var(--radius-md) var(--radius-md) 0;
        }
        .markdown-report hr {
          border: none;
          border-top: 1px solid var(--border-color);
          margin: 24px 0;
        }
        .markdown-report strong { color: var(--text-primary); }
      `}</style>
    </div>
  );
}
