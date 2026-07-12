import { useEffect, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'

interface Branch {
  id: string
  name: string
}

interface ShiftSummary {
  id: string
  branch_id: string
  user_id: string
  opened_at: string
  closed_at: string | null
  opening_cash: number
  expected_closing_cash: number | null
  counted_closing_cash: number | null
  cash_variance: number | null
  status: 'open' | 'closed'
  running_cash_sales: number
}

interface ShiftHistoryRow {
  id: string
  opened_at: string
  closed_at: string | null
  opening_cash: number
  expected_closing_cash: number | null
  counted_closing_cash: number | null
  cash_variance: number | null
  status: 'open' | 'closed'
}

function formatDateTime(iso: string | null) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('en-IN')
}

export default function ShiftPage() {
  const [branch, setBranch] = useState<Branch | null>(null)
  const [current, setCurrent] = useState<ShiftSummary | null>(null)
  const [history, setHistory] = useState<ShiftHistoryRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [openingCash, setOpeningCash] = useState('')
  const [countedCash, setCountedCash] = useState('')
  const [busy, setBusy] = useState(false)

  async function refresh(branchId: string) {
    const [currentRes, historyRes] = await Promise.all([
      apiClient.get<ShiftSummary | null>('/billing/shifts/current', { params: { branch_id: branchId } }),
      apiClient.get<ShiftHistoryRow[]>('/billing/shifts', { params: { branch_id: branchId, limit: 20 } }),
    ])
    setCurrent(currentRes.data)
    setHistory(historyRes.data)
  }

  useEffect(() => {
    apiClient.get<Branch[]>('/org/branches').then(async (res) => {
      const b = res.data[0] ?? null
      setBranch(b)
      if (b) {
        try {
          await refresh(b.id)
        } catch (err) {
          setError(apiErrorMessage(err))
        }
      }
      setLoading(false)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleOpenShift(e: React.FormEvent) {
    e.preventDefault()
    if (!branch) return
    setError(null)
    setBusy(true)
    try {
      await apiClient.post('/billing/shifts/open', { branch_id: branch.id, opening_cash: Number(openingCash) })
      setOpeningCash('')
      await refresh(branch.id)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleCloseShift(e: React.FormEvent) {
    e.preventDefault()
    if (!branch || !current) return
    setError(null)
    setBusy(true)
    try {
      await apiClient.post(`/billing/shifts/${current.id}/close`, { counted_closing_cash: Number(countedCash) })
      setCountedCash('')
      await refresh(branch.id)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  if (loading) {
    return <p className="text-sm text-slate-500 dark:text-slate-400">Loading...</p>
  }

  if (!branch) {
    return <p className="text-sm text-slate-500 dark:text-slate-400">No branch found.</p>
  }

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold text-slate-900 dark:text-slate-50">Shift &amp; Cash Drawer</h1>

      {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

      {!current && (
        <form
          onSubmit={handleOpenShift}
          className="mb-6 max-w-sm rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-800"
        >
          <h2 className="mb-3 text-lg font-semibold text-slate-900 dark:text-slate-50">Open Shift</h2>
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Opening cash</label>
          <input
            required
            type="number"
            min="0"
            step="0.01"
            value={openingCash}
            onChange={(e) => setOpeningCash(e.target.value)}
            className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          />
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {busy ? 'Opening...' : 'Open Shift'}
          </button>
        </form>
      )}

      {current && (
        <div className="mb-6 max-w-sm rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-800">
          <h2 className="mb-3 text-lg font-semibold text-slate-900 dark:text-slate-50">Shift Open</h2>
          <dl className="mb-4 space-y-1 text-sm text-slate-600 dark:text-slate-300">
            <div className="flex justify-between">
              <dt>Opened at</dt>
              <dd>{formatDateTime(current.opened_at)}</dd>
            </div>
            <div className="flex justify-between">
              <dt>Opening cash</dt>
              <dd>₹{current.opening_cash.toFixed(2)}</dd>
            </div>
            <div className="flex justify-between">
              <dt>Cash sales so far</dt>
              <dd>₹{current.running_cash_sales.toFixed(2)}</dd>
            </div>
            <div className="flex justify-between font-medium text-slate-900 dark:text-slate-100">
              <dt>Expected cash in drawer</dt>
              <dd>₹{(current.opening_cash + current.running_cash_sales).toFixed(2)}</dd>
            </div>
          </dl>
          <form onSubmit={handleCloseShift}>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
              Counted closing cash
            </label>
            <input
              required
              type="number"
              min="0"
              step="0.01"
              value={countedCash}
              onChange={(e) => setCountedCash(e.target.value)}
              className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              {busy ? 'Closing...' : 'Close Shift'}
            </button>
          </form>
        </div>
      )}

      <h2 className="mb-3 text-lg font-semibold text-slate-900 dark:text-slate-50">Recent Shifts</h2>
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
            <tr>
              <th className="px-4 py-3">Opened</th>
              <th className="px-4 py-3">Closed</th>
              <th className="px-4 py-3">Opening Cash</th>
              <th className="px-4 py-3">Expected</th>
              <th className="px-4 py-3">Counted</th>
              <th className="px-4 py-3">Variance</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {history.map((s) => (
              <tr key={s.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{formatDateTime(s.opened_at)}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{formatDateTime(s.closed_at)}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">₹{s.opening_cash.toFixed(2)}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                  {s.expected_closing_cash != null ? `₹${s.expected_closing_cash.toFixed(2)}` : '-'}
                </td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                  {s.counted_closing_cash != null ? `₹${s.counted_closing_cash.toFixed(2)}` : '-'}
                </td>
                <td
                  className={`px-4 py-3 font-medium ${
                    s.cash_variance == null
                      ? 'text-slate-400'
                      : s.cash_variance === 0
                        ? 'text-slate-600 dark:text-slate-300'
                        : s.cash_variance < 0
                          ? 'text-red-600 dark:text-red-400'
                          : 'text-emerald-600 dark:text-emerald-400'
                  }`}
                >
                  {s.cash_variance != null ? `₹${s.cash_variance.toFixed(2)}` : '-'}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      s.status === 'open'
                        ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                        : 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
                    }`}
                  >
                    {s.status}
                  </span>
                </td>
              </tr>
            ))}
            {history.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-slate-400">
                  No shifts yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
