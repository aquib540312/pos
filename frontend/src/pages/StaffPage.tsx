import { useEffect, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'
import { useAuthStore } from '../store/auth'

interface Role {
  id: string
  name: string
  description: string | null
}

interface StaffUser {
  id: string
  full_name: string
  email: string
  phone: string | null
  is_active: boolean
  role_ids: string[]
  role_names: string[]
}

export default function StaffPage() {
  const currentUserId = useAuthStore((s) => s.user?.id)
  const [users, setUsers] = useState<StaffUser[]>([])
  const [roles, setRoles] = useState<Role[]>([])
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [editingRolesFor, setEditingRolesFor] = useState<StaffUser | null>(null)
  const [editingRoleIds, setEditingRoleIds] = useState<string[]>([])

  const [form, setForm] = useState({ full_name: '', email: '', phone: '', password: '', role_ids: [] as string[] })

  async function refresh() {
    const [usersRes, rolesRes] = await Promise.all([
      apiClient.get<StaffUser[]>('/auth/users'),
      apiClient.get<Role[]>('/rbac/roles'),
    ])
    setUsers(usersRes.data)
    setRoles(rolesRes.data)
  }

  useEffect(() => {
    refresh().catch((err) => setError(apiErrorMessage(err)))
  }, [])

  function toggleRoleInForm(roleId: string) {
    setForm((f) => ({
      ...f,
      role_ids: f.role_ids.includes(roleId) ? f.role_ids.filter((id) => id !== roleId) : [...f.role_ids, roleId],
    }))
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await apiClient.post('/auth/users', {
        full_name: form.full_name,
        email: form.email,
        phone: form.phone || null,
        password: form.password,
        role_ids: form.role_ids,
      })
      setForm({ full_name: '', email: '', phone: '', password: '', role_ids: [] })
      setShowForm(false)
      await refresh()
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function toggleActive(user: StaffUser) {
    setError(null)
    try {
      await apiClient.patch(`/auth/users/${user.id}/active`, { is_active: !user.is_active })
      await refresh()
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  function openRoleEditor(user: StaffUser) {
    setEditingRolesFor(user)
    setEditingRoleIds(user.role_ids)
  }

  async function saveRoles() {
    if (!editingRolesFor) return
    setError(null)
    setBusy(true)
    try {
      await apiClient.patch(`/auth/users/${editingRolesFor.id}/roles`, { role_ids: editingRoleIds })
      setEditingRolesFor(null)
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
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-50">Staff</h1>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
        >
          {showForm ? 'Cancel' : '+ New Staff'}
        </button>
      </div>

      {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

      {showForm && (
        <form
          onSubmit={handleCreate}
          className="mb-6 grid grid-cols-1 gap-3 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-800 md:grid-cols-2"
        >
          <input
            required
            placeholder="Full name"
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          />
          <input
            required
            type="email"
            placeholder="Email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          />
          <input
            placeholder="Phone (optional)"
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          />
          <input
            required
            type="password"
            minLength={8}
            placeholder="Password (min 8 characters)"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          />
          <div className="col-span-full">
            <p className="mb-2 text-sm font-medium text-slate-700 dark:text-slate-300">Roles</p>
            <div className="flex flex-wrap gap-3">
              {roles.map((r) => (
                <label key={r.id} className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                  <input
                    type="checkbox"
                    checked={form.role_ids.includes(r.id)}
                    onChange={() => toggleRoleInForm(r.id)}
                  />
                  {r.name}
                </label>
              ))}
            </div>
          </div>
          <button
            type="submit"
            disabled={busy}
            className="col-span-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {busy ? 'Creating...' : 'Create Staff Login'}
          </button>
        </form>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Roles</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">{u.full_name}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{u.email}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                  {u.role_names.length > 0 ? u.role_names.join(', ') : '-'}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      u.is_active
                        ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                        : 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400'
                    }`}
                  >
                    {u.is_active ? 'active' : 'inactive'}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={() => openRoleEditor(u)}
                    className="mr-3 text-sm font-medium text-indigo-600 hover:text-indigo-500"
                  >
                    Edit roles
                  </button>
                  <button
                    onClick={() => toggleActive(u)}
                    disabled={u.id === currentUserId && u.is_active}
                    className="text-sm font-medium text-red-600 hover:text-red-500 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {u.is_active ? 'Deactivate' : 'Reactivate'}
                  </button>
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                  No staff yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {editingRolesFor && (
        <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-sm rounded-xl bg-white p-5 shadow-xl dark:bg-slate-800">
            <h2 className="mb-1 text-lg font-semibold text-slate-900 dark:text-slate-50">Edit roles</h2>
            <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">{editingRolesFor.full_name}</p>
            <div className="mb-4 flex flex-wrap gap-3">
              {roles.map((r) => (
                <label key={r.id} className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                  <input
                    type="checkbox"
                    checked={editingRoleIds.includes(r.id)}
                    onChange={() =>
                      setEditingRoleIds((ids) => (ids.includes(r.id) ? ids.filter((id) => id !== r.id) : [...ids, r.id]))
                    }
                  />
                  {r.name}
                </label>
              ))}
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setEditingRolesFor(null)}
                className="rounded-lg px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
              >
                Cancel
              </button>
              <button
                onClick={saveRoles}
                disabled={busy}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
              >
                {busy ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
