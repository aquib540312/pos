import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { apiClient, apiErrorMessage } from '../api/client'

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') ?? ''
  const [newPassword, setNewPassword] = useState('')
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await apiClient.post('/auth/reset-password', { token, new_password: newPassword })
      setDone(true)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 dark:bg-slate-900">
      <div className="w-full max-w-sm rounded-xl bg-white p-8 shadow-md dark:bg-slate-800">
        <h1 className="mb-1 text-2xl font-semibold text-slate-900 dark:text-slate-50">Reset your password</h1>

        {!token && (
          <p className="mb-4 text-sm text-red-600 dark:text-red-400">
            This link is missing its reset token. Request a new one from the forgot-password page.
          </p>
        )}

        {done ? (
          <>
            <p className="mb-4 text-sm text-slate-700 dark:text-slate-300">
              Your password has been updated.
            </p>
            <button
              onClick={() => navigate('/login')}
              className="w-full rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
            >
              Go to sign in
            </button>
          </>
        ) : (
          <form onSubmit={handleSubmit}>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
              New password
            </label>
            <input
              type="password"
              required
              minLength={8}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />

            {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

            <button
              type="submit"
              disabled={loading || !token}
              className="w-full rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              {loading ? 'Updating...' : 'Update password'}
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
