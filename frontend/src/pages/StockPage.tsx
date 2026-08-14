import { useEffect, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'
import type { Product, StockItem, StockLedgerRow } from '../types'

export default function StockPage() {
  const [stock, setStock] = useState<StockItem[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [ledger, setLedger] = useState<StockLedgerRow[]>([])
  const [ledgerProduct, setLedgerProduct] = useState<string | null>(null)
  const [form, setForm] = useState({ productId: '', quantity: '0', reason: '' })

  async function load() {
    try {
      const [stockRes, productRes] = await Promise.all([
        apiClient.get<StockItem[]>('/inventory/stock'),
        apiClient.get<Product[]>('/catalog/products'),
      ])
      setStock(stockRes.data)
      setProducts(productRes.data)
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function handleAdjust(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)
    setError(null)
    try {
      await apiClient.post('/inventory/adjust', {
        product_id: form.productId,
        quantity_delta: Number(form.quantity),
        reason: form.reason,
      })
      setForm({ productId: '', quantity: '0', reason: '' })
      setMessage('Stock adjusted.')
      await load()
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  async function viewLedger(productId: string) {
    setLedgerProduct(productId)
    setError(null)
    try {
      const res = await apiClient.get<StockLedgerRow[]>('/reports/stock-ledger', { params: { product_id: productId } })
      setLedger(res.data)
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  const productName = (id: string) => products.find((p) => p.id === id)?.name ?? id.slice(0, 8)

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-50">Stock & Adjustments</h1>
      </div>

      {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}
      {message && <p className="mb-4 text-sm text-emerald-600 dark:text-emerald-400">{message}</p>}

      <form onSubmit={handleAdjust} className="mb-6 grid grid-cols-1 gap-3 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-800 md:grid-cols-4">
        <select
          required
          value={form.productId}
          onChange={(e) => setForm({ ...form, productId: e.target.value })}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
        >
          <option value="">Select product...</option>
          {products.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} ({p.sku})
            </option>
          ))}
        </select>
        <input
          type="number"
          step="0.001"
          required
          placeholder="Quantity delta (+ add / - remove)"
          value={form.quantity}
          onChange={(e) => setForm({ ...form, quantity: e.target.value })}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
        />
        <input
          required
          placeholder="Reason (e.g. stocktake, damage)"
          value={form.reason}
          onChange={(e) => setForm({ ...form, reason: e.target.value })}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
        />
        <button type="submit" className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500">
          Adjust Stock
        </button>
      </form>

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
            <tr>
              <th className="px-4 py-3">Product</th>
              <th className="px-4 py-3">Warehouse</th>
              <th className="px-4 py-3">Batch</th>
              <th className="px-4 py-3">On Hand</th>
              <th className="px-4 py-3">Movement History</th>
            </tr>
          </thead>
          <tbody>
            {stock.map((s) => (
              <tr key={`${s.warehouse_id}-${s.product_id}-${s.batch_id ?? 'none'}`} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">{productName(s.product_id)}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{s.warehouse_id.slice(0, 8)}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{s.batch_id ? s.batch_id.slice(0, 8) : '—'}</td>
                <td className="px-4 py-3 text-slate-900 dark:text-slate-100">{s.quantity_on_hand}</td>
                <td className="px-4 py-3">
                  <button onClick={() => viewLedger(s.product_id)} className="text-indigo-600 hover:underline dark:text-indigo-400">
                    View ledger
                  </button>
                </td>
              </tr>
            ))}
            {stock.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                  No stock items yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {ledgerProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => setLedgerProduct(null)}>
          <div className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white p-6 dark:bg-slate-800" onClick={(e) => e.stopPropagation()}>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-50">
                Stock Ledger: {productName(ledgerProduct)}
              </h2>
              <button onClick={() => setLedgerProduct(null)} className="text-slate-500 hover:text-slate-700 dark:text-slate-400">✕</button>
            </div>
            <table className="w-full text-left text-sm">
              <thead className="border-b text-slate-500">
                <tr>
                  <th className="px-2 py-2">Date</th>
                  <th className="px-2 py-2">Movement</th>
                  <th className="px-2 py-2">Qty Δ</th>
                  <th className="px-2 py-2">Reference</th>
                  <th className="px-2 py-2">Notes</th>
                </tr>
              </thead>
              <tbody>
                {ledger.map((row) => (
                  <tr key={row.id} className="border-b border-slate-100 last:border-0">
                    <td className="px-2 py-2 text-slate-600 dark:text-slate-300">{new Date(row.created_at).toLocaleString()}</td>
                    <td className="px-2 py-2">{row.movement_type}</td>
                    <td className={`px-2 py-2 ${row.quantity_delta >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                      {row.quantity_delta >= 0 ? '+' : ''}
                      {row.quantity_delta}
                    </td>
                    <td className="px-2 py-2 text-slate-600 dark:text-slate-300">{row.reference_type}</td>
                    <td className="px-2 py-2 text-slate-600 dark:text-slate-300">{row.notes ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}