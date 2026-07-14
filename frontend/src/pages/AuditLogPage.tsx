import { Fragment, useEffect, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'

interface AuditLogEntry {
  id: string
  user_id: string | null
  action: string
  entity_type: string
  entity_id: string | null
  details: string | null
  created_at: string
}

interface StaffUser {
  id: string
  full_name: string
  email: string
}

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString('en-IN')
}

function formatDetails(raw: string | null) {
  if (!raw) return null
  try {
    return JSON.stringify(JSON.parse(raw), null, 2)
  } catch {
    return raw
  }
}

export default function AuditLogPage() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([])
  const [userNames, setUserNames] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)
  const [actionFilter, setActionFilter] = useState('')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([apiClient.get<AuditLogEntry[]>('/audit/logs'), apiClient.get<StaffUser[]>('/auth/users')])
      .then(([logsRes, usersRes]) => {
        setLogs(logsRes.data)
        setUserNames(Object.fromEntries(usersRes.data.map((u) => [u.id, `${u.full_name} (${u.email})`])))
      })
      .catch((err) => setError(apiErrorMessage(err)))
  }, [])

  const actions = Array.from(new Set(logs.map((l) => l.action))).sort()
  const visibleLogs = actionFilter ? logs.filter((l) => l.action === actionFilter) : logs

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold text-slate-900 dark:text-slate-50">Audit Log</h1>

      {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

      <div className="mb-4">
        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
        >
          <option value="">All actions</option>
          {actions.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
            <tr>
              <th className="px-4 py-3">When</th>
              <th className="px-4 py-3">User</th>
              <th className="px-4 py-3">Action</th>
              <th className="px-4 py-3">Entity</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {visibleLogs.map((log) => (
              <Fragment key={log.id}>
                <tr className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                  <td className="px-4 py-3 whitespace-nowrap text-slate-600 dark:text-slate-300">
                    {formatDateTime(log.created_at)}
                  </td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                    {log.user_id ? (userNames[log.user_id] ?? log.user_id) : 'system'}
                  </td>
                  <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">{log.action}</td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                    {log.entity_type}
                    {log.entity_id ? ` #${log.entity_id.slice(0, 8)}` : ''}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {log.details && (
                      <button
                        onClick={() => setExpandedId(expandedId === log.id ? null : log.id)}
                        className="text-sm font-medium text-indigo-600 hover:text-indigo-500"
                      >
                        {expandedId === log.id ? 'Hide' : 'Details'}
                      </button>
                    )}
                  </td>
                </tr>
                {expandedId === log.id && log.details && (
                  <tr className="border-b border-slate-100 bg-slate-50 dark:border-slate-700 dark:bg-slate-900">
                    <td colSpan={5} className="px-4 py-3">
                      <pre className="whitespace-pre-wrap text-xs text-slate-600 dark:text-slate-300">
                        {formatDetails(log.details)}
                      </pre>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
            {visibleLogs.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                  No audit log entries.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
