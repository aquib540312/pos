import { useEffect, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'
import { useCan, PERMS } from '../auth/permissions'
import type { GoodsReceipt, PendingGRNItem, Product, PurchaseOrder, PurchaseReturn, PurchaseReturnItem, Supplier } from '../types'

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
  discount_amount: string
}

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

export default function PurchasingPage() {
  const canCreate = useCan(PERMS.PURCHASE_CREATE)
  const canReceive = useCan(PERMS.PURCHASE_RECEIVE)
  const [tab, setTab] = useState<'orders' | 'receipts' | 'returns'>(() => (canCreate ? 'orders' : 'receipts'))
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
    if (canCreate) refreshOrders()
    if (canReceive) {
      refreshReceipts()
      refreshReturns()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
        {(
          [
            ['orders', canCreate],
            ['receipts', canReceive],
            ['returns', canReceive],
          ] as const
        )
          .filter(([, ok]) => ok)
          .map(([t]) => (
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
          productNames={productNames}
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
          receipts={receipts}
          returns={returns}
          warehouse={branchInfo?.warehouse ?? null}
          productNames={productNames}
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
  batch_id?: string | null
  original_grn_item_id?: string | null
}

function PurchaseReturnsTab({
  suppliers,
  receipts,
  returns,
  warehouse,
  productNames,
  onCreated,
  onError,
  onNotice,
  supplierName,
}: {
  suppliers: Supplier[]
  receipts: GoodsReceipt[]
  returns: PurchaseReturn[]
  warehouse: Warehouse | null
  productNames: Record<string, string>
  onCreated: () => void
  onError: (msg: string | null) => void
  onNotice: (msg: string | null) => void
  supplierName: (id: string) => string
}) {
  const [showForm, setShowForm] = useState(false)
  const [supplierId, setSupplierId] = useState('')
  const [goodsReceiptId, setGoodsReceiptId] = useState('')
  const [reason, setReason] = useState('')
  const [items, setItems] = useState<ReturnDraftItem[]>([])
  const [busy, setBusy] = useState(false)
  const [viewDoc, setViewDoc] = useState<PurchaseReturn | null>(null)
  const [retQuery, setRetQuery] = useState('')
  const [retDateFrom, setRetDateFrom] = useState('')
  const [retDateTo, setRetDateTo] = useState('')
  const [retFilterProduct, setRetFilterProduct] = useState<Product | null>(null)

  const filteredReturns = returns.filter((r) => {
    const q = retQuery.trim().toLowerCase()
    if (q && !r.return_number.toLowerCase().includes(q)) return false
    const d = new Date(r.return_date)
    if (retDateFrom && d < new Date(`${retDateFrom}T00:00:00`)) return false
    if (retDateTo) {
      const end = new Date(`${retDateTo}T23:59:59`)
      if (d > end) return false
    }
    if (retFilterProduct && !r.items.some((i) => i.product_id === retFilterProduct.id)) return false
    return true
  })

  const retProductSummary = retFilterProduct
    ? filteredReturns
        .map((r) => ({
          ret: r,
          qty: r.items.filter((i) => i.product_id === retFilterProduct.id).reduce((s, i) => s + i.quantity, 0),
        }))
        .filter((row) => row.qty > 0)
    : []

  const receiptsForSupplier = supplierId
    ? receipts.filter((g) => g.supplier_id === supplierId)
    : []

  function applyGoodsReceipt(grnId: string) {
    setGoodsReceiptId(grnId)
    const grn = receipts.find((g) => g.id === grnId)
    if (!grn) {
      setItems([])
      return
    }
    setItems(
      grn.items.map((i) => ({
        key: i.id,
        product_id: i.product_id,
        product_name: productNames[i.product_id] ?? i.product_id,
        quantity: String(i.quantity - i.free_quantity),
        unit_cost: String(i.unit_cost),
        batch_id: i.batch_id,
        original_grn_item_id: i.id,
      })),
    )
  }

  function addProduct(p: Product) {
    setItems((cur) => [
      ...cur,
      {
        key: `${p.id}-${Date.now()}`,
        product_id: p.id,
        product_name: p.name,
        quantity: '1',
        unit_cost: String(p.purchase_price),
        batch_id: null,
        original_grn_item_id: null,
      },
    ])
  }

  function updateItem(key: string, field: 'quantity' | 'unit_cost' | 'free_quantity' | 'discount_amount', value: string) {
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
        goods_receipt_id: goodsReceiptId || null,
        reason: reason || null,
        items: items.map((it) => ({
          product_id: it.product_id,
          quantity: Number(it.quantity),
          unit_cost: Number(it.unit_cost),
          batch_id: it.batch_id ?? null,
          original_grn_item_id: it.original_grn_item_id ?? null,
        })),
      })
      setItems([])
      setSupplierId('')
      setGoodsReceiptId('')
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
              onChange={(e) => {
                setSupplierId(e.target.value)
                setGoodsReceiptId('')
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
              value={goodsReceiptId}
              onChange={(e) => applyGoodsReceipt(e.target.value)}
              disabled={!supplierId}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            >
              <option value="">No invoice (standalone return)</option>
              {receiptsForSupplier.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.supplier_invoice_number ? `INV ${g.supplier_invoice_number}` : g.grn_number} ({g.grn_number})
                </option>
              ))}
            </select>
          </div>
          <input
            placeholder="Reason (optional)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="mb-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          />
          <p className="mb-2 text-xs text-slate-400">
            Pick an invoice (GRN) above to load its lines for return, or add products manually. Stock is issued from the
            selected warehouse and the supplier's payable balance is reduced by the returned value (including tax on the
            returned lines).
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

      <div className="mb-4 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-800">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <input
            value={retQuery}
            onChange={(e) => setRetQuery(e.target.value)}
            placeholder="Search by return number..."
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          />
          <input
            type="date"
            value={retDateFrom}
            onChange={(e) => setRetDateFrom(e.target.value)}
            title="Returned from"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          />
          <input
            type="date"
            value={retDateTo}
            onChange={(e) => setRetDateTo(e.target.value)}
            title="Returned up to"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          />
          <ProductFilterPicker product={retFilterProduct} onPick={setRetFilterProduct} />
        </div>
        {(retQuery || retDateFrom || retDateTo || retFilterProduct) && (
          <div className="mt-2 flex items-center justify-between">
            <span className="text-xs text-slate-500 dark:text-slate-400">
              {filteredReturns.length} of {returns.length} returns
            </span>
            <button
              onClick={() => {
                setRetQuery('')
                setRetDateFrom('')
                setRetDateTo('')
                setRetFilterProduct(null)
              }}
              className="text-xs font-semibold text-indigo-600 hover:underline dark:text-indigo-400"
            >
              Clear filters
            </button>
          </div>
        )}
      </div>

      {retFilterProduct && retProductSummary.length > 0 && (
        <div className="mb-4 rounded-xl border border-indigo-200 bg-indigo-50 p-4 dark:border-indigo-800 dark:bg-indigo-950/30">
          <p className="mb-2 text-sm font-semibold text-indigo-900 dark:text-indigo-200">
            {retFilterProduct.name} — returned {retProductSummary.reduce((s, r) => s + r.qty, 0).toFixed(3)} units across{' '}
            {retProductSummary.length} purchase return{retProductSummary.length === 1 ? '' : 's'}
          </p>
          <ul className="space-y-1 text-sm text-indigo-800 dark:text-indigo-300">
            {retProductSummary.map((r) => (
              <li key={r.ret.id} className="flex justify-between">
                <span>
                   {r.ret.return_number} · {supplierName(r.ret.supplier_id)} · {new Date(r.ret.return_date).toLocaleDateString('en-SA')}
                </span>
                <span className="font-semibold">{r.qty.toFixed(3)} units</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
            <tr>
<th className="px-4 py-3">Return Number</th>
              <th className="px-4 py-3">Supplier</th>
              <th className="px-4 py-3">Invoice (GRN)</th>
              <th className="px-4 py-3">Return Date</th>
              <th className="px-4 py-3">Reason</th>
              <th className="px-4 py-3 text-right">Return Total</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredReturns.map((r) => {
              const grn = r.goods_receipt_id ? receipts.find((g) => g.id === r.goods_receipt_id) : null
              return (
                <tr key={r.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                  <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">{r.return_number}</td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{supplierName(r.supplier_id)}</td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                    {grn ? (grn.supplier_invoice_number ? `INV ${grn.supplier_invoice_number}` : grn.grn_number) : '-'}
                  </td>
                   <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{new Date(r.return_date).toLocaleString('en-SA')}</td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{r.reason ?? '-'}</td>
                  <td className="px-4 py-3 text-right font-medium text-slate-900 dark:text-slate-100">SAR {r.return_total.toFixed(2)}</td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => setViewDoc(r)}
                      className="rounded-lg bg-slate-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-slate-500"
                    >
                      View
                    </button>
                  </td>
                </tr>
              )
            })}
            {filteredReturns.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-slate-400">
                  {returns.length === 0 ? 'No purchase returns yet.' : 'No purchase returns match the current filters.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {viewDoc && (
        <PurchaseDocModal
          kind="return"
          doc={viewDoc}
          supplierName={supplierName(viewDoc.supplier_id)}
          productNames={productNames}
          onClose={() => setViewDoc(null)}
        />
      )}
    </div>
  )
}

function PurchaseOrdersTab({
  suppliers,
  orders,
  branchId,
  productNames,
  onCreated,
  onError,
  onNotice,
  supplierName,
}: {
  suppliers: Supplier[]
  orders: PurchaseOrder[]
  branchId: string | null
  productNames: Record<string, string>
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
  const [viewDoc, setViewDoc] = useState<PurchaseOrder | null>(null)
  const [poQuery, setPoQuery] = useState('')
  const [poDateFrom, setPoDateFrom] = useState('')
  const [poDateTo, setPoDateTo] = useState('')
  const [poFilterProduct, setPoFilterProduct] = useState<Product | null>(null)

  const filteredOrders = orders.filter((po) => {
    const q = poQuery.trim().toLowerCase()
    if (q && !po.po_number.toLowerCase().includes(q)) return false
    if (poDateFrom && po.order_date < poDateFrom) return false
    if (poDateTo && po.order_date > poDateTo) return false
    if (poFilterProduct && !po.items.some((i) => i.product_id === poFilterProduct.id)) return false
    return true
  })

  const poProductSummary = poFilterProduct
    ? filteredOrders
        .map((po) => ({
          po,
          ordered: po.items.filter((i) => i.product_id === poFilterProduct.id).reduce((s, i) => s + i.quantity_ordered, 0),
          received: po.items.filter((i) => i.product_id === poFilterProduct.id).reduce((s, i) => s + i.quantity_received, 0),
        }))
        .filter((r) => r.ordered > 0)
    : []

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
        discount_amount: '0',
      },
    ])
  }

  function updateItem(key: string, field: 'quantity' | 'free_quantity' | 'unit_cost' | 'discount_amount', value: string) {
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
          discount_amount: Number(it.discount_amount || 0),
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
            <ItemsTable items={items} onChange={updateItem} onRemove={removeItem} costLabel="Unit Cost" showDiscount />
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

      <div className="mb-4 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-800">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <input
            value={poQuery}
            onChange={(e) => setPoQuery(e.target.value)}
            placeholder="Search by PO number..."
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          />
          <input
            type="date"
            value={poDateFrom}
            onChange={(e) => setPoDateFrom(e.target.value)}
            title="Ordered from"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          />
          <input
            type="date"
            value={poDateTo}
            onChange={(e) => setPoDateTo(e.target.value)}
            title="Ordered up to"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          />
          <ProductFilterPicker product={poFilterProduct} onPick={setPoFilterProduct} />
        </div>
        {(poQuery || poDateFrom || poDateTo || poFilterProduct) && (
          <div className="mt-2 flex items-center justify-between">
            <span className="text-xs text-slate-500 dark:text-slate-400">
              {filteredOrders.length} of {orders.length} purchase orders
            </span>
            <button
              onClick={() => {
                setPoQuery('')
                setPoDateFrom('')
                setPoDateTo('')
                setPoFilterProduct(null)
              }}
              className="text-xs font-semibold text-indigo-600 hover:underline dark:text-indigo-400"
            >
              Clear filters
            </button>
          </div>
        )}
      </div>

      {poFilterProduct && poProductSummary.length > 0 && (
        <div className="mb-4 rounded-xl border border-indigo-200 bg-indigo-50 p-4 dark:border-indigo-800 dark:bg-indigo-950/30">
          <p className="mb-2 text-sm font-semibold text-indigo-900 dark:text-indigo-200">
            {poFilterProduct.name} — ordered {poProductSummary.reduce((s, r) => s + r.ordered, 0).toFixed(3)} units across{' '}
            {poProductSummary.length} purchase order{poProductSummary.length === 1 ? '' : 's'}
          </p>
          <ul className="space-y-1 text-sm text-indigo-800 dark:text-indigo-300">
            {poProductSummary.map((r) => (
              <li key={r.po.id} className="flex justify-between">
                <span>
                  {r.po.po_number} · {supplierName(r.po.supplier_id)} · {r.po.order_date} · {r.po.status}
                </span>
                <span className="font-semibold">
                  {r.ordered.toFixed(3)} ordered / {r.received.toFixed(3)} received
                </span>
              </li>
            ))}
          </ul>
        </div>
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
            {filteredOrders.map((po) => (
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
                  <div className="inline-flex gap-1">
                    <button
                      onClick={() => setViewDoc(po)}
                      className="rounded-lg bg-slate-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-slate-500"
                    >
                      View
                    </button>
                    {(po.status === 'submitted' || po.status === 'draft' || po.status === 'received') && (
                      <>
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
                      </>
                    )}
                  </div>
                  {pendingByPo.has(po.id) && po.items.some((i) => i.quantity_received < i.quantity_ordered) && (
                    <span className="ml-2 inline-block rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-700 dark:bg-amber-900/40 dark:text-amber-300">
                      Pending GRN
                    </span>
                  )}
                </td>
              </tr>
            ))}
            {filteredOrders.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
                  {orders.length === 0 ? 'No purchase orders yet.' : 'No purchase orders match the current filters.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {viewDoc && (
        <PurchaseDocModal
          kind="po"
          doc={viewDoc}
          supplierName={supplierName(viewDoc.supplier_id)}
          productNames={productNames}
          onClose={() => setViewDoc(null)}
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

function ProductFilterPicker({
  product,
  onPick,
}: {
  product: Product | null
  onPick: (p: Product | null) => void
}) {
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

  if (product) {
    return (
      <div className="flex items-center justify-between rounded-lg border border-indigo-300 bg-indigo-50 px-3 py-2 text-sm dark:border-indigo-700 dark:bg-indigo-950/40">
        <span className="truncate font-medium text-indigo-900 dark:text-indigo-200">
          {product.name} <span className="text-xs text-indigo-500">({product.sku})</span>
        </span>
        <button type="button" onClick={() => onPick(null)} className="ml-2 text-indigo-600 hover:text-indigo-500 dark:text-indigo-400">
          &times;
        </button>
      </div>
    )
  }

  return (
    <div className="relative">
      <input
        value={query}
        onChange={(e) => search(e.target.value)}
        placeholder="Search product to see purchase history..."
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
  showDiscount,
}: {
  items: Array<{ key: string; product_name: string; quantity: string; free_quantity?: string; unit_cost: string; discount_amount?: string }>
  onChange: (key: string, field: 'quantity' | 'free_quantity' | 'unit_cost' | 'discount_amount', value: string) => void
  onRemove: (key: string) => void
  costLabel: string
  showFreeQty?: boolean
  showDiscount?: boolean
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
          {showDiscount && <th className="py-1">Discount (SAR)</th>}
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
            {showDiscount && (
              <td className="py-1 pr-2">
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  max={Number((parseFloat(it.quantity || '0') - parseFloat(it.free_quantity || '0')) * parseFloat(it.unit_cost || '0')) || undefined}
                  value={it.discount_amount}
                  onChange={(e) => onChange(it.key, 'discount_amount', e.target.value)}
                  title="Per-line discount off the gross line value (paid qty x unit cost)."
                  className="w-24 rounded-lg border border-slate-300 px-2 py-1 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                />
              </td>
            )}
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
  const [supplierInvoiceNumber, setSupplierInvoiceNumber] = useState('')
  const [items, setItems] = useState<DraftItem[]>([])
  const [busy, setBusy] = useState(false)
  const [viewDoc, setViewDoc] = useState<GoodsReceipt | null>(null)
  const [invQuery, setInvQuery] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [filterProduct, setFilterProduct] = useState<Product | null>(null)

  const filteredReceipts = receipts.filter((g) => {
    const q = invQuery.trim().toLowerCase()
    if (q && !g.grn_number.toLowerCase().includes(q) && !(g.supplier_invoice_number ?? '').toLowerCase().includes(q)) {
      return false
    }
    const d = new Date(g.received_at)
    if (dateFrom && d < new Date(`${dateFrom}T00:00:00`)) return false
    if (dateTo) {
      const end = new Date(`${dateTo}T23:59:59`)
      if (d > end) return false
    }
    if (filterProduct && !g.items.some((i) => i.product_id === filterProduct.id)) return false
    return true
  })

  const productPurchaseSummary = filterProduct
    ? filteredReceipts
        .map((g) => ({
          grn: g,
          qty: g.items.filter((i) => i.product_id === filterProduct.id).reduce((s, i) => s + i.quantity, 0),
        }))
        .filter((r) => r.qty > 0)
    : []

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
        discount_amount: '0',
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
          discount_amount: String(i.discount_amount ?? 0),
        })),
    )
  }

  function updateItem(key: string, field: 'quantity' | 'free_quantity' | 'unit_cost' | 'discount_amount', value: string) {
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
        supplier_invoice_number: supplierInvoiceNumber || null,
        items: items.map((it) => ({
          product_id: it.product_id,
          quantity: Number(it.quantity) || 0,
          free_quantity: Number(it.free_quantity || 0),
          unit_cost: Number(it.unit_cost) || 0,
          discount_amount: Number(it.discount_amount || 0),
        })),
      })
      setItems([])
      setSupplierId('')
      setPurchaseOrderId('')
      setSupplierInvoiceNumber('')
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

      <div className="mb-4 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-800">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <input
            value={invQuery}
            onChange={(e) => setInvQuery(e.target.value)}
            placeholder="Search by GRN / invoice number..."
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          />
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            title="Received from"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          />
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            title="Received up to"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          />
          <ProductFilterPicker product={filterProduct} onPick={setFilterProduct} />
        </div>
        {(invQuery || dateFrom || dateTo || filterProduct) && (
          <div className="mt-2 flex items-center justify-between">
            <span className="text-xs text-slate-500 dark:text-slate-400">
              {filteredReceipts.length} of {receipts.length} receipts
            </span>
            <button
              onClick={() => {
                setInvQuery('')
                setDateFrom('')
                setDateTo('')
                setFilterProduct(null)
              }}
              className="text-xs font-semibold text-indigo-600 hover:underline dark:text-indigo-400"
            >
              Clear filters
            </button>
          </div>
        )}
      </div>

      {filterProduct && productPurchaseSummary.length > 0 && (
        <div className="mb-4 rounded-xl border border-indigo-200 bg-indigo-50 p-4 dark:border-indigo-800 dark:bg-indigo-950/30">
          <p className="mb-2 text-sm font-semibold text-indigo-900 dark:text-indigo-200">
            {filterProduct.name} — purchased {productPurchaseSummary.reduce((s, r) => s + r.qty, 0).toFixed(3)} units across{' '}
            {productPurchaseSummary.length} purchase invoice{productPurchaseSummary.length === 1 ? '' : 's'}
          </p>
          <ul className="space-y-1 text-sm text-indigo-800 dark:text-indigo-300">
            {productPurchaseSummary.map((r) => (
              <li key={r.grn.id} className="flex justify-between">
                <span>
                  {r.grn.supplier_invoice_number ? `INV ${r.grn.supplier_invoice_number} ` : ''}
                  {r.grn.grn_number} · {supplierName(r.grn.supplier_id)} ·{' '}
                   {new Date(r.grn.received_at).toLocaleDateString('en-SA')}
                </span>
                <span className="font-semibold">{r.qty.toFixed(3)} units</span>
              </li>
            ))}
          </ul>
        </div>
      )}

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
          <input
            placeholder="Supplier invoice number (optional)"
            value={supplierInvoiceNumber}
            onChange={(e) => setSupplierInvoiceNumber(e.target.value)}
            className="mb-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          />
          <ProductPicker onPick={addProduct} />
          <div className="mt-3">
            <ItemsTable items={items} onChange={updateItem} onRemove={removeItem} costLabel="Unit Cost" showFreeQty showDiscount />
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
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredReceipts.map((g) => (
              <tr key={g.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">
                  {g.supplier_invoice_number ? (
                    <>
                      <span className="block">{g.grn_number}</span>
                      <span className="text-xs text-slate-400">INV {g.supplier_invoice_number}</span>
                    </>
                  ) : (
                    g.grn_number
                  )}
                </td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{supplierName(g.supplier_id)}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{new Date(g.received_at).toLocaleString('en-SA')}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{g.items.length}</td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={() => setViewDoc(g)}
                    className="rounded-lg bg-slate-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-slate-500"
                  >
                    View
                  </button>
                </td>
              </tr>
            ))}
            {filteredReceipts.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                  {receipts.length === 0 ? 'No goods receipts yet.' : 'No receipts match the current filters.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {viewDoc && (
        <PurchaseDocModal
          kind="grn"
          doc={viewDoc}
          supplierName={supplierName(viewDoc.supplier_id)}
          productNames={productNames}
          onClose={() => setViewDoc(null)}
        />
      )}
    </div>
  )
}

function PurchaseDocModal({
  kind,
  doc,
  supplierName,
  productNames,
  onClose,
}: {
  kind: 'po' | 'grn' | 'return'
  doc: PurchaseOrder | GoodsReceipt | PurchaseReturn
  supplierName: string
  productNames: Record<string, string>
  onClose: () => void
}) {
  function printDoc() {
    document.body.classList.add('printing-purchase')
    window.print()
    document.body.classList.remove('printing-purchase')
  }

  const title = kind === 'po' ? 'PURCHASE ORDER' : kind === 'grn' ? 'PURCHASE INVOICE (GOODS RECEIPT)' : 'PURCHASE RETURN'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div
        id="print-doc"
        onClick={(e) => e.stopPropagation()}
        className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white p-6 text-slate-900 shadow-xl print:text-black"
      >
        <div className="mb-4 flex justify-end gap-2 print:hidden">
          <button
            onClick={printDoc}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
          >
            Print
          </button>
          <button
            onClick={onClose}
            className="rounded-lg bg-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-300 dark:bg-slate-700 dark:text-slate-100"
          >
            Close
          </button>
        </div>

        {kind === 'po' && <PoDocument doc={doc as PurchaseOrder} supplierName={supplierName} productNames={productNames} title={title} />}
        {kind === 'grn' && <GrnDocument doc={doc as GoodsReceipt} supplierName={supplierName} productNames={productNames} title={title} />}
        {kind === 'return' && <ReturnDocument doc={doc as PurchaseReturn} supplierName={supplierName} productNames={productNames} title={title} />}
      </div>
    </div>
  )
}

function DocHeader({ title, number, date, supplier, extra }: { title: string; number: string; date: string; supplier: string; extra?: string }) {
  return (
    <div className="mb-4 border-b-2 border-slate-900 pb-3">
      <p className="text-center text-lg font-bold tracking-wide">{title}</p>
      <div className="mt-2 flex justify-between text-sm">
        <span>No: <span className="font-semibold">{number}</span></span>
        <span>Date: <span className="font-semibold">{date}</span></span>
      </div>
      <div className="mt-1 flex justify-between text-sm">
        <span>Supplier: <span className="font-semibold">{supplier}</span></span>
        {extra && <span>{extra}</span>}
      </div>
    </div>
  )
}

function DocTable({ head, children }: { head: string[]; children: React.ReactNode }) {
  return (
    <table className="mb-3 w-full border-collapse text-sm">
      <thead>
        <tr className="border-b-2 border-slate-900">
          {head.map((h) => (
            <th key={h} className="py-1 text-left font-semibold">{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>{children}</tbody>
    </table>
  )
}

function PoDocument({
  doc,
  supplierName,
  productNames,
  title,
}: {
  doc: PurchaseOrder
  supplierName: string
  productNames: Record<string, string>
  title: string
}) {
  const total = doc.items.reduce((s, i) => s + i.quantity_ordered * i.unit_cost - i.discount_amount, 0)
  return (
    <div>
      <DocHeader
        title={title}
        number={doc.po_number}
        date={doc.order_date}
        supplier={supplierName}
        extra={`Status: ${doc.status}`}
      />
      <DocTable head={['Product', 'Qty Ordered', 'Unit Cost (SAR)', 'Discount (SAR)', 'Net (SAR)']}>
        {doc.items.map((i) => (
          <tr key={i.id} className="border-b border-slate-300 print:border-slate-400">
            <td className="py-1 pr-2">{productNames[i.product_id] ?? i.product_id}</td>
            <td className="py-1 pr-2">{i.quantity_ordered}</td>
            <td className="py-1 pr-2">{i.unit_cost.toFixed(2)}</td>
            <td className="py-1 pr-2">{(i.discount_amount ?? 0).toFixed(2)}</td>
            <td className="py-1 pr-2 font-medium">{(i.quantity_ordered * i.unit_cost - (i.discount_amount ?? 0)).toFixed(2)}</td>
          </tr>
        ))}
      </DocTable>
      <div className="flex justify-end text-sm font-bold">
        <span>Order Total: SAR {total.toFixed(2)}</span>
      </div>
    </div>
  )
}

function GrnDocument({
  doc,
  supplierName,
  productNames,
  title,
}: {
  doc: GoodsReceipt
  supplierName: string
  productNames: Record<string, string>
  title: string
}) {
  const rows = doc.items.map((i) => {
    const paidQty = i.quantity - (i.free_quantity ?? 0)
    const taxable = paidQty * i.unit_cost - (i.discount_amount ?? 0)
    const vat = i.vat_amount ?? 0
    return { i, paidQty, taxable, vat, total: taxable + vat }
  })
  const taxableTotal = rows.reduce((s, r) => s + r.taxable, 0)
  const vatTotal = rows.reduce((s, r) => s + r.vat, 0)
  return (
    <div>
      <DocHeader
        title={title}
        number={doc.grn_number}
        date={new Date(doc.received_at).toLocaleString('en-SA')}
        supplier={supplierName}
        extra={doc.supplier_invoice_number ? `Supplier Invoice: ${doc.supplier_invoice_number}` : undefined}
      />
      <DocTable head={['Product', 'Paid Qty', 'Unit Cost (SAR)', 'Discount (SAR)', 'Taxable (SAR)', 'VAT (SAR)', 'Total (SAR)']}>
        {rows.map(({ i, paidQty, taxable, vat, total }) => (
          <tr key={i.id} className="border-b border-slate-300 print:border-slate-400">
            <td className="py-1 pr-2">{productNames[i.product_id] ?? i.product_id}</td>
            <td className="py-1 pr-2">{paidQty}</td>
            <td className="py-1 pr-2">{i.unit_cost.toFixed(2)}</td>
            <td className="py-1 pr-2">{(i.discount_amount ?? 0).toFixed(2)}</td>
            <td className="py-1 pr-2">{taxable.toFixed(2)}</td>
            <td className="py-1 pr-2">{vat.toFixed(2)}</td>
            <td className="py-1 pr-2 font-medium">{total.toFixed(2)}</td>
          </tr>
        ))}
      </DocTable>
      <div className="flex justify-end gap-8 text-sm">
        <span className="font-semibold">Taxable: SAR {taxableTotal.toFixed(2)}</span>
        <span className="font-semibold">VAT: SAR {vatTotal.toFixed(2)}</span>
        <span className="font-bold">Invoice Total: SAR {(taxableTotal + vatTotal).toFixed(2)}</span>
      </div>
    </div>
  )
}

function ReturnDocument({
  doc,
  supplierName,
  productNames,
  title,
}: {
  doc: PurchaseReturn
  supplierName: string
  productNames: Record<string, string>
  title: string
}) {
  const vatOf = (i: PurchaseReturnItem) => i.vat_amount ?? 0
  return (
    <div>
      <DocHeader
        title={title}
        number={doc.return_number}
        date={new Date(doc.return_date).toLocaleString('en-SA')}
        supplier={supplierName}
        extra={doc.is_debit_note ? 'Debit Note' : 'Credit Note'}
      />
      {doc.reason && (
        <p className="mb-3 text-sm">
          Reason: <span className="font-medium">{doc.reason}</span>
        </p>
      )}
      <DocTable head={['Product', 'Qty', 'Unit Cost (SAR)', 'Taxable (SAR)', 'VAT (SAR)', 'Line Total (SAR)']}>
        {doc.items.map((i) => (
          <tr key={i.id} className="border-b border-slate-300 print:border-slate-400">
            <td className="py-1 pr-2">{productNames[i.product_id] ?? i.product_id}</td>
            <td className="py-1 pr-2">{i.quantity}</td>
            <td className="py-1 pr-2">{i.unit_cost.toFixed(2)}</td>
            <td className="py-1 pr-2">{i.taxable_value.toFixed(2)}</td>
            <td className="py-1 pr-2">{vatOf(i).toFixed(2)}</td>
            <td className="py-1 pr-2 font-medium">{i.line_total.toFixed(2)}</td>
          </tr>
        ))}
      </DocTable>
      <div className="flex justify-end text-sm font-bold">
        <span>Return Total: SAR {doc.return_total.toFixed(2)}</span>
      </div>
    </div>
  )
}
