import { useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { Sparkles, ArrowRight } from 'lucide-react'
import { login, signup } from './api'

export default function Login({ onLoggedIn }) {
  const [mode, setMode] = useState('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      if (mode === 'login') await login(username, password)
      else await signup(username, password)
      onLoggedIn()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative flex h-screen items-center justify-center overflow-hidden bg-surface text-white">
      <div className="stars" />
      <div className="orb-wrap -left-40 -bottom-40 h-[480px] w-[480px]">
        <div className="orb-core" />
        <div className="orb-grid" />
        <div className="orb-highlight" />
      </div>

      <div className="absolute right-6 top-6 flex items-center gap-1.5 text-xs text-accent-light/70">
        <Sparkles className="h-3.5 w-3.5" /> LOCAL RAG ASSISTANT
      </div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="relative z-10 w-[380px] rounded-2xl border border-accent/15 bg-surface-raised/70 p-8 shadow-2xl backdrop-blur-xl"
      >
        <h1 className="mb-5 text-xl font-semibold">
          Welcome <span className="text-accent-light">{mode === 'login' ? 'Back' : ''}</span>
        </h1>

        <div className="mb-5 flex rounded-lg bg-white/5 p-1 text-xs">
          <button
            onClick={() => { setMode('signup'); setError(null) }}
            className={`flex-1 rounded-md py-1.5 text-center font-medium transition-colors ${
              mode === 'signup' ? 'bg-accent text-black' : 'text-white/50'
            }`}
          >
            Sign up
          </button>
          <button
            onClick={() => { setMode('login'); setError(null) }}
            className={`flex-1 rounded-md py-1.5 text-center font-medium transition-colors ${
              mode === 'login' ? 'bg-accent text-black' : 'text-white/50'
            }`}
          >
            Login
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div>
            <label className="mb-1 block text-[0.7rem] text-white/40">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              minLength={3}
              className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2.5 text-sm outline-none transition-colors placeholder:text-white/25 focus:border-accent-light"
              placeholder="Username"
            />
          </div>
          <div>
            <label className="mb-1 block text-[0.7rem] text-white/40">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2.5 text-sm outline-none transition-colors placeholder:text-white/25 focus:border-accent-light"
              placeholder="Password"
            />
          </div>

          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="rounded-lg bg-red-500/10 px-3 py-2 text-[0.7rem] text-red-300"
              >
                {error}
              </motion.div>
            )}
          </AnimatePresence>

          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            type="submit"
            disabled={loading}
            className="mt-2 flex items-center justify-center gap-2 rounded-lg bg-accent py-2.5 text-sm font-medium text-black transition-opacity disabled:opacity-50"
          >
            {loading ? 'Please wait...' : mode === 'login' ? (
              <>Sign in <ArrowRight className="h-4 w-4" /></>
            ) : (
              <>Create account <ArrowRight className="h-4 w-4" /></>
            )}
          </motion.button>
        </form>

        <div className="mt-5 text-center text-[0.7rem] text-white/40">
          {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
          <button
            className="text-accent-light hover:underline"
            onClick={() => { setMode(mode === 'login' ? 'signup' : 'login'); setError(null) }}
          >
            {mode === 'login' ? 'Sign up' : 'Log in'}
          </button>
        </div>
      </motion.div>
    </div>
  )
}
