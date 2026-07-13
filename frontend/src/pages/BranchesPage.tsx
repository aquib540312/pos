import { useEffect, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'

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
  business_type: string
  state_code: string
  warehouses: Warehouse[]
}

const BUSINESS_TYPES = ['grocery', 'supermarket', 'medical', 'electronics', 'garment', 'restaurant']

export default function BranchesPage() {
  const [branches, setBranches] = useState<Branch[]>([])
  const [error, setError] = useState<string | null>(null)
  const [showBranchForm, setShowBranchForm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [branchForm, setBranchForm] = useState({
    code: '',
    name: '',
    business_type: 'grocery',
    state_code: '',
    gstin: '',
    address: '',
  })
  const [warehouseFormFor, setWarehouseFormFor] = useState<string | null>(null)
  const [warehouseForm, setWarehouseForm] = useState({ code: '', name: '', is_default: false })

  async function refresh() {
    const res = await apiClient.get<Branch[]>('/org/branches')
    setBranches(res.data)
  }

  useEffect(() => {
    refresh().catch((err) => setError(apiErrorMessage(err)))
  }, [])

  async function handleCreateBranch(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await apiClient.post('/org/branches', {
        code: branchForm.code,
        name: branchForm.name,
        business_type: branchForm.business_type,
        state_code: branchForm.state_code,
        gstin: branchForm.gstin || null,
        address: branchForm.address || null,
      })
      setBranchForm({ code: '', name: '', business_type: 'grocery', state_code: '', gstin: '', address: '' })
      setShowBranchForm(false)
      await refresh()
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleCreateWarehouse(e: React.FormEvent) {
    e.preventDefault()
    if (!warehouseFormFor) return
    setError(null)
    setBusy(true)
    try {
      await apiClient.post(`/org/branches/${warehouseFormFor}/warehouses`, warehouseForm)
      setWarehouseForm({ code: '', name: '', is_default: false })
      setWarehouseFormFor(null)
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
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-50">Branches &amp; Warehouses</h1>
        <button
          onClick={() => setShowBranchForm((v) => !v)}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
        >
          {showBranchForm ? 'Cancel' : '+ New Branch'}
        </button>
      </div>

      {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

      {showBranchForm && (
        <form
          onSubmit={handleCreateBranch}
          className="mb-6 grid grid-cols-2 gap-3 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-800 md:grid-cols-3"
        >
          <input
            required
            placeholder="Code (e.g. NORTH)"
            value={branchForm.code}
            onChange={(e) => setBranchForm({ ...branchForm, code: e.target.value })}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          />
          <input
            required
            placeholder="Name"
            value={branchForm.name}
            onChange={(e) => setBranchForm({ ...branchForm, name: e.target.value })}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          />
          <select
            value={branchForm.business_type}
            onChange={(e) => setBranchForm({ ...branchForm, business_type: e.target.value })}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          >
            {BUSINESS_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <input
            required
            placeholder="State code (e.g. 27)"
            maxLength={2}
            value={branchForm.state_code}
            onChange={(e) => setBranchForm({ ...branchForm, state_code: e.target.value })}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          />
          <input
            placeholder="GSTIN (optional)"
            value={branchForm.gstin}
            onChange={(e) => setBranchForm({ ...branchForm, gstin: e.target.value })}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          />
          <input
            placeholder="Address (optional)"
            value={branchForm.address}
            onChange={(e) => setBranchForm({ ...branchForm, address: e.target.value })}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          />
          <button
            type="submit"
            disabled={busy}
            className="col-span-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {busy ? 'Saving...' : 'Save branch'}
          </button>
        </form>
      )}

      <div className="space-y-4">
        {branches.map((b) => (
          <div key={b.id} className="rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3 dark:border-slate-700">
              <div>
                <p className="font-semibold text-slate-900 dark:text-slate-100">
                  {b.name} <span className="font-normal text-slate-400">({b.code})</span>
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {b.business_type} · state {b.state_code}
                </p>
              </div>
              <button
                onClick={() => setWarehouseFormFor(warehouseFormFor === b.id ? null : b.id)}
                className="text-sm font-medium text-indigo-600 hover:text-indigo-500"
              >
                {warehouseFormFor === b.id ? 'Cancel' : '+ Add warehouse'}
              </button>
            </div>

            {warehouseFormFor === b.id && (
              <form onSubmit={handleCreateWarehouse} className="flex flex-wrap items-end gap-3 border-b border-slate-200 px-4 py-3 dark:border-slate-700">
                <input
                  required
                  placeholder="Code (e.g. WH2)"
                  value={warehouseForm.code}
                  onChange={(e) => setWarehouseForm({ ...warehouseForm, code: e.target.value })}
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                />
                <input
                  required
                  placeholder="Name"
                  value={warehouseForm.name}
                  onChange={(e) => setWarehouseForm({ ...warehouseForm, name: e.target.value })}
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                />
                <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                  <input
                    type="checkbox"
                    checked={warehouseForm.is_default}
                    onChange={(e) => setWarehouseForm({ ...warehouseForm, is_default: e.target.checked })}
                  />
                  Default warehouse
                </label>
                <button
                  type="submit"
                  disabled={busy}
                  className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
                >
                  {busy ? 'Saving...' : 'Save warehouse'}
                </button>
              </form>
            )}

            <table className="w-full text-left text-sm">
              <thead className="text-slate-500 dark:text-slate-400">
                <tr>
                  <th className="px-4 py-2">Code</th>
                  <th className="px-4 py-2">Name</th>
                  <th className="px-4 py-2">Default</th>
                </tr>
              </thead>
              <tbody>
                {b.warehouses.map((w) => (
                  <tr key={w.id} className="border-t border-slate-100 dark:border-slate-700">
                    <td className="px-4 py-2 text-slate-600 dark:text-slate-300">{w.code}</td>
                    <td className="px-4 py-2 font-medium text-slate-900 dark:text-slate-100">{w.name}</td>
                    <td className="px-4 py-2 text-slate-600 dark:text-slate-300">{w.is_default ? 'Yes' : ''}</td>
                  </tr>
                ))}
                {b.warehouses.length === 0 && (
                  <tr>
                    <td colSpan={3} className="px-4 py-4 text-center text-slate-400">
                      No warehouses yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        ))}
        {branches.length === 0 && <p className="text-sm text-slate-400">No branches yet.</p>}
      </div>
    </div>
  )
}
