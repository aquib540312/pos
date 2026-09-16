import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
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

// Deterministic gradient per category index so the menu looks "cool" and
// color-coded without needing uploaded images.
const CATEGORY_GRADIENTS = [
  'from-rose-500 to-pink-600',
  'from-orange-500 to-amber-500',
  'from-emerald-500 to-teal-600',
  'from-sky-500 to-blue-600',
  'from-violet-500 to-purple-600',
  'from-fuchsia-500 to-pink-600',
  'from-lime-500 to-green-600',
  'from-cyan-500 to-sky-600',
  'from-amber-500 to-orange-600',
  'from-indigo-500 to-blue-500',
  'from-red-500 to-rose-600',
  'from-teal-500 to-cyan-600',
]

const TABLE_STATUS_STYLES: Record<DiningTable['status'], { card: string; label: string }> = {
  available: { card: 'border-emerald-400 bg-emerald-500/90', label: 'Free' },
  occupied: { card: 'border-rose-400 bg-rose-500/90', label: 'Occupied' },
  reserved: { card: 'border-amber-400 bg-amber-500/90', label: 'Reserved' },
  cleaning: { card: 'border-slate-400 bg-slate-500/90', label: 'Cleaning' },
}

const ITEM_STATUS_STYLES: Record<DiningOrderItem['status'], string> = {
  pending: 'bg-slate-600 text-white',
  preparing: 'bg-orange-500 text-white',
  ready: 'bg-sky-500 text-white',
  served: 'bg-emerald-600 text-white',
  cancelled: 'bg-slate-300 text-slate-600 line-through',
}

function inr(value: number): string {
  return `₹${value.toFixed(2)}`
}

export default function RestaurantMenuPage() {
  const navigate = useNavigate()
  const [branch, setBranch] = useState<Branch | null>(null)
  const [warehouseId, setWarehouseId] = useState<string | null>(null)
  const [shiftId, setShiftId] = useState<string | null>(null)
  const [tables, setTables] = useState<DiningTable[]>([])
  const [openOrders, setOpenOrders] = useState<DiningOrder[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [activeCategory, setActiveCategory] = useState<string | null>(null)
  // 'all' shows every category grouped below; 'favorites' only starred items;
  // a category id shows just that category's products.
  const [favorites, setFavorites] = useState<Set<string>>(() => {
    try {
      return new Set<string>(JSON.parse(localStorage.getItem('restaurant_favorites') ?? '[]'))
    } catch {
      return new Set<string>()
    }
  })
  const [menuSearch, setMenuSearch] = useState('')
  const [selectedTable, setSelectedTable] = useState<DiningTable | null>(null)
  const [order, setOrder] = useState<DiningOrder | null>(null)
  const [estimate, setEstimate] = useState<DiningOrderEstimate | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [toast, setToast] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)
  const [loading, setLoading] = useState(true)
  const [showTablePicker, setShowTablePicker] = useState(false)
  const [showSettle, setShowSettle] = useState(false)
  const [settling, setSettling] = useState(false)
  const [payments, setPayments] = useState<PaymentRow[]>([{ method: 'cash', amount: 0, received: 0, reference: '' }])
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  function notify(kind: 'success' | 'error', text: string) {
    if (toastTimer.current) clearTimeout(toastTimer.current)
    setToast({ kind, text })
    toastTimer.current = setTimeout(() => setToast(null), 3500)
  }

  function toggleFavorite(productId: string) {
    setFavorites((prev) => {
      const next = new Set(prev)
      if (next.has(productId)) {
        next.delete(productId)
      } else {
        next.add(productId)
      }
      localStorage.setItem('restaurant_favorites', JSON.stringify(Array.from(next)))
      return next
    })
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
      .catch(() => {
        setProducts([])
        setCategories([])
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!branch) return
    setWarehouseId(branch.warehouses.find((w) => w.is_default)?.id ?? branch.warehouses[0]?.id ?? null)
    apiClient
      .get<{ id: string } | null>('/billing/shifts/current', { params: { branch_id: branch.id } })
      .then((res) => setShiftId(res.data?.id ?? null))
      .catch(() => setShiftId(null))
    loadTables()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [branch])

  // Periodic refresh keeps cross-terminal state honest.
  useEffect(() => {
    if (!branch) return
    const timer = setInterval(() => loadTables(), 30_000)
    return () => clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [branch])

  async function loadTables() {
    if (!branch) return
    try {
      const [tablesRes, ordersRes] = await Promise.all([
        apiClient.get<DiningTable[]>('/dining/tables', { params: { branch_id: branch.id } }),
        apiClient.get<DiningOrder[]>('/dining/orders', { params: { branch_id: branch.id, status: 'open' } }),
      ])
      setTables(tablesRes.data)
      setOpenOrders(ordersRes.data)
    } catch {
      /* leave previous state on transient failure */
    } finally {
      setLoading(false)
    }
  }

  async function reloadOrder(orderId: string) {
    setBusy('order')
    try {
      const [o, e] = await Promise.all([
        apiClient.get<DiningOrder>(`/dining/orders/${orderId}`),
        apiClient.post<DiningOrderEstimate>(`/dining/orders/${orderId}/estimate`),
      ])
      setOrder(o.data)
      setEstimate(e.data)
      syncPayments(e.data.grand_total)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(null)
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
    setShowTablePicker(false)
    setShowSettle(false)
    if (!table.is_active || table.status === 'cleaning') return
    if (table.active_order_id) {
      reloadOrder(table.active_order_id)
    }
  }

  async function openOrderFor(table: DiningTable) {
    if (!branch) return
    selectTable(table)
    try {
      const { data } = await apiClient.post<DiningOrder>(
        '/dining/orders',
        { table_id: table.id, shift_id: shiftId },
        { params: { branch_id: branch.id } },
      )
      await loadTables()
      await reloadOrder(data.id)
      setSelectedTable((t) => (t ? { ...t, status: 'occupied', active_order_id: data.id } : t))
      notify('success', `Table ${table.name || table.table_number} is open — start ordering!`)
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  async function openParcelOrder() {
    if (!branch) return
    if (!window.confirm('Start a PARCEL (takeaway) order? No table will be occupied.')) return
    // A parcel order has no table; show the order as a "PARCEL" placeholder.
    setSelectedTable({ id: '', table_number: 'PARCEL', name: 'Parcel', capacity: 99, status: 'occupied', is_active: true, active_order_id: null })
    setShowTablePicker(false)
    try {
      const { data } = await apiClient.post<DiningOrder>(
        '/dining/orders',
        { table_id: null, order_type: 'parcel', shift_id: shiftId },
        { params: { branch_id: branch.id } },
      )
      await loadTables()
      await reloadOrder(data.id)
      notify('success', 'Parcel order opened — add dishes & settle at the counter.')
    } catch (err : any) {
      const msg = apiErrorMessage(err)
      setError(msg)
      notify('error', msg)
      setSelectedTable(null)
    }
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

  async function updateItem(item: DiningOrderItem, patch: { quantity?: number; note?: string }) {
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
      if (item.status === 'pending') {
        await apiClient.delete(`/dining/orders/${order.id}/items/${item.id}`)
      } else {
        await apiClient.post(`/dining/orders/${order.id}/items/${item.id}/cancel`, { note: 'Removed from bill' })
      }
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
      notify('success', `${pending.length} item${pending.length > 1 ? 's' : ''} sent to kitchen · ${kot}`)
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

  function openSettle() {
    if (!order || !estimate) return
    setShowSettle(true)
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
      setPayments([{ method: 'cash', amount: 0, received: 0, reference: '' }])
      const sawTable = selectedTable
      setSelectedTable((t) => (t ? { ...t, active_order_id: null, status: 'available' } : t))
      await loadTables()
      notify(
        'success',
        `Bill settled · Invoice ${data.invoice_number}${cashChange > 0 ? ` · change ${inr(cashChange)}` : ''}`,
      )
      if (sawTable) setShowTablePicker(false)
    } catch (err) {
      const msg = apiErrorMessage(err)
      setError(msg)
      notify('error', msg)
    } finally {
      setSettling(false)
    }
  }

  type MenuGroup = {
  category: Category | null
  products: Product[]
  favorites?: boolean
}

const tableMap = useMemo(() => {
    const map = new Map<string, DiningOrder>()
    for (const o of openOrders) if (o.table_id) map.set(o.table_id, o)
    return map
  }, [openOrders])

  const menuGroups: MenuGroup[] = useMemo(() => {
    const q = menuSearch.trim().toLowerCase()
    const nameMatches = (p: Product) =>
      p.name.toLowerCase().includes(q) ||
      p.sku.toLowerCase().includes(q) ||
      (p.barcode ?? '').toLowerCase().includes(q)

    // Any active search filters everything, grouped by category.
    if (q) {
      const filtered = products.filter(nameMatches)
      const byCat = new Map<string | null, Product[]>()
      for (const p of filtered) {
        const key = p.category_id
        if (!byCat.has(key)) byCat.set(key, [])
        byCat.get(key)!.push(p)
      }
      return Array.from(byCat.entries())
        .map(([catId, items]) => ({
          category: categories.find((c) => c.id === catId) ?? null,
          products: items.sort((a, b) => a.name.localeCompare(b.name)),
        }))
        .sort((a, b) => (a.category?.name ?? 'Other').localeCompare(b.category?.name ?? 'Other'))
    }

    // "Favorites" view: only starred items, single flat list.
    if (activeCategory === 'favorites') {
      const favs = products
        .filter((p) => favorites.has(p.id))
        .sort((a, b) => a.name.localeCompare(b.name))
      return [{ category: null, products: favs, favorites: true }]
    }

    // A specific category: show ONLY that category's products.
    if (activeCategory) {
      const items = products
        .filter((p) => p.category_id === activeCategory)
        .sort((a, b) => a.name.localeCompare(b.name))
      return [{ category: categories.find((c) => c.id === activeCategory) ?? null, products: items }]
    }

    // "All dishes": grouped by category sections below.
    const byCat = new Map<string | null, Product[]>()
    for (const p of products) {
      const key = p.category_id
      if (!byCat.has(key)) byCat.set(key, [])
      byCat.get(key)!.push(p)
    }
    return Array.from(byCat.entries())
      .map(([catId, items]) => ({
        category: categories.find((c) => c.id === catId) ?? null,
        products: items.sort((a, b) => a.name.localeCompare(b.name)),
      }))
      .sort((a, b) => (a.category?.name ?? 'Other').localeCompare(b.category?.name ?? 'Other'))
  }, [products, categories, activeCategory, menuSearch, favorites])

  const activeItems = order?.items.filter((i) => i.status !== 'cancelled') ?? []
  const pendingCount = order?.items.filter((i) => i.status === 'pending').length ?? 0
  const readyCount = order?.items.filter((i) => i.status === 'ready').length ?? 0
  const preparingCount = order?.items.filter((i) => i.status === 'preparing').length ?? 0
  const taxTotal = (estimate?.cgst_total ?? 0) + (estimate?.sgst_total ?? 0) + (estimate?.igst_total ?? 0)
  const canSettle = !!order && !!estimate && estimate.grand_total > 0 && order.status === 'open'

  function gradientFor(index: number): string {
    return CATEGORY_GRADIENTS[index % CATEGORY_GRADIENTS.length]
  }

  return (
    <div
      className={`flex min-h-screen flex-col bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-100 ${
        selectedTable && order ? '' : 'pb-24'
      } lg:h-screen lg:overflow-hidden lg:pb-0`}
    >
      {/* Top bar */}
      <header className="sticky top-0 z-30 border-b border-white/10 bg-slate-950/90 backdrop-blur">
        <div className="flex items-center gap-3 px-4 py-3">
          <button
            onClick={() => navigate('/restaurant')}
            className="rounded-lg border border-white/15 px-3 py-2 text-sm font-medium text-slate-200 hover:bg-white/10"
          >
            ← Exit
          </button>
          <div className="min-w-0">
            <h1 className="truncate text-lg font-bold text-white">
              {order && order.order_type === 'parcel'
                ? '📦 Parcel Order'
                : selectedTable
                  ? `Table ${selectedTable.name || selectedTable.table_number}`
                  : 'Restaurant Menu'}
            </h1>
            <p className="truncate text-xs text-slate-400">
              {branch?.name ?? 'No branch'}
              {order ? ` · ${activeItems.length} items` : ''}
            </p>
          </div>

          {!order && (
            <div className="ml-auto flex shrink-0 items-center gap-2">
              <button
                onClick={openParcelOrder}
                className="shrink-0 rounded-lg border border-amber-400/50 bg-amber-500/20 px-4 py-2 text-sm font-bold text-amber-300 hover:bg-amber-500/30"
              >
                📦 Parcel (takeaway)
              </button>
              <button
                onClick={() => setShowTablePicker(true)}
                className="shrink-0 rounded-lg bg-emerald-500 px-4 py-2 text-sm font-bold text-white hover:bg-emerald-400"
              >
                {selectedTable ? `Reorder ${selectedTable.name || selectedTable.table_number}` : 'Pick a table to order'}
              </button>
            </div>
          )}

          {order && (
            <div className="ml-auto flex shrink-0 items-center gap-2">
              <div className="flex gap-1.5">
                <button
                  onClick={() => setShowTablePicker(true)}
                  disabled={busy !== null}
                  className="rounded-lg border border-white/15 px-3 py-2 text-sm font-medium text-slate-200 hover:bg-white/10 disabled:opacity-50"
                >
                  Change table
                </button>
                {pendingCount > 0 && (
                  <button
                    onClick={sendToKitchen}
                    disabled={busy !== null}
                    className="rounded-lg bg-orange-500 px-4 py-2 text-sm font-bold text-white hover:bg-orange-400 disabled:opacity-50"
                  >
                    {busy === 'kitchen' ? 'Sending…' : `Send KOT · ${pendingCount}`}
                  </button>
                )}
                {readyCount > 0 && (
                  <button
                    onClick={() => markServed(order.items.filter((i) => i.status === 'ready').map((i) => i.id))}
                    disabled={busy !== null}
                    className="rounded-lg bg-sky-500 px-4 py-2 text-sm font-bold text-white hover:bg-sky-400 disabled:opacity-50"
                  >
                    Serve {readyCount} ready
                  </button>
                )}
                {preparingCount > 0 && (
                  <button
                    onClick={() => markServed(order.items.filter((i) => i.status === 'preparing').map((i) => i.id))}
                    disabled={busy !== null}
                    className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-bold text-white hover:bg-emerald-500 disabled:opacity-50"
                  >
                    Serve {preparingCount} preparing
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </header>

      {error && (
        <div className="mx-4 mt-3 rounded-lg border border-red-500/40 bg-red-500/15 px-4 py-2 text-sm text-red-200">
          {error}
        </div>
      )}
      {toast && (
        <div
          className={`mx-4 mt-3 rounded-lg border px-4 py-2 text-sm font-medium shadow-lg ${
            toast.kind === 'success'
              ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-200'
              : 'border-red-500/40 bg-red-500/15 text-red-200'
          }`}
        >
          {toast.text}
        </div>
      )}

      {/* Body */}
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row lg:gap-0">
        <main className="min-h-0 flex-1 overflow-y-auto p-4">
          {/* Category chips (a la food-delivery apps) */}
          <div className="sticky top-0 z-20 -mx-4 mb-4 bg-slate-950/95 px-4 py-3 backdrop-blur">
            <input
              value={menuSearch}
              onChange={(e) => setMenuSearch(e.target.value)}
              placeholder="🔍 Search dish, SKU or barcode…"
              className="mb-3 w-full rounded-xl border border-white/15 bg-white/10 px-4 py-2.5 text-sm text-white placeholder-slate-400 outline-none focus:border-emerald-400"
            />
            <div className="flex gap-2 overflow-x-auto pb-1">
              <button
                onClick={() => {
                  setActiveCategory(null)
                  setMenuSearch('')
                }}
                className={`shrink-0 rounded-full px-4 py-2 text-sm font-semibold ${
                  activeCategory === null && !menuSearch
                    ? 'bg-white text-slate-900'
                    : 'border border-white/15 bg-white/5 text-slate-200 hover:bg-white/10'
                }`}
              >
                All dishes
              </button>
              <button
                onClick={() => {
                  setActiveCategory('favorites')
                  setMenuSearch('')
                }}
                className={`shrink-0 rounded-full px-4 py-2 text-sm font-semibold ${
                  activeCategory === 'favorites'
                    ? 'bg-gradient-to-r from-amber-400 to-orange-500 text-white shadow'
                    : 'border border-white/15 bg-white/5 text-slate-200 hover:bg-white/10'
                }`}
              >
                ★ Favorites{favorites.size > 0 ? ` (${favorites.size})` : ''}
              </button>
              {categories.map((c, i) => (
                <button
                  key={c.id}
                  onClick={() => {
                    setActiveCategory(c.id)
                    setMenuSearch('')
                  }}
                  className={`shrink-0 rounded-full px-4 py-2 text-sm font-semibold ${
                    activeCategory === c.id
                      ? `bg-gradient-to-r ${gradientFor(i)} text-white shadow`
                      : 'border border-white/15 bg-white/5 text-slate-200 hover:bg-white/10'
                  }`}
                >
                  {c.name} ({products.filter((p) => p.category_id === c.id).length})
                </button>
              ))}
            </div>
          </div>

          {loading ? (
            <p className="py-16 text-center text-slate-400">Loading menu…</p>
          ) : products.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-white/20 p-12 text-center text-slate-300">
              <p className="mb-2 text-lg font-semibold">No dishes on the menu yet</p>
              <p className="text-sm text-slate-400">
                Add products in <span className="font-medium text-slate-200">Products</span> and they'll appear here as
                the restaurant menu.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {menuGroups.map((group, gi) => (
                <section key={group.category?.id ?? (group.favorites ? 'favorites' : `uncat-${gi}`)}>
                  <div className="mb-3 flex items-center gap-3">
                    <span
                      className={`h-6 w-6 shrink-0 rounded-lg bg-gradient-to-br ${
                        group.favorites ? 'from-amber-400 to-orange-500' : gradientFor(gi)
                      }`}
                      aria-hidden
                    />
                    <h2 className="text-sm font-bold uppercase tracking-wider text-slate-300">
                      {group.favorites ? '★ Your favorites' : (group.category?.name ?? 'Other')}
                    </h2>
                    <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs text-slate-300">
                      {group.products.length}
                    </span>
                  </div>
{group.products.length === 0 ? (
                      <p className="rounded-2xl border border-dashed border-white/20 p-10 text-center text-sm text-slate-400">
                        {group.favorites
                          ? 'Star dishes you love to see them here for one-tap reordering. Tap the ★ on any dish card to save it.'
                          : 'No dishes in this category yet.'}
                      </p>
                    ) : (
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
                      {group.products.map((p, pi) => (
                        <MenuCard
                          key={p.id}
                          product={p}
                          accent={gradientFor((pi % categories.length) + gi)}
                          orderOpen={!!order}
                          busy={busy === 'add'}
                          isFavorite={favorites.has(p.id)}
                          onToggleFavorite={toggleFavorite}
                          onAdd={addProduct}
                        />
                      ))}
                    </div>
                  )}
                </section>
              ))}
              {menuSearch.trim() && menuGroups.every((g) => g.products.length === 0) && (
                <p className="py-12 text-center text-slate-400">No dishes match “{menuSearch}”.</p>
              )}
            </div>
          )}
        </main>

        {/* Right order cart */}
        <aside className="flex min-h-0 w-full shrink-0 flex-col border-t border-white/10 bg-slate-950/80 lg:w-[380px] lg:border-l lg:border-t-0">
          <OrderCart
            order={order}
            estimate={estimate}
            table={selectedTable}
            taxTotal={taxTotal}
            busy={busy}
            itemStatusStyles={ITEM_STATUS_STYLES}
            pendingCount={pendingCount}
            preparingCount={preparingCount}
            readyCount={readyCount}
            canSettle={canSettle}
            onUpdateItem={updateItem}
            onRemoveItem={removeItem}
            onSendKot={sendToKitchen}
            onServeReady={
              readyCount > 0
                ? () => markServed(order?.items.filter((i) => i.status === 'ready').map((i) => i.id) ?? [])
                : undefined
            }
            onSettle={openSettle}
            onPickTable={() => setShowTablePicker(true)}
          />
        </aside>
      </div>

      {/* Table picker */}
      {showTablePicker && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm">
          <div className="flex max-h-[85vh] w-full max-w-3xl flex-col rounded-2xl border border-white/10 bg-slate-900 p-5 shadow-2xl">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-white">Pick a table</h2>
                <p className="text-xs text-slate-400">Free tables open a new order · occupied tables continue billing</p>
              </div>
              <button
                onClick={() => setShowTablePicker(false)}
                className="rounded-lg border border-white/15 px-3 py-1.5 text-sm text-slate-300 hover:bg-white/10"
              >
                Close
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto">
            <div className="mb-3 rounded-2xl border-2 border-dashed border-amber-400/60 bg-amber-500/10 p-4">
              <p className="text-sm font-bold text-amber-300">📦 Parcel / Takeaway</p>
              <p className="mb-3 text-xs text-slate-400">No table needed — fast counter order for walk-in cash customers.</p>
              <button
                onClick={openParcelOrder}
                className="rounded-xl bg-amber-500 px-4 py-2.5 text-sm font-bold text-white hover:bg-amber-400"
              >
                Start parcel order
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
              {tables
                .filter((t) => t.is_active)
                .map((t) => {
                  const style = TABLE_STATUS_STYLES[t.status]
                  const currentOrder = tableMap.get(t.id)
                  const selected = selectedTable?.id === t.id
                  return (
                    <button
                      key={t.id}
                      onClick={() => {
                        const o = tableMap.get(t.id)
                        if (t.status === 'available') openOrderFor(t)
                        else if (t.active_order_id && o) selectTable(t)
                        else if (t.is_active && t.status !== 'cleaning') openOrderFor(t)
                      }}
                      className={`rounded-2xl border-2 p-4 text-left transition ${
                        selected ? 'ring-2 ring-white' : ''
                      } ${style.card}`}
                    >
                      <div className="flex items-center justify-between">
                        <p className="text-lg font-bold text-white">{t.name || t.table_number}</p>
                        <span className="rounded-full bg-black/30 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">
                          {style.label}
                        </span>
                      </div>
                      <p className="text-xs text-white/80">
                        {t.capacity} seats
                        {currentOrder ? ` · ${currentOrder.items.length} items` : ''}
                      </p>
                      {currentOrder && (
                        <p className="mt-1 text-sm font-semibold text-white">
                          {inr(currentOrder.subtotal - currentOrder.discount_total)}
                        </p>
                      )}
                    </button>
                  )
                })}
              {tables.filter((t) => t.is_active).length === 0 && (
                <p className="col-span-full py-10 text-center text-slate-400">No tables yet — add one in Restaurant.</p>
              )}
            </div>
            </div>
          </div>
        </div>
      )}

      {showSettle && order && estimate && (
        <SettleModal
          order={order}
          estimate={estimate}
          payments={payments}
          onPayments={setPayments}
          totalPaid={payments.reduce((s, p) => s + p.amount, 0)}
          cashChange={payments
            .filter((p) => p.method === 'cash')
            .reduce((s, p) => s + Math.max(0, (p.received || p.amount) - p.amount), 0)}
          settling={settling}
          onClose={() => setShowSettle(false)}
          onComplete={() =>
            completeSettlement(
              payments.filter((p) => p.method === 'cash').reduce((s, p) => s + Math.max(0, (p.received || p.amount) - p.amount), 0),
            )
          }
        />
      )}
    </div>
  )
}

/* ---------------- Menu card ---------------- */

function MenuCard({
  product,
  accent,
  orderOpen,
  busy,
  isFavorite,
  onToggleFavorite,
  onAdd,
}: {
  product: Product
  accent: string
  orderOpen: boolean
  busy: boolean
  isFavorite: boolean
  onToggleFavorite: (productId: string) => void
  onAdd: (p: Product) => void
}) {
  const enabled = product.is_active && orderOpen
  return (
    <div
      className={`group relative flex flex-col overflow-hidden rounded-2xl border text-left transition ${
        enabled
          ? 'border-white/10 bg-slate-900 hover:-translate-y-0.5 hover:border-emerald-400/60 hover:shadow-xl hover:shadow-emerald-500/10'
          : 'cursor-not-allowed border-white/10 bg-slate-900/70 opacity-60'
      }`}
    >
      <button
        onClick={() => enabled && !busy && onAdd(product)}
        disabled={!enabled || busy}
        title={product.is_active ? (orderOpen ? `Add ${product.name}` : 'Open a table first') : 'Unavailable'}
        className="block w-full text-left"
      >
        <div className="relative aspect-[4/3] w-full overflow-hidden bg-slate-800">
          {product.image_path ? (
            <img
              src={`/api/v1/catalog/products/${product.id}/image.png`}
              alt={product.name}
              loading="lazy"
              className="h-full w-full object-cover transition duration-300 group-hover:scale-105"
              onError={(e) => {
                // Broken/missing file: fall back to the gradient tile below.
                ;(e.currentTarget as HTMLImageElement).style.display = 'none'
              }}
            />
          ) : (
            <span className={`block h-full w-full bg-gradient-to-br ${accent}`} />
          )}
          <span className={`absolute inset-x-0 top-0 h-1.5 bg-gradient-to-r ${accent}`} />
          {orderOpen && (
            <span className="absolute bottom-2 right-2 rounded-full bg-emerald-500/90 px-2 py-0.5 text-[10px] font-bold text-white opacity-0 transition group-hover:opacity-100">
              Add +
            </span>
          )}
        </div>
        <div className="flex flex-1 flex-col p-3">
          <p className="line-clamp-2 text-sm font-semibold text-white">{product.name}</p>
          {product.sku && <p className="mt-0.5 text-[10px] text-slate-500">{product.sku}</p>}
          <div className="mt-auto flex items-end justify-between pt-3">
            <span className="text-lg font-bold text-emerald-400">{inr(product.sale_price)}</span>
            {!product.is_active && (
              <span className="rounded bg-white/10 px-1.5 py-0.5 text-[10px] text-slate-300">Off</span>
            )}
          </div>
          {product.tax_rate_percent ? <p className="text-[10px] text-slate-500">{product.tax_rate_percent}% GST</p> : null}
        </div>
      </button>
      <button
        onClick={() => onToggleFavorite(product.id)}
        title={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
        aria-pressed={isFavorite}
        className={`absolute right-2 top-2 flex h-8 w-8 items-center justify-center rounded-full text-base shadow-lg transition ${
          isFavorite ? 'bg-amber-400 text-white' : 'bg-slate-950/60 text-slate-200 hover:bg-amber-400 hover:text-white'
        }`}
      >
        {isFavorite ? '★' : '☆'}
      </button>
    </div>
  )
}

/* ---------------- Order cart ---------------- */

function OrderCart({
  order,
  estimate,
  table,
  taxTotal,
  busy,
  itemStatusStyles,
  pendingCount,
  preparingCount,
  readyCount,
  canSettle,
  onUpdateItem,
  onRemoveItem,
  onSendKot,
  onServeReady,
  onSettle,
  onPickTable,
}: {
  order: DiningOrder | null
  estimate: DiningOrderEstimate | null
  table: DiningTable | null
  taxTotal: number
  busy: string | null
  itemStatusStyles: Record<string, string>
  pendingCount: number
  preparingCount: number
  readyCount: number
  canSettle: boolean
  onUpdateItem: (item: DiningOrderItem, patch: { quantity?: number; note?: string }) => void
  onRemoveItem: (item: DiningOrderItem) => void
  onSendKot: () => void
  onServeReady: (() => void) | undefined
  onSettle: () => void
  onPickTable: () => void
}) {
  const activeItems = order?.items.filter((i) => i.status !== 'cancelled') ?? []
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="shrink-0 border-b border-white/10 p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-300">
            Current bill ·{' '}
            {order
              ? order.order_type === 'parcel'
                ? '📦 PARCEL'
                : `Table ${order.table_number}`
              : table
                ? `Table ${table.name || table.table_number}`
                : 'no table'}
          </h2>
          <span className="rounded-full bg-white/10 px-2.5 py-0.5 text-xs font-semibold text-slate-200">
            {activeItems.length} item{activeItems.length !== 1 ? 's' : ''}
          </span>
        </div>
        {order && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {pendingCount > 0 && (
              <span className="rounded-full bg-white/10 px-2 py-0.5 text-[11px] font-semibold text-slate-200">
                {pendingCount} pending
              </span>
            )}
            {preparingCount > 0 && (
              <span className="rounded-full bg-orange-500/20 px-2 py-0.5 text-[11px] font-semibold text-orange-300">
                {preparingCount} preparing
              </span>
            )}
            {readyCount > 0 && (
              <span className="rounded-full bg-sky-500/20 px-2 py-0.5 text-[11px] font-semibold text-sky-300">
                {readyCount} ready
              </span>
            )}
          </div>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {!order && (
          <div className="flex h-full flex-col items-center justify-center py-10 text-center">
            <p className="mb-4 text-sm text-slate-400">
              No order yet. Pick a table and tap dishes to build the bill.
            </p>
            <button
              onClick={onPickTable}
              className="rounded-xl bg-emerald-500 px-6 py-3 text-sm font-bold text-white hover:bg-emerald-400"
            >
              Pick a table
            </button>
          </div>
        )}

        {order && activeItems.length === 0 && (
          <p className="py-6 text-center text-sm text-slate-400">No dishes yet — tap a menu card to add.</p>
        )}

        {activeItems.length > 0 && (
          <div className="space-y-2">
            {activeItems.map((item) => {
              const editable = item.status === 'pending'
              return (
                <div key={item.id} className="rounded-xl border border-white/10 bg-slate-900 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="min-w-0 truncate text-sm font-medium text-white">{item.product_name}</p>
                    <span className={`shrink-0 rounded px-1.5 py-0.5 text-[9px] font-bold uppercase ${itemStatusStyles[item.status]}`}>
                      {item.status}
                    </span>
                  </div>
                  {item.kot_number && <p className="text-[11px] text-slate-500">{item.kot_number}</p>}
                  <div className="mt-2 flex items-center gap-1.5">
                    {editable && (
                      <>
                        <button
                          disabled={busy !== null}
                          onClick={() => onUpdateItem(item, { quantity: Math.max(1, item.quantity - 1) })}
                          className="h-8 w-8 rounded-lg border border-white/15 text-white hover:bg-white/10 disabled:opacity-50"
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
                            if (Number.isFinite(qty) && qty > 0) onUpdateItem(item, { quantity: qty })
                          }}
                          className="h-8 w-12 rounded-lg border border-white/15 bg-slate-800 text-center text-sm text-white"
                        />
                        <button
                          disabled={busy !== null}
                          onClick={() => onUpdateItem(item, { quantity: item.quantity + 1 })}
                          className="h-8 w-8 rounded-lg border border-white/15 text-white hover:bg-white/10 disabled:opacity-50"
                        >
                          +
                        </button>
                      </>
                    )}
                    <span className="ml-auto text-sm font-semibold text-white">{inr(item.line_total)}</span>
                    <button
                      disabled={busy !== null}
                      onClick={() => onRemoveItem(item)}
                      className="h-8 w-8 rounded-lg text-red-400 hover:bg-red-500/20 disabled:opacity-50"
                      title={item.status === 'pending' ? 'Remove' : 'Void (remove from bill)'}
                    >
                      ✕
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      <div className="shrink-0 border-t border-white/10 p-4">
        {order && estimate && (
          <div className="mb-3 space-y-1 text-sm text-slate-300">
            <div className="flex justify-between">
              <span>Subtotal</span>
              <span>{inr(estimate.subtotal)}</span>
            </div>
            {estimate.discount_total > 0 && (
              <div className="flex justify-between">
                <span>Discount</span>
                <span className="text-emerald-400">− {inr(estimate.discount_total)}</span>
              </div>
            )}
            {taxTotal > 0 && (
              <div className="flex justify-between">
                <span>GST (CGST+SGST)</span>
                <span>{inr(taxTotal)}</span>
              </div>
            )}
            {estimate.round_off !== 0 && (
              <div className="flex justify-between">
                <span>Round off</span>
                <span>{estimate.round_off > 0 ? `+ ${inr(estimate.round_off)}` : `− ${inr(Math.abs(estimate.round_off))}`}</span>
              </div>
            )}
            <div className="flex justify-between border-t border-white/10 pt-2 text-base font-bold text-white">
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
                className="w-full rounded-xl bg-orange-500 px-4 py-3 text-base font-bold text-white hover:bg-orange-400 disabled:opacity-50"
              >
                {busy === 'kitchen' ? 'Sending KOT…' : `SEND KOT · ${pendingCount} pending`}
              </button>
            )}
            {onServeReady && (
              <button
                onClick={onServeReady}
                disabled={busy !== null}
                className="w-full rounded-xl bg-sky-500 px-4 py-2.5 text-sm font-bold text-white hover:bg-sky-400 disabled:opacity-50"
              >
                Serve {readyCount} ready
              </button>
            )}
            <button
              onClick={onSettle}
              disabled={!canSettle || busy !== null}
              className="w-full rounded-xl bg-emerald-500 px-4 py-3.5 text-base font-bold text-white shadow-lg shadow-emerald-500/20 hover:bg-emerald-400 disabled:opacity-40"
            >
              {estimate ? `SETTLE · ${inr(estimate.grand_total)}` : 'SETTLE PAYMENT'}
            </button>
          </div>
        ) : (
          order && <p className="text-center text-sm font-medium text-slate-400">Order {order.status}.</p>
        )}
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
      className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm"
      onClick={settling ? undefined : onClose}
    >
      <div className="w-full max-w-md rounded-2xl bg-slate-900 p-5 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-white">Settle bill</h2>
            <p className="text-xs text-slate-400">
              Table {order.table_number} · {order.items.filter((i) => i.status !== 'cancelled').length} items
            </p>
          </div>
          <div className="text-right">
            <p className="text-base font-bold text-emerald-400">{inr(estimate.grand_total)}</p>
            <p className="text-xs text-slate-400">Total (incl. GST)</p>
          </div>
        </div>

        <div className="mb-4 max-h-[45vh] space-y-2 overflow-y-auto">
          {payments.map((p, i) => {
            const lineChange = p.method === 'cash' ? Math.max(0, (p.received || p.amount) - p.amount) : 0
            return (
              <div key={i} className="rounded-xl border border-white/10 p-3">
                <div className="flex gap-2">
                  <select
                    value={p.method}
                    disabled={settling}
                    onChange={(e) => {
                      const method = e.target.value as PaymentRow['method']
                      onPayments(payments.map((row, idx) => (idx === i ? { ...row, method, received: row.amount } : row)))
                    }}
                    className="rounded-lg border border-white/15 bg-slate-800 px-2 py-2 text-sm text-white"
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
                    className="w-24 rounded-lg border border-white/15 bg-slate-800 px-2 py-2 text-sm text-white"
                  />
                  {payments.length > 1 && (
                    <button
                      onClick={() => onPayments(payments.filter((_, idx) => idx !== i))}
                      disabled={settling}
                      className="rounded p-1 text-red-400 hover:bg-red-500/20"
                    >
                      ✕
                    </button>
                  )}
                  {i === payments.length - 1 && (
                    <button
                      onClick={() => onPayments([...payments, { method: 'cash', amount: 0, received: 0, reference: '' }])}
                      disabled={settling}
                      className="ml-auto shrink-0 rounded-lg bg-white/10 px-2.5 py-1.5 text-xs font-medium text-slate-200 hover:bg-white/15 disabled:opacity-50"
                    >
                      + Split
                    </button>
                  )}
                </div>
                {p.method === 'cash' && (
                  <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
                    <label className="block">
                      <span className="mb-0.5 block text-[11px] text-slate-400">Received</span>
                      <input
                        type="number"
                        min={0}
                        step="0.01"
                        value={p.received || ''}
                        disabled={settling}
                        onChange={(e) =>
                          onPayments(payments.map((row, idx) => (idx === i ? { ...row, received: Number(e.target.value) } : row)))
                        }
                        className="w-full rounded-lg border border-white/15 bg-slate-800 px-2 py-1.5 text-sm text-white"
                      />
                    </label>
                    <label className="block">
                      <span className="mb-0.5 block text-[11px] text-slate-400">Change</span>
                      <input
                        type="text"
                        value={inr(lineChange)}
                        disabled
                        className="w-full rounded-lg border border-white/10 bg-slate-800 px-2 py-1.5 text-sm font-medium text-white"
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
                    className="mt-2 w-full rounded-lg border border-white/15 bg-slate-800 px-2 py-1.5 text-sm text-white placeholder-slate-500"
                  />
                )}
              </div>
            )
          })}
        </div>

        <div className="mb-4 space-y-1 border-t border-white/10 pt-3 text-sm">
          <div className="flex justify-between">
            <span>Collected</span>
            <span>{inr(totalPaid)}</span>
          </div>
          {balanceLeft > 0 && (
            <div className="flex justify-between font-medium text-amber-400">
              <span>Still due</span>
              <span>{inr(balanceLeft)}</span>
            </div>
          )}
          {cashChange > 0 && (
            <div className="flex justify-between font-medium text-emerald-400">
              <span>Cash change</span>
              <span>{inr(cashChange)}</span>
            </div>
          )}
        </div>

        <div className="flex gap-2">
          <button
            onClick={onClose}
            disabled={settling}
            className="rounded-xl border border-white/15 px-4 py-2.5 text-sm font-semibold text-slate-300 hover:bg-white/10 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={onComplete}
            disabled={settling || !fullyPaid}
            className="flex-1 rounded-xl bg-emerald-500 px-4 py-2.5 text-base font-bold text-white hover:bg-emerald-400 disabled:opacity-50"
          >
            {settling ? 'POSTING INVOICE…' : 'COMPLETE PAYMENT'}
          </button>
        </div>
        {!fullyPaid && !settling && <p className="mt-2 text-center text-xs text-slate-400">Cover the full bill before posting.</p>}
      </div>
    </div>
  )
}