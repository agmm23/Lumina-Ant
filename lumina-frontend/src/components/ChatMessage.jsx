import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// Custom Tailwind components for react-markdown
const markdownComponents = {
  p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,
  h1: ({ children }) => <h1 className="text-base font-bold mb-2 mt-1">{children}</h1>,
  h2: ({ children }) => <h2 className="text-sm font-bold mb-1.5 mt-1">{children}</h2>,
  h3: ({ children }) => <h3 className="text-sm font-semibold mb-1 mt-1">{children}</h3>,
  ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-0.5">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-0.5">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  hr: () => <hr className="my-2 border-gray-200 dark:border-gray-600" />,
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-blue-400 pl-3 my-2 text-gray-600 dark:text-gray-400 italic">
      {children}
    </blockquote>
  ),
  code: ({ inline, children }) =>
    inline ? (
      <code className="bg-gray-100 dark:bg-gray-700 text-pink-600 dark:text-pink-400 px-1 py-0.5 rounded text-[0.8em] font-mono">
        {children}
      </code>
    ) : (
      <pre className="bg-gray-100 dark:bg-gray-700 rounded p-2 my-2 overflow-x-auto">
        <code className="text-xs font-mono text-gray-800 dark:text-gray-200">{children}</code>
      </pre>
    ),
  table: ({ children }) => (
    <div className="overflow-x-auto my-2">
      <table className="text-xs border-collapse w-full">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-gray-300 dark:border-gray-600 bg-gray-100 dark:bg-gray-700 px-2 py-1 text-left font-semibold">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border border-gray-300 dark:border-gray-600 px-2 py-1">{children}</td>
  ),
}

function ChatMessage({ message, onFollowupClick }) {
  const isUser = message.role === 'user'
  const isError = message.isError
  const isStreaming = message.streaming

  const hasFollowups = !isUser && !isStreaming && message.suggested_followups?.length > 0
  const hasSources = !isUser && !isStreaming && message.data_sources?.length > 0
  const hasTokens = !isUser && !isStreaming && message.usage?.total_tokens > 0
  const hasFooter = message.timestamp && !isStreaming

  return (
    <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} mb-5`}>
      {/* Bubble */}
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? 'bg-blue-600 text-white rounded-br-md'
            : isError
              ? 'bg-red-50 dark:bg-red-900/30 text-red-800 dark:text-red-200 border border-red-200 dark:border-red-800 rounded-bl-md'
              : 'bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 border border-gray-200 dark:border-gray-700 rounded-bl-md'
        }`}
      >
        {/* Contenido del mensaje */}
        <div className="text-sm">
          {isUser ? (
            <span className="leading-relaxed">{message.content}</span>
          ) : isStreaming && !message.content ? (
            <span className="flex gap-1 items-center py-0.5">
              <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:0ms]" />
              <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:150ms]" />
              <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:300ms]" />
            </span>
          ) : (
            <>
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                {message.content}
              </ReactMarkdown>
              {isStreaming && (
                <span className="inline-block w-0.5 h-3.5 bg-current align-middle ml-0.5 animate-pulse" />
              )}
            </>
          )}
        </div>

        {/* Footer: hora · tokens · fuentes */}
        {hasFooter && (
          <div className={`flex items-center flex-wrap gap-x-1 text-[10px] mt-2 ${isUser ? 'text-blue-200' : 'text-gray-400 dark:text-gray-500'}`}>
            <span>
              {new Date(message.timestamp).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })}
            </span>
            {hasTokens && (
              <span title={`Input: ${message.usage.input_tokens} · Output: ${message.usage.output_tokens}`}>
                &nbsp;· {message.usage.total_tokens.toLocaleString()} tokens{message.usage.source === 'estimated' ? '*' : ''}
              </span>
            )}
            {hasSources && message.data_sources.map((src) => (
              <span key={src}>&nbsp;· {src}</span>
            ))}
          </div>
        )}
      </div>

      {/* Follow-ups: fuera del bubble, como texto sutil */}
      {hasFollowups && (
        <div className="flex flex-col gap-0.5 mt-1.5 px-1 max-w-[80%]">
          {message.suggested_followups.map((followup, i) => (
            <button
              key={i}
              onClick={() => onFollowupClick?.(followup)}
              className="text-[11px] text-left text-gray-400 dark:text-gray-500 hover:text-blue-500 dark:hover:text-blue-400 transition-colors cursor-pointer"
            >
              ↳ {followup}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default ChatMessage
