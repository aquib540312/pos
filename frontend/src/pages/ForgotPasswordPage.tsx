import { useState } from 'react'
import { Link } from 'react-router-dom'
import { apiClient, apiErrorMessage } from '../api/client'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await apiClient.post('/auth/forgot-password', { email })
      setSubmitted(true)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 dark:bg-slate-900">
      <div className="w-full max-w-sm rounded-xl bg-white p-8 shadow-md dark:bg-slate-800">
        <h1 className="mb-1 text-2xl font-semibold text-slate-900 dark:text-slate-50">
          Forgot your password?
        </h1>
        <p className="mb-6 text-sm text-slate-500 dark:text-slate-400">
          Enter your email and we'll send you a reset link.
        </p>

        {submitted ? (
          <p className="text-sm text-slate-700 dark:text-slate-300">
            If that email is registered, a reset link has been sent. Check your inbox.
          </p>
        ) : (
          <form onSubmit={handleSubmit}>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />

            {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              {loading ? 'Sending...' : 'Send reset link'}
            </button>
          </form>
        )}

        <p className="mt-4 text-center text-sm text-slate-500 dark:text-slate-400">
          <Link to="/login" className="font-medium text-indigo-600 hover:text-indigo-500">
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
