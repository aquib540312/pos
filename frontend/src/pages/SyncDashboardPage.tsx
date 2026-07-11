import { useCallback, useEffect, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'
import type { SyncConflict, SyncStatus } from '../types'

interface Warehouse {
  id: string
  code: string
  name: string
  is_default: boolean
}
interface Branch {
  id: string
  code: string
  name: string
  warehouses: Warehouse[]
}

const POLL_INTERVAL_MS = 10000

function timeAgo(iso: string | null): string {
  if (!iso) return 'Never'
  const seconds = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000))
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return `${Math.floor(seconds / 86400)}d ago`
}

export default function SyncDashboardPage() {
  const [status, setStatus] = useState<SyncStatus | null>(null)
  const [conflicts, setConflicts] = useState<SyncConflict[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const [branches, setBranches] = useState<Branch[]>([])
  const [showRegisterForm, setShowRegisterForm] = useState(false)
  const [registerForm, setRegisterForm] = useState({ branchId: '', name: '', deviceFingerprint: '' })
  const [registerError, setRegisterError] = useState<string | null>(null)
  const [registering, setRegistering] = useState(false)
  const [issuedApiKey, setIssuedApiKey] = useState<string | null>(null)

  const [resolvingId, setResolvingId] = useState<string | null>(null)
  const [notesById, setNotesById] = useState<Record<string, string>>({})

  const refresh = useCallback(async () => {
    setError(null)
    try {
      const [statusRes, conflictsRes] = await Promise.all([
        apiClient.get<SyncStatus>('/sync/status'),
        apiClient.get<SyncConflict[]>('/sync/conflicts', { params: { status_filter: 'open' } }),
      ])
      setStatus(statusRes.data)
      setConflicts(conflictsRes.data)
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }, [])

  useEffect(() => {
    apiClient.get<Branch[]>('/org/branches').then((res) => {
      setBranches(res.data)
      setRegisterForm((f) => ({ ...f, branchId: f.branchId || res.data[0]?.id || '' }))
    })
    refresh()
    const interval = window.setInterval(refresh, POLL_INTERVAL_MS)
    return () => window.clearInterval(interval)
  }, [refresh])

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault()
    setRegisterError(null)
    setRegistering(true)
    try {
      const res = await apiClient.post('/sync/register', {
        branch_id: registerForm.branchId,
        name: registerForm.name,
        device_fingerprint: registerForm.deviceFingerprint,
      })
      setIssuedApiKey(res.data.api_key)
      setRegisterForm((f) => ({ ...f, name: '', deviceFingerprint: '' }))
      refresh()
    } catch (err) {
      setRegisterError(apiErrorMessage(err))
    } finally {
      setRegistering(false)
    }
  }

  async function resolveConflict(conflictId: string, resolution: 'retry' | 'cancel') {
    setResolvingId(conflictId)
    setError(null)
    try {
      await apiClient.post(`/sync/conflicts/${conflictId}/resolve`, {
        resolution,
        notes: notesById[conflictId] || null,
      })
      await refresh()
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setResolvingId(null)
    }
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-50">Sync Status</h1>
        <div className="flex gap-2">
          <button
            onClick={() => setShowRegisterForm((v) => !v)}
            className="rounded-lg bg-slate-200 px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-300 dark:bg-slate-700 dark:text-slate-100"
          >
            {showRegisterForm ? 'Cancel' : '+ Register Terminal'}
          </button>
          <button
            onClick={() => {
              setLoading(true)
              refresh().finally(() => setLoading(false))
            }}
            disabled={loading}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {loading ? 'Refreshing...' : 'Refresh now'}
          </button>
        </div>
      </div>

      {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

      {showRegisterForm && (
        <form
          onSubmit={handleRegister}
          className="mb-6 grid grid-cols-1 gap-3 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-800 md:grid-cols-4"
        >
          <select
            required
            value={registerForm.branchId}
            onChange={(e) => setRegisterForm({ ...registerForm, branchId: e.target.value })}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          >
            {branches.map((b) => (
              <option key={b.id} value={b.id}>{b.name}</option>
            ))}
          </select>
          <input
            required
            placeholder="Terminal name (e.g. Front Till)"
            value={registerForm.name}
            onChange={(e) => setRegisterForm({ ...registerForm, name: e.target.value })}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          />
          <input
            required
            placeholder="Device fingerprint (unique id)"
            value={registerForm.deviceFingerprint}
            onChange={(e) => setRegisterForm({ ...registerForm, deviceFingerprint: e.target.value })}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          />
          <button
            type="submit"
            disabled={registering}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {registering ? 'Registering...' : 'Register'}
          </button>
          {registerError && <p className="col-span-full text-sm text-red-600 dark:text-red-400">{registerError}</p>}
        </form>
      )}

      {issuedApiKey && (
        <div className="mb-6 rounded-xl border border-emerald-300 bg-emerald-50 p-4 text-sm dark:border-emerald-700 dark:bg-emerald-950/40">
          <p className="mb-1 font-semibold text-emerald-800 dark:text-emerald-300">
            Terminal registered. Copy this API key now -- it will not be shown again:
          </p>
          <code className="block break-all rounded bg-white px-2 py-1 text-emerald-900 dark:bg-slate-900 dark:text-emerald-200">
            {issuedApiKey}
          </code>
          <button onClick={() => setIssuedApiKey(null)} className="mt-2 text-xs text-emerald-700 underline dark:text-emerald-400">
            Dismiss
          </button>
        </div>
      )}

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-800">
          <p className="text-sm text-slate-500 dark:text-slate-400">Registered Terminals</p>
          <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-slate-50">{status?.terminals.length ?? '—'}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-800">
          <p className="text-sm text-slate-500 dark:text-slate-400">Open Conflicts</p>
          <p className={`mt-2 text-2xl font-semibold ${(status?.open_conflicts ?? 0) > 0 ? 'text-amber-600' : 'text-slate-900 dark:text-slate-50'}`}>
            {status?.open_conflicts ?? '—'}
          </p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-800">
          <p className="text-sm text-slate-500 dark:text-slate-400">Latest Change-log Id</p>
          <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-slate-50">{status?.latest_change_log_id ?? '—'}</p>
        </div>
      </div>

      <h2 className="mb-2 text-lg font-semibold text-slate-800 dark:text-slate-200">Terminals</h2>
      <div className="mb-8 overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Last Seen</th>
            </tr>
          </thead>
          <tbody>
            {(status?.terminals ?? []).map((t) => (
              <tr key={t.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">{t.name}</td>
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${t.is_active ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300' : 'bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-300'}`}>
                    {t.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{timeAgo(t.last_seen_at)}</td>
              </tr>
            ))}
            {(status?.terminals ?? []).length === 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-6 text-center text-slate-400">No terminals registered yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <h2 className="mb-2 text-lg font-semibold text-slate-800 dark:text-slate-200">Open Conflicts</h2>
      <div className="space-y-3">
        {conflicts.map((c) => (
          <div key={c.id} className="rounded-xl border border-amber-300 bg-amber-50 p-4 dark:border-amber-700 dark:bg-amber-950/30">
            <div className="mb-2 flex items-center justify-between">
              <span className="rounded-full bg-amber-200 px-2 py-0.5 text-xs font-semibold text-amber-900 dark:bg-amber-800 dark:text-amber-100">
                {c.conflict_type.replace(/_/g, ' ')}
              </span>
              <span className="text-xs text-slate-500 dark:text-slate-400">{timeAgo(c.created_at)}</span>
            </div>
            {typeof c.details?.message === 'string' && (
              <p className="mb-2 text-sm text-slate-700 dark:text-slate-300">{c.details.message as string}</p>
            )}
            <input
              placeholder="Resolution notes (optional)"
              value={notesById[c.id] ?? ''}
              onChange={(e) => setNotesById((prev) => ({ ...prev, [c.id]: e.target.value }))}
              className="mb-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
            <div className="flex gap-2">
              <button
                onClick={() => resolveConflict(c.id, 'retry')}
                disabled={resolvingId === c.id}
                className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
              >
                {resolvingId === c.id ? 'Working...' : 'Retry'}
              </button>
              <button
                onClick={() => resolveConflict(c.id, 'cancel')}
                disabled={resolvingId === c.id}
                className="rounded-lg bg-slate-200 px-3 py-1.5 text-sm font-semibold text-slate-800 hover:bg-slate-300 disabled:opacity-50 dark:bg-slate-700 dark:text-slate-100"
              >
                Cancel Sale
              </button>
            </div>
          </div>
        ))}
        {conflicts.length === 0 && (
          <p className="rounded-xl border border-slate-200 bg-white p-6 text-center text-slate-400 dark:border-slate-800 dark:bg-slate-800">
            No open conflicts.
          </p>
        )}
      </div>
    </div>
  )
}
