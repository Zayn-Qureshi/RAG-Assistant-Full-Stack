import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { ArrowUp, ChevronDown } from 'lucide-react'
import { isLoggedIn, clearToken, checkHealth, sendQuery, getConversationMessages } from './api'
import Login from './Login'
import Sidebar from './Sidebar'

function getUsername() {
  return localStorage.getItem('rag_username') || 'User'
}

export default function App() {
  const [loggedIn, setLoggedIn] = useState(isLoggedIn())
  const [backendStatus, setBackendStatus] = useState('checking')
  const [activeConversationId, setActiveConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const messagesEndRef = useRef(null)
  const username = getUsername()
  const initial = username.charAt(0).toUpperCase()

  useEffect(() => {
    checkHealth().then(() => setBackendStatus('online')).catch(() => setBackendStatus('offline'))
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (!activeConversationId) { setMessages([]); return }
    getConversationMessages(activeConversationId)
      .then((msgs) => setMessages(msgs.map((m) => ({ role: m.role, content: m.content, sources: m.sources }))))
      .catch(() => setMessages([]))
  }, [activeConversationId])

  function handleLoggedOut() {
    clearToken()
    setLoggedIn(false)
    setActiveConversationId(null)
    setMessages([])
  }

  async function handleSubmit(e) {
    e.preventDefault()
    const query = input.trim()
    if (!query || loading || !activeConversationId) return

    setInput('')
    setError(null)
    setMessages((prev) => [...prev, { role: 'user', content: query }])
    setLoading(true)

    try {
      const result = await sendQuery(query, activeConversationId)
      setMessages((prev) => [...prev, { role: 'assistant', content: result.answer, sources: result.sources, latency: result.latency_seconds }])
    } catch (err) {
      if (err.status === 401) {
        setLoggedIn(false)
        return
      }
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (!loggedIn) {
    return <Login onLoggedIn={() => setLoggedIn(true)} />
  }

  return (
    <div className="relative flex h-screen overflow-hidden bg-surface text-white">
      <div className="stars" />
      <div className="orb-wrap left-1/3 -top-52 h-[480px] w-[480px]">
        <div className="orb-core" />
        <div className="orb-grid" />
        <div className="orb-highlight" />
      </div>

      <div className="relative z-10 flex w-full">
        <Sidebar
          activeConversationId={activeConversationId}
          onSelectConversation={setActiveConversationId}
          onLoggedOut={handleLoggedOut}
          username={username}
        />

        <div className="flex flex-1 flex-col">
          <div className="flex justify-end p-6">
            <div className="flex items-center gap-2.5 rounded-full border border-white/10 bg-white/5 py-1.5 pl-1.5 pr-4">
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-accent-light to-accent-dark text-xs font-semibold text-black">
                {initial}
              </div>
              <span className="text-sm font-medium text-white/90">{username}</span>
              <ChevronDown className="h-3.5 w-3.5 text-white/40" />
            </div>
          </div>

          <div className="scrollbar-thin flex-1 overflow-y-auto px-8 pb-4">
            {!activeConversationId && (
              <div className="mx-auto mt-16 max-w-sm text-center">
                <p className="text-sm text-white/40">
                  Pick a conversation from the sidebar, or start a new one to begin.
                </p>
              </div>
            )}

            {activeConversationId && messages.length === 0 && (
              <div className="mx-auto mt-10 max-w-xl text-center">
                <h2 className="text-3xl font-semibold text-white/90">Hey! {username}</h2>
                <p className="text-3xl font-semibold text-white/40">What can I help with?</p>
              </div>
            )}

            <div className="mx-auto flex max-w-2xl flex-col gap-5 pt-4">
              <AnimatePresence initial={false}>
                {messages.map((msg, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={msg.role === 'user' ? 'ml-auto max-w-[80%]' : 'mr-auto max-w-[80%]'}
                  >
                    {msg.role === 'assistant' && (
                      <div className="mb-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-br from-accent-light to-accent-dark text-[0.65rem] font-semibold text-black">
                        AI
                      </div>
                    )}
                    <div className={`whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                      msg.role === 'user'
                        ? 'bg-accent text-black'
                        : 'border border-white/10 bg-white/5 text-white/90'
                    }`}>
                      {msg.content}
                      {msg.sources?.length > 0 && (
                        <div className="mt-2.5 flex flex-wrap gap-1.5 border-t border-white/10 pt-2">
                          {msg.sources.map((s, j) => (
                            <span key={j} className="rounded-md bg-white/5 px-2 py-0.5 text-[0.7rem] text-white/40">
                              {s}
                            </span>
                          ))}
                          {msg.latency && <span className="text-[0.7rem] text-white/25">{msg.latency}s</span>}
                        </div>
                      )}
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>

              {loading && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mr-auto max-w-[80%]">
                  <div className="flex gap-1 rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
                    {[0, 1, 2].map((i) => (
                      <motion.span
                        key={i}
                        className="h-1.5 w-1.5 rounded-full bg-white/30"
                        animate={{ opacity: [0.3, 1, 0.3] }}
                        transition={{ duration: 1, repeat: Infinity, delay: i * 0.15 }}
                      />
                    ))}
                  </div>
                </motion.div>
              )}

              <AnimatePresence>
                {error && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-300"
                  >
                    {error}
                  </motion.div>
                )}
              </AnimatePresence>

              <div ref={messagesEndRef} />
            </div>
          </div>

          <form onSubmit={handleSubmit} className="px-8 pb-8">
            <div className="mx-auto max-w-2xl rounded-2xl border border-white/10 bg-white/5 p-3 backdrop-blur-md">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={activeConversationId ? 'Ask something about your documents...' : 'Select a conversation first'}
                disabled={loading || backendStatus === 'offline' || !activeConversationId}
                className="w-full bg-transparent px-1 py-1 text-sm text-white outline-none placeholder:text-white/30 disabled:opacity-50"
              />
              <div className="mt-2 flex items-center justify-between">
                <span className={`flex items-center gap-1.5 text-xs ${
                  backendStatus === 'online' ? 'text-emerald-400' : 'text-red-400'
                }`}>
                  <span className={`h-1.5 w-1.5 rounded-full ${backendStatus === 'online' ? 'bg-emerald-400' : 'bg-red-400'}`} />
                  {backendStatus === 'online' ? 'Online' : 'Offline'}
                </span>
                <motion.button
                  whileTap={{ scale: 0.9 }}
                  type="submit"
                  disabled={loading || !input.trim() || !activeConversationId}
                  className="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-black disabled:opacity-30"
                >
                  <ArrowUp className="h-4 w-4" />
                </motion.button>
              </div>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
