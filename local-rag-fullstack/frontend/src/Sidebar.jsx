import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { Plus, MessageSquare, FileText, X, Paperclip, LogOut } from 'lucide-react'
import {
  listConversations, createConversation, deleteConversation,
  listDocuments, deleteDocument, uploadDocument, logout,
} from './api'

export default function Sidebar({ activeConversationId, onSelectConversation, onLoggedOut, username }) {
  const [conversations, setConversations] = useState([])
  const [documents, setDocuments] = useState([])
  const [uploadStatus, setUploadStatus] = useState(null)
  const fileInputRef = useRef(null)

  async function refreshConversations() {
    try { setConversations(await listConversations()) } catch (err) { console.error(err) }
  }
  async function refreshDocuments() {
    try { setDocuments((await listDocuments()).documents) } catch (err) { console.error(err) }
  }

  useEffect(() => { refreshConversations(); refreshDocuments() }, [])

  async function handleNewConversation() {
    const convo = await createConversation()
    await refreshConversations()
    onSelectConversation(convo.id)
  }

  async function handleDeleteConversation(id, e) {
    e.stopPropagation()
    if (!confirm('Delete this conversation?')) return
    await deleteConversation(id)
    await refreshConversations()
    if (id === activeConversationId) onSelectConversation(null)
  }

  async function handleFileSelect(e) {
    const file = e.target.files[0]
    if (!file) return
    setUploadStatus({ type: 'uploading', message: `Uploading ${file.name}...` })
    try {
      const result = await uploadDocument(file)
      setUploadStatus({ type: 'success', message: result.message })
      await refreshDocuments()
    } catch (err) {
      setUploadStatus({ type: 'error', message: err.message })
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = ''
      setTimeout(() => setUploadStatus(null), 6000)
    }
  }

  async function handleDeleteDocument(filename) {
    if (!confirm(`Delete "${filename}"?`)) return
    try {
      await deleteDocument(filename)
      await refreshDocuments()
    } catch (err) {
      alert(`Failed to delete: ${err.message}`)
    }
  }

  const initial = username.charAt(0).toUpperCase()

  return (
    <div className="scrollbar-thin flex w-72 flex-col overflow-y-auto border-r border-surface-border bg-surface-raised p-4">
      <div className="mb-5 flex items-center justify-between rounded-full border border-white/10 bg-white/5 py-1.5 pl-1.5 pr-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-accent-light to-accent-dark text-xs font-semibold text-black">
            {initial}
          </div>
          <span className="text-sm font-medium text-white/90">{username}</span>
        </div>
        <button
          onClick={async () => { await logout(); onLoggedOut() }}
          title="Log out"
          className="text-white/30 hover:text-white/70"
        >
          <LogOut className="h-4 w-4" />
        </button>
      </div>

      <motion.button
        whileTap={{ scale: 0.97 }}
        onClick={handleNewConversation}
        className="mb-6 flex items-center justify-center gap-1.5 rounded-xl border border-white/10 bg-white/5 py-2.5 text-sm text-white/90 transition-colors hover:bg-white/10"
      >
        <Plus className="h-4 w-4 text-accent-light" /> New conversation
      </motion.button>

      <div className="mb-6 flex-1">
        <div className="mb-2 px-1 text-[0.65rem] font-medium uppercase tracking-wider text-white/25">
          Conversations
        </div>
        <div className="scrollbar-thin flex max-h-52 flex-col gap-1 overflow-y-auto">
          {conversations.length === 0 && (
            <div className="px-1 py-2 text-xs text-white/25">Nothing yet — start one above</div>
          )}
          <AnimatePresence initial={false}>
            {conversations.map((c) => (
              <motion.div
                key={c.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={() => onSelectConversation(c.id)}
                className={`group flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors ${
                  c.id === activeConversationId ? 'bg-accent/15 text-white' : 'text-white/60 hover:bg-white/5'
                }`}
              >
                <MessageSquare className="h-3.5 w-3.5 shrink-0 opacity-60" />
                <span className="flex-1 overflow-hidden text-ellipsis whitespace-nowrap">{c.title}</span>
                <button
                  onClick={(e) => handleDeleteConversation(c.id, e)}
                  className="text-white/0 group-hover:text-white/30 hover:!text-red-400"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between px-1">
          <span className="text-[0.65rem] font-medium uppercase tracking-wider text-white/25">Documents</span>
          <label className="flex cursor-pointer items-center gap-1 text-xs text-accent-light hover:text-accent">
            <Paperclip className="h-3 w-3" /> Upload
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.txt,.md"
              onChange={handleFileSelect}
              disabled={uploadStatus?.type === 'uploading'}
              className="hidden"
            />
          </label>
        </div>

        <AnimatePresence>
          {uploadStatus && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className={`mb-2 rounded-lg px-2.5 py-1.5 text-xs ${
                uploadStatus.type === 'success' ? 'bg-emerald-500/10 text-emerald-300'
                : uploadStatus.type === 'error' ? 'bg-red-500/10 text-red-300'
                : 'bg-white/5 text-white/50'
              }`}
            >
              {uploadStatus.message}
            </motion.div>
          )}
        </AnimatePresence>

        <div className="scrollbar-thin flex max-h-52 flex-col gap-1 overflow-y-auto">
          {documents.length === 0 && (
            <div className="px-1 py-2 text-xs text-white/25">No documents yet</div>
          )}
          <AnimatePresence initial={false}>
            {documents.map((doc) => (
              <motion.div
                key={doc}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="group flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-white/60 hover:bg-white/5"
              >
                <FileText className="h-3.5 w-3.5 shrink-0 opacity-60" />
                <span className="flex-1 overflow-hidden text-ellipsis whitespace-nowrap" title={doc}>{doc}</span>
                <button
                  onClick={() => handleDeleteDocument(doc)}
                  className="text-white/0 group-hover:text-white/30 hover:!text-red-400"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
