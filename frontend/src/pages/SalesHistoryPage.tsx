import { useEffect, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'
import type { SaleInvoice, SalesReturn } from '../types'

export default function SalesHistoryPage() {
  const [tab, setTab] = useState<'invoices' | 'returns'>('invoices')
  const [invoices, setInvoices] = useState<SaleInvoice[]>([])
  const [returns, setReturns] = useState<SalesReturn[]>([])
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [selectedInvoice, setSelectedInvoice] = useState<SaleInvoice | null>(null)
  const [cancelling, setCancelling] = useState<string | null>(null)

  async function loadInvoices() {
    try {
      const res = await apiClient.get<SaleInvoice[]>('/sales')
      setInvoices(res.data)
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  async function loadReturns() {
    try {
      const res = await apiClient.get<SalesReturn[]>('/sales/returns')
      setReturns(res.data)
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  useEffect(() => {
    loadInvoices()
    loadReturns()
  }, [])

  async function handleCancel(invoiceId: string) {
    if (!window.confirm('Cancel this invoice? This restores stock and reverses the ledger entry.')) return
    setCancelling(invoiceId)
    setError(null)
    try {
      await apiClient.post(`/sales/${invoiceId}/cancel`, { reason: 'Cancelled from sales history' })
      setSelectedInvoice(null)
      await loadInvoices()
      await loadReturns()
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setCancelling(null)
    }
  }

  const filtered = search
    ? invoices.filter(
        (i) =>
          i.invoice_number.toLowerCase().includes(search.toLowerCase()) ||
          (i.customer_id ?? '').includes(search),
      )
    : invoices

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-50">Sales History & Returns</h1>
        <div className="flex gap-2">
          <button
            onClick={() => setTab('invoices')}
            className={`rounded-lg px-4 py-2 text-sm font-semibold ${
              tab === 'invoices' ? 'bg-indigo-600 text-white' : 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200'
            }`}
          >
            Invoices
          </button>
          <button
            onClick={() => setTab('returns')}
            className={`rounded-lg px-4 py-2 text-sm font-semibold ${
              tab === 'returns' ? 'bg-indigo-600 text-white' : 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200'
            }`}
          >
            Returns
          </button>
        </div>
      </div>

      {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

      {tab === 'invoices' ? (
        <>
          <div className="mb-4">
            <input
              placeholder="Search by invoice number or customer..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full max-w-sm rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
            />
          </div>
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
                <tr>
                  <th className="px-4 py-3">Invoice</th>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Customer</th>
                  <th className="px-4 py-3">Total</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((inv) => (
                  <tr key={inv.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                    <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">{inv.invoice_number}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                      {new Date(inv.invoice_date).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                      {inv.customer_id ? inv.customer_id.slice(0, 8) : 'Walk-in'}
                    </td>
                    <td className="px-4 py-3 text-slate-900 dark:text-slate-100">₹{inv.grand_total.toFixed(2)}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          inv.status === 'posted'
                            ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                            : 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300'
                        }`}
                      >
                        {inv.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <button onClick={() => setSelectedInvoice(inv)} className="text-indigo-600 hover:underline dark:text-indigo-400">
                        View
                      </button>
                      {inv.status === 'posted' && (
                        <button
                          onClick={() => handleCancel(inv.id)}
                          disabled={cancelling === inv.id}
                          className="ml-3 text-red-600 hover:underline disabled:opacity-50 dark:text-red-400"
                        >
                          {cancelling === inv.id ? '...' : 'Cancel'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
                      No invoices found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
              <tr>
                <th className="px-4 py-3">Return #</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Refund</th>
                <th className="px-4 py-3">Mode</th>
                <th className="px-4 py-3">Reason</th>
                <th className="px-4 py-3">Items</th>
              </tr>
            </thead>
            <tbody>
              {returns.map((r) => (
                <tr key={r.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                  <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">{r.return_number}</td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{new Date(r.return_date).toLocaleString()}</td>
                  <td className="px-4 py-3 text-slate-900 dark:text-slate-100">₹{r.refund_total.toFixed(2)}</td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{r.refund_mode}</td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{r.reason ?? '—'}</td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{r.items.length}</td>
                </tr>
              ))}
              {returns.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
                    No returns recorded.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {selectedInvoice && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => setSelectedInvoice(null)}>
          <div className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white p-6 dark:bg-slate-800" onClick={(e) => e.stopPropagation()}>
            <h2 className="mb-4 text-xl font-semibold text-slate-900 dark:text-slate-50">{selectedInvoice.invoice_number}</h2>
            <p className="mb-4 text-sm text-slate-500">Date: {new Date(selectedInvoice.invoice_date).toLocaleString()}</p>
            <table className="mb-4 w-full text-left text-sm">
              <thead className="border-b text-slate-500">
                <tr>
                  <th className="px-2 py-2">Product</th>
                  <th className="px-2 py-2">Qty</th>
                  <th className="px-2 py-2">Price</th>
                  <th className="px-2 py-2">Taxable</th>
                  <th className="px-2 py-2">GST</th>
                  <th className="px-2 py-2">Total</th>
                </tr>
              </thead>
              <tbody>
                {selectedInvoice.items.map((item) => (
                  <tr key={item.id} className="border-b border-slate-100 last:border-0">
                    <td className="px-2 py-2">{item.product_id.slice(0, 8)}</td>
                    <td className="px-2 py-2">{item.quantity}</td>
                    <td className="px-2 py-2">₹{item.unit_price.toFixed(2)}</td>
                    <td className="px-2 py-2">₹{item.taxable_value.toFixed(2)}</td>
                    <td className="px-2 py-2">₹{(item.cgst_amount + item.sgst_amount + item.igst_amount).toFixed(2)}</td>
                    <td className="px-2 py-2">₹{item.line_total.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="mb-4 text-right">
              <p className="text-sm">Subtotal: ₹{selectedInvoice.subtotal.toFixed(2)}</p>
              <p className="text-sm">GST: ₹{(selectedInvoice.cgst_total + selectedInvoice.sgst_total + selectedInvoice.igst_total).toFixed(2)}</p>
              <p className="text-lg font-semibold">Grand Total: ₹{selectedInvoice.grand_total.toFixed(2)}</p>
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => setSelectedInvoice(null)} className="rounded-lg bg-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 dark:bg-slate-700 dark:text-slate-200">
                Close
              </button>
              {selectedInvoice.status === 'posted' && (
                <button onClick={() => handleCancel(selectedInvoice.id)} className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-500">
                  Cancel Invoice
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
