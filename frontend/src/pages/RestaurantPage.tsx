import { useEffect, useMemo, useRef, useState, type RefObject } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'
import type {
  Category,
  DiningOrder,
  DiningOrderEstimate,
  DiningOrderItem,
  DiningTable,
  Product,
} from '../types'

interface Branch {
  id: string
  code: string
  name: string
  warehouses: { id: string; code: string; name: string; is_default: boolean }[]
}

interface PaymentRow {
  method: 'cash' | 'card' | 'upi' | 'wallet' | 'credit' | 'gift_card'
  amount: number
  received: number
  reference: string
}

const PAYMENT_METHODS: PaymentRow['method'][] = ['cash', 'card', 'upi', 'wallet', 'credit', 'gift_card']

const TABLE_STATUS_STYLES: Record<DiningTable['status'], { card: string; badge: string; label: string }> = {
  available: {
    card: 'border-emerald-300 bg-emerald-50 dark:border-emerald-700 dark:bg-emerald-950/40',
    badge: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300',
    label: 'Available',
  },
  occupied: {
    card: 'border-rose-300 bg-rose-50 dark:border-rose-700 dark:bg-rose-950/40',
    badge: 'bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300',
    label: 'Occupied',
  },
  reserved: {
    card: 'border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950/40',
    badge: 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300',
    label: 'Reserved',
  },
  cleaning: {
    card: 'border-slate-300 bg-slate-100 dark:border-slate-700 dark:bg-slate-800/60',
    badge: 'bg-slate-200 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
    label: 'Cleaning',
  },
}

const TABLE_FILTERS: { value: DiningTable['status'] | 'all'; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'available', label: 'Available' },
  { value: 'occupied', label: 'Occupied' },
  { value: 'reserved', label: 'Reserved' },
  { value: 'cleaning', label: 'Cleaning' },
]

const ITEM_STATUS_STYLES: Record<DiningOrderItem['status'], string> = {
  pending: 'bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-200',
  preparing: 'bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-300',
  ready: 'bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300',
  served: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300',
  cancelled: 'bg-slate-100 text-slate-400 line-through dark:bg-slate-800 dark:text-slate-500',
}

function inr(value: number): string {
  return `₹${value.toFixed(2)}`
}

function elapsedMinutes(openedAt: string): number {
  return Math.max(0, Math.floor((Date.now() - new Date(openedAt).getTime()) / 60000))
}

function formatElapsed(mins: number): string {
  if (mins < 1) return 'now'
  if (mins < 60) return `${mins} min`
  const h = Math.floor(mins / 60)
  const m = mins % 60
  return m ? `${h}h ${m}m` : `${h}h`
}

interface OrderPanelProps {
  selectedTable: DiningTable | null
  order: DiningOrder | null
  estimate: DiningOrderEstimate | null
  loading: boolean
  reserved: boolean
  cleaning: boolean
  pendingCount: number
  preparingCount: number
  readyCount: number
  servedItems: DiningOrderItem[]
  cancelledItems: DiningOrderItem[]
  activeItems: DiningOrderItem[]
  taxTotal: number
  busy: string | null
  busyKitchen: boolean
  canSettle: boolean
  onUpdateItem: (item: DiningOrderItem, patch: { quantity?: number; discount_amount?: number; note?: string }) => void
  onRemoveItem: (item: DiningOrderItem) => void
  onSendKot: () => void
  onServeReady: (() => void) | undefined
  onServePreparing: (() => void) | undefined
  onSettle: () => void
  onCancelOrder: (() => void) | undefined
  onOpenOrder: () => void
  onMarkCleaning: (() => void) | undefined
  onMarkAvailable: (() => void) | undefined
  onReserve: (() => void) | undefined
  kotCounter: number
  showKot: boolean
  onToggleKot: () => void
  kotNotice: { kot: string; count: number } | null
  printRef: RefObject<HTMLDivElement | null>
  transferTargets: DiningTable[]
  transferTo: string
  onTransferTo: (id: string) => void
  onTransfer: (() => void) | undefined
  onLoadTransferTargets: () => Promise<void>
}

export default function RestaurantPage() {
  const [branch, setBranch] = useState<Branch | null>(null)
  const [warehouseId, setWarehouseId] = useState<string | null>(null)
  const [shiftId, setShiftId] = useState<string | null>(null)
  const [tables, setTables] = useState<DiningTable[]>([])
  const [openOrders, setOpenOrders] = useState<DiningOrder[]>([])
  const [tableFilter, setTableFilter] = useState<DiningTable['status'] | 'all'>('all')
  const [tableSearch, setTableSearch] = useState('')
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [activeCategory, setActiveCategory] = useState<string | null>(null)
  const [menuSearch, setMenuSearch] = useState('')
  const [selectedTable, setSelectedTable] = useState<DiningTable | null>(null)
  const [order, setOrder] = useState<DiningOrder | null>(null)
  const [estimate, setEstimate] = useState<DiningOrderEstimate | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [toast, setToast] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)
  const [loadingTables, setLoadingTables] = useState(true)
  const [loadingOrder, setLoadingOrder] = useState(false)
  const [showAddTable, setShowAddTable] = useState(false)
  const [newTable, setNewTable] = useState({ table_number: '', name: '', capacity: 4 })
  const [showKot, setShowKot] = useState(false)
  const [kotNotice, setKotNotice] = useState<{ kot: string; count: number } | null>(null)
  const [showSettle, setShowSettle] = useState(false)
  const [settling, setSettling] = useState(false)
  const [payments, setPayments] = useState<PaymentRow[]>([{ method: 'cash', amount: 0, received: 0, reference: '' }])
  const [showOrderDrawer, setShowOrderDrawer] = useState(false)
  const [transferTo, setTransferTo] = useState<string>('')
  const [transferTargets, setTransferTargets] = useState<DiningTable[]>([])
  const printRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  function notify(kind: 'success' | 'error', text: string) {
    if (toastTimer.current) clearTimeout(toastTimer.current)
    setToast({ kind, text })
    toastTimer.current = setTimeout(() => setToast(null), 3500)
  }

  async function loadTables() {
    if (!branch) return
    try {
      const [tablesRes, ordersRes] = await Promise.all([
        apiClient.get<DiningTable[]>('/dining/tables', { params: { branch_id: branch.id } }),
        apiClient.get<DiningOrder[]>('/dining/orders', { params: { branch_id: branch.id, status: 'open' } }),
      ])
      setTables(tablesRes.data)
      setOpenOrders(ordersRes.data)
    } finally {
      setLoadingTables(false)
    }
  }

  useEffect(() => {
    apiClient
      .get<Branch[]>('/org/branches')
      .then((res) => setBranch(res.data[0] ?? null))
      .catch(() => setBranch(null))
    Promise.all([apiClient.get<Product[]>('/catalog/products'), apiClient.get<Category[]>('/catalog/categories')])
      .then(([p, c]) => {
        setProducts(p.data)
        setCategories(c.data)
      })
      .catch(() => setProducts([]))
  }, [])

  useEffect(() => {
    if (!branch) return
    setLoadingTables(true)
    loadTables()
    setWarehouseId(branch.warehouses.find((w) => w.is_default)?.id ?? branch.warehouses[0]?.id ?? null)
    apiClient
      .get<{ id: string } | null>('/billing/shifts/current', { params: { branch_id: branch.id } })
      .then((res) => setShiftId(res.data?.id ?? null))
      .catch(() => setShiftId(null))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [branch])

  // Periodic refresh keeps cross-terminal state honest (orders settled or
  // moved from another till become visible here without a reload).
  useEffect(() => {
    if (!branch) return
    const timer = setInterval(() => loadTables(), 30_000)
    return () => clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [branch])

  async function withError(fn: () => Promise<void>, okText?: string) {
    setError(null)
    try {
      await fn()
      if (okText) notify('success', okText)
    } catch (err) {
      const msg = apiErrorMessage(err)
      setError(msg)
      notify('error', msg)
    }
  }

  async function reloadOrder(orderId: string) {
    setLoadingOrder(true)
    try {
      const [o, e] = await Promise.all([
        apiClient.get<DiningOrder>(`/dining/orders/${orderId}`),
        apiClient.post<DiningOrderEstimate>(`/dining/orders/${orderId}/estimate`),
      ])
      setOrder(o.data)
      setEstimate(e.data)
      syncPayments(e.data.grand_total)
    } finally {
      setLoadingOrder(false)
    }
  }

  function syncPayments(grandTotal: number) {
    setPayments((prev) => {
      if (prev.length === 1 && prev[0].amount === 0) {
        return [{ ...prev[0], amount: grandTotal, received: grandTotal }]
      }
      return prev
    })
  }

  function selectTable(table: DiningTable) {
    setSelectedTable(table)
    setOrder(null)
    setEstimate(null)
    setShowKot(false)
    setKotNotice(null)
    setShowSettle(false)
    setShowOrderDrawer(false)
    setTransferTo('')
    setTransferTargets([])
    if (!table.is_active || table.status === 'cleaning') return
    if (table.active_order_id) {
      withError(() => reloadOrder(table.active_order_id!))
    }
  }

  async function openOrder() {
    if (!selectedTable || !branch) return
    await withError(async () => {
      const { data } = await apiClient.post<DiningOrder>(
        '/dining/orders',
        { table_id: selectedTable.id, shift_id: shiftId },
        { params: { branch_id: branch.id } },
      )
      await loadTables()
      await reloadOrder(data.id)
      setSelectedTable((t) => (t ? { ...t, status: 'occupied', active_order_id: data.id } : t))
    }, 'Table opened')
  }

  async function addProduct(product: Product) {
    if (!order) return
    setBusy('add')
    try {
      const { data } = await apiClient.post<DiningOrder>(`/dining/orders/${order.id}/items`, {
        items: [{ product_id: product.id, quantity: 1, discount_amount: 0 }],
      })
      setOrder(data)
      await refreshEstimate(order.id)
      await loadTables()
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function refreshEstimate(orderId: string) {
    const e = (await apiClient.post<DiningOrderEstimate>(`/dining/orders/${orderId}/estimate`)).data
    setEstimate(e)
    setPayments((prev) => {
      if (prev.length === 1 && prev[0].method === 'cash') {
        return [{ ...prev[0], amount: e.grand_total, received: e.grand_total }]
      }
      return prev
    })
  }

  async function updateItem(item: DiningOrderItem, patch: { quantity?: number; discount_amount?: number; note?: string }) {
    if (!order) return
    setBusy(`update-${item.id}`)
    try {
      await apiClient.patch(`/dining/orders/${order.id}/items/${item.id}`, patch)
      await reloadOrder(order.id)
      await refreshEstimate(order.id)
      await loadTables()
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function removeItem(item: DiningOrderItem) {
    if (!order) return
    setBusy(`remove-${item.id}`)
    try {
      await apiClient.delete(`/dining/orders/${order.id}/items/${item.id}`)
      await reloadOrder(order.id)
      await refreshEstimate(order.id)
      await loadTables()
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function sendToKitchen() {
    if (!order) return
    const pending = order.items.filter((i) => i.status === 'pending')
    if (pending.length === 0) return
    setBusy('kitchen')
    try {
      const { data } = await apiClient.post<DiningOrder>(`/dining/orders/${order.id}/kitchen`)
      await reloadOrder(order.id)
      await loadTables()
      const kots = data.items.map((i) => i.kot_number).filter((v): v is string => !!v)
      const kot = kots[kots.length - 1] ?? `KOT-${data.kot_counter}`
      setKotNotice({ kot, count: pending.length })
      notify('success', `${pending.length} item${pending.length > 1 ? 's' : ''} sent to kitchen · ${kot}`)
      setShowKot(true)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function markServed(itemIds: string[]) {
    if (!order || itemIds.length === 0) return
    setBusy('serve')
    try {
      await apiClient.post(`/dining/orders/${order.id}/serve`, { item_ids: itemIds })
      await reloadOrder(order.id)
      await loadTables()
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function cancelOrder() {
    if (!order) return
    if (!window.confirm(`Cancel the order on table "${order.table_number}"? This cannot be undone.`)) return
    setBusy('cancel')
    try {
      await apiClient.post(`/dining/orders/${order.id}/cancel`)
      setOrder(null)
      setEstimate(null)
      setSelectedTable((t) => (t ? { ...t, active_order_id: null, status: 'available' } : t))
      await loadTables()
      notify('success', 'Order cancelled')
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  function openSettle() {
    if (!order || !estimate) return
    setShowSettle(true)
    setShowOrderDrawer(false)
  }

  async function completeSettlement(cashChange: number) {
    if (!order || !warehouseId) return
    const validPayments = payments.filter((p) => p.amount > 0)
    if (validPayments.length === 0) {
      notify('error', 'Add at least one payment')
      return
    }
    const paid = validPayments.reduce((s, p) => s + p.amount, 0)
    if (paid < estimate!.grand_total) {
      notify('error', `Collected ${inr(paid)} is less than the bill ${inr(estimate!.grand_total)}`)
      return
    }
    setSettling(true)
    try {
      const { data } = await apiClient.post(`/dining/orders/${order.id}/settle`, {
        warehouse_id: warehouseId,
        shift_id: shiftId,
        payments: validPayments.map((p) => ({ method: p.method, amount: p.amount, reference: p.reference || null })),
        is_credit_sale: false,
      })
      setShowSettle(false)
      setOrder(null)
      setEstimate(null)
      setSelectedTable((t) => (t ? { ...t, active_order_id: null, status: 'available' } : t))
      setPayments([{ method: 'cash', amount: 0, received: 0, reference: '' }])
      await loadTables()
      notify('success', `Bill settled · Invoice ${data.invoice_number}${cashChange > 0 ? ` · change ${inr(cashChange)}` : ''}`)
    } catch (err) {
      const msg = apiErrorMessage(err)
      setError(msg)
      notify('error', msg)
    } finally {
      setSettling(false)
    }
  }

  async function createTable() {
    if (!branch || !newTable.table_number.trim()) return
    await withError(async () => {
      await apiClient.post('/dining/tables', newTable, { params: { branch_id: branch.id } })
      setShowAddTable(false)
      setNewTable({ table_number: '', name: '', capacity: 4 })
      await loadTables()
    }, 'Table created')
  }

  async function setTableStatus(table: DiningTable, status: DiningTable['status']) {
    setBusy(`status-${table.id}`)
    try {
      const { data } = await apiClient.patch<DiningTable>(`/dining/tables/${table.id}`, { status })
      setTables((prev) => prev.map((t) => (t.id === table.id ? { ...data, active_order_id: t.active_order_id } : t)))
      setSelectedTable((cur) => (cur?.id === table.id ? { ...cur, ...data } : cur))
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function transferOrder() {
    if (!order || !transferTo) return
    setBusy('transfer')
    try {
      const { data } = await apiClient.post<DiningOrder>(`/dining/orders/${order.id}/transfer`, {
        target_table_id: transferTo,
      })
      await loadTables()
      await reloadOrder(order.id)
      setSelectedTable((cur) => (cur ? { ...cur, status: 'available', active_order_id: null } : cur))
      setTransferTo('')
      setTransferTargets([])
      notify('success', `Order moved to table ${data.table_number}`)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  const menuProducts = useMemo(() => {
    let list = products
    if (activeCategory) list = list.filter((p) => p.category_id === activeCategory)
    const q = menuSearch.trim().toLowerCase()
    if (q) {
      list = list.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          p.sku.toLowerCase().includes(q) ||
          (p.barcode ?? '').toLowerCase().includes(q) ||
          (p.brand ?? '').toLowerCase().includes(q),
      )
    }
    return [...list].sort((a, b) => a.name.localeCompare(b.name))
  }, [products, activeCategory, menuSearch])

  const tableMap = useMemo(() => {
    const map = new Map<string, DiningOrder>()
    for (const o of openOrders) map.set(o.table_id, o)
    return map
  }, [openOrders])

  const visibleTables = useMemo(() => {
    let list = tables.filter((t) => t.is_active)
    if (tableFilter !== 'all') list = list.filter((t) => t.status === tableFilter)
    const q = tableSearch.trim().toLowerCase()
    if (q) list = list.filter((t) => `${t.name ?? ''} ${t.table_number}`.toLowerCase().includes(q))
    return list
  }, [tables, tableFilter, tableSearch])

  const pendingCount = order?.items.filter((i) => i.status === 'pending').length ?? 0
  const preparingCount = order?.items.filter((i) => i.status === 'preparing').length ?? 0
  const readyCount = order?.items.filter((i) => i.status === 'ready').length ?? 0
  const servedItems = order?.items.filter((i) => i.status === 'served') ?? []
  const cancelledItems = order?.items.filter((i) => i.status === 'cancelled') ?? []
  const activeItems = order?.items.filter((i) => i.status !== 'cancelled') ?? []
  const taxTotal = (estimate?.cgst_total ?? 0) + (estimate?.sgst_total ?? 0) + (estimate?.igst_total ?? 0)

  const totalPaid = payments.reduce((s, p) => s + p.amount, 0)
  const cashChange = payments
    .filter((p) => p.method === 'cash')
    .reduce((s, p) => s + Math.max(0, (p.received || p.amount) - p.amount), 0)

  const isTableCleaning = selectedTable?.status === 'cleaning'

  async function loadTransferTargets() {
    if (!order || !branch) return
    const res = await apiClient.get<DiningTable[]>('/dining/tables', { params: { branch_id: branch.id } })
    setTransferTargets(res.data.filter((t) => t.is_active && t.status === 'available' && t.id !== order.table_id))
  }

  const canSettle = !!order && !!estimate && estimate.grand_total > 0 && order.status === 'open'

  const orderPanelProps: OrderPanelProps = {
    selectedTable,
    order,
    estimate,
    loading: loadingOrder,
    reserved: selectedTable?.status === 'reserved',
    cleaning: isTableCleaning,
    pendingCount,
    preparingCount,
    readyCount,
    servedItems,
    cancelledItems,
    activeItems,
    taxTotal,
    busy,
    busyKitchen: busy === 'kitchen',
    canSettle,
    onUpdateItem: updateItem,
    onRemoveItem: removeItem,
    onSendKot: sendToKitchen,
    onServeReady: readyCount > 0 ? () => markServed(order?.items.filter((i) => i.status === 'ready').map((i) => i.id) ?? []) : undefined,
    onServePreparing: preparingCount > 0 ? () => markServed(order?.items.filter((i) => i.status === 'preparing').map((i) => i.id) ?? []) : undefined,
    onSettle: openSettle,
    onCancelOrder: order && order.status === 'open' ? cancelOrder : undefined,
    onOpenOrder: openOrder,
    onMarkCleaning: selectedTable?.status === 'available' ? () => setTableStatus(selectedTable, 'cleaning') : undefined,
    onMarkAvailable: isTableCleaning ? () => setTableStatus(selectedTable!, 'available') : undefined,
    onReserve: selectedTable?.status === 'available' ? () => setTableStatus(selectedTable, 'reserved') : undefined,
    kotCounter: order?.kot_counter ?? 0,
    showKot,
    onToggleKot: () => setShowKot((v) => !v),
    kotNotice,
    printRef,
    transferTargets,
    transferTo,
    onTransferTo: setTransferTo,
    onTransfer: order && transferTo ? transferOrder : undefined,
    onLoadTransferTargets: loadTransferTargets,
  }

  return (
    <div className="flex h-[calc(100vh-7rem)] flex-col">
      <div className="mb-3 flex shrink-0 flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-50">Restaurant</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {branch?.name ?? 'No branch'} · {tables.filter((t) => t.status === 'occupied').length} occupied ·{' '}
            {tables.filter((t) => t.status === 'available').length} free
          </p>
        </div>
        <button
          onClick={() => setShowAddTable((v) => !v)}
          className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
        >
          {showAddTable ? 'Close' : '+ Add table'}
        </button>
      </div>

      {showAddTable && (
        <div className="mb-3 flex shrink-0 flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-800">
          <label className="block">
            <span className="mb-1 block text-xs text-slate-500">Table number *</span>
            <input
              value={newTable.table_number}
              onChange={(e) => setNewTable({ ...newTable, table_number: e.target.value })}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700"
              placeholder="T10"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-slate-500">Name (optional)</span>
            <input
              value={newTable.name}
              onChange={(e) => setNewTable({ ...newTable, name: e.target.value })}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700"
              placeholder="Terrace"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-slate-500">Capacity</span>
            <input
              type="number"
              min={1}
              value={newTable.capacity}
              onChange={(e) => setNewTable({ ...newTable, capacity: Number(e.target.value) })}
              className="w-24 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700"
            />
          </label>
          <button
            onClick={createTable}
            disabled={busy !== null}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            Save table
          </button>
        </div>
      )}

      {error && (
        <div className="mb-3 shrink-0 rounded-lg border border-red-300 bg-red-50 px-4 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
          {error}
        </div>
      )}

      {toast && (
        <div
          className={`mb-3 shrink-0 rounded-lg border px-4 py-2 text-sm font-medium shadow-lg ${
            toast.kind === 'success'
              ? 'border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
              : 'border-red-300 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300'
          }`}
        >
          {toast.text}
        </div>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 lg:grid-cols-[260px_minmax(0,1fr)_360px]">
        <TablesPanel
          tables={visibleTables}
          orderByTable={tableMap}
          loading={loadingTables}
          selectedId={selectedTable?.id ?? null}
          filter={tableFilter}
          onFilterChange={setTableFilter}
          search={tableSearch}
          onSearchChange={setTableSearch}
          onSelect={selectTable}
          busy={busy}
        />

        <MenuPanel
          products={menuProducts}
          categories={categories}
          activeCategory={activeCategory}
          onCategoryChange={setActiveCategory}
          search={menuSearch}
          onSearchChange={setMenuSearch}
          searchRef={searchRef}
          orderOpen={!!order}
          busy={busy === 'add'}
          onAdd={addProduct}
          onOpenOrder={selectedTable && !order && selectedTable.is_active && !isTableCleaning && !selectedTable.active_order_id ? openOrder : undefined}
          pendingCount={pendingCount}
          preparingCount={preparingCount}
          readyCount={readyCount}
          onServePreparing={preparingCount > 0 ? () => markServed(order?.items.filter((i) => i.status === 'preparing').map((i) => i.id) ?? []) : undefined}
          onShowOrder={() => setShowOrderDrawer(true)}
        />

        <div className="hidden lg:block">
          <OrderPanel {...orderPanelProps} />
        </div>
      </div>

      <div className="sticky bottom-0 z-20 mt-2 lg:hidden">
        {order && (
          <button
            onClick={() => setShowOrderDrawer(true)}
            className="flex w-full items-center justify-between rounded-xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white shadow-lg dark:bg-slate-100 dark:text-slate-900"
          >
            <span>
              Table {order.table_number} · {activeItems.length} item{activeItems.length !== 1 ? 's' : ''}
            </span>
            <span>{estimate ? inr(estimate.grand_total) : inr(order.subtotal)}</span>
          </button>
        )}
      </div>

      <div
        className={`fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm transition-opacity lg:hidden ${
          showOrderDrawer ? 'opacity-100' : 'pointer-events-none opacity-0'
        }`}
        onClick={() => setShowOrderDrawer(false)}
      >
        <div
          className={`absolute bottom-0 left-0 right-0 max-h-[85vh] overflow-y-auto rounded-t-2xl bg-slate-50 p-4 transition-transform dark:bg-slate-900 ${
            showOrderDrawer ? 'translate-y-0' : 'translate-y-full'
          }`}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-50">Current order</h2>
            <button onClick={() => setShowOrderDrawer(false)} className="rounded-lg px-2 py-1 text-sm text-slate-500">
              Close
            </button>
          </div>
          <OrderPanel {...orderPanelProps} />
        </div>
      </div>

      {showSettle && order && estimate && (
        <SettleModal
          order={order}
          estimate={estimate}
          payments={payments}
          onPayments={setPayments}
          totalPaid={totalPaid}
          cashChange={cashChange}
          settling={settling}
          onClose={() => setShowSettle(false)}
          onComplete={() => completeSettlement(cashChange)}
        />
      )}
    </div>
  )
}

/* ---------------- Panel: tables ---------------- */

function TablesPanel({
  tables,
  orderByTable,
  loading,
  selectedId,
  filter,
  onFilterChange,
  search,
  onSearchChange,
  onSelect,
  busy,
}: {
  tables: DiningTable[]
  orderByTable: Map<string, DiningOrder>
  loading: boolean
  selectedId: string | null
  filter: DiningTable['status'] | 'all'
  onFilterChange: (f: DiningTable['status'] | 'all') => void
  search: string
  onSearchChange: (q: string) => void
  onSelect: (t: DiningTable) => void
  busy: string | null
}) {
  return (
    <section className="flex min-h-0 flex-col rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-800">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-300">Tables</h2>
        <span className="text-xs text-slate-400">{tables.length}</span>
      </div>
      <input
        value={search}
        onChange={(e) => onSearchChange(e.target.value)}
        placeholder="Search table…"
        className="mb-2 w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-700"
      />
      <div className="mb-2 flex flex-wrap gap-1">
        {TABLE_FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => onFilterChange(f.value)}
            className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium ${
              filter === f.value
                ? 'bg-slate-800 text-white dark:bg-slate-600'
                : 'bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto">
        {loading && tables.length === 0 && <p className="py-8 text-center text-sm text-slate-400">Loading tables…</p>}
        {!loading && tables.length === 0 && (
          <p className="py-8 text-center text-sm text-slate-400">
            No tables{filter !== 'all' ? ` (${filter})` : ''}. Add one to get started.
          </p>
        )}
        {tables.map((table) => {
          const style = TABLE_STATUS_STYLES[table.status]
          const currentOrder = orderByTable.get(table.id)
          const elapsed = currentOrder ? elapsedMinutes(currentOrder.opened_at) : null
          return (
            <TableCard
              key={table.id}
              table={table}
              style={style}
              orderAmount={currentOrder ? currentOrder.subtotal - currentOrder.discount_total : null}
              elapsed={elapsed}
              selected={selectedId === table.id}
              busy={busy === `status-${table.id}`}
              onSelect={onSelect}
            />
          )
        })}
      </div>
    </section>
  )
}

function TableCard({
  table,
  style,
  orderAmount,
  elapsed,
  selected,
  busy,
  onSelect,
}: {
  table: DiningTable
  style: { card: string; badge: string; label: string }
  orderAmount: number | null
  elapsed: number | null
  selected: boolean
  busy: boolean
  onSelect: (t: DiningTable) => void
}) {
  const clickable = table.is_active
  const subText = [
    `${table.table_number} · ${table.capacity} seats`,
    table.name && table.name !== table.table_number ? table.name : null,
  ]
    .filter(Boolean)
    .join(' · ')
  return (
    <button
      onClick={() => clickable && !busy && onSelect(table)}
      disabled={!clickable || busy}
      className={`w-full rounded-xl border-2 px-3 py-2.5 text-left transition ${style.card} ${
        selected ? 'ring-2 ring-indigo-500' : ''
      } ${clickable ? 'hover:shadow-md' : 'opacity-60'}`}
    >
      <div className="flex items-center justify-between">
        <p className="text-base font-bold text-slate-900 dark:text-slate-100">{table.name || table.table_number}</p>
        <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${style.badge}`}>
          {style.label}
        </span>
      </div>
      <p className="truncate text-xs text-slate-500 dark:text-slate-400">{subText}</p>
      {table.status === 'occupied' && orderAmount !== null && (
        <div className="mt-1 flex items-center justify-between text-sm">
          <span className="font-semibold text-slate-900 dark:text-slate-100">{inr(orderAmount)}</span>
          {elapsed !== null && <span className="text-xs text-slate-500 dark:text-slate-400">{formatElapsed(elapsed)}</span>}
        </div>
      )}
    </button>
  )
}

/* ---------------- Panel: menu ---------------- */

function MenuPanel({
  products,
  categories,
  activeCategory,
  onCategoryChange,
  search,
  onSearchChange,
  searchRef,
  orderOpen,
  busy,
  onAdd,
  onOpenOrder,
  pendingCount,
  preparingCount,
  readyCount,
  onServePreparing,
  onShowOrder,
}: {
  products: Product[]
  categories: Category[]
  activeCategory: string | null
  onCategoryChange: (id: string | null) => void
  search: string
  onSearchChange: (q: string) => void
  searchRef: RefObject<HTMLInputElement | null>
  orderOpen: boolean
  busy: boolean
  onAdd: (p: Product) => void
  onOpenOrder: (() => void) | undefined
  pendingCount: number
  preparingCount: number
  readyCount: number
  onServePreparing: (() => void) | undefined
  onShowOrder: () => void
}) {
  return (
    <section className="flex min-h-0 flex-col rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
      <div className="shrink-0 border-b border-slate-200 p-3 dark:border-slate-700">
        <div className="flex items-center gap-2">
          <input
            ref={searchRef}
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search menu by name, SKU or barcode…"
            className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700"
          />
          <button
            onClick={onShowOrder}
            className="relative rounded-lg bg-slate-800 px-3 py-2 text-xs font-semibold text-white dark:bg-slate-600 lg:hidden"
          >
            Order
            {pendingCount + preparingCount + readyCount > 0 && (
              <span className="absolute -right-1.5 -top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-orange-500 px-1 text-[10px] font-bold">
                {pendingCount + preparingCount + readyCount}
              </span>
            )}
          </button>
        </div>
        <div className="mt-2 flex max-w-full flex-wrap gap-1 overflow-x-auto">
          <button
            onClick={() => onCategoryChange(null)}
            className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium ${
              activeCategory === null
                ? 'bg-slate-800 text-white dark:bg-slate-600'
                : 'bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
            }`}
          >
            All
          </button>
          {categories.map((c) => (
            <button
              key={c.id}
              onClick={() => onCategoryChange(c.id)}
              className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium ${
                activeCategory === c.id
                  ? 'bg-slate-800 text-white dark:bg-slate-600'
                  : 'bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
              }`}
            >
              {c.name}
            </button>
          ))}
        </div>
        {!orderOpen && (
          <div className="mt-2 rounded-lg border border-dashed border-slate-300 px-3 py-2 text-xs text-slate-500 dark:border-slate-700 dark:text-slate-400">
            {onOpenOrder ? (
              <>
                No order yet on the selected table.{' '}
                <button onClick={onOpenOrder} className="font-semibold text-indigo-600 underline dark:text-indigo-400">
                  Open table & start order
                </button>
              </>
            ) : (
              'Select an available table to start an order.'
            )}
          </div>
        )}
        {onServePreparing && (
          <button
            onClick={onServePreparing}
            className="mt-2 w-full rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-emerald-500"
          >
            Mark {preparingCount} preparing item{preparingCount > 1 ? 's' : ''} as served
          </button>
        )}
      </div>

      <div className="grid min-h-0 flex-1 auto-rows-min grid-cols-2 gap-2 overflow-y-auto p-3 xl:grid-cols-3 2xl:grid-cols-4">
        {products.map((product) => (
          <MenuCard key={product.id} product={product} orderOpen={orderOpen} busy={busy} onAdd={onAdd} />
        ))}
        {products.length === 0 && (
          <p className="col-span-full py-12 text-center text-sm text-slate-400">
            {search.trim() ? `No menu items match "${search}".` : 'No menu items in this category.'}
          </p>
        )}
      </div>
    </section>
  )
}

function MenuCard({ product, orderOpen, busy, onAdd }: { product: Product; orderOpen: boolean; busy: boolean; onAdd: (p: Product) => void }) {
  const available = product.is_active
  const enabled = available && orderOpen
  return (
    <button
      onClick={() => enabled && !busy && onAdd(product)}
      disabled={!enabled || busy}
      title={available ? (orderOpen ? `Add ${product.name}` : 'Select an occupied table first') : 'Unavailable'}
      className={`flex min-h-24 flex-col rounded-xl border p-2.5 text-left transition ${
        enabled
          ? 'border-slate-200 bg-white hover:border-indigo-400 hover:shadow dark:border-slate-700 dark:bg-slate-800'
          : 'cursor-not-allowed border-slate-200 bg-slate-50 opacity-60 dark:border-slate-700 dark:bg-slate-800/50'
      }`}
    >
      <p className="line-clamp-2 text-sm font-medium text-slate-900 dark:text-slate-100">{product.name}</p>
      {product.sku && <p className="mt-0.5 text-[10px] text-slate-400">{product.sku}</p>}
      <div className="mt-auto flex items-center justify-between pt-2">
        <span className="text-base font-semibold text-indigo-600 dark:text-indigo-400">{inr(product.sale_price)}</span>
        {!available && (
          <span className="rounded bg-slate-200 px-1.5 py-0.5 text-[10px] font-medium text-slate-500 dark:bg-slate-700 dark:text-slate-300">
            Off
          </span>
        )}
      </div>
    </button>
  )
}

/* ---------------- Panel: current order ---------------- */

function OrderPanel(props: OrderPanelProps) {
  const {
    selectedTable,
    order,
    estimate,
    loading,
    reserved,
    cleaning,
    pendingCount,
    preparingCount,
    readyCount,
    servedItems,
    cancelledItems,
    activeItems,
    taxTotal,
    busy,
    busyKitchen,
    canSettle,
    onUpdateItem,
    onRemoveItem,
    onSendKot,
    onServeReady,
    onServePreparing,
    onSettle,
    onCancelOrder,
    onOpenOrder,
    onMarkCleaning,
    onMarkAvailable,
    onReserve,
    kotCounter,
    showKot,
    onToggleKot,
    kotNotice,
    printRef,
    transferTargets,
    transferTo,
    onTransferTo,
    onTransfer,
    onLoadTransferTargets,
  } = props

  return (
    <section className="flex h-full min-h-0 max-h-full flex-col rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
      <div className="shrink-0 border-b border-slate-200 p-3 dark:border-slate-700">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate text-base font-bold text-slate-900 dark:text-slate-50">
              {selectedTable ? `Table ${selectedTable.name || selectedTable.table_number}` : 'Current order'}
            </p>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {order
                ? `${order.status} · ${order.items.filter((i) => i.status !== 'cancelled').length} items`
                : reserved
                  ? 'Reserved — start the order when guests arrive.'
                  : cleaning
                    ? 'Cleaning in progress.'
                    : 'No order selected'}
            </p>
          </div>
          {order && (
            <button
              onClick={onToggleKot}
              className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium ${
                showKot ? 'bg-slate-800 text-white dark:bg-slate-600' : 'bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
              }`}
            >
              {kotCounter > 0 ? `${kotCounter} KOT` : 'KOT'}
            </button>
          )}
        </div>

        {order?.status === 'open' && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {pendingCount > 0 && <Chip label={`${pendingCount} pending`} className="bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-200" />}
            {preparingCount > 0 && <Chip label={`${preparingCount} preparing`} className="bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-300" />}
            {readyCount > 0 && <Chip label={`${readyCount} ready`} className="bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300" />}
            {servedItems.length > 0 && <Chip label={`${servedItems.length} served`} className="bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300" />}
            {cancelledItems.length > 0 && <Chip label={`${cancelledItems.length} voided`} className="bg-slate-100 text-slate-400 dark:bg-slate-800 dark:text-slate-500" />}
          </div>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {loading && <p className="py-10 text-center text-sm text-slate-400">Loading order…</p>}

        {!loading && !order && (
          <div className="flex h-full flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 p-6 text-center dark:border-slate-700">
            {reserved && <p className="mb-3 text-sm text-slate-500">Reserved — start the order when guests arrive.</p>}
            {cleaning && <p className="mb-3 text-sm text-slate-500">Cleaning in progress.</p>}
            {!reserved && !cleaning && selectedTable && (
              <p className="mb-3 text-sm text-slate-500">No open order on this table in this browser. Select an order from the left or start fresh.</p>
            )}
            {!reserved && !cleaning && !selectedTable && <p className="mb-3 text-sm text-slate-500">Select a table from the left to start.</p>}
            {selectedTable && !reserved && !cleaning && selectedTable.status === 'available' && (
              <>
                <button onClick={onOpenOrder} className="mb-2 rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-500">
                  Open table & start order
                </button>
                <div className="flex gap-2">
                  {onReserve && (
                    <button onClick={onReserve} className="rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-400">
                      Reserve
                    </button>
                  )}
                  {onMarkCleaning && (
                    <button onClick={onMarkCleaning} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-300">
                      Cleaning
                    </button>
                  )}
                </div>
              </>
            )}
            {onMarkAvailable && (
              <button onClick={onMarkAvailable} className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-500">
                Mark available
              </button>
            )}
          </div>
        )}

        {order && (
          <>
            {showKot && kotCounter > 0 && <KotView order={order} printRef={printRef} onClose={onToggleKot} />}
            {kotNotice && kotCounter > 0 && (
              <div className="mb-3 rounded-lg border border-orange-300 bg-orange-50 px-3 py-2 text-sm font-medium text-orange-700 dark:border-orange-800 dark:bg-orange-950/40 dark:text-orange-300">
                <span className="font-bold">{kotNotice.kot}</span> · {kotNotice.count} item{kotNotice.count > 1 ? 's' : ''} sent to kitchen
              </div>
            )}

            <div className="space-y-2">
              {activeItems.map((item) => (
                <OrderItemRow
                  key={item.id}
                  item={item}
                  busy={busy === `update-${item.id}` || busy === `remove-${item.id}` || busy === 'serve'}
                  onUpdate={onUpdateItem}
                  onRemove={onRemoveItem}
                />
              ))}
              {activeItems.length === 0 && (
                <p className="py-6 text-center text-sm text-slate-400">No items yet — tap a menu item to add.</p>
              )}
            </div>
          </>
        )}
      </div>

      <div className="shrink-0 border-t border-slate-200 p-3 dark:border-slate-700">
        {order && estimate && (
          <div className="mb-3 space-y-1 text-sm text-slate-600 dark:text-slate-300">
            <SummaryRow label="Subtotal" value={inr(estimate.subtotal)} />
            {estimate.discount_total > 0 && <SummaryRow label="Discount" value={`− ${inr(estimate.discount_total)}`} muted />}
            {taxTotal > 0 && <SummaryRow label="GST (CGST+SGST)" value={inr(taxTotal)} />}
            {estimate.round_off !== 0 && (
              <SummaryRow
                label="Round off"
                value={estimate.round_off > 0 ? `+ ${inr(estimate.round_off)}` : `− ${inr(Math.abs(estimate.round_off))}`}
              />
            )}
            <div className="flex justify-between border-t border-slate-200 pt-2 text-base font-bold text-slate-900 dark:border-slate-700 dark:text-slate-50">
              <span>Total</span>
              <span>{inr(estimate.grand_total)}</span>
            </div>
          </div>
        )}

        {order?.status === 'open' ? (
          <div className="space-y-2">
            {pendingCount > 0 && (
              <button
                onClick={onSendKot}
                disabled={busy !== null}
                className="w-full rounded-xl bg-orange-600 px-4 py-3 text-base font-bold text-white hover:bg-orange-500 disabled:opacity-50"
              >
                {busyKitchen ? 'Sending KOT…' : `SEND KOT · ${pendingCount} pending`}
              </button>
            )}

            <div className="flex gap-2">
              {onServeReady && (
                <button
                  onClick={onServeReady}
                  disabled={busy !== null}
                  className="flex-1 rounded-xl bg-sky-600 px-3 py-2.5 text-sm font-bold text-white hover:bg-sky-500 disabled:opacity-50"
                >
                  Serve {readyCount} ready
                </button>
              )}
              {onServePreparing && (
                <button
                  onClick={onServePreparing}
                  disabled={busy !== null}
                  className="flex-1 rounded-xl bg-emerald-600 px-3 py-2.5 text-sm font-bold text-white hover:bg-emerald-500 disabled:opacity-50"
                >
                  Mark {preparingCount} preparing served
                </button>
              )}
            </div>

            <button
              onClick={onSettle}
              disabled={!canSettle || busy !== null}
              className="w-full rounded-xl bg-emerald-600 px-4 py-3 text-base font-bold text-white shadow-sm hover:bg-emerald-500 disabled:opacity-40"
            >
              {estimate ? `SETTLE · ${inr(estimate.grand_total)}` : 'SETTLE PAYMENT'}
            </button>

            {transferTargets.length > 0 && (
              <div className="flex gap-1.5 pt-1">
                <select
                  value={transferTo}
                  onChange={(e) => onTransferTo(e.target.value)}
                  className="min-w-0 flex-1 rounded-lg border border-slate-300 px-2 py-1.5 text-xs dark:border-slate-600 dark:bg-slate-700"
                >
                  <option value="">Move to…</option>
                  {transferTargets.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name || t.table_number}
                    </option>
                  ))}
                </select>
                <button
                  onClick={onTransfer}
                  disabled={!transferTo || busy !== null}
                  className="shrink-0 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:text-slate-200"
                >
                  Transfer
                </button>
              </div>
            )}
            {transferTargets.length === 0 && order && order.status === 'open' && (
              <button
                onClick={onLoadTransferTargets}
                disabled={busy !== null}
                className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:text-slate-300"
              >
                Transfer to another table…
              </button>
            )}

            {onCancelOrder && (
              <button
                onClick={onCancelOrder}
                disabled={busy !== null}
                className="w-full rounded-lg border border-red-300 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950/40"
              >
                Cancel order
              </button>
            )}
          </div>
        ) : (
          order && <p className="text-center text-sm font-medium text-slate-500 dark:text-slate-400">Order {order.status} — no further actions.</p>
        )}
      </div>
    </section>
  )
}

function Chip({ label, className }: { label: string; className: string }) {
  return <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${className}`}>{label}</span>
}

function SummaryRow({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <div className="flex justify-between">
      <span>{label}</span>
      <span className={muted ? 'text-emerald-600 dark:text-emerald-400' : ''}>{value}</span>
    </div>
  )
}

function OrderItemRow({
  item,
  busy,
  onUpdate,
  onRemove,
}: {
  item: DiningOrderItem
  busy: boolean
  onUpdate: (item: DiningOrderItem, patch: { quantity?: number; discount_amount?: number; note?: string }) => void
  onRemove: (item: DiningOrderItem) => void
}) {
  const cancelled = item.status === 'cancelled'
  const editable = item.status === 'pending'
  return (
    <div className={`rounded-lg border p-2 ${cancelled ? 'border-slate-100 opacity-60 dark:border-slate-800' : 'border-slate-100 dark:border-slate-700'}`}>
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className={`truncate text-sm font-medium ${cancelled ? 'text-slate-400 line-through' : 'text-slate-900 dark:text-slate-100'}`}>
            {item.product_name}
          </p>
          {item.kot_number && (
            <p className="text-[11px] text-slate-400">
              {item.kot_number} · {item.status}
              {item.note ? ` · "${item.note}"` : ''}
            </p>
          )}
        </div>
        <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium uppercase ${ITEM_STATUS_STYLES[item.status]}`}>
          {item.status}
        </span>
      </div>
      <div className="mt-1.5 flex items-center gap-1.5">
        {editable && (
          <div className="flex items-center rounded-lg border border-slate-300 dark:border-slate-600">
            <button
              disabled={busy}
              onClick={() => onUpdate(item, { quantity: Math.max(1, item.quantity - 1) })}
              className="px-2 py-1 text-slate-600 hover:bg-slate-100 disabled:opacity-50 dark:text-slate-300 dark:hover:bg-slate-700"
            >
              −
            </button>
            <input
              type="number"
              min={0.001}
              step={1}
              value={item.quantity}
              onChange={(e) => {
                const qty = Number(e.target.value)
                if (Number.isFinite(qty) && qty > 0) onUpdate(item, { quantity: qty })
              }}
              className="w-12 rounded-none border-x border-slate-300 bg-transparent px-1 py-1 text-center text-sm dark:border-slate-600"
            />
            <button
              disabled={busy}
              onClick={() => onUpdate(item, { quantity: item.quantity + 1 })}
              className="px-2 py-1 text-slate-600 hover:bg-slate-100 disabled:opacity-50 dark:text-slate-300 dark:hover:bg-slate-700"
            >
              +
            </button>
          </div>
        )}
        <span className="text-xs text-slate-400">{inr(item.unit_price)} each</span>
        <span className={`ml-auto text-sm font-semibold ${cancelled ? 'text-slate-400 line-through' : 'text-slate-900 dark:text-slate-100'}`}>
          {inr(item.line_total)}
        </span>
        {editable && (
          <button
            disabled={busy}
            onClick={() => onRemove(item)}
            className="rounded px-1.5 py-1 text-xs font-medium text-red-500 hover:bg-red-50 disabled:opacity-50 dark:hover:bg-red-950/40"
            title="Remove item"
          >
            ✕
          </button>
        )}
      </div>
    </div>
  )
}

/* ---------------- KOT view ---------------- */

function KotView({ order, printRef, onClose }: { order: DiningOrder; printRef: RefObject<HTMLDivElement | null>; onClose: () => void }) {
  if (order.kot_counter === 0) {
    return <p className="mb-3 text-sm text-slate-400">No kitchen ticket yet.</p>
  }
  const grouped = new Map<string, DiningOrderItem[]>()
  for (const item of order.items) {
    if (item.kot_number) {
      const arr = grouped.get(item.kot_number) ?? []
      arr.push(item)
      grouped.set(item.kot_number, arr)
    }
  }
  return (
    <div className="mb-3 rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-900">
      <div className="mb-1 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Kitchen tickets</p>
        <div className="flex gap-1">
          <button
            onClick={() => {
              document.body.classList.add('printing-kot')
              window.print()
              document.body.classList.remove('printing-kot')
            }}
            className="rounded-lg bg-slate-800 px-2.5 py-1 text-xs font-semibold text-white hover:bg-slate-700"
          >
            Print
          </button>
          <button onClick={onClose} className="rounded-lg px-2 py-1 text-xs text-slate-500 hover:bg-slate-200 dark:hover:bg-slate-700">
            Close
          </button>
        </div>
      </div>
      <div ref={printRef}>
        <div id="print-kot">
          {Array.from(grouped.entries()).map(([kot, items]) => (
            <div key={kot} className="mb-3 border-b border-dashed border-slate-300 pb-2 last:border-0 dark:border-slate-600">
              <p className="font-mono text-sm font-bold text-slate-900 dark:text-slate-100">
                KITCHEN ORDER · {kot}
              </p>
              <p className="text-xs text-slate-400">
                Table {order.table_number} · {new Date(order.opened_at).toLocaleTimeString('en-IN')}
              </p>
              {items.map((item) => (
                <p key={item.id} className="text-sm text-slate-700 dark:text-slate-200">
                  {item.quantity} × {item.product_name}
                  {item.note ? ` (${item.note})` : ''}
                </p>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

/* ---------------- Settlement modal ---------------- */

function SettleModal({
  order,
  estimate,
  payments,
  onPayments,
  totalPaid,
  cashChange,
  settling,
  onClose,
  onComplete,
}: {
  order: DiningOrder
  estimate: DiningOrderEstimate
  payments: PaymentRow[]
  onPayments: (rows: PaymentRow[]) => void
  totalPaid: number
  cashChange: number
  settling: boolean
  onClose: () => void
  onComplete: () => void
}) {
  const balanceLeft = Math.max(0, estimate.grand_total - totalPaid)
  const fullyPaid = totalPaid >= estimate.grand_total - 0.001

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-sm"
      onClick={settling ? undefined : onClose}
    >
      <div className="w-full max-w-md rounded-2xl bg-white p-5 shadow-2xl dark:bg-slate-900" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-900 dark:text-slate-50">Settle bill</h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Table {order.table_number} · {order.items.filter((i) => i.status !== 'cancelled').length} items
            </p>
          </div>
          <div className="text-right">
            <p className="text-base font-bold text-emerald-600 dark:text-emerald-400">{inr(estimate.grand_total)}</p>
            <p className="text-xs text-slate-500 dark:text-slate-400">Total (incl. GST)</p>
          </div>
        </div>

        <div className="mb-4 max-h-[45vh] space-y-2 overflow-y-auto">
          {payments.map((p, i) => {
            const lineChange = p.method === 'cash' ? Math.max(0, (p.received || p.amount) - p.amount) : 0
            return (
              <div key={i} className="rounded-xl border border-slate-200 p-3 dark:border-slate-700">
                <div className="flex gap-2">
                  <select
                    value={p.method}
                    disabled={settling}
                    onChange={(e) => {
                      const method = e.target.value as PaymentRow['method']
                      onPayments(payments.map((row, idx) => (idx === i ? { ...row, method, received: row.amount } : row)))
                    }}
                    className="rounded-lg border border-slate-300 px-2 py-2 text-sm dark:border-slate-600 dark:bg-slate-700"
                  >
                    {PAYMENT_METHODS.map((m) => (
                      <option key={m} value={m}>
                        {m.toUpperCase()}
                      </option>
                    ))}
                  </select>
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    value={p.amount || ''}
                    disabled={settling}
                    onChange={(e) =>
                      onPayments(payments.map((row, idx) => (idx === i ? { ...row, amount: Number(e.target.value), received: Number(e.target.value) } : row)))
                    }
                    className="w-24 rounded-lg border border-slate-300 px-2 py-2 text-sm dark:border-slate-600 dark:bg-slate-700"
                  />
                  {payments.length > 1 && (
                    <button
                      onClick={() => onPayments(payments.filter((_, idx) => idx !== i))}
                      disabled={settling}
                      className="rounded p-1 text-red-500 hover:bg-red-50 dark:hover:bg-red-950/40"
                    >
                      ✕
                    </button>
                  )}
                  {i === payments.length - 1 && (
                    <button
                      onClick={() => onPayments([...payments, { method: 'cash', amount: 0, received: 0, reference: '' }])}
                      disabled={settling}
                      className="ml-auto shrink-0 rounded-lg bg-slate-200 px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-300 disabled:opacity-50 dark:bg-slate-700 dark:text-slate-200"
                    >
                      + Split
                    </button>
                  )}
                </div>
                {p.method === 'cash' && (
                  <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
                    <label className="block">
                      <span className="mb-0.5 block text-[11px] text-slate-500">Received</span>
                      <input
                        type="number"
                        min={0}
                        step="0.01"
                        value={p.received || ''}
                        disabled={settling}
                        onChange={(e) =>
                          onPayments(payments.map((row, idx) => (idx === i ? { ...row, received: Number(e.target.value) } : row)))
                        }
                        className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-700"
                      />
                    </label>
                    <label className="block">
                      <span className="mb-0.5 block text-[11px] text-slate-500">Change</span>
                      <input
                        type="text"
                        value={inr(lineChange)}
                        disabled
                        className="w-full rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5 text-sm font-medium dark:border-slate-700 dark:bg-slate-800"
                      />
                    </label>
                  </div>
                )}
                {p.method !== 'cash' && (
                  <input
                    value={p.reference || ''}
                    onChange={(e) => onPayments(payments.map((row, idx) => (idx === i ? { ...row, reference: e.target.value } : row)))}
                    disabled={settling}
                    placeholder="Reference (optional)"
                    className="mt-2 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-700"
                  />
                )}
              </div>
            )
          })}
        </div>

        <div className="mb-4 space-y-1 border-t border-slate-200 pt-3 text-sm dark:border-slate-700">
          <div className="flex justify-between">
            <span>Collected</span>
            <span>{inr(totalPaid)}</span>
          </div>
          {balanceLeft > 0 && (
            <div className="flex justify-between font-medium text-amber-600 dark:text-amber-400">
              <span>Still due</span>
              <span>{inr(balanceLeft)}</span>
            </div>
          )}
          {cashChange > 0 && (
            <div className="flex justify-between font-medium text-emerald-600 dark:text-emerald-400">
              <span>Cash change</span>
              <span>{inr(cashChange)}</span>
            </div>
          )}
        </div>

        <div className="flex gap-2">
          <button
            onClick={onClose}
            disabled={settling}
            className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
          >
            Cancel
          </button>
          <button
            onClick={onComplete}
            disabled={settling || !fullyPaid}
            className="flex-1 rounded-xl bg-emerald-600 px-4 py-2.5 text-base font-bold text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            {settling ? 'POSTING INVOICE…' : 'COMPLETE PAYMENT'}
          </button>
        </div>
        {!fullyPaid && !settling && <p className="mt-2 text-center text-xs text-slate-400">Cover the full bill before posting.</p>}
      </div>
    </div>
  )
}