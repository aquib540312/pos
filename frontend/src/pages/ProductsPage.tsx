import { useEffect, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'
import type { HSN, Product, UOM } from '../types'

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([])
  const [uoms, setUoms] = useState<UOM[]>([])
  const [hsnCodes, setHsnCodes] = useState<HSN[]>([])
  const [search, setSearch] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)

  const [form, setForm] = useState({
    sku: '',
    barcode: '',
    name: '',
    uom_id: '',
    hsn_code_id: '',
    mrp: '',
    sale_price: '',
    purchase_price: '',
  })

  async function loadProducts(q?: string) {
    const res = await apiClient.get<Product[]>('/catalog/products', { params: q ? { search: q } : {} })
    setProducts(res.data)
  }

  useEffect(() => {
    loadProducts()
    apiClient.get<UOM[]>('/catalog/uom').then((r) => setUoms(r.data))
    apiClient.get<HSN[]>('/catalog/hsn').then((r) => setHsnCodes(r.data))
  }, [])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await apiClient.post('/catalog/products', {
        sku: form.sku,
        barcode: form.barcode || null,
        name: form.name,
        uom_id: form.uom_id,
        hsn_code_id: form.hsn_code_id || null,
        mrp: Number(form.mrp),
        sale_price: Number(form.sale_price),
        purchase_price: Number(form.purchase_price || 0),
      })
      setForm({ sku: '', barcode: '', name: '', uom_id: '', hsn_code_id: '', mrp: '', sale_price: '', purchase_price: '' })
      setShowForm(false)
      loadProducts(search)
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-50">Products</h1>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
        >
          {showForm ? 'Cancel' : '+ New Product'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="mb-6 grid grid-cols-2 gap-3 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-800 md:grid-cols-4">
          <input required placeholder="SKU" value={form.sku} onChange={(e) => setForm({ ...form, sku: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <input placeholder="Barcode" value={form.barcode} onChange={(e) => setForm({ ...form, barcode: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <input required placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="col-span-2 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <select required value={form.uom_id} onChange={(e) => setForm({ ...form, uom_id: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100">
            <option value="">Unit...</option>
            {uoms.map((u) => (
              <option key={u.id} value={u.id}>{u.code} - {u.name}</option>
            ))}
          </select>
          <select value={form.hsn_code_id} onChange={(e) => setForm({ ...form, hsn_code_id: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100">
            <option value="">HSN/GST rate...</option>
            {hsnCodes.map((h) => (
              <option key={h.id} value={h.id}>{h.code} ({h.current_rate_percent ?? '?'}%)</option>
            ))}
          </select>
          <input required type="number" step="0.01" placeholder="MRP" value={form.mrp} onChange={(e) => setForm({ ...form, mrp: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <input required type="number" step="0.01" placeholder="Sale price" value={form.sale_price} onChange={(e) => setForm({ ...form, sale_price: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <input type="number" step="0.01" placeholder="Purchase price" value={form.purchase_price} onChange={(e) => setForm({ ...form, purchase_price: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          {error && <p className="col-span-full text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button type="submit" className="col-span-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500">
            Save product
          </button>
        </form>
      )}

      <div className="mb-4">
        <input
          placeholder="Search by name, SKU, or barcode..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            loadProducts(e.target.value)
          }}
          className="w-full max-w-sm rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
        />
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
            <tr>
              <th className="px-4 py-3">SKU</th>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">MRP</th>
              <th className="px-4 py-3">Sale Price</th>
            </tr>
          </thead>
          <tbody>
            {products.map((p) => (
              <tr key={p.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{p.sku}</td>
                <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">{p.name}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">₹{p.mrp.toFixed(2)}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">₹{p.sale_price.toFixed(2)}</td>
              </tr>
            ))}
            {products.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-slate-400">No products found.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
