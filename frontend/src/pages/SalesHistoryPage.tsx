import { useEffect, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'
import { useCan, PERMS } from '../auth/permissions'
import { useOrgStore } from '../store/org'
import type { SaleInvoice, SalesReturn } from '../types'

export default function SalesHistoryPage() {
  const [tab, setTab] = useState<'invoices' | 'returns'>('invoices')
  const [invoices, setInvoices] = useState<SaleInvoice[]>([])
  const [returns, setReturns] = useState<SalesReturn[]>([])
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [selectedInvoice, setSelectedInvoice] = useState<SaleInvoice | null>(null)
  const [cancelling, setCancelling] = useState<string | null>(null)
  const canReturn = useCan(PERMS.SALES_RETURN)
  const profile = useOrgStore((s) => s.profile)

  function printInvoice(inv: SaleInvoice) {
    const w = window.open('', '_blank', 'width=400,height=700')
    if (!w) return
    const bizName = profile?.trade_name || profile?.legal_name || 'Store'
    const payLines = inv.payments.map((p) => `<div style="display:flex;justify-content:space-between"><span>${p.method.toUpperCase()}</span><span>SAR ${p.amount.toFixed(2)}</span></div>`).join('')
    const itemLines = inv.items.map((it) => `<div style="margin:2px 0"><div style="display:flex;justify-content:space-between"><span>${it.product_name || it.product_id.slice(0, 8)}</span><span>SAR ${it.line_total.toFixed(2)}</span></div><div style="font-size:11px;color:#666">${it.barcode ? it.barcode + ' | ' : ''}${it.quantity} x SAR ${it.unit_price.toFixed(2)}</div></div>`).join('')
    const offlinePending = inv.status === 'offline_pending'
    w.document.write(`<!DOCTYPE html><html><head><title>${inv.invoice_number}</title><style>
      *{margin:0;padding:0;box-sizing:border-box}
      body{font-family:'Courier New',monospace;font-size:13px;width:320px;margin:0 auto;padding:10px}
      .center{text-align:center}
      .bold{font-weight:700}
      .line{border-top:1px dashed #000;margin:6px 0}
      .row{display:flex;justify-content:space-between}
      @media print{body{margin:0;padding:5px}}
    </style></head><body>
      ${profile?.has_logo ? `<div class="center"><img src="/org/logo.png" style="height:56px;object-fit:contain" /></div>` : ''}
      <div class="center bold" style="font-size:14px">${bizName}</div>
      ${profile?.address ? `<div class="center" style="font-size:11px;white-space:pre-line">${profile.address}</div>` : ''}
      ${profile?.phone ? `<div class="center" style="font-size:11px">Tel: ${profile.phone}</div>` : ''}
      ${profile?.vat_number ? `<div class="center" style="font-size:11px">VAT: ${profile.vat_number}</div>` : ''}
      <div class="line"></div>
      <div class="center bold" style="font-size:15px">${offlinePending ? 'إيصال مبدئي / PROVISIONAL RECEIPT' : (profile?.vat_number ? 'فاتورة ضريبية / TAX INVOICE' : 'فاتورة / INVOICE')}</div>
      <div class="center" style="font-size:11px">${inv.invoice_number}</div>
      <div class="center" style="font-size:11px">${new Date(inv.invoice_date).toLocaleString('en-SA')}</div>
      <div class="line"></div>
      ${itemLines}
      <div class="line"></div>
      ${profile?.vat_number
        ? (offlinePending
          ? `<div class="row"><span>المجموع الفرعي (ضريبة معلقة) / Subtotal</span><span>SAR ${inv.taxable_total.toFixed(2)}</span></div>`
          : `<div class="row"><span>القيمة الخاضعة للضريبة / Taxable value</span><span>SAR ${inv.taxable_total.toFixed(2)}</span></div>`)
        : `<div class="row"><span>المجموع / Subtotal</span><span>SAR ${inv.subtotal.toFixed(2)}</span></div>`
      }
      ${profile?.vat_number && inv.vat_total > 0 ? `<div class="row"><span>ضريبة القيمة المضافة (15%) / VAT</span><span>SAR ${inv.vat_total.toFixed(2)}</span></div>` : ''}
      ${inv.coupon_discount_amount > 0 ? `<div class="row"><span>الخصم / Coupon (${inv.coupon_code || ''})</span><span>-SAR ${inv.coupon_discount_amount.toFixed(2)}</span></div>` : ''}
      <div class="row"><span>تقريب / Round off</span><span>SAR ${inv.round_off.toFixed(2)}</span></div>
      <div class="line"></div>
      <div class="row bold" style="font-size:15px"><span>الإجمالي / Grand Total</span><span>SAR ${inv.grand_total.toFixed(2)}</span></div>
      <div class="line"></div>
      ${payLines}
      <div class="line"></div>
      <div class="center" style="font-size:11px">${profile?.footer_note || 'شكراً لتسوقكم معنا! / Thank you for shopping with us!'}</div>
      <div class="line"></div>
      ${inv.qr_code_data ? `<div class="center"><img src="data:image/png;base64,${inv.qr_code_data}" style="height:80px;width:80px" /></div>` : ''}
    </body></html>`)
    w.document.close()
    w.print()
  }

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
                    <td className="px-4 py-3 text-slate-900 dark:text-slate-100">SAR {inv.grand_total.toFixed(2)}</td>
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
                      <div className="flex gap-2">
                        <button onClick={() => setSelectedInvoice(inv)} className="text-indigo-600 hover:underline dark:text-indigo-400">
                          View
                        </button>
                        <button onClick={() => printInvoice(inv)} className="text-slate-600 hover:underline dark:text-slate-400">
                          Print
                        </button>
                        {canReturn && inv.status === 'posted' && (
                          <button
                            onClick={() => handleCancel(inv.id)}
                            disabled={cancelling === inv.id}
                            className="text-red-600 hover:underline disabled:opacity-50 dark:text-red-400"
                          >
                            {cancelling === inv.id ? '...' : 'Cancel'}
                          </button>
                        )}
                      </div>
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
                  <td className="px-4 py-3 text-slate-900 dark:text-slate-100">SAR {r.refund_total.toFixed(2)}</td>
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
          <div className="max-h-[85vh] w-full max-w-md overflow-y-auto rounded-xl border border-slate-200 bg-white p-6 font-mono text-sm dark:border-slate-800 dark:bg-slate-800" onClick={(e) => e.stopPropagation()}>
            {(profile?.has_logo || profile?.trade_name || profile?.legal_name) && (
              <>
                {profile?.has_logo && <img src="/org/logo.png" alt="Store logo" className="mx-auto mb-1 h-14 object-contain" />}
                <p className="text-center text-sm font-bold">{profile?.trade_name || profile?.legal_name}</p>
                {profile?.address && <p className="whitespace-pre-line text-center text-xs">{profile.address}</p>}
                {profile?.phone && <p className="text-center text-xs">Tel: {profile.phone}</p>}
                {profile?.vat_number && <p className="text-center text-xs">VAT: {profile.vat_number}</p>}
                <hr className="my-2 border-dashed" />
              </>
            )}
            <p className="text-center text-base font-bold">
              {selectedInvoice.status === 'offline_pending'
                ? 'إيصال مبدئي / PROVISIONAL RECEIPT'
                : profile?.vat_number
                  ? 'فاتورة ضريبية / TAX INVOICE'
                  : 'فاتورة / INVOICE'}
            </p>
            <p className="text-center text-xs">{selectedInvoice.invoice_number}</p>
            <p className="text-center text-xs">{new Date(selectedInvoice.invoice_date).toLocaleString('en-SA')}</p>
            <hr className="my-2 border-dashed" />
            {selectedInvoice.items.map((item) => (
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
                {selectedInvoice.status === 'offline_pending' ? (
                  <div className="flex justify-between"><span>المجموع الفرعي (ضريبة معلقة) / Subtotal</span><span>SAR {selectedInvoice.taxable_total.toFixed(2)}</span></div>
                ) : (
                  <div className="flex justify-between"><span>القيمة الخاضعة للضريبة / Taxable value</span><span>SAR {selectedInvoice.taxable_total.toFixed(2)}</span></div>
                )}
                {selectedInvoice.vat_total > 0 && <div className="flex justify-between"><span>ضريبة القيمة المضافة (15%) / VAT</span><span>SAR {selectedInvoice.vat_total.toFixed(2)}</span></div>}
              </>
            ) : (
              <div className="flex justify-between"><span>المجموع / Subtotal</span><span>SAR {selectedInvoice.subtotal.toFixed(2)}</span></div>
            )}
            {selectedInvoice.coupon_discount_amount > 0 && (
              <div className="flex justify-between"><span>Coupon ({selectedInvoice.coupon_code})</span><span>-SAR {selectedInvoice.coupon_discount_amount.toFixed(2)}</span></div>
            )}
            <div className="flex justify-between"><span>تقريب / Round off</span><span>SAR {selectedInvoice.round_off.toFixed(2)}</span></div>
            <hr className="my-2 border-dashed" />
            <div className="flex justify-between text-base font-bold"><span>الإجمالي / Grand Total</span><span>SAR {selectedInvoice.grand_total.toFixed(2)}</span></div>
            <hr className="my-2 border-dashed" />
            {selectedInvoice.payments.map((p) => (
              <div key={p.id} className="flex justify-between"><span>{p.method.toUpperCase()}</span><span>SAR {p.amount.toFixed(2)}</span></div>
            ))}
            {profile?.footer_note ? (
              <p className="mt-4 text-center text-xs whitespace-pre-line">{profile.footer_note}</p>
            ) : (
              <p className="mt-4 text-center text-xs">شكراً لتسوقكم معنا! / Thank you for shopping with us!</p>
            )}
            {selectedInvoice.qr_code_data && (
              <div className="mt-3 flex justify-center">
                <img
                  src={`data:image/png;base64,${selectedInvoice.qr_code_data}`}
                  alt="ZATCA QR"
                  className="h-20 w-20"
                />
              </div>
            )}
            <div className="mt-4 flex justify-end gap-2 print:hidden">
              <button onClick={() => setSelectedInvoice(null)} className="rounded-lg bg-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 dark:bg-slate-700 dark:text-slate-200">
                Close
              </button>
              <button onClick={() => printInvoice(selectedInvoice)} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500">
                Print Receipt
              </button>
              {canReturn && selectedInvoice.status === 'posted' && (
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
