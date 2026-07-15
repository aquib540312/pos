import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiClient, apiErrorMessage } from '../api/client'
import { useAuthStore } from '../store/auth'

export default function LoginPage() {
  const [email, setEmail] = useState('admin@demo.local')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const setSession = useAuthStore((s) => s.setSession)
  const navigate = useNavigate()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const form = new URLSearchParams()
      form.set('username', email)
      form.set('password', password)
      const tokenResp = await apiClient.post('/auth/login', form, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      const token = tokenResp.data.access_token as string
      // Temporarily store token so the /auth/me call below is authenticated.
      useAuthStore.getState().setSession(token, { id: '', full_name: '', email: '' })
      const me = await apiClient.get('/auth/me')
      setSession(token, me.data)
      navigate('/')
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 dark:bg-slate-900">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm rounded-xl bg-white p-8 shadow-md dark:bg-slate-800"
      >
        <h1 className="mb-1 text-2xl font-semibold text-slate-900 dark:text-slate-50">
          Retail POS
        </h1>
        <p className="mb-6 text-sm text-slate-500 dark:text-slate-400">Sign in to continue</p>

        <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Email</label>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
        />

        <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Password</label>
        <input
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
        />

        {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {loading ? 'Signing in...' : 'Sign in'}
        </button>

        <div className="mt-4 flex justify-between text-sm">
          <Link to="/forgot-password" className="font-medium text-indigo-600 hover:text-indigo-500">
            Forgot password?
          </Link>
          <Link to="/signup" className="font-medium text-indigo-600 hover:text-indigo-500">
            Start free trial
          </Link>
        </div>
      </form>
    </div>
  )
}
