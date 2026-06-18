import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cn } from '@/lib/utils'

interface MarkdownRendererProps {
  content: string
  className?: string
}

export function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  return (
    <div className={cn('text-sm prose prose-slate dark:prose-invert max-w-none', className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // 自定义段落样式
          p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,
          // 自定义标题样式
          h1: ({ children }) => <h1 className="text-lg font-bold mb-2">{children}</h1>,
          h2: ({ children }) => <h2 className="text-base font-bold mb-2">{children}</h2>,
          h3: ({ children }) => <h3 className="text-sm font-bold mb-1">{children}</h3>,
          // 自定义列表样式
          ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          // 自定义代码样式
          code: ({ className: codeClassName, children, ...props }) => {
            const isInline = !codeClassName
            return isInline
              ? <code className="bg-surface-dim px-1 py-0.5 rounded text-xs" {...props}>{children}</code>
              : <code className="block bg-surface-alt rounded-lg p-2 text-xs overflow-x-auto" {...props}>{children}</code>
          },
          pre: ({ children }) => <pre className="mb-2 overflow-x-auto">{children}</pre>,
          // 自定义链接样式
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-t-blue hover:text-t-blue underline"
            >
              {children}
            </a>
          ),
          // 自定义引用样式
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-line pl-3 italic text-content-muted">
              {children}
            </blockquote>
          ),
          // 自定义表格样式
          table: ({ children }) => (
            <div className="overflow-x-auto mb-2">
              <table className="min-w-full border border-line">{children}</table>
            </div>
          ),
          th: ({ children }) => <th className="border border-line px-2 py-1 bg-surface-alt">{children}</th>,
          td: ({ children }) => <td className="border border-line px-2 py-1">{children}</td>,
          // 自定义分隔线
          hr: () => <hr className="border-line my-2" />,
          // 自定义强调
          strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
          em: ({ children }) => <em className="italic">{children}</em>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}