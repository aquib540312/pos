import { useEffect, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'
import type { WasteEntry, Product } from '../types'

const WASTE_REASONS = [
  { value: 'spoilage', label: 'Spoilage' },
  { value: 'expired', label: 'Expired' },
  { value: 'damaged', label: 'Damaged' },
  { value: 'cutting_loss', label: 'Cutting Loss' },
  { value: 'bone_loss', label: 'Bone Loss' },
  { value: 'processing_loss', label: 'Processing Loss' },
  { value: 'other', label: 'Other' },
]

export default function WastePage() {
  const [entries, setEntries] = useState<WasteEntry[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState({ product_id: '', quantity: '', unit_cost: '', reason: 'spoilage', notes: '' })

  async function load() {
    const res = await apiClient.get<WasteEntry[]>('/waste')
    setEntries(res.data)
  }

  useEffect(() => {
    load()
    apiClient.get<Product[]>('/catalog/products').then((r) => setProducts(r.data))
  }, [])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await apiClient.post('/waste', {
        product_id: form.product_id,
        quantity: Number(form.quantity),
        unit_cost: Number(form.unit_cost),
        reason: form.reason,
        notes: form.notes || null,
      })
      setForm({ product_id: '', quantity: '', unit_cost: '', reason: 'spoilage', notes: '' })
      setShowForm(false)
      load()
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-50">Waste Tracking</h1>
        <button onClick={() => setShowForm((v) => !v)} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500">
          {showForm ? 'Cancel' : '+ Record Waste'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="mb-6 grid grid-cols-2 gap-3 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-800 md:grid-cols-4">
          <select required value={form.product_id} onChange={(e) => setForm({ ...form, product_id: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100">
            <option value="">Select product...</option>
            {products.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.sku})</option>)}
          </select>
          <input required type="number" step="0.001" min="0.001" placeholder="Weight (KG)" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <input required type="number" step="0.01" min="0" placeholder="Cost per KG (SAR)" value={form.unit_cost} onChange={(e) => setForm({ ...form, unit_cost: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <select value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100">
            {WASTE_REASONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
          <input placeholder="Notes" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="col-span-2 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          {error && <p className="col-span-full text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button type="submit" className="col-span-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500">Record Waste</button>
        </form>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
            <tr>
              <th className="px-4 py-3">Date</th>
              <th className="px-4 py-3">Product</th>
              <th className="px-4 py-3">Weight (KG)</th>
              <th className="px-4 py-3">Cost/KG</th>
              <th className="px-4 py-3">Total Loss</th>
              <th className="px-4 py-3">Reason</th>
              <th className="px-4 py-3">Notes</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{new Date(e.created_at).toLocaleDateString()}</td>
                <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">{e.product_name}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{e.quantity.toFixed(3)}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">SAR {e.unit_cost.toFixed(2)}</td>
                <td className="px-4 py-3 font-medium text-red-600">SAR {e.total_cost.toFixed(2)}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{e.reason.replace('_', ' ')}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{e.notes ?? '—'}</td>
              </tr>
            ))}
            {entries.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-6 text-center text-slate-400">No waste entries recorded.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
