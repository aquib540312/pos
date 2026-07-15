import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiClient, apiErrorMessage } from '../api/client'
import { useAuthStore } from '../store/auth'
import type { Plan } from '../types'

const INDIAN_STATE_CODES: { code: string; name: string }[] = [
  { code: '27', name: 'Maharashtra' },
  { code: '07', name: 'Delhi' },
  { code: '29', name: 'Karnataka' },
  { code: '33', name: 'Tamil Nadu' },
  { code: '24', name: 'Gujarat' },
  { code: '09', name: 'Uttar Pradesh' },
  { code: '19', name: 'West Bengal' },
]

export default function SignupPage() {
  const [plans, setPlans] = useState<Plan[]>([])
  const [legalName, setLegalName] = useState('')
  const [tradeName, setTradeName] = useState('')
  const [gstin, setGstin] = useState('')
  const [stateCode, setStateCode] = useState('27')
  const [branchName, setBranchName] = useState('Main Store')
  const [adminFullName, setAdminFullName] = useState('')
  const [adminEmail, setAdminEmail] = useState('')
  const [adminPassword, setAdminPassword] = useState('')
  const [planCode, setPlanCode] = useState('starter')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const setSession = useAuthStore((s) => s.setSession)
  const navigate = useNavigate()

  useEffect(() => {
    apiClient.get<Plan[]>('/subscriptions/plans').then((res) => setPlans(res.data))
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const resp = await apiClient.post('/auth/signup', {
        legal_name: legalName,
        trade_name: tradeName,
        gstin: gstin || null,
        default_state_code: stateCode,
        branch_name: branchName,
        admin_full_name: adminFullName,
        admin_email: adminEmail,
        admin_password: adminPassword,
        plan_code: planCode,
      })
      const token = resp.data.access_token as string
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
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10 dark:bg-slate-900">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-lg rounded-xl bg-white p-8 shadow-md dark:bg-slate-800"
      >
        <h1 className="mb-1 text-2xl font-semibold text-slate-900 dark:text-slate-50">
          Start your free trial
        </h1>
        <p className="mb-6 text-sm text-slate-500 dark:text-slate-400">
          14 days free, no card required. Set up your store in under a minute.
        </p>

        <div className="mb-4 grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
              Legal business name
            </label>
            <input
              required
              value={legalName}
              onChange={(e) => setLegalName(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
              Trade name
            </label>
            <input
              required
              value={tradeName}
              onChange={(e) => setTradeName(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
          </div>
        </div>

        <div className="mb-4 grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
              Home state (GST)
            </label>
            <select
              required
              value={stateCode}
              onChange={(e) => setStateCode(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            >
              {INDIAN_STATE_CODES.map((s) => (
                <option key={s.code} value={s.code}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
              GSTIN (optional)
            </label>
            <input
              value={gstin}
              onChange={(e) => setGstin(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
          </div>
        </div>

        <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
          First store name
        </label>
        <input
          required
          value={branchName}
          onChange={(e) => setBranchName(e.target.value)}
          className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
        />

        <div className="mb-4 grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
              Your name
            </label>
            <input
              required
              value={adminFullName}
              onChange={(e) => setAdminFullName(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
              Work email
            </label>
            <input
              required
              type="email"
              value={adminEmail}
              onChange={(e) => setAdminEmail(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
          </div>
        </div>

        <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Password</label>
        <input
          required
          type="password"
          minLength={8}
          value={adminPassword}
          onChange={(e) => setAdminPassword(e.target.value)}
          className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
        />

        <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Plan</label>
        <div className="mb-4 grid grid-cols-3 gap-2">
          {plans.map((p) => (
            <button
              type="button"
              key={p.code}
              onClick={() => setPlanCode(p.code)}
              className={`rounded-lg border px-3 py-2 text-left text-sm ${
                planCode === p.code
                  ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-950/40'
                  : 'border-slate-300 dark:border-slate-600'
              }`}
            >
              <div className="font-semibold text-slate-900 dark:text-slate-100">{p.name}</div>
              <div className="text-slate-500 dark:text-slate-400">₹{p.price_monthly}/mo</div>
            </button>
          ))}
        </div>

        {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {loading ? 'Setting up your store...' : 'Start free trial'}
        </button>

        <p className="mt-4 text-center text-sm text-slate-500 dark:text-slate-400">
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-indigo-600 hover:text-indigo-500">
            Sign in
          </Link>
        </p>
      </form>
    </div>
  )
}
