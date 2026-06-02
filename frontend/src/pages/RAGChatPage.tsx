import { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, BookOpen, Loader2 } from 'lucide-react'
import { api } from '../services/api'

interface Source {
  title: string
  content_hash: string
  relevance_score: number
  ipfs_cid: string
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
}

function RAGChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [provider, setProvider] = useState('openai')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const res = await api.rag({ query: input, top_k: 3, provider }) as {
        answer: string
        sources: Source[]
        query: string
      }

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: res.answer,
        sources: res.sources,
      }
      setMessages(prev => [...prev, assistantMessage])
    } catch (err) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `Error: ${err instanceof Error ? err.message : 'Failed to get response'}`,
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <div className="mb-4">
        <h1 className="text-2xl font-bold mb-1">RAG Chat</h1>
        <p className="text-dark-200">Ask questions — answers are grounded in verified knowledge sources.</p>
      </div>

      <div className="flex-1 overflow-y-auto space-y-4 mb-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center space-y-4">
              <div className="w-16 h-16 bg-stellar-600/20 rounded-2xl flex items-center justify-center mx-auto">
                <Bot className="w-8 h-8 text-stellar-400" />
              </div>
              <div>
                <p className="text-dark-100 font-medium">Ask a question</p>
                <p className="text-dark-300 text-sm">
                  Responses are generated from verified knowledge in the network.
                </p>
              </div>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}
          >
            {msg.role === 'assistant' && (
              <div className="w-8 h-8 bg-stellar-600/20 rounded-lg flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4 text-stellar-400" />
              </div>
            )}
            <div
              className={`max-w-[70%] ${
                msg.role === 'user'
                  ? 'bg-stellar-600 rounded-2xl rounded-tr-md px-4 py-3'
                  : 'bg-dark-700 rounded-2xl rounded-tl-md px-4 py-3 border border-dark-400'
              }`}
            >
              <p className="whitespace-pre-wrap text-sm">{msg.content}</p>

              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-3 pt-3 border-t border-dark-400">
                  <p className="text-xs font-medium text-dark-200 flex items-center gap-1 mb-2">
                    <BookOpen className="w-3 h-3" /> Sources
                  </p>
                  <div className="space-y-1">
                    {msg.sources.map((source, i) => (
                      <div key={i} className="text-xs text-dark-300 flex items-center gap-2">
                        <span className="bg-dark-600 px-1.5 py-0.5 rounded">
                          {(source.relevance_score * 100).toFixed(0)}%
                        </span>
                        <span className="truncate">{source.title}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
            {msg.role === 'user' && (
              <div className="w-8 h-8 bg-dark-500 rounded-lg flex items-center justify-center shrink-0">
                <User className="w-4 h-4 text-dark-100" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 bg-stellar-600/20 rounded-lg flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4 text-stellar-400" />
            </div>
            <div className="bg-dark-700 rounded-2xl rounded-tl-md px-4 py-3 border border-dark-400">
              <Loader2 className="w-4 h-4 animate-spin text-stellar-400" />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSend} className="flex gap-3">
        <select
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
          className="input-field w-36 text-sm"
        >
          <option value="openai">OpenAI</option>
          <option value="claude">Claude</option>
          <option value="gemini">Gemini</option>
        </select>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about the knowledge network..."
          className="input-field flex-1"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="btn-primary disabled:opacity-50"
        >
          <Send className="w-5 h-5" />
        </button>
      </form>
    </div>
  )
}

export default RAGChatPage
