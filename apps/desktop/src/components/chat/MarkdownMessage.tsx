/**
 * Renders assistant/user markdown with syntax-highlighted code blocks
 * and a copy-to-clipboard button on each block.
 */

import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { Check, Copy } from 'lucide-react';
import 'highlight.js/styles/github-dark.css';

/** Flatten a React node tree to its text (for copying code). */
function nodeText(node: React.ReactNode): string {
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(nodeText).join('');
  if (React.isValidElement(node)) return nodeText((node.props as { children?: React.ReactNode }).children);
  return '';
}

const CodeBlock: React.FC<{ children?: React.ReactNode }> = ({ children }) => {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    await navigator.clipboard.writeText(nodeText(children).replace(/\n$/, ''));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="relative group my-3">
      <button
        onClick={copy}
        className="absolute top-2 right-2 p-1.5 rounded-md bg-neutral-700/80 text-neutral-200 opacity-0 group-hover:opacity-100 transition-opacity"
        title="Copy code"
      >
        {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
      </button>
      <pre className="overflow-x-auto rounded-lg bg-neutral-900 p-4 text-sm">{children}</pre>
    </div>
  );
};

export const MarkdownMessage: React.FC<{ content: string }> = ({ content }) => (
  <div className="text-sm leading-relaxed break-words space-y-3 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_a]:text-brand-600 [&_a]:underline [&_h1]:text-xl [&_h1]:font-semibold [&_h2]:text-lg [&_h2]:font-semibold [&_h3]:font-semibold [&_blockquote]:border-l-4 [&_blockquote]:border-neutral-300 [&_blockquote]:pl-3 [&_blockquote]:text-neutral-600 [&_table]:border-collapse [&_th]:border [&_th]:px-2 [&_th]:py-1 [&_td]:border [&_td]:px-2 [&_td]:py-1 dark:[&_blockquote]:border-neutral-600 dark:[&_blockquote]:text-neutral-400">
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeHighlight]}
      components={{
        pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
        code: ({ className, children, ...props }) =>
          className ? (
            <code className={className} {...props}>
              {children}
            </code>
          ) : (
            <code className="rounded bg-neutral-200 px-1 py-0.5 text-[0.85em] dark:bg-neutral-700" {...props}>
              {children}
            </code>
          ),
      }}
    >
      {content}
    </ReactMarkdown>
  </div>
);

export default MarkdownMessage;
