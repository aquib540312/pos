import { useEffect, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'
import type { GoodsReceipt, PendingGRNItem, Product, PurchaseOrder, PurchaseReturn, Supplier } from '../types'

interface Warehouse {
  id: string
  code: string
  name: string
  is_default: boolean
}
interface Branch {
  id: string
  warehouses: Warehouse[]
}

interface BranchInfo {
  id: string
  warehouse: Warehouse | null
}

interface DraftItem {
  key: string
  product_id: string
  product_name: string
  quantity: string
  free_quantity: string
  unit_cost: string
}

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

export default function PurchasingPage() {
  const [tab, setTab] = useState<'orders' | 'receipts' | 'returns'>('orders')
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [orders, setOrders] = useState<PurchaseOrder[]>([])
  const [receipts, setReceipts] = useState<GoodsReceipt[]>([])
  const [returns, setReturns] = useState<PurchaseReturn[]>([])
  const [branchInfo, setBranchInfo] = useState<BranchInfo | null>(null)
  const [productNames, setProductNames] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    apiClient.get<Supplier[]>('/party/suppliers').then((r) => setSuppliers(r.data))
    apiClient.get<Branch[]>('/org/branches').then((r) => {
      const branch = r.data[0]
      if (branch) {
        setBranchInfo({
          id: branch.id,
          warehouse: branch.warehouses.find((w) => w.is_default) ?? branch.warehouses[0] ?? null,
        })
      }
    })
    apiClient.get<Product[]>('/catalog/products').then((r) => {
      setProductNames(Object.fromEntries(r.data.map((p) => [p.id, p.name])))
    })
    refreshOrders()
    refreshReceipts()
    refreshReturns()
  }, [])

  async function refreshOrders() {
    const res = await apiClient.get<PurchaseOrder[]>('/purchasing/purchase-orders')
    setOrders(res.data)
  }

  async function refreshReceipts() {
    const res = await apiClient.get<GoodsReceipt[]>('/purchasing/goods-receipts')
    setReceipts(res.data)
  }

  async function refreshReturns() {
    const res = await apiClient.get<PurchaseReturn[]>('/purchasing/purchase-returns')
    setReturns(res.data)
  }

  function supplierName(id: string) {
    return suppliers.find((s) => s.id === id)?.name ?? id
  }

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold text-slate-900 dark:text-slate-50">Purchasing</h1>

      <div className="mb-6 flex gap-2 border-b border-slate-200 dark:border-slate-700">
        {(['orders', 'receipts', 'returns'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
              tab === t
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
            }`}
          >
            {t === 'orders' ? 'Purchase Orders' : t === 'receipts' ? 'Goods Receipts' : 'Returns'}
          </button>
        ))}
      </div>

      {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}
      {notice && <p className="mb-4 text-sm text-emerald-600 dark:text-emerald-400">{notice}</p>}

      {tab === 'orders' && (
        <PurchaseOrdersTab
          suppliers={suppliers}
          orders={orders}
          branchId={branchInfo?.id ?? null}
          onCreated={refreshOrders}
          onError={setError}
          onNotice={setNotice}
          supplierName={supplierName}
        />
      )}
      {tab === 'receipts' && (
        <GoodsReceiptsTab
          suppliers={suppliers}
          orders={orders}
          receipts={receipts}
          warehouse={branchInfo?.warehouse ?? null}
          productNames={productNames}
          onCreated={() => {
            refreshReceipts()
            refreshOrders()
            refreshReturns()
          }}
          onError={setError}
          supplierName={supplierName}
        />
      )}
      {tab === 'returns' && (
        <PurchaseReturnsTab
          suppliers={suppliers}
          returns={returns}
          warehouse={branchInfo?.warehouse ?? null}
          onCreated={() => {
            refreshReturns()
            refreshReceipts()
          }}
          onError={setError}
          onNotice={setNotice}
          supplierName={supplierName}
        />
      )}
    </div>
  )
}

interface ReturnDraftItem {
  key: string
  product_id: string
  product_name: string
  quantity: string
  unit_cost: string
}

function PurchaseReturnsTab({
  suppliers,
  returns,
  warehouse,
  onCreated,
  onError,
  onNotice,
  supplierName,
}: {
  suppliers: Supplier[]
  returns: PurchaseReturn[]
  warehouse: Warehouse | null
  onCreated: () => void
  onError: (msg: string | null) => void
  onNotice: (msg: string | null) => void
  supplierName: (id: string) => string
}) {
  const [showForm, setShowForm] = useState(false)
  const [supplierId, setSupplierId] = useState('')
  const [reason, setReason] = useState('')
  const [items, setItems] = useState<ReturnDraftItem[]>([])
  const [busy, setBusy] = useState(false)

  function addProduct(p: Product) {
    setItems((cur) => [
      ...cur,
      {
        key: `${p.id}-${Date.now()}`,
        product_id: p.id,
        product_name: p.name,
        quantity: '1',
        unit_cost: String(p.purchase_price),
      },
    ])
  }

  function updateItem(key: string, field: 'quantity' | 'unit_cost' | 'free_quantity', value: string) {
    setItems((cur) => cur.map((it) => (it.key === key ? { ...it, [field]: value } : it)))
  }

  function removeItem(key: string) {
    setItems((cur) => cur.filter((it) => it.key !== key))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    onError(null)
    if (!supplierId || !warehouse || items.length === 0) {
      onError('Pick a supplier, make sure a warehouse is configured, and add at least one product.')
      return
    }
    setBusy(true)
    try {
      await apiClient.post('/purchasing/purchase-returns', {
        warehouse_id: warehouse.id,
        supplier_id: supplierId,
        reason: reason || null,
        items: items.map((it) => ({
          product_id: it.product_id,
          quantity: Number(it.quantity),
          unit_cost: Number(it.unit_cost),
        })),
      })
      setItems([])
      setSupplierId('')
      setReason('')
      setShowForm(false)
      onNotice('Purchase return posted. Supplier payable reduced.')
      onCreated()
    } catch (err) {
      onError(apiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <div className="mb-4 flex justify-end">
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
        >
          {showForm ? 'Cancel' : '+ Return to Supplier'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="mb-6 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-800">
          <div className="mb-3 grid grid-cols-2 gap-3">
            <select
              required
              value={supplierId}
              onChange={(e) => setSupplierId(e.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            >
              <option value="">Supplier...</option>
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            <input
              placeholder="Reason (optional)"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
          </div>
          <p className="mb-2 text-xs text-slate-400">
            Stock is issued from the selected warehouse and the supplier's payable balance is reduced by the returned value
            (including GST on the returned lines).
          </p>
          <ProductPicker onPick={addProduct} />
          <div className="mt-3">
            <ItemsTable items={items} onChange={updateItem} onRemove={removeItem} costLabel="Unit Cost" />
          </div>
          <button
            type="submit"
            disabled={busy}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {busy ? 'Posting...' : 'Post Purchase Return'}
          </button>
        </form>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
            <tr>
              <th className="px-4 py-3">Return Number</th>
              <th className="px-4 py-3">Supplier</th>
              <th className="px-4 py-3">Return Date</th>
              <th className="px-4 py-3">Reason</th>
              <th className="px-4 py-3 text-right">Return Total</th>
            </tr>
          </thead>
          <tbody>
            {returns.map((r) => (
              <tr key={r.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">{r.return_number}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{supplierName(r.supplier_id)}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{new Date(r.return_date).toLocaleString('en-IN')}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{r.reason ?? '-'}</td>
                <td className="px-4 py-3 text-right font-medium text-slate-900 dark:text-slate-100">â‚¹{r.return_total.toFixed(2)}</td>
              </tr>
            ))}
            {returns.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                  No purchase returns yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function PurchaseOrdersTab({
  suppliers,
  orders,
  branchId,
  onCreated,
  onError,
  onNotice,
  supplierName,
}: {
  suppliers: Supplier[]
  orders: PurchaseOrder[]
  branchId: string | null
  onCreated: () => void
  onError: (msg: string | null) => void
  onNotice: (msg: string | null) => void
  supplierName: (id: string) => string
}) {
  const [showForm, setShowForm] = useState(false)
  const [supplierId, setSupplierId] = useState('')
  const [orderDate, setOrderDate] = useState(todayIso())
  const [items, setItems] = useState<DraftItem[]>([])
  const [busy, setBusy] = useState(false)
  const [pending, setPending] = useState<PendingGRNItem[]>([])
  const [showPending, setShowPending] = useState(false)

  async function loadPending() {
    const res = await apiClient.get<PendingGRNItem[]>('/purchasing/purchase-orders/pending')
    setPending(res.data)
  }

  function addProduct(p: Product) {
    setItems((cur) => [
      ...cur,
      {
        key: p.id,
        product_id: p.id,
        product_name: p.name,
        quantity: '1',
        free_quantity: '0',
        unit_cost: String(p.purchase_price),
      },
    ])
  }

  function updateItem(key: string, field: 'quantity' | 'free_quantity' | 'unit_cost', value: string) {
    setItems((cur) => cur.map((it) => (it.key === key ? { ...it, [field]: value } : it)))
  }

  function removeItem(key: string) {
    setItems((cur) => cur.filter((it) => it.key !== key))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    onError(null)
    if (!supplierId || !branchId || items.length === 0) {
      onError('Pick a supplier and at least one product.')
      return
    }
    setBusy(true)
    try {
      await apiClient.post('/purchasing/purchase-orders', {
        branch_id: branchId,
        supplier_id: supplierId,
        order_date: orderDate,
        items: items.map((it) => ({
          product_id: it.product_id,
          quantity_ordered: Number(it.quantity),
          unit_cost: Number(it.unit_cost),
        })),
      })
      setItems([])
      setSupplierId('')
      setShowForm(false)
      onNotice('Purchase order created.')
      onCreated()
    } catch (err) {
      onError(apiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function changeStatus(poId: string, status: string) {
    onError(null)
    try {
      await apiClient.patch(`/purchasing/purchase-orders/${poId}/status`, { status })
      onNotice(`Purchase order ${status}.`)
      onCreated()
    } catch (err) {
      onError(apiErrorMessage(err))
    }
  }

  const poById = new Map(orders.map((o) => [o.id, o]))
  const pendingByPo = new Map<string, PendingGRNItem[]>()
  for (const row of pending) {
    const arr = pendingByPo.get(row.po_id) ?? []
    arr.push(row)
    pendingByPo.set(row.po_id, arr)
  }

  return (
    <div>
      <div className="mb-4 flex justify-end gap-2">
        <button
          onClick={() => {
            setShowPending((v) => !v)
            loadPending()
          }}
          className="rounded-lg border border-indigo-600 px-4 py-2 text-sm font-semibold text-indigo-600 hover:bg-indigo-50 dark:hover:bg-indigo-950"
        >
          {showPending ? 'Hide' : 'View'} Pending GRN
        </button>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
        >
          {showForm ? 'Cancel' : '+ New Purchase Order'}
        </button>
      </div>

      {showPending && (
        <div className="mb-6 overflow-x-auto rounded-xl border border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30">
          <p className="px-4 py-2 text-sm font-semibold text-amber-800 dark:text-amber-300">
            Under-delivered purchase orders â€” goods still owed by the supplier
          </p>
          <table className="w-full text-left text-sm">
            <thead className="border-y border-amber-200 text-amber-700 dark:border-amber-800 dark:text-amber-400">
              <tr>
                <th className="px-4 py-2">PO</th>
                <th className="px-4 py-2">Supplier</th>
                <th className="px-4 py-2">Product</th>
                <th className="px-4 py-2 text-right">Ordered</th>
                <th className="px-4 py-2 text-right">Received</th>
                <th className="px-4 py-2 text-right">Outstanding</th>
              </tr>
            </thead>
            <tbody>
              {pending.map((row) => {
                const po = poById.get(row.po_id)
                return (
                  <tr key={`${row.po_id}-${row.product_id}`} className="border-b border-amber-100 last:border-0 dark:border-amber-800/60">
                    <td className="px-4 py-2 font-medium text-amber-900 dark:text-amber-200">{row.po_number}</td>
                    <td className="px-4 py-2 text-amber-800 dark:text-amber-300">
                      {supplierName(po?.supplier_id ?? row.supplier_id)}
                    </td>
                    <td className="px-4 py-2 text-amber-800 dark:text-amber-300">
                      {row.product_name} <span className="text-xs text-amber-500">({row.sku})</span>
                    </td>
                    <td className="px-4 py-2 text-right text-amber-800 dark:text-amber-300">{row.quantity_ordered.toFixed(2)}</td>
                    <td className="px-4 py-2 text-right text-amber-800 dark:text-amber-300">{row.quantity_received.toFixed(2)}</td>
                    <td className="px-4 py-2 text-right font-semibold text-amber-900 dark:text-amber-200">{row.outstanding_quantity.toFixed(2)}</td>
                  </tr>
                )
              })}
              {pending.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-4 text-center text-amber-500">
                    All purchase orders fully delivered.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {showForm && (
        <form onSubmit={handleSubmit} className="mb-6 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-800">
          <div className="mb-3 grid grid-cols-2 gap-3">
            <select
              required
              value={supplierId}
              onChange={(e) => setSupplierId(e.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            >
              <option value="">Supplier...</option>
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            <input
              required
              type="date"
              value={orderDate}
              onChange={(e) => setOrderDate(e.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
          </div>
          <ProductPicker onPick={addProduct} />
          <div className="mt-3">
            <ItemsTable items={items} onChange={updateItem} onRemove={removeItem} costLabel="Unit Cost" />
          </div>
          <button
            type="submit"
            disabled={busy}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {busy ? 'Saving...' : 'Create Purchase Order'}
          </button>
        </form>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
            <tr>
              <th className="px-4 py-3">PO Number</th>
              <th className="px-4 py-3">Supplier</th>
              <th className="px-4 py-3">Order Date</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Items</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((po) => (
              <tr key={po.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">{po.po_number}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{supplierName(po.supplier_id)}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{po.order_date}</td>
                <td className="px-4 py-3">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                      po.status === 'draft'
                        ? 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
                        : po.status === 'submitted'
                          ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300'
                          : po.status === 'received'
                            ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'
                            : 'bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-400'
                    }`}
                  >
                    {po.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                  {po.items.reduce((s, i) => s + i.quantity_received, 0)} / {po.items.reduce((s, i) => s + i.quantity_ordered, 0)} received
                </td>
                <td className="px-4 py-3 text-right">
                  {(po.status === 'submitted' || po.status === 'draft' || po.status === 'received') && (
                    <div className="inline-flex gap-1">
                      {po.status === 'draft' && (
                        <button
                          onClick={() => changeStatus(po.id, 'submitted')}
                          className="rounded-lg bg-blue-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-blue-500"
                        >
                          Submit
                        </button>
                      )}
                      {po.status === 'submitted' && (
                        <button
                          onClick={() => changeStatus(po.id, 'closed')}
                          className="rounded-lg bg-slate-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-slate-500"
                        >
                          Close
                        </button>
                      )}
                      <button
                        onClick={() => changeStatus(po.id, 'cancelled')}
                        className="rounded-lg bg-red-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-red-500"
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                  {pendingByPo.has(po.id) && po.items.some((i) => i.quantity_received < i.quantity_ordered) && (
                    <span className="ml-2 inline-block rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-700 dark:bg-amber-900/40 dark:text-amber-300">
                      Pending GRN
                    </span>
                  )}
                </td>
              </tr>
            ))}
            {orders.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
                  No purchase orders yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ProductPicker({ onPick }: { onPick: (p: Product) => void }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Product[]>([])

  async function search(q: string) {
    setQuery(q)
    if (!q) {
      setResults([])
      return
    }
    const res = await apiClient.get<Product[]>('/catalog/products', { params: { search: q } })
    setResults(res.data)
  }

  return (
    <div className="relative">
      <input
        value={query}
        onChange={(e) => search(e.target.value)}
        placeholder="Search product to add..."
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
      />
      {results.length > 0 && (
        <ul className="absolute z-10 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-800">
          {results.map((p) => (
            <li
              key={p.id}
              onClick={() => {
                onPick(p)
                setQuery('')
                setResults([])
              }}
              className="cursor-pointer px-3 py-2 text-sm hover:bg-slate-100 dark:text-slate-100 dark:hover:bg-slate-700"
            >
              {p.name} <span className="text-slate-400">({p.sku})</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function ItemsTable({
  items,
  onChange,
  onRemove,
  costLabel,
  showFreeQty,
}: {
  items: Array<{ key: string; product_name: string; quantity: string; free_quantity?: string; unit_cost: string }>
  onChange: (key: string, field: 'quantity' | 'free_quantity' | 'unit_cost', value: string) => void
  onRemove: (key: string) => void
  costLabel: string
  showFreeQty?: boolean
}) {
  if (items.length === 0) return null
  return (
    <table className="mb-3 w-full text-left text-sm">
      <thead className="text-slate-500 dark:text-slate-400">
        <tr>
          <th className="py-1">Product</th>
          <th className="py-1">Qty</th>
          {showFreeQty && <th className="py-1">Free/Bonus Qty</th>}
          <th className="py-1">{costLabel}</th>
          <th className="py-1" />
        </tr>
      </thead>
      <tbody>
        {items.map((it) => (
          <tr key={it.key}>
            <td className="py-1 pr-2">{it.product_name}</td>
            <td className="py-1 pr-2">
              <input
                type="number"
                min="0.001"
                step="0.001"
                value={it.quantity}
                onChange={(e) => onChange(it.key, 'quantity', e.target.value)}
                className="w-24 rounded-lg border border-slate-300 px-2 py-1 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
              />
            </td>
            {showFreeQty && (
              <td className="py-1 pr-2">
                <input
                  type="number"
                  min="0"
                  step="0.001"
                  max={it.quantity || undefined}
                  value={it.free_quantity}
                  onChange={(e) => onChange(it.key, 'free_quantity', e.target.value)}
                  title="Bonus/free pieces included in Qty above (e.g. a supplier's '10+1 free' scheme) -- received into stock but not billed."
                  className="w-24 rounded-lg border border-slate-300 px-2 py-1 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                />
              </td>
            )}
            <td className="py-1 pr-2">
              <input
                type="number"
                min="0"
                step="0.01"
                value={it.unit_cost}
                onChange={(e) => onChange(it.key, 'unit_cost', e.target.value)}
                className="w-24 rounded-lg border border-slate-300 px-2 py-1 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
              />
            </td>
            <td className="py-1 text-right">
              <button type="button" onClick={() => onRemove(it.key)} className="text-red-600 hover:text-red-500">
                &times;
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}


function GoodsReceiptsTab({
  suppliers,
  orders,
  receipts,
  warehouse,
  productNames,
  onCreated,
  onError,
  supplierName,
}: {
  suppliers: Supplier[]
  orders: PurchaseOrder[]
  receipts: GoodsReceipt[]
  warehouse: Warehouse | null
  productNames: Record<string, string>
  onCreated: () => void
  onError: (msg: string | null) => void
  supplierName: (id: string) => string
}) {
  const [showForm, setShowForm] = useState(false)
  const [supplierId, setSupplierId] = useState('')
  const [purchaseOrderId, setPurchaseOrderId] = useState('')
  const [items, setItems] = useState<DraftItem[]>([])
  const [busy, setBusy] = useState(false)

  const openOrdersForSupplier = orders.filter(
    (po) => po.supplier_id === supplierId && po.items.some((i) => i.quantity_received < i.quantity_ordered),
  )

  function addProduct(p: Product) {
    setItems((cur) => [
      ...cur,
      {
        key: `${p.id}-${Date.now()}`,
        product_id: p.id,
        product_name: p.name,
        quantity: '1',
        free_quantity: '0',
        unit_cost: String(p.purchase_price),
      },
    ])
  }

  function applyPurchaseOrder(poId: string) {
    setPurchaseOrderId(poId)
    const po = orders.find((o) => o.id === poId)
    if (!po) return
    setItems(
      po.items
        .filter((i) => i.quantity_received < i.quantity_ordered)
        .map((i) => ({
          key: i.id,
          product_id: i.product_id,
          product_name: productNames[i.product_id] ?? i.product_id,
          quantity: String(i.quantity_ordered - i.quantity_received),
          free_quantity: '0',
          unit_cost: String(i.unit_cost),
        })),
    )
  }

  function updateItem(key: string, field: 'quantity' | 'free_quantity' | 'unit_cost', value: string) {
    setItems((cur) => cur.map((it) => (it.key === key ? { ...it, [field]: value } : it)))
  }

  function removeItem(key: string) {
    setItems((cur) => cur.filter((it) => it.key !== key))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    onError(null)
    if (!supplierId || !warehouse || items.length === 0) {
      onError('Pick a supplier, make sure a warehouse is configured, and add at least one product.')
      return
    }
    setBusy(true)
    try {
      await apiClient.post('/purchasing/goods-receipts', {
        warehouse_id: warehouse.id,
        supplier_id: supplierId,
        purchase_order_id: purchaseOrderId || null,
        items: items.map((it) => ({
          product_id: it.product_id,
          quantity: Number(it.quantity),
          free_quantity: Number(it.free_quantity || 0),
          unit_cost: Number(it.unit_cost),
        })),
      })
      setItems([])
      setSupplierId('')
      setPurchaseOrderId('')
      setShowForm(false)
      onCreated()
    } catch (err) {
      onError(apiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <div className="mb-4 flex justify-end">
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
        >
          {showForm ? 'Cancel' : '+ Receive Stock'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="mb-6 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-800">
          <div className="mb-3 grid grid-cols-2 gap-3">
            <select
              required
              value={supplierId}
              onChange={(e) => {
                setSupplierId(e.target.value)
                setPurchaseOrderId('')
                setItems([])
              }}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            >
              <option value="">Supplier...</option>
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            <select
              value={purchaseOrderId}
              onChange={(e) => applyPurchaseOrder(e.target.value)}
              disabled={!supplierId}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            >
              <option value="">No purchase order (direct receipt)</option>
              {openOrdersForSupplier.map((po) => (
                <option key={po.id} value={po.id}>
                  {po.po_number}
                </option>
              ))}
            </select>
          </div>
          <ProductPicker onPick={addProduct} />
          <div className="mt-3">
            <ItemsTable items={items} onChange={updateItem} onRemove={removeItem} costLabel="Unit Cost" showFreeQty />
          </div>
          <button
            type="submit"
            disabled={busy}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {busy ? 'Saving...' : 'Post Goods Receipt'}
          </button>
        </form>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
            <tr>
              <th className="px-4 py-3">GRN Number</th>
              <th className="px-4 py-3">Supplier</th>
              <th className="px-4 py-3">Received At</th>
              <th className="px-4 py-3">Items</th>
            </tr>
          </thead>
          <tbody>
            {receipts.map((g) => (
              <tr key={g.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">{g.grn_number}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{supplierName(g.supplier_id)}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{new Date(g.received_at).toLocaleString('en-IN')}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{g.items.length}</td>
              </tr>
            ))}
            {receipts.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-slate-400">
                  No goods receipts yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
