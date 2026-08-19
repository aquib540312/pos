import { useEffect, useMemo, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'

interface Permission {
  code: string
  description: string | null
}

interface Role {
  id: string
  name: string
  description: string | null
  permission_codes: string[]
}

// Human-readable labels for the permission codes the backend emits (mirrors
// app/core/permissions.py Perm). Codes not in this map fall back to the raw
// string so new permissions never render as blank.
const PERMISSION_LABELS: Record<string, string> = {
  'users:manage': 'Manage staff users',
  'roles:manage': 'Manage roles & permissions',
  'catalog:view': 'View products/catalog',
  'catalog:manage': 'Add/edit products, offers',
  'inventory:view': 'View stock',
  'inventory:adjust': 'Adjust stock levels',
  'party:manage': 'Manage customers/suppliers',
  'purchase:create': 'Create purchases (POs)',
  'purchase:receive': 'Receive goods (GRN)',
  'sales:create': 'Make sales (POS)',
  'sales:return': 'Process sales returns',
  'quotation:create': 'Create quotations',
  'shift:manage': 'Open/close cash shifts',
  'reports:view': 'View reports',
  'org:manage': 'Org & branch settings, billing',
  'sync:manage': 'Sync/offline dashboard',
}

function permissionLabel(code: string): string {
  return PERMISSION_LABELS[code] ?? code
}

export default function RolesPage() {
  const [roles, setRoles] = useState<Role[]>([])
  const [permissions, setPermissions] = useState<Permission[]>([])
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', description: '', permission_codes: [] as string[] })

  // Group permissions by their resource ("catalog:view" -> "catalog") so the
  // create form reads like a capability sheet, not a flat code list.
  const groupedPermissions = useMemo(() => {
    const groups: Record<string, Permission[]> = {}
    for (const p of permissions) {
      const resource = p.code.split(':')[0]
      ;(groups[resource] ??= []).push(p)
    }
    return groups
  }, [permissions])

  async function refresh() {
    const [rolesRes, permsRes] = await Promise.all([
      apiClient.get<Role[]>('/rbac/roles'),
      apiClient.get<Permission[]>('/rbac/permissions'),
    ])
    setRoles(rolesRes.data)
    setPermissions(permsRes.data)
  }

  useEffect(() => {
    refresh().catch((err) => setError(apiErrorMessage(err)))
  }, [])

  function togglePermission(code: string) {
    setForm((f) => ({
      ...f,
      permission_codes: f.permission_codes.includes(code)
        ? f.permission_codes.filter((c) => c !== code)
        : [...f.permission_codes, code],
    }))
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setMessage(null)
    if (!form.name.trim()) {
      setError('Role name is required.')
      return
    }
    setBusy(true)
    try {
      await apiClient.post('/rbac/roles', {
        name: form.name.trim(),
        description: form.description.trim() || null,
        permission_codes: form.permission_codes,
      })
      setForm({ name: '', description: '', permission_codes: [] })
      setShowForm(false)
      setMessage(`Role "${form.name.trim()}" created. Assign it to users from the Staff page.`)
      await refresh()
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-50">Roles & Permissions</h1>
        <button
          onClick={() => {
            setShowForm((v) => !v)
            setMessage(null)
          }}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
        >
          {showForm ? 'Cancel' : '+ New Role'}
        </button>
      </div>

      {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}
      {message && <p className="mb-4 text-sm text-emerald-600 dark:text-emerald-400">{message}</p>}

      {showForm && (
        <form
          onSubmit={handleCreate}
          className="mb-6 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-800"
        >
          <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            <input
              required
              placeholder="Role name (e.g. Floor Supervisor)"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
            <input
              placeholder="Description (optional)"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
          </div>

          <p className="mb-2 text-sm font-medium text-slate-700 dark:text-slate-300">Permissions</p>
          {Object.keys(groupedPermissions).length === 0 ? (
            <p className="mb-4 text-sm text-slate-400">Loading permissions...</p>
          ) : (
            <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Object.entries(groupedPermissions).map(([resource, perms]) => (
                <div key={resource} className="rounded-lg border border-slate-200 p-3 dark:border-slate-700">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                    {resource}
                  </p>
                  <div className="space-y-2">
                    {perms.map((p) => (
                      <label key={p.code} className="flex cursor-pointer items-start gap-2 text-sm text-slate-600 dark:text-slate-300">
                        <input
                          type="checkbox"
                          checked={form.permission_codes.includes(p.code)}
                          onChange={() => togglePermission(p.code)}
                          className="mt-0.5"
                        />
                        <span>
                          <span className="block font-medium">{permissionLabel(p.code)}</span>
                          {p.description && <span className="block text-xs text-slate-400">{p.description}</span>}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="flex items-center justify-between">
            <p className="text-xs text-slate-400">{form.permission_codes.length} permission(s) selected</p>
            <button
              type="submit"
              disabled={busy}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              {busy ? 'Creating...' : 'Create Role'}
            </button>
          </div>
        </form>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
            <tr>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Permissions</th>
            </tr>
          </thead>
          <tbody>
            {roles.map((r) => (
              <tr key={r.id} className="border-b border-slate-100 align-top last:border-0 dark:border-slate-700">
                <td className="px-4 py-3">
                  <p className="font-medium text-slate-900 dark:text-slate-100">{r.name}</p>
                  {r.description && <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{r.description}</p>}
                </td>
                <td className="px-4 py-3">
                  {r.permission_codes.length > 0 ? (
                    <div className="flex flex-wrap gap-1.5">
                      {r.permission_codes.map((code) => (
                        <span
                          key={code}
                          className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300"
                        >
                          {permissionLabel(code)}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="text-slate-400">No permissions</span>
                  )}
                </td>
              </tr>
            ))}
            {roles.length === 0 && (
              <tr>
                <td colSpan={2} className="px-4 py-6 text-center text-slate-400">
                  No roles yet. Create your first one above.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}