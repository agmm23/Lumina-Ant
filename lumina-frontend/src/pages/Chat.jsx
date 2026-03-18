import { useState, useEffect, useRef, useCallback } from 'react'
import { chatService } from '../services/api'
import ChatMessage from '../components/ChatMessage'
import { useLanguage } from '../contexts/LanguageContext'

const STORAGE_KEY = 'lumina_chat_history'
const STREAM_URL = 'http://localhost:8000/api/chat/stream'

function Chat() {
  const { t } = useLanguage()

  const getWelcomeMessage = () => ({
    role: 'assistant',
    content: t('chat.welcome'),
    intents: [],
    data_sources: [],
    suggested_followups: [],
    timestamp: Date.now(),
  })

  const [messages, setMessages] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      return saved ? JSON.parse(saved) : [getWelcomeMessage()]
    } catch {
      return [getWelcomeMessage()]
    }
  })
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [prompts, setPrompts] = useState([])
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  // Persist messages to localStorage — exclude in-flight streaming messages
  useEffect(() => {
    const toSave = messages.filter((m) => !m.streaming)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(toSave))
  }, [messages])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Load suggested prompts on mount
  useEffect(() => {
    chatService.getSuggestedPrompts()
      .then((res) => setPrompts(res.data.prompts || []))
      .catch(() => {})
  }, [])

  const sendMessage = useCallback(async (text) => {
    const trimmed = text.trim()
    if (!trimmed || loading) return

    const userMsg = { role: 'user', content: trimmed, timestamp: Date.now() }
    // Unique id for the streaming placeholder
    const placeholderId = Date.now() + 1

    setMessages((prev) => [
      ...prev,
      userMsg,
      { role: 'assistant', content: '', streaming: true, timestamp: placeholderId },
    ])
    setInput('')
    setLoading(true)

    try {
      const allMessages = [...messages, userMsg]
      const history = allMessages
        .slice(-20)
        .map((m) => ({ role: m.role, content: m.content }))

      const response = await fetch(STREAM_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: trimmed, history }),
      })

      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        // SSE events are separated by double newline
        const events = buffer.split('\n\n')
        buffer = events.pop() // keep incomplete tail

        for (const event of events) {
          const line = event.trim()
          if (!line.startsWith('data: ')) continue
          try {
            const data = JSON.parse(line.slice(6))

            if (data.type === 'delta') {
              setMessages((prev) =>
                prev.map((m) =>
                  m.timestamp === placeholderId
                    ? { ...m, content: m.content + data.content }
                    : m
                )
              )
            } else if (data.type === 'done') {
              setMessages((prev) =>
                prev.map((m) =>
                  m.timestamp === placeholderId
                    ? {
                        ...m,
                        streaming: false,
                        intents: data.intents || [],
                        data_sources: data.data_sources || [],
                        suggested_followups: data.suggested_followups || [],
                        usage: data.usage || null,
                      }
                    : m
                )
              )
            } else if (data.type === 'error') {
              setMessages((prev) =>
                prev.map((m) =>
                  m.timestamp === placeholderId
                    ? { ...m, content: data.content, streaming: false, isError: true }
                    : m
                )
              )
            }
          } catch {
            // malformed JSON — ignore
          }
        }
      }
    } catch {
      setMessages((prev) =>
        prev.map((m) =>
          m.timestamp === placeholderId
            ? { ...m, content: t('chat.errorRespuesta'), streaming: false, isError: true }
            : m
        )
      )
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }, [messages, loading, t])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  const clearChat = () => {
    setMessages([getWelcomeMessage()])
    localStorage.removeItem(STORAGE_KEY)
  }

  const hasOnlyWelcome = messages.length <= 1
  const isDemo = messages.some((m) => m.role === 'assistant' && m.usage?.source === 'estimated')

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
        <div className="flex items-center gap-3">
          <div>
            <h1 className="text-lg font-semibold text-gray-900 dark:text-white">
              {t('chat.title')}
            </h1>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
              {t('chat.subtitle')}
            </p>
          </div>
          {isDemo && (
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400 border border-amber-200 dark:border-amber-800 font-medium">
              Demo
            </span>
          )}
        </div>
        {!hasOnlyWelcome && (
          <button
            onClick={clearChat}
            className="text-xs px-3 py-1.5 rounded-lg text-gray-400 dark:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-600 dark:hover:text-gray-300 transition-colors cursor-pointer"
          >
            {t('chat.limpiarChat')}
          </button>
        )}
      </div>

      {/* Quick prompts */}
      {hasOnlyWelcome && prompts.length > 0 && (
        <div className="px-6 py-3 border-b border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900">
          <p className="text-xs text-gray-400 dark:text-gray-500 mb-2">{t('chat.sugerencias')}</p>
          <div className="flex flex-wrap gap-2">
            {prompts.map((p, i) => (
              <button
                key={i}
                onClick={() => sendMessage(p.text)}
                disabled={loading}
                className="text-xs px-3 py-1.5 rounded-full bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:border-blue-400 hover:text-blue-600 dark:hover:border-blue-500 dark:hover:text-blue-400 transition-colors cursor-pointer disabled:opacity-50"
              >
                <span className="mr-1">{p.icon}</span>
                {p.text}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto bg-gray-50 dark:bg-gray-950">
        <div className="max-w-3xl mx-auto px-4 py-6">
          {messages.map((msg, i) => (
            <ChatMessage
              key={i}
              message={msg}
              onFollowupClick={(text) => sendMessage(text)}
            />
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input area */}
      <div className="border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-4 py-4">
        <div className="flex gap-3 items-end max-w-3xl mx-auto">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t('chat.placeholder')}
            rows={1}
            disabled={loading}
            className="flex-1 resize-none rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50 placeholder:text-gray-400"
            style={{ maxHeight: '120px' }}
            onInput={(e) => {
              e.target.style.height = 'auto'
              e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
            }}
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || loading}
            className="px-4 py-3 rounded-xl bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer flex-shrink-0"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
              <path d="M3.105 2.288a.75.75 0 0 0-.826.95l1.414 4.926A1.5 1.5 0 0 0 5.135 9.25h6.115a.75.75 0 0 1 0 1.5H5.135a1.5 1.5 0 0 0-1.442 1.086l-1.414 4.926a.75.75 0 0 0 .826.95l14.095-5.927a.75.75 0 0 0 0-1.37L3.105 2.288Z" />
            </svg>
          </button>
        </div>
        <p className="text-[10px] text-gray-400 dark:text-gray-500 text-center mt-2">
          {t('chat.instruccion')}
        </p>
      </div>
    </div>
  )
}

export default Chat
