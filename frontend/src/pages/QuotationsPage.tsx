import { useEffect, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'
import type { Customer, Product, Quotation } from '../types'

interface Warehouse {
  id: string
  code: string
  name: string
  is_default: boolean
}
interface Branch {
  id: string
  name: string
  warehouses: Warehouse[]
}

interface DraftLine {
  key: string
  product_id: string
  product_name: string
  quantity: string
  unit_price: string
  discount_amount: string
}

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

export default function QuotationsPage() {
  const [quotations, setQuotations] = useState<Quotation[]>([])
  const [branches, setBranches] = useState<Branch[]>([])
  const [customerNames, setCustomerNames] = useState<Record<string, string>>({})
  const [productTaxRates, setProductTaxRates] = useState<Record<string, number>>({})
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  const [showForm, setShowForm] = useState(false)
  const [branchId, setBranchId] = useState('')
  const [quotationDate, setQuotationDate] = useState(todayIso())
  const [validUntil, setValidUntil] = useState('')
  const [customerQuery, setCustomerQuery] = useState('')
  const [customerResults, setCustomerResults] = useState<Customer[]>([])
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [productQuery, setProductQuery] = useState('')
  const [productResults, setProductResults] = useState<Product[]>([])
  const [lines, setLines] = useState<DraftLine[]>([])

  const [convertingFor, setConvertingFor] = useState<Quotation | null>(null)
  const [convertWarehouseId, setConvertWarehouseId] = useState('')
  const [convertAmount, setConvertAmount] = useState('')

  async function refresh() {
    const res = await apiClient.get<Quotation[]>('/sales/quotations')
    setQuotations(res.data)
    const missingIds = Array.from(
      new Set(res.data.map((q) => q.customer_id).filter((id): id is string => Boolean(id))),
    )
    if (missingIds.length > 0) {
      const customers = await apiClient.get<Customer[]>('/party/customers')
      setCustomerNames(Object.fromEntries(customers.data.map((c) => [c.id, c.name])))
    }
  }

  useEffect(() => {
    apiClient.get<Branch[]>('/org/branches').then((res) => {
      setBranches(res.data)
      if (res.data[0]) setBranchId(res.data[0].id)
    })
    apiClient.get<Product[]>('/catalog/products').then((res) => {
      setProductTaxRates(Object.fromEntries(res.data.map((p) => [p.id, p.tax_rate_percent ?? 0])))
    })
    refresh().catch((err) => setError(apiErrorMessage(err)))
  }, [])

  async function searchCustomers(q: string) {
    setCustomerQuery(q)
    if (!q) {
      setCustomerResults([])
      return
    }
    const res = await apiClient.get<Customer[]>('/party/customers', { params: { search: q } })
    setCustomerResults(res.data)
  }

  async function searchProducts(q: string) {
    setProductQuery(q)
    if (!q) {
      setProductResults([])
      return
    }
    const res = await apiClient.get<Product[]>('/catalog/products', { params: { search: q } })
    setProductResults(res.data)
  }

  function addLine(p: Product) {
    setLines((cur) => [
      ...cur,
      {
        key: `${p.id}-${Date.now()}`,
        product_id: p.id,
        product_name: p.name,
        quantity: '1',
        unit_price: String(p.sale_price),
        discount_amount: '0',
      },
    ])
    setProductQuery('')
    setProductResults([])
  }

  function updateLine(key: string, field: 'quantity' | 'unit_price' | 'discount_amount', value: string) {
    setLines((cur) => cur.map((l) => (l.key === key ? { ...l, [field]: value } : l)))
  }

  function removeLine(key: string) {
    setLines((cur) => cur.filter((l) => l.key !== key))
  }

  function resetForm() {
    setBranchId(branches[0]?.id ?? '')
    setQuotationDate(todayIso())
    setValidUntil('')
    setCustomer(null)
    setCustomerQuery('')
    setLines([])
    setShowForm(false)
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!branchId || lines.length === 0) {
      setError('Pick a branch and add at least one product.')
      return
    }
    setBusy('create')
    try {
      await apiClient.post('/sales/quotations', {
        branch_id: branchId,
        customer_id: customer?.id ?? null,
        quotation_date: quotationDate,
        valid_until: validUntil || null,
        items: lines.map((l) => ({
          product_id: l.product_id,
          quantity: Number(l.quantity),
          unit_price: Number(l.unit_price),
          discount_amount: Number(l.discount_amount || 0),
        })),
      })
      resetForm()
      await refresh()
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function sendQuotation(q: Quotation) {
    setError(null)
    setBusy(q.id)
    try {
      await apiClient.post(`/sales/quotations/${q.id}/send`)
      await refresh()
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function expireQuotation(q: Quotation) {
    setError(null)
    setBusy(q.id)
    try {
      await apiClient.post(`/sales/quotations/${q.id}/expire`)
      await refresh()
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  function openConvert(q: Quotation) {
    setConvertingFor(q)
    const branch = branches.find((b) => b.id === q.branch_id)
    const warehouse = branch?.warehouses.find((w) => w.is_default) ?? branch?.warehouses[0]
    setConvertWarehouseId(warehouse?.id ?? '')
    // A quotation's grand_total has no GST baked in (see the Quotation
    // model), but the real invoice created on conversion always does --
    // defaulting to grand_total as-is would under-collect payment by the
    // tax amount and fail create_sale's "payments don't cover total"
    // check. Estimate the GST-inclusive total from each line's own
    // product tax rate, then round to the nearest whole rupee exactly
    // like round_invoice_total does server-side (gst/service.py) -- a
    // 2-decimal estimate (e.g. 47.20) overshoots the server's actual
    // rounded total (47) and trips the "payments exceed total" check
    // instead. The server remains authoritative regardless (same
    // reasoning as POSPage's roundHalfUp) -- the cashier can still
    // adjust before confirming.
    const estimate = q.items.reduce((sum, item) => {
      const rate = productTaxRates[item.product_id] ?? 0
      return sum + item.line_total * (1 + rate / 100)
    }, 0)
    setConvertAmount(String(Math.round(estimate)))
  }

  async function confirmConvert() {
    if (!convertingFor || !convertWarehouseId) return
    setError(null)
    setBusy(convertingFor.id)
    try {
      await apiClient.post(`/sales/quotations/${convertingFor.id}/convert`, {
        warehouse_id: convertWarehouseId,
        payments: [{ method: 'cash', amount: Number(convertAmount) }],
      })
      setConvertingFor(null)
      await refresh()
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-50">Quotations</h1>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
        >
          {showForm ? 'Cancel' : '+ New Quotation'}
        </button>
      </div>

      {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

      {showForm && (
        <form onSubmit={handleCreate} className="mb-6 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-800">
          <div className="mb-3 grid grid-cols-2 gap-3 md:grid-cols-3">
            <select
              required
              value={branchId}
              onChange={(e) => setBranchId(e.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            >
              <option value="">Branch...</option>
              {branches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
            <input
              required
              type="date"
              value={quotationDate}
              onChange={(e) => setQuotationDate(e.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
            <input
              type="date"
              placeholder="Valid until (optional)"
              value={validUntil}
              onChange={(e) => setValidUntil(e.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
          </div>

          <div className="relative mb-3">
            <input
              value={customer ? customer.name : customerQuery}
              onChange={(e) => {
                setCustomer(null)
                searchCustomers(e.target.value)
              }}
              placeholder="Search customer (optional)..."
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
            {customerResults.length > 0 && (
              <ul className="absolute z-10 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-800">
                {customerResults.map((c) => (
                  <li
                    key={c.id}
                    onClick={() => {
                      setCustomer(c)
                      setCustomerResults([])
                    }}
                    className="cursor-pointer px-3 py-2 text-sm hover:bg-slate-100 dark:text-slate-100 dark:hover:bg-slate-700"
                  >
                    {c.name} {c.phone && <span className="text-slate-400">({c.phone})</span>}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="relative mb-3">
            <input
              value={productQuery}
              onChange={(e) => searchProducts(e.target.value)}
              placeholder="Search product to add..."
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
            {productResults.length > 0 && (
              <ul className="absolute z-10 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-800">
                {productResults.map((p) => (
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
                  <th className="py-1">Unit Price</th>
                  <th className="py-1">Discount</th>
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
                        onChange={(e) => updateLine(l.key, 'quantity', e.target.value)}
                        className="w-20 rounded-lg border border-slate-300 px-2 py-1 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      />
                    </td>
                    <td className="py-1 pr-2">
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={l.unit_price}
                        onChange={(e) => updateLine(l.key, 'unit_price', e.target.value)}
                        className="w-24 rounded-lg border border-slate-300 px-2 py-1 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      />
                    </td>
                    <td className="py-1 pr-2">
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={l.discount_amount}
                        onChange={(e) => updateLine(l.key, 'discount_amount', e.target.value)}
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
            {busy === 'create' ? 'Saving...' : 'Save Quotation (Draft)'}
          </button>
        </form>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
            <tr>
              <th className="px-4 py-3">Quotation #</th>
              <th className="px-4 py-3">Customer</th>
              <th className="px-4 py-3">Date</th>
              <th className="px-4 py-3">Valid Until</th>
              <th className="px-4 py-3">Grand Total</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {quotations.map((q) => (
              <tr key={q.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">{q.quotation_number}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                  {q.customer_id ? (customerNames[q.customer_id] ?? q.customer_id) : 'Walk-in'}
                </td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{q.quotation_date}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{q.valid_until ?? '-'}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">₹{q.grand_total.toFixed(2)}</td>
                <td className="px-4 py-3">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      q.status === 'converted'
                        ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                        : q.status === 'expired'
                          ? 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400'
                          : q.status === 'sent'
                            ? 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300'
                            : 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300'
                    }`}
                  >
                    {q.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-right whitespace-nowrap">
                  {(q.status === 'draft' || q.status === 'sent') && (
                    <>
                      {q.status === 'draft' && (
                        <button
                          onClick={() => sendQuotation(q)}
                          disabled={busy === q.id}
                          className="mr-3 text-sm font-medium text-indigo-600 hover:text-indigo-500 disabled:opacity-50"
                        >
                          Send
                        </button>
                      )}
                      <button
                        onClick={() => openConvert(q)}
                        disabled={busy === q.id}
                        className="mr-3 text-sm font-medium text-emerald-600 hover:text-emerald-500 disabled:opacity-50"
                      >
                        Convert to Sale
                      </button>
                      <button
                        onClick={() => expireQuotation(q)}
                        disabled={busy === q.id}
                        className="text-sm font-medium text-red-600 hover:text-red-500 disabled:opacity-50"
                      >
                        Mark Expired
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
            {quotations.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-slate-400">
                  No quotations yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {convertingFor && (
        <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-sm rounded-xl bg-white p-5 shadow-xl dark:bg-slate-800">
            <h2 className="mb-1 text-lg font-semibold text-slate-900 dark:text-slate-50">Convert to Sale</h2>
            <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">{convertingFor.quotation_number}</p>

            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Warehouse</label>
            <select
              value={convertWarehouseId}
              onChange={(e) => setConvertWarehouseId(e.target.value)}
              className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            >
              <option value="">Warehouse...</option>
              {branches
                .find((b) => b.id === convertingFor.branch_id)
                ?.warehouses.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
            </select>

            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
              Cash payment amount
            </label>
            <input
              type="number"
              min="0"
              step="0.01"
              value={convertAmount}
              onChange={(e) => setConvertAmount(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
            <p className="mb-4 mt-1 text-xs text-slate-400">
              Includes an estimated GST -- the quoted total ({convertingFor && `₹${convertingFor.grand_total.toFixed(2)}`}) doesn't. Adjust if this doesn't match the confirmation.
            </p>

            <div className="flex justify-end gap-2">
              <button
                onClick={() => setConvertingFor(null)}
                className="rounded-lg px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
              >
                Cancel
              </button>
              <button
                onClick={confirmConvert}
                disabled={busy === convertingFor.id || !convertWarehouseId}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
              >
                {busy === convertingFor.id ? 'Converting...' : 'Confirm Sale'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
