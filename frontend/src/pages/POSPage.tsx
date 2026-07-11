import { useEffect, useMemo, useRef, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'
import type { CartLine, Customer, PaymentLine, Product, SaleInvoice } from '../types'

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

const PAYMENT_METHODS: PaymentLine['method'][] = ['cash', 'card', 'upi', 'wallet']

// Mirrors the backend's Decimal ROUND_HALF_UP (see gst/service.py) closely
// enough for typical retail amounts, so the default payment amount we
// suggest matches what the server will actually compute. The server
// remains authoritative -- this is only a convenience default, and the
// "Balance due" indicator will catch the rare sub-cent mismatch case
// (component-level CGST/SGST rounding can differ from a single combined
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
  const barcodeRef = useRef<HTMLInputElement>(null)

  const [couponCodeInput, setCouponCodeInput] = useState('')
  const [appliedCoupon, setAppliedCoupon] = useState<{ code: string; discount: number } | null>(null)
  const [couponError, setCouponError] = useState<string | null>(null)
  const [checkingCoupon, setCheckingCoupon] = useState(false)
  const [giftCardNumber, setGiftCardNumber] = useState('')
  const [giftCardAmount, setGiftCardAmount] = useState(0)

  useEffect(() => {
    apiClient.get<Branch[]>('/org/branches').then((res) => setBranch(res.data[0] ?? null))
    barcodeRef.current?.focus()
  }, [])

  const warehouse = branch?.warehouses.find((w) => w.is_default) ?? branch?.warehouses[0]

  // Client-side preview -- the server recomputes and is authoritative
  // (stock could be gone, or a rate could change, between preview and
  // submit), but using each product's real tax_rate_percent keeps this
  // preview exact enough to auto-suggest the payment amount.
  const estimate = useMemo(() => {
    let taxable = 0
    let tax = 0
    for (const line of cart) {
      const gross = line.quantity * line.product.sale_price
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
    const res = await apiClient.get<Product[]>('/catalog/products', { params: { search: q } })
    setSearchResults(res.data)
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
      return [...prev, { product, quantity: 1, discountAmount: 0 }]
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
    const res = await apiClient.get<Customer[]>('/party/customers', { params: { search: q } })
    setCustomerResults(res.data)
  }

  function updatePayment(index: number, patch: Partial<PaymentLine>) {
    setPayments((prev) => prev.map((p, i) => (i === index ? { ...p, ...patch } : p)))
  }

  async function completeSale() {
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
          discount_amount: l.discountAmount,
        })),
        payments: isCreditSale ? [] : payments.filter((p) => p.amount > 0),
        coupon_code: appliedCoupon?.code ?? null,
        gift_card_number: giftCardNumber || null,
        gift_card_amount: giftCardNumber ? giftCardAmount : 0,
      })
      setCompletedInvoice(res.data)
      setCart([])
      setCustomer(null)
      setIsCreditSale(false)
      setPayments([{ method: 'cash', amount: 0 }])
      setCouponCodeInput('')
      setAppliedCoupon(null)
      setCouponError(null)
      setGiftCardNumber('')
      setGiftCardAmount(0)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  if (completedInvoice) {
    return <Receipt invoice={completedInvoice} onNewSale={() => setCompletedInvoice(null)} />
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <div className="lg:col-span-2">
        <h1 className="mb-4 text-2xl font-semibold text-slate-900 dark:text-slate-50">Billing</h1>

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
                    <span>{p.name} <span className="text-slate-400">({p.sku})</span></span>
                    <span className="font-medium">₹{p.sale_price.toFixed(2)}</span>
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
                const lineTotal = Math.max(0, line.quantity * line.product.sale_price - line.discountAmount)
                return (
                  <tr key={line.product.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                    <td className="px-3 py-2 font-medium text-slate-900 dark:text-slate-100">{line.product.name}</td>
                    <td className="px-3 py-2">
                      <input
                        type="number"
                        min={0.001}
                        step="1"
                        value={line.quantity}
                        onChange={(e) => updateLine(line.product.id, { quantity: Number(e.target.value) })}
                        className="w-20 rounded border border-slate-300 px-2 py-1 dark:border-slate-600 dark:bg-slate-700"
                      />
                    </td>
                    <td className="px-3 py-2 text-slate-600 dark:text-slate-300">₹{line.product.sale_price.toFixed(2)}</td>
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
                    <td className="px-3 py-2 font-medium">₹{lineTotal.toFixed(2)}</td>
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
                {appliedCoupon.code} applied (-₹{appliedCoupon.discount.toFixed(2)})
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
            <div className="flex justify-between"><span>Taxable value</span><span>₹{estimate.taxable.toFixed(2)}</span></div>
            <div className="flex justify-between"><span>GST (approx.)</span><span>₹{estimate.tax.toFixed(2)}</span></div>
            {appliedCoupon && (
              <div className="flex justify-between text-emerald-600">
                <span>Coupon discount</span><span>-₹{appliedCoupon.discount.toFixed(2)}</span>
              </div>
            )}
            <div className="flex justify-between border-t border-slate-200 pt-2 text-base font-semibold text-slate-900 dark:border-slate-700 dark:text-slate-50">
              <span>Grand total (approx.)</span><span>₹{estimate.grandTotalEstimate.toFixed(2)}</span>
            </div>
          </div>
          <p className="mt-1 text-xs text-slate-400">Exact GST & rounding are calculated by the server at checkout.</p>
        </div>

        {!isCreditSale && (
          <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-800">
            <h2 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-300">Payment</h2>
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
              {balanceDue > 0 ? `Balance due: ₹${balanceDue.toFixed(2)}` : 'Fully paid'}
            </p>
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

function Receipt({ invoice, onNewSale }: { invoice: SaleInvoice; onNewSale: () => void }) {
  return (
    <div className="mx-auto max-w-md">
      <div className="mb-4 flex justify-end gap-2 print:hidden">
        <button onClick={() => window.print()} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500">
          Print Receipt
        </button>
        <button onClick={onNewSale} className="rounded-lg bg-slate-200 px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-300 dark:bg-slate-700 dark:text-slate-100">
          New Sale
        </button>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-6 font-mono text-sm dark:border-slate-800 dark:bg-slate-800 print:w-[80mm] print:border-0 print:p-2 print:text-black">
        <p className="text-center text-base font-bold">TAX INVOICE</p>
        <p className="text-center text-xs">{invoice.invoice_number}</p>
        <p className="text-center text-xs">{new Date(invoice.invoice_date).toLocaleString('en-IN')}</p>
        <hr className="my-2 border-dashed" />
        {invoice.items.map((item) => (
          <div key={item.id} className="mb-1 flex justify-between">
            <span>{item.quantity} x ₹{item.unit_price.toFixed(2)}</span>
            <span>₹{item.line_total.toFixed(2)}</span>
          </div>
        ))}
        <hr className="my-2 border-dashed" />
        <div className="flex justify-between"><span>Taxable value</span><span>₹{invoice.taxable_total.toFixed(2)}</span></div>
        {invoice.cgst_total > 0 && <div className="flex justify-between"><span>CGST</span><span>₹{invoice.cgst_total.toFixed(2)}</span></div>}
        {invoice.sgst_total > 0 && <div className="flex justify-between"><span>SGST</span><span>₹{invoice.sgst_total.toFixed(2)}</span></div>}
        {invoice.igst_total > 0 && <div className="flex justify-between"><span>IGST</span><span>₹{invoice.igst_total.toFixed(2)}</span></div>}
        {invoice.coupon_discount_amount > 0 && (
          <div className="flex justify-between"><span>Coupon ({invoice.coupon_code})</span><span>-₹{invoice.coupon_discount_amount.toFixed(2)}</span></div>
        )}
        <div className="flex justify-between"><span>Round off</span><span>₹{invoice.round_off.toFixed(2)}</span></div>
        <hr className="my-2 border-dashed" />
        <div className="flex justify-between text-base font-bold"><span>Grand Total</span><span>₹{invoice.grand_total.toFixed(2)}</span></div>
        <hr className="my-2 border-dashed" />
        {invoice.payments.map((p) => (
          <div key={p.id} className="flex justify-between"><span>{p.method.toUpperCase()}</span><span>₹{p.amount.toFixed(2)}</span></div>
        ))}
        <p className="mt-4 text-center text-xs">Thank you for shopping with us!</p>
      </div>
    </div>
  )
}
