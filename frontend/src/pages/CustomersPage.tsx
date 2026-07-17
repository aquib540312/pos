import { useEffect, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'
import type { Customer } from '../types'

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([])
  const [search, setSearch] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState({
    name: '',
    phone: '',
    gstin: '',
    stateCode: '',
    isCredit: false,
    creditLimit: '',
  })

  async function load(q?: string) {
    const res = await apiClient.get<Customer[]>('/party/customers', { params: q ? { search: q } : {} })
    setCustomers(res.data)
  }

  useEffect(() => {
    load()
  }, [])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await apiClient.post('/party/customers', {
        name: form.name,
        phone: form.phone || null,
        gstin: form.gstin || null,
        state_code: form.stateCode || null,
        is_credit_customer: form.isCredit,
        credit_limit: form.isCredit ? Number(form.creditLimit || 0) : 0,
      })
      setForm({ name: '', phone: '', gstin: '', stateCode: '', isCredit: false, creditLimit: '' })
      setShowForm(false)
      load(search)
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-50">Customers</h1>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
        >
          {showForm ? 'Cancel' : '+ New Customer'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="mb-6 grid grid-cols-2 gap-3 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-800 md:grid-cols-4">
          <input required placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <input placeholder="Phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <input placeholder="GSTIN (business customers only)" value={form.gstin} onChange={(e) => setForm({ ...form, gstin: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <input placeholder="State code (e.g. 27)" value={form.stateCode} onChange={(e) => setForm({ ...form, stateCode: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
            <input type="checkbox" checked={form.isCredit} onChange={(e) => setForm({ ...form, isCredit: e.target.checked })} />
            Credit customer
          </label>
          {form.isCredit && (
            <input type="number" step="0.01" placeholder="Credit limit" value={form.creditLimit} onChange={(e) => setForm({ ...form, creditLimit: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          )}
          {error && <p className="col-span-full text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button type="submit" className="col-span-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500">
            Save customer
          </button>
        </form>
      )}

      <div className="mb-4">
        <input
          placeholder="Search by name or phone..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            load(e.target.value)
          }}
          className="w-full max-w-sm rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
        />
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Phone</th>
              <th className="px-4 py-3">GSTIN</th>
              <th className="px-4 py-3">Credit Limit</th>
              <th className="px-4 py-3">Credit Balance</th>
              <th className="px-4 py-3">Loyalty Points</th>
            </tr>
          </thead>
          <tbody>
            {customers.map((c) => (
              <tr key={c.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">{c.name}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{c.phone ?? '—'}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{c.gstin ?? '—'}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{c.is_credit_customer ? `₹${c.credit_limit.toFixed(2)}` : '—'}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{c.is_credit_customer ? `₹${c.credit_balance.toFixed(2)}` : '—'}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{c.loyalty_points_balance}</td>
              </tr>
            ))}
            {customers.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-400">No customers found.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
