import { useEffect, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'
import type { Product } from '../types'

interface Warehouse {
  id: string
  code: string
  name: string
}
interface Branch {
  id: string
  name: string
  warehouses: Warehouse[]
}
interface WarehouseOption {
  id: string
  label: string
}

interface TransferItem {
  id: string
  product_id: string
  batch_id: string | null
  quantity: number
}

interface Transfer {
  id: string
  transfer_number: string
  source_warehouse_id: string
  destination_warehouse_id: string
  status: string
  dispatched_at: string | null
  received_at: string | null
  items: TransferItem[]
}

interface DraftLine {
  key: string
  product_id: string
  product_name: string
  quantity: string
}

function formatDateTime(iso: string | null) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('en-IN')
}

export default function StockTransferPage() {
  const [warehouseOptions, setWarehouseOptions] = useState<WarehouseOption[]>([])
  const [productNames, setProductNames] = useState<Record<string, string>>({})
  const [transfers, setTransfers] = useState<Transfer[]>([])
  const [showForm, setShowForm] = useState(false)
  const [sourceId, setSourceId] = useState('')
  const [destinationId, setDestinationId] = useState('')
  const [lines, setLines] = useState<DraftLine[]>([])
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Product[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  async function refreshTransfers() {
    const res = await apiClient.get<Transfer[]>('/inventory/transfers')
    setTransfers(res.data)
  }

  useEffect(() => {
    apiClient.get<Branch[]>('/org/branches').then((res) => {
      const options = res.data.flatMap((b) => b.warehouses.map((w) => ({ id: w.id, label: `${b.name} - ${w.name}` })))
      setWarehouseOptions(options)
    })
    apiClient.get<Product[]>('/catalog/products').then((res) => {
      setProductNames(Object.fromEntries(res.data.map((p) => [p.id, p.name])))
    })
    refreshTransfers()
  }, [])

  function warehouseLabel(id: string) {
    return warehouseOptions.find((w) => w.id === id)?.label ?? id
  }

  async function searchProducts(q: string) {
    setQuery(q)
    if (!q) {
      setResults([])
      return
    }
    const res = await apiClient.get<Product[]>('/catalog/products', { params: { search: q } })
    setResults(res.data)
  }

  function addLine(p: Product) {
    setLines((cur) => [...cur, { key: `${p.id}-${Date.now()}`, product_id: p.id, product_name: p.name, quantity: '1' }])
    setQuery('')
    setResults([])
  }

  function updateLineQty(key: string, value: string) {
    setLines((cur) => cur.map((l) => (l.key === key ? { ...l, quantity: value } : l)))
  }

  function removeLine(key: string) {
    setLines((cur) => cur.filter((l) => l.key !== key))
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!sourceId || !destinationId || lines.length === 0) {
      setError('Pick a source, a destination, and at least one product.')
      return
    }
    if (sourceId === destinationId) {
      setError('Source and destination warehouse must differ.')
      return
    }
    setBusy('create')
    try {
      await apiClient.post('/inventory/transfers', {
        source_warehouse_id: sourceId,
        destination_warehouse_id: destinationId,
        items: lines.map((l) => ({ product_id: l.product_id, quantity: Number(l.quantity) })),
      })
      setSourceId('')
      setDestinationId('')
      setLines([])
      setShowForm(false)
      await refreshTransfers()
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function dispatchTransfer(id: string) {
    setError(null)
    setBusy(id)
    try {
      await apiClient.post(`/inventory/transfers/${id}/dispatch`)
      await refreshTransfers()
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function receiveTransfer(id: string) {
    setError(null)
    setBusy(id)
    try {
      await apiClient.post(`/inventory/transfers/${id}/receive`)
      await refreshTransfers()
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-50">Stock Transfer</h1>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
        >
          {showForm ? 'Cancel' : '+ New Transfer'}
        </button>
      </div>

      {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

      {showForm && (
        <form onSubmit={handleCreate} className="mb-6 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-800">
          <div className="mb-3 grid grid-cols-2 gap-3">
            <select
              required
              value={sourceId}
              onChange={(e) => setSourceId(e.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            >
              <option value="">From warehouse...</option>
              {warehouseOptions.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.label}
                </option>
              ))}
            </select>
            <select
              required
              value={destinationId}
              onChange={(e) => setDestinationId(e.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            >
              <option value="">To warehouse...</option>
              {warehouseOptions.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.label}
                </option>
              ))}
            </select>
          </div>

          <div className="relative mb-3">
            <input
              value={query}
              onChange={(e) => searchProducts(e.target.value)}
              placeholder="Search product to add..."
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
            {results.length > 0 && (
              <ul className="absolute z-10 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-800">
                {results.map((p) => (
                  <li
                    key={p.id}
                    onClick={() => addLine(p)}
                    className="cursor-pointer px-3 py-2 text-sm hover:bg-slate-100 dark:text-slate-100 dark:hover:bg-slate-700"
                  >
                    {p.name} <span className="text-slate-400">({p.sku})</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {lines.length > 0 && (
            <table className="mb-3 w-full text-left text-sm">
              <thead className="text-slate-500 dark:text-slate-400">
                <tr>
                  <th className="py-1">Product</th>
                  <th className="py-1">Qty</th>
                  <th className="py-1" />
                </tr>
              </thead>
              <tbody>
                {lines.map((l) => (
                  <tr key={l.key}>
                    <td className="py-1 pr-2">{l.product_name}</td>
                    <td className="py-1 pr-2">
                      <input
                        type="number"
                        min="0.001"
                        step="0.001"
                        value={l.quantity}
                        onChange={(e) => updateLineQty(l.key, e.target.value)}
                        className="w-24 rounded-lg border border-slate-300 px-2 py-1 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      />
                    </td>
                    <td className="py-1 text-right">
                      <button type="button" onClick={() => removeLine(l.key)} className="text-red-600 hover:text-red-500">
                        &times;
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <button
            type="submit"
            disabled={busy === 'create'}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {busy === 'create' ? 'Saving...' : 'Create Transfer (Draft)'}
          </button>
        </form>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
            <tr>
              <th className="px-4 py-3">Transfer #</th>
              <th className="px-4 py-3">From</th>
              <th className="px-4 py-3">To</th>
              <th className="px-4 py-3">Items</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Dispatched</th>
              <th className="px-4 py-3">Received</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {transfers.map((t) => (
              <tr key={t.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">{t.transfer_number}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{warehouseLabel(t.source_warehouse_id)}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{warehouseLabel(t.destination_warehouse_id)}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                  {t.items.map((i) => `${productNames[i.product_id] ?? i.product_id} (${i.quantity})`).join(', ')}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      t.status === 'received'
                        ? 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
                        : t.status === 'dispatched'
                          ? 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300'
                          : 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300'
                    }`}
                  >
                    {t.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{formatDateTime(t.dispatched_at)}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{formatDateTime(t.received_at)}</td>
                <td className="px-4 py-3 text-right">
                  {t.status === 'draft' && (
                    <button
                      onClick={() => dispatchTransfer(t.id)}
                      disabled={busy === t.id}
                      className="text-sm font-medium text-indigo-600 hover:text-indigo-500 disabled:opacity-50"
                    >
                      {busy === t.id ? 'Dispatching...' : 'Dispatch'}
                    </button>
                  )}
                  {t.status === 'dispatched' && (
                    <button
                      onClick={() => receiveTransfer(t.id)}
                      disabled={busy === t.id}
                      className="text-sm font-medium text-indigo-600 hover:text-indigo-500 disabled:opacity-50"
                    >
                      {busy === t.id ? 'Receiving...' : 'Receive'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {transfers.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-6 text-center text-slate-400">
                  No stock transfers yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
