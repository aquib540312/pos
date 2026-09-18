import { useEffect, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'
import type { CuttingOrder, Product } from '../types'

interface CuttingItemForm {
  product_id: string
  output_weight: string
  waste_weight: string
}

export default function CuttingPage() {
  const [orders, setOrders] = useState<CuttingOrder[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState({
    source_product_id: '',
    input_weight: '',
    butcher_name: '',
    notes: '',
    items: [{ product_id: '', output_weight: '', waste_weight: '0' }] as CuttingItemForm[],
  })

  async function load() {
    const res = await apiClient.get<CuttingOrder[]>('/cutting/orders')
    setOrders(res.data)
  }

  useEffect(() => {
    load()
    apiClient.get<Product[]>('/catalog/products').then((r) => setProducts(r.data))
  }, [])

  function addItem() {
    setForm({ ...form, items: [...form.items, { product_id: '', output_weight: '', waste_weight: '0' }] })
  }

  function updateItem(index: number, patch: Partial<CuttingItemForm>) {
    setForm({ ...form, items: form.items.map((item, i) => i === index ? { ...item, ...patch } : item) })
  }

  function removeItem(index: number) {
    setForm({ ...form, items: form.items.filter((_, i) => i !== index) })
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await apiClient.post('/cutting/orders', {
        source_product_id: form.source_product_id,
        input_weight: Number(form.input_weight),
        butcher_name: form.butcher_name || null,
        notes: form.notes || null,
        items: form.items.map((item) => ({
          product_id: item.product_id,
          output_weight: Number(item.output_weight),
          waste_weight: Number(item.waste_weight || 0),
        })),
      })
      setForm({ source_product_id: '', input_weight: '', butcher_name: '', notes: '', items: [{ product_id: '', output_weight: '', waste_weight: '0' }] })
      setShowForm(false)
      load()
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  async function completeOrder(id: string) {
    try {
      await apiClient.patch(`/cutting/orders/${id}/complete`)
      load()
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-50">Cutting / Butchery</h1>
        <button onClick={() => setShowForm((v) => !v)} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500">
          {showForm ? 'Cancel' : '+ New Cutting Order'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="mb-6 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-800">
          <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            <select required value={form.source_product_id} onChange={(e) => setForm({ ...form, source_product_id: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100">
              <option value="">Source product (carcass/whole)...</option>
              {products.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.sku})</option>)}
            </select>
            <input required type="number" step="0.001" min="0.001" placeholder="Input weight (KG)" value={form.input_weight} onChange={(e) => setForm({ ...form, input_weight: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
            <input placeholder="Butcher name" value={form.butcher_name} onChange={(e) => setForm({ ...form, butcher_name: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
            <input placeholder="Notes" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          </div>

          <h3 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-300">Output cuts</h3>
          {form.items.map((item, i) => (
            <div key={i} className="mb-2 flex gap-2">
              <select required value={item.product_id} onChange={(e) => updateItem(i, { product_id: e.target.value })} className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100">
                <option value="">Cut product...</option>
                {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
              <input required type="number" step="0.001" min="0.001" placeholder="Weight (KG)" value={item.output_weight} onChange={(e) => updateItem(i, { output_weight: e.target.value })} className="w-28 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
              <input type="number" step="0.001" min="0" placeholder="Waste (KG)" value={item.waste_weight} onChange={(e) => updateItem(i, { waste_weight: e.target.value })} className="w-28 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
              {form.items.length > 1 && <button type="button" onClick={() => removeItem(i)} className="text-red-500">✕</button>}
            </div>
          ))}
          <button type="button" onClick={addItem} className="mb-4 text-sm font-medium text-indigo-600 hover:text-indigo-500">+ Add cut</button>

          {error && <p className="mb-3 text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button type="submit" className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500">Create Order</button>
        </form>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
            <tr>
              <th className="px-4 py-3">Date</th>
              <th className="px-4 py-3">Source</th>
              <th className="px-4 py-3">Input (KG)</th>
              <th className="px-4 py-3">Butcher</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Cuts</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((o) => (
              <tr key={o.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{new Date(o.created_at).toLocaleDateString()}</td>
                <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">{o.source_product_name}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{o.input_weight.toFixed(3)}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{o.butcher_name ?? '—'}</td>
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${o.status === 'completed' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300' : 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300'}`}>
                    {o.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{o.items.length} cuts</td>
                <td className="px-4 py-3">
                  {o.status === 'pending' && (
                    <button onClick={() => completeOrder(o.id)} className="rounded-lg bg-emerald-600 px-3 py-1 text-xs font-semibold text-white hover:bg-emerald-500">
                      Complete
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {orders.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-6 text-center text-slate-400">No cutting orders.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
