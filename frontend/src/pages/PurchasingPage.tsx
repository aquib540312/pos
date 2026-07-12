import { useEffect, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'
import type { GoodsReceipt, Product, PurchaseOrder, Supplier } from '../types'

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
  unit_cost: string
}

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

export default function PurchasingPage() {
  const [tab, setTab] = useState<'orders' | 'receipts'>('orders')
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [orders, setOrders] = useState<PurchaseOrder[]>([])
  const [receipts, setReceipts] = useState<GoodsReceipt[]>([])
  const [branchInfo, setBranchInfo] = useState<BranchInfo | null>(null)
  const [productNames, setProductNames] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)

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
  }, [])

  async function refreshOrders() {
    const res = await apiClient.get<PurchaseOrder[]>('/purchasing/purchase-orders')
    setOrders(res.data)
  }

  async function refreshReceipts() {
    const res = await apiClient.get<GoodsReceipt[]>('/purchasing/goods-receipts')
    setReceipts(res.data)
  }

  function supplierName(id: string) {
    return suppliers.find((s) => s.id === id)?.name ?? id
  }

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold text-slate-900 dark:text-slate-50">Purchasing</h1>

      <div className="mb-6 flex gap-2 border-b border-slate-200 dark:border-slate-700">
        {(['orders', 'receipts'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
              tab === t
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
            }`}
          >
            {t === 'orders' ? 'Purchase Orders' : 'Goods Receipts'}
          </button>
        ))}
      </div>

      {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

      {tab === 'orders' && (
        <PurchaseOrdersTab
          suppliers={suppliers}
          orders={orders}
          branchId={branchInfo?.id ?? null}
          onCreated={refreshOrders}
          onError={setError}
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
          }}
          onError={setError}
          supplierName={supplierName}
        />
      )}
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
}: {
  items: DraftItem[]
  onChange: (key: string, field: 'quantity' | 'unit_cost', value: string) => void
  onRemove: (key: string) => void
  costLabel: string
}) {
  if (items.length === 0) return null
  return (
    <table className="mb-3 w-full text-left text-sm">
      <thead className="text-slate-500 dark:text-slate-400">
        <tr>
          <th className="py-1">Product</th>
          <th className="py-1">Qty</th>
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

function PurchaseOrdersTab({
  suppliers,
  orders,
  branchId,
  onCreated,
  onError,
  supplierName,
}: {
  suppliers: Supplier[]
  orders: PurchaseOrder[]
  branchId: string | null
  onCreated: () => void
  onError: (msg: string | null) => void
  supplierName: (id: string) => string
}) {
  const [showForm, setShowForm] = useState(false)
  const [supplierId, setSupplierId] = useState('')
  const [orderDate, setOrderDate] = useState(todayIso())
  const [items, setItems] = useState<DraftItem[]>([])
  const [busy, setBusy] = useState(false)

  function addProduct(p: Product) {
    setItems((cur) => [
      ...cur,
      { key: p.id, product_id: p.id, product_name: p.name, quantity: '1', unit_cost: String(p.purchase_price) },
    ])
  }

  function updateItem(key: string, field: 'quantity' | 'unit_cost', value: string) {
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
          {showForm ? 'Cancel' : '+ New Purchase Order'}
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
            </tr>
          </thead>
          <tbody>
            {orders.map((po) => (
              <tr key={po.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">{po.po_number}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{supplierName(po.supplier_id)}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{po.order_date}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{po.status}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                  {po.items.reduce((s, i) => s + i.quantity_received, 0)} / {po.items.reduce((s, i) => s + i.quantity_ordered, 0)} received
                </td>
              </tr>
            ))}
            {orders.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
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
      { key: `${p.id}-${Date.now()}`, product_id: p.id, product_name: p.name, quantity: '1', unit_cost: String(p.purchase_price) },
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
          unit_cost: String(i.unit_cost),
        })),
    )
  }

  function updateItem(key: string, field: 'quantity' | 'unit_cost', value: string) {
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
            <ItemsTable items={items} onChange={updateItem} onRemove={removeItem} costLabel="Unit Cost" />
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
