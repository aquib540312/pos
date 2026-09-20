import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiClient, apiErrorMessage } from '../api/client'
import type { CartLine, Customer, FeatureFlags, OrgProfile, PaymentGatewayTransaction, PaymentLine, Product, SaleInvoice } from '../types'

interface Warehouse {
  id: string
  code: string
  name: string
  is_default: boolean
}
interface Branch {
  id: string
  code: string
  name: string
  warehouses: Warehouse[]
}

const PAYMENT_METHODS: PaymentLine['method'][] = ['cash', 'card', 'bank_transfer', 'credit']

function getProductPrice(product: Product, customerPriceLevel: string | null): number {
  if (!customerPriceLevel || customerPriceLevel === 'retail') return product.sale_price
  switch (customerPriceLevel) {
    case 'wholesale': return product.wholesale_price || product.sale_price
    case 'restaurant': return product.restaurant_price || product.sale_price
    case 'vip': return product.vip_price || product.sale_price
    default: return product.sale_price
  }
}

// Mirrors the backend's Decimal ROUND_HALF_UP (see vat/service.py) closely
// enough for typical retail amounts, so the default payment amount we
// suggest matches what the server will actually compute. The server
// remains authoritative -- this is only a convenience default, and the
// "Balance due" indicator will catch the rare sub-cent mismatch case
// (component-level VAT rounding can differ from a single combined
// rounding by up to Re.0.01) before the cashier submits.
function roundHalfUp(value: number, decimals: number): number {
  const factor = 10 ** decimals
  return (Math.sign(value) || 1) * Math.round(Math.abs(value) * factor + Number.EPSILON) / factor
}

export default function POSPage() {
  const [branch, setBranch] = useState<Branch | null>(null)
  const [cart, setCart] = useState<CartLine[]>([])
  const [barcodeInput, setBarcodeInput] = useState('')
  const [searchResults, setSearchResults] = useState<Product[]>([])
  const [customerQuery, setCustomerQuery] = useState('')
  const [customerResults, setCustomerResults] = useState<Customer[]>([])
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [isCreditSale, setIsCreditSale] = useState(false)
  const [payments, setPayments] = useState<PaymentLine[]>([{ method: 'cash', amount: 0 }])
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [completedInvoice, setCompletedInvoice] = useState<SaleInvoice | null>(null)
  const [autoPrint, setAutoPrint] = useState(false)
  const barcodeRef = useRef<HTMLInputElement>(null)

  const [features, setFeatures] = useState<FeatureFlags | null>(null)
  const [saleSessionId, setSaleSessionId] = useState(0)
  // Guards against the payment panel's onPaid firing more than once (e.g. a
  // stray extra poll tick) from ever resulting in two POST /sales calls
  // for the same paid transaction.
  const finalizingRef = useRef(false)

  const [couponCodeInput, setCouponCodeInput] = useState('')
  const [appliedCoupon, setAppliedCoupon] = useState<{ code: string; discount: number } | null>(null)
  const [couponError, setCouponError] = useState<string | null>(null)
  const [checkingCoupon, setCheckingCoupon] = useState(false)
  const [giftCardNumber, setGiftCardNumber] = useState('')
  const [giftCardAmount, setGiftCardAmount] = useState(0)
  const [openShiftId, setOpenShiftId] = useState<string | null>(null)

  useEffect(() => {
    apiClient.get<Branch[]>('/org/branches').then((res) => setBranch(res.data[0] ?? null))
    apiClient.get<FeatureFlags>('/org/features').then((res) => setFeatures(res.data)).catch(() => setFeatures(null))
    barcodeRef.current?.focus()
  }, [])

  useEffect(() => {
    if (!branch) return
    // Best-effort: a cashier without an open shift can still bill (this
    // doesn't gate checkout), but a sale tagged with the current shift is
    // what makes the Shift page's cash-drawer reconciliation reflect real
    // sales instead of always reading zero.
    apiClient
      .get<{ id: string } | null>('/billing/shifts/current', { params: { branch_id: branch.id } })
      .then((res) => setOpenShiftId(res.data?.id ?? null))
      .catch(() => setOpenShiftId(null))
  }, [branch])

  const warehouse = branch?.warehouses.find((w) => w.is_default) ?? branch?.warehouses[0]

  useEffect(() => {
    setCart((prev) =>
      prev.map((l) => ({
        ...l,
        unitPrice: getProductPrice(l.product, customer?.price_level ?? null),
      })),
    )
  }, [customer])

  // Client-side preview -- the server recomputes and is authoritative
  // (stock could be gone, or a rate could change, between preview and
  // submit), but using each product's real tax_rate_percent keeps this
  // preview exact enough to auto-suggest the payment amount.
  const estimate = useMemo(() => {
    let taxable = 0
    let tax = 0
    for (const line of cart) {
      const gross = line.quantity * line.unitPrice
      const lineTaxable = roundHalfUp(Math.max(0, gross - line.discountAmount), 2)
      const lineTax = roundHalfUp((lineTaxable * (line.product.tax_rate_percent ?? 0)) / 100, 2)
      taxable += lineTaxable
      tax += lineTax
    }
    const preDiscount = taxable + tax
    const couponDiscount = appliedCoupon?.discount ?? 0
    const grandTotalEstimate = Math.max(0, roundHalfUp(preDiscount, 0) - couponDiscount)
    return { taxable, tax, grandTotalEstimate }
  }, [cart, appliedCoupon])

  // Keep the default single cash payment in sync with the live estimate
  // (net of gift card redemption) so the common case needs no manual
  // entry; split-tender users editing multiple rows are left alone.
  useEffect(() => {
    const dueAfterGiftCard = Math.max(0, estimate.grandTotalEstimate - (giftCardAmount || 0))
    setPayments((prev) => (prev.length === 1 ? [{ ...prev[0], amount: dueAfterGiftCard }] : prev))
  }, [estimate.grandTotalEstimate, giftCardAmount])

  async function applyCoupon() {
    if (!couponCodeInput) return
    setCheckingCoupon(true)
    setCouponError(null)
    try {
      const res = await apiClient.post('/loyalty/coupons/validate', {
        code: couponCodeInput,
        order_value: estimate.taxable,
      })
      if (res.data.valid) {
        setAppliedCoupon({ code: couponCodeInput, discount: res.data.discount_amount })
      } else {
        setAppliedCoupon(null)
        setCouponError(res.data.reason ?? 'Coupon is not valid')
      }
    } catch (err) {
      setAppliedCoupon(null)
      setCouponError(apiErrorMessage(err))
    } finally {
      setCheckingCoupon(false)
    }
  }

  const paymentTotal = payments.reduce((sum, p) => sum + (Number.isFinite(p.amount) ? p.amount : 0), 0)
  const balanceDue = Math.max(0, estimate.grandTotalEstimate - paymentTotal)

  async function searchProducts(q: string) {
    setBarcodeInput(q)
    if (!q) {
      setSearchResults([])
      return
    }
    try {
      const res = await apiClient.get<Product[]>('/catalog/products', { params: { search: q } })
      setSearchResults(res.data)
    } catch {
      setSearchResults([])
    }
  }

  async function handleBarcodeEnter() {
    if (!barcodeInput) return
    try {
      const res = await apiClient.get<Product>(`/catalog/products/barcode/${encodeURIComponent(barcodeInput)}`)
      addToCart(res.data)
      setBarcodeInput('')
      setSearchResults([])
    } catch {
      // not a barcode match; leave the search dropdown results for manual pick
    }
  }

  function addToCart(product: Product) {
    setCart((prev) => {
      const existing = prev.find((l) => l.product.id === product.id)
      if (existing) {
        return prev.map((l) => (l.product.id === product.id ? { ...l, quantity: l.quantity + 1 } : l))
      }
      return [...prev, { product, quantity: 1, discountAmount: 0, unitPrice: getProductPrice(product, customer?.price_level ?? null) }]
    })
    setSearchResults([])
    setBarcodeInput('')
    barcodeRef.current?.focus()
  }

  function updateLine(productId: string, patch: Partial<CartLine>) {
    setCart((prev) => prev.map((l) => (l.product.id === productId ? { ...l, ...patch } : l)))
  }

  function removeLine(productId: string) {
    setCart((prev) => prev.filter((l) => l.product.id !== productId))
  }

  async function searchCustomers(q: string) {
    setCustomerQuery(q)
    if (!q) {
      setCustomerResults([])
      return
    }
    try {
      const res = await apiClient.get<Customer[]>('/party/customers', { params: { search: q } })
      setCustomerResults(res.data)
    } catch {
      setCustomerResults([])
    }
  }

  function updatePayment(index: number, patch: Partial<PaymentLine>) {
    setPayments((prev) => prev.map((p, i) => (i === index ? { ...p, ...patch } : p)))
  }

  function resetForNewSale() {
    setCart([])
    setCustomer(null)
    setIsCreditSale(false)
    setPayments([{ method: 'cash', amount: 0 }])
    setCouponCodeInput('')
    setAppliedCoupon(null)
    setCouponError(null)
    setGiftCardNumber('')
    setGiftCardAmount(0)
    setSaleSessionId((id) => id + 1)
  }

  async function submitSale(gatewayTransactionId?: string) {
    if (!branch || !warehouse) {
      setError('No branch/warehouse configured.')
      return
    }
    if (cart.length === 0) {
      setError('Cart is empty.')
      return
    }
    setError(null)
    setSubmitting(true)
    try {
      const res = await apiClient.post<SaleInvoice>('/sales', {
        branch_id: branch.id,
        warehouse_id: warehouse.id,
        customer_id: customer?.id ?? null,
        is_credit_sale: isCreditSale,
        items: cart.map((l) => ({
          product_id: l.product.id,
          quantity: l.quantity,
          unit_price: l.unitPrice,
          discount_amount: l.discountAmount,
        })),
        payments: isCreditSale || gatewayTransactionId ? [] : payments.filter((p) => p.amount > 0),
        coupon_code: appliedCoupon?.code ?? null,
        gift_card_number: giftCardNumber || null,
        gift_card_amount: giftCardNumber ? giftCardAmount : 0,
        payment_gateway_transaction_id: gatewayTransactionId ?? null,
        shift_id: openShiftId,
      })
      setCompletedInvoice(res.data)
      setAutoPrint(Boolean(gatewayTransactionId))
      resetForNewSale()
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  function completeSale() {
    return submitSale()
  }

  async function finalizeWithGatewayTransaction(transaction: PaymentGatewayTransaction) {
    if (finalizingRef.current) return
    finalizingRef.current = true
    try {
      await submitSale(transaction.id)
    } finally {
      finalizingRef.current = false
    }
  }

  if (completedInvoice) {
    return (
      <Receipt
        invoice={completedInvoice}
        autoPrint={autoPrint}
        onNewSale={() => {
          setCompletedInvoice(null)
          setAutoPrint(false)
        }}
      />
    )
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <div className="lg:col-span-2">
        <h1 className="mb-4 text-2xl font-semibold text-slate-900 dark:text-slate-50">Billing</h1>

        {!openShiftId && (
          <div className="mb-4 flex items-center justify-between rounded-lg border border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
            <span>No shift open -- cash sales won't be reflected in cash-drawer reconciliation.</span>
            <Link to="/shift" className="font-medium underline">
              Open one
            </Link>
          </div>
        )}

        <div className="relative mb-4">
          <input
            ref={barcodeRef}
            value={barcodeInput}
            onChange={(e) => searchProducts(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleBarcodeEnter()}
            placeholder="Scan barcode or search product by name..."
            className="w-full rounded-lg border border-slate-300 px-4 py-3 text-base dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
          />
          {searchResults.length > 0 && (
            <ul className="absolute z-10 mt-1 max-h-64 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-800">
              {searchResults.map((p) => (
                <li key={p.id}>
                  <button
                    onClick={() => addToCart(p)}
                    className="flex w-full items-center justify-between px-4 py-2 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-700"
                  >
                    <span>
                      {p.name} <span className="text-slate-400">({p.sku})</span>
                      {p.barcode && <span className="ml-1 text-xs text-slate-400">[{p.barcode}]</span>}
                      {p.variant_label && <span className="ml-1 rounded bg-slate-200 px-1.5 py-0.5 text-xs dark:bg-slate-700">{p.variant_label}</span>}
                      {p.is_weighted && <span className="ml-1 text-xs text-indigo-500">weight</span>}
                    </span>
                    <span className="font-medium">SAR {getProductPrice(p, customer?.price_level ?? null).toFixed(2)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
              <tr>
                <th className="px-3 py-2">Product</th>
                <th className="px-3 py-2">Qty</th>
                <th className="px-3 py-2">Price</th>
                <th className="px-3 py-2">Discount</th>
                <th className="px-3 py-2">Total</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {cart.map((line) => {
                const lineTotal = Math.max(0, line.quantity * line.unitPrice - line.discountAmount)
                return (
                  <tr key={line.product.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                    <td className="px-3 py-2 font-medium text-slate-900 dark:text-slate-100">{line.product.name}</td>
                    <td className="px-3 py-2">
                      <input
                        type="number"
                        min={0.001}
                        step={line.product.is_weighted ? 0.001 : 1}
                        value={line.quantity}
                        onChange={(e) => {
                          const qty = Math.max(0.001, Number(e.target.value) || 0.001)
                          updateLine(line.product.id, { quantity: qty })
                        }}
                        className="w-20 rounded border border-slate-300 px-2 py-1 dark:border-slate-600 dark:bg-slate-700"
                      />
                    </td>
                    <td className="px-3 py-2 text-slate-600 dark:text-slate-300">SAR {line.unitPrice.toFixed(2)}</td>
                    <td className="px-3 py-2">
                      <input
                        type="number"
                        min={0}
                        step="0.01"
                        value={line.discountAmount}
                        onChange={(e) => updateLine(line.product.id, { discountAmount: Number(e.target.value) })}
                        className="w-20 rounded border border-slate-300 px-2 py-1 dark:border-slate-600 dark:bg-slate-700"
                      />
                    </td>
                    <td className="px-3 py-2 font-medium">SAR {lineTotal.toFixed(2)}</td>
                    <td className="px-3 py-2">
                      <button onClick={() => removeLine(line.product.id)} className="text-red-500 hover:text-red-600">✕</button>
                    </td>
                  </tr>
                )
              })}
              {cart.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-3 py-8 text-center text-slate-400">Cart is empty. Scan or search a product.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="space-y-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-800">
          <h2 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-300">Customer</h2>
          {customer ? (
            <div className="flex items-center justify-between text-sm">
              <span>{customer.name}{customer.is_credit_customer ? ' (credit)' : ''}</span>
              <button onClick={() => setCustomer(null)} className="text-red-500">Remove</button>
            </div>
          ) : (
            <div className="relative">
              <input
                value={customerQuery}
                onChange={(e) => searchCustomers(e.target.value)}
                placeholder="Search customer (optional)..."
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
              />
              {customerResults.length > 0 && (
                <ul className="absolute z-10 mt-1 max-h-48 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-800">
                  {customerResults.map((c) => (
                    <li key={c.id}>
                      <button
                        onClick={() => {
                          setCustomer(c)
                          setCustomerResults([])
                          setCustomerQuery('')
                        }}
                        className="block w-full px-3 py-2 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-700"
                      >
                        {c.name} {c.phone && `(${c.phone})`}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {customer?.is_credit_customer && (
            <label className="mt-3 flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
              <input type="checkbox" checked={isCreditSale} onChange={(e) => setIsCreditSale(e.target.checked)} />
              Bill on credit
            </label>
          )}
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-800">
          <h2 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-300">Coupon</h2>
          {appliedCoupon ? (
            <div className="flex items-center justify-between text-sm">
              <span className="text-emerald-600">
                {appliedCoupon.code} applied (-SAR {appliedCoupon.discount.toFixed(2)})
              </span>
              <button
                onClick={() => {
                  setAppliedCoupon(null)
                  setCouponCodeInput('')
                }}
                className="text-red-500"
              >
                Remove
              </button>
            </div>
          ) : (
            <div className="flex gap-2">
              <input
                value={couponCodeInput}
                onChange={(e) => {
                  setCouponCodeInput(e.target.value.toUpperCase())
                  setCouponError(null)
                }}
                placeholder="Coupon code"
                className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
              />
              <button
                onClick={applyCoupon}
                disabled={checkingCoupon || !couponCodeInput}
                className="rounded-lg bg-slate-800 px-3 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50 dark:bg-slate-600"
              >
                {checkingCoupon ? '...' : 'Apply'}
              </button>
            </div>
          )}
          {couponError && <p className="mt-1 text-xs text-red-600 dark:text-red-400">{couponError}</p>}
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-800">
          <h2 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-300">Gift Card (optional)</h2>
          <div className="flex gap-2">
            <input
              value={giftCardNumber}
              onChange={(e) => setGiftCardNumber(e.target.value)}
              placeholder="Card number"
              className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
            <input
              type="number"
              min={0}
              step="0.01"
              value={giftCardAmount || ''}
              onChange={(e) => setGiftCardAmount(Number(e.target.value))}
              placeholder="Amount"
              className="w-28 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-800">
          <h2 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-300">Summary (estimate)</h2>
          <div className="space-y-1 text-sm text-slate-600 dark:text-slate-300">
            <div className="flex justify-between"><span>Taxable value</span><span>SAR {estimate.taxable.toFixed(2)}</span></div>
            <div className="flex justify-between"><span>VAT (approx.)</span><span>SAR {estimate.tax.toFixed(2)}</span></div>
            {appliedCoupon && (
              <div className="flex justify-between text-emerald-600">
                <span>Coupon discount</span><span>-SAR {appliedCoupon.discount.toFixed(2)}</span>
              </div>
            )}
            <div className="flex justify-between border-t border-slate-200 pt-2 text-base font-semibold text-slate-900 dark:border-slate-700 dark:text-slate-50">
              <span>Grand total (approx.)</span><span>SAR {estimate.grandTotalEstimate.toFixed(2)}</span>
            </div>
          </div>
          <p className="mt-1 text-xs text-slate-400">Exact VAT & rounding are calculated by the server at checkout.</p>
        </div>

        {!isCreditSale && (
          <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-800">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-300">Payment</h2>
            </div>

            <>
              {payments.map((p, i) => (
                <div key={i} className="mb-2 flex gap-2">
                  <select
                    value={p.method}
                    onChange={(e) => updatePayment(i, { method: e.target.value as PaymentLine['method'] })}
                    className="rounded-lg border border-slate-300 px-2 py-1 text-sm dark:border-slate-600 dark:bg-slate-700"
                  >
                    {PAYMENT_METHODS.map((m) => (
                      <option key={m} value={m}>{m.toUpperCase()}</option>
                    ))}
                  </select>
                  <input
                    type="number"
                    step="0.01"
                    value={p.amount || ''}
                    onChange={(e) => updatePayment(i, { amount: Number(e.target.value) })}
                    className="w-24 rounded-lg border border-slate-300 px-2 py-1 text-sm dark:border-slate-600 dark:bg-slate-700"
                  />
                  {payments.length > 1 && (
                    <button onClick={() => setPayments((prev) => prev.filter((_, idx) => idx !== i))} className="text-red-500">✕</button>
                  )}
                </div>
              ))}
              <button
                onClick={() => setPayments((prev) => [...prev, { method: 'cash', amount: 0 }])}
                className="text-sm font-medium text-indigo-600 hover:text-indigo-500"
              >
                + Add payment method
              </button>
              <p className={`mt-2 text-sm ${balanceDue > 0 ? 'text-amber-600' : 'text-emerald-600'}`}>
                {balanceDue > 0 ? `Balance due: SAR ${balanceDue.toFixed(2)}` : 'Fully paid'}
              </p>
            </>
          </div>
        )}

        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

        <button
          onClick={completeSale}
          disabled={submitting || cart.length === 0}
          className="w-full rounded-lg bg-emerald-600 px-4 py-3 text-base font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
        >
          {submitting ? 'Processing...' : 'Complete Sale'}
        </button>
      </div>
    </div>
  )
}

function Receipt({
  invoice,
  onNewSale,
  autoPrint,
}: {
  invoice: SaleInvoice
  onNewSale: () => void
  autoPrint?: boolean
}) {
  // A UPI QR sale is confirmed with nobody's hand on the mouse -- printing
  // must happen automatically instead of waiting for a cashier click. The
  // ref guard keeps this to a single print even under React StrictMode's
  // dev-mode double-invoke of effects.
  const printedRef = useRef(false)
  useEffect(() => {
    if (autoPrint && !printedRef.current) {
      printedRef.current = true
      window.print()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Sales rung up while the desktop shell can't reach the backend are
  // queued locally by sync_agent's local server and come back with this
  // status instead of "posted" -- there's no real VAT invoice yet (no
  // cached tax rates to compute VAT from), just a provisional
  // slip, until the sale syncs and the server posts the real one.
  const isOfflinePending = invoice.status === 'offline_pending'

  // Org branding (trade name, address, VAT number, logo, footer note) rides along
  // on the printed/dialog receipt so every till in the branch shares one look.
  // Fetched here instead of at the page level because this component is the
  // only consumer, and a 404/offline org profile shouldn't block the POS.
  const [profile, setProfile] = useState<OrgProfile | null>(null)
  useEffect(() => {
    let cancelled = false
    apiClient
      .get<OrgProfile>('/org/profile')
      .then(({ data }) => {
        if (!cancelled) setProfile(data)
      })
      .catch(() => {
        /* receipt still renders without branding */
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const [drawerStatus, setDrawerStatus] = useState<'idle' | 'opening' | 'failed'>('idle')
  async function openDrawer() {
    setDrawerStatus('opening')
    try {
      const { data } = await apiClient.post('/printing/drawer/kick')
      setDrawerStatus(data.status === 'ok' ? 'idle' : 'failed')
    } catch {
      setDrawerStatus('failed')
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <div className="mb-4 flex justify-end gap-2 print:hidden">
        <button onClick={() => window.print()} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500">
          Print Receipt
        </button>
        <button
          onClick={openDrawer}
          disabled={drawerStatus === 'opening'}
          title={drawerStatus === 'failed' ? 'Could not reach the receipt printer/drawer' : undefined}
          className="rounded-lg bg-slate-200 px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-300 disabled:opacity-60 dark:bg-slate-700 dark:text-slate-100"
        >
          {drawerStatus === 'opening' ? 'Opening...' : drawerStatus === 'failed' ? 'Drawer: retry' : 'Open Drawer'}
        </button>
        <button onClick={onNewSale} className="rounded-lg bg-slate-200 px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-300 dark:bg-slate-700 dark:text-slate-100">
          New Sale
        </button>
      </div>
      {isOfflinePending && (
        <div className="mb-4 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800 print:hidden dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200">
          Offline sale — saved on this till and will sync automatically once connected. This is a provisional
          receipt, not the final VAT tax invoice; reprint the real one after it syncs.
        </div>
      )}
      <div className="rounded-xl border border-slate-200 bg-white p-6 font-mono text-sm dark:border-slate-800 dark:bg-slate-800 print:w-[80mm] print:border-0 print:p-2 print:text-black">
        {(profile?.has_logo || profile?.trade_name || profile?.legal_name) && (
          <>
            {profile?.has_logo && <img src="/org/logo.png" alt="Store logo" className="mx-auto mb-1 h-14 object-contain" />}
            <p className="text-center text-sm font-bold">{profile?.trade_name || profile?.legal_name}</p>
            {profile?.address && <p className="text-center text-xs whitespace-pre-line">{profile.address}</p>}
            {profile?.phone && <p className="text-center text-xs">Tel: {profile.phone}</p>}
            {profile?.vat_number && <p className="text-center text-xs">VAT: {profile.vat_number}</p>}
            <hr className="my-2 border-dashed" />
          </>
        )}
        <p className="text-center text-base font-bold">
          {isOfflinePending
            ? 'إيصال مبدئي / PROVISIONAL RECEIPT'
            : profile?.vat_number
              ? 'فاتورة ضريبية / TAX INVOICE'
              : 'فاتورة / INVOICE'}
        </p>
        <p className="text-center text-xs">{invoice.invoice_number}</p>
        <p className="text-center text-xs">{new Date(invoice.invoice_date).toLocaleString('en-SA')}</p>
        <hr className="my-2 border-dashed" />
        {invoice.items.map((item) => (
          <div key={item.id} className="mb-1">
            <div className="flex justify-between">
              <span className="truncate max-w-[70%]">{item.product_name ?? item.product_id.slice(0, 8)}</span>
              <span>SAR {item.line_total.toFixed(2)}</span>
            </div>
            <div className="text-xs text-slate-500">
              {item.barcode && <span className="mr-2">{item.barcode}</span>}
              {item.quantity} x SAR {item.unit_price.toFixed(2)}
            </div>
          </div>
        ))}
        <hr className="my-2 border-dashed" />
        {profile?.vat_number ? (
          <>
            {isOfflinePending ? (
              <div className="flex justify-between"><span>المجموع الفرعي (ضريبة معلقة) / Subtotal</span><span>SAR {invoice.taxable_total.toFixed(2)}</span></div>
            ) : (
              <div className="flex justify-between"><span>القيمة الخاضعة للضريبة / Taxable value</span><span>SAR {invoice.taxable_total.toFixed(2)}</span></div>
            )}
            {invoice.vat_total > 0 && <div className="flex justify-between"><span>ضريبة القيمة المضافة (15%) / VAT</span><span>SAR {invoice.vat_total.toFixed(2)}</span></div>}
          </>
        ) : (
          <div className="flex justify-between"><span>المجموع / Subtotal</span><span>SAR {invoice.subtotal.toFixed(2)}</span></div>
        )}
        {invoice.coupon_discount_amount > 0 && (
          <div className="flex justify-between"><span>الخصم / Coupon ({invoice.coupon_code})</span><span>-SAR {invoice.coupon_discount_amount.toFixed(2)}</span></div>
        )}
        <div className="flex justify-between"><span>تقريب / Round off</span><span>SAR {invoice.round_off.toFixed(2)}</span></div>
        <hr className="my-2 border-dashed" />
        <div className="flex justify-between text-base font-bold"><span>الإجمالي / Grand Total</span><span>SAR {invoice.grand_total.toFixed(2)}</span></div>
        <hr className="my-2 border-dashed" />
        {invoice.payments.map((p) => (
          <div key={p.id} className="flex justify-between"><span>{p.method.toUpperCase()}</span><span>SAR {p.amount.toFixed(2)}</span></div>
        ))}
        {profile?.footer_note ? (
          <p className="mt-4 text-center text-xs whitespace-pre-line">{profile.footer_note}</p>
        ) : (
          <p className="mt-4 text-center text-xs">شكراً لتسوقكم معنا! / Thank you for shopping with us!</p>
        )}
        {invoice.qr_code_data && (
          <div className="mt-3 flex justify-center print:mt-2">
            <img
              src={`data:image/png;base64,${invoice.qr_code_data}`}
              alt="ZATCA QR"
              className="h-20 w-20 print:h-16 print:w-16"
            />
          </div>
        )}
      </div>
    </div>
  )
}
