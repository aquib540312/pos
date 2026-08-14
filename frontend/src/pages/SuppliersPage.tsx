import { useEffect, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'
import type { Supplier, SupplierPayment } from '../types'

export default function SuppliersPage() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState({ name: '', phone: '', email: '', gstin: '', state_code: '' })
  const [payFor, setPayFor] = useState<Supplier | null>(null)
  const [payments, setPayments] = useState<SupplierPayment[]>([])

  async function load() {
    const res = await apiClient.get<Supplier[]>('/party/suppliers')
    setSuppliers(res.data)
  }

  useEffect(() => {
    load()
  }, [])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await apiClient.post('/party/suppliers', {
        name: form.name,
        phone: form.phone || null,
        email: form.email || null,
        gstin: form.gstin || null,
        state_code: form.state_code || null,
      })
      setForm({ name: '', phone: '', email: '', gstin: '', state_code: '' })
      setShowForm(false)
      load()
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  async function openPay(supplier: Supplier) {
    setPayFor(supplier)
    const res = await apiClient.get<SupplierPayment[]>(`/party/suppliers/${supplier.id}/payments`)
    setPayments(res.data)
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-50">Suppliers</h1>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
        >
          {showForm ? 'Cancel' : '+ New Supplier'}
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={handleCreate}
          className="mb-6 grid grid-cols-2 gap-3 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-800 md:grid-cols-3"
        >
          <input required placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <input placeholder="Phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <input placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <input placeholder="GSTIN" value={form.gstin} onChange={(e) => setForm({ ...form, gstin: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <input placeholder="State code" value={form.state_code} onChange={(e) => setForm({ ...form, state_code: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          {error && <p className="col-span-full text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button type="submit" className="col-span-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500">
            Save supplier
          </button>
        </form>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Phone</th>
              <th className="px-4 py-3">GSTIN</th>
              <th className="px-4 py-3">Payable Balance</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {suppliers.map((s) => (
              <tr key={s.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">{s.name}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{s.phone ?? '-'}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{s.gstin ?? '-'}</td>
                <td className="px-4 py-3 text-slate-600 dark:text-slate-300">₹{s.payable_balance.toFixed(2)}</td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={() => openPay(s)}
                    disabled={s.payable_balance <= 0}
                    className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-40"
                  >
                    Pay / History
                  </button>
                </td>
              </tr>
            ))}
            {suppliers.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                  No suppliers found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {payFor && (
        <SupplierPaymentModal
          supplier={payFor}
          payments={payments}
          onClose={() => setPayFor(null)}
          onPaid={load}
          onError={setError}
        />
      )}
    </div>
  )
}

function SupplierPaymentModal({
  supplier,
  payments,
  onClose,
  onPaid,
  onError,
}: {
  supplier: Supplier
  payments: SupplierPayment[]
  onClose: () => void
  onPaid: () => void
  onError: (msg: string | null) => void
}) {
  const [amount, setAmount] = useState('')
  const [method, setMethod] = useState('bank')
  const [reference, setReference] = useState('')
  const [busy, setBusy] = useState(false)

  async function handlePay(e: React.FormEvent) {
    e.preventDefault()
    onError(null)
    const value = Number(amount)
    if (!value || value <= 0) {
      onError('Enter a positive amount.')
      return
    }
    setBusy(true)
    try {
      await apiClient.post(`/party/suppliers/${supplier.id}/pay`, {
        amount: value,
        method,
        reference: reference || null,
      })
      setAmount('')
      setReference('')
      onPaid()
    } catch (err) {
      onError(apiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-xl border border-slate-200 bg-white p-6 shadow-xl dark:border-slate-700 dark:bg-slate-800"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-50">
            Pay {supplier.name}
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">
            &times;
          </button>
        </div>

        <div className="mb-4 rounded-lg bg-slate-50 px-4 py-3 dark:bg-slate-700">
          <p className="text-xs text-slate-500 dark:text-slate-400">Outstanding payable</p>
          <p className="text-xl font-semibold text-slate-900 dark:text-slate-50">₹{supplier.payable_balance.toFixed(2)}</p>
        </div>

        <form onSubmit={handlePay} className="mb-6 grid grid-cols-2 gap-3">
          <input
            required
            type="number"
            min="0.01"
            step="0.01"
            placeholder="Amount"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          />
          <select
            value={method}
            onChange={(e) => setMethod(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          >
            <option value="bank">Bank transfer</option>
            <option value="cash">Cash</option>
            <option value="card">Card</option>
            <option value="upi">UPI</option>
          </select>
          <input
            placeholder="Reference (e.g. RTGS/UTR)"
            value={reference}
            onChange={(e) => setReference(e.target.value)}
            className="col-span-2 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
          />
          <button
            type="submit"
            disabled={busy}
            className="col-span-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            {busy ? 'Recording...' : 'Record Payment'}
          </button>
        </form>

        <h3 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-300">Payment history</h3>
        <div className="max-h-56 overflow-y-auto">
          {payments.length === 0 && <p className="text-sm text-slate-400">No payments recorded.</p>}
          {payments.map((p) => (
            <div
              key={p.id}
              className="flex items-center justify-between border-b border-slate-100 py-2 text-sm last:border-0 dark:border-slate-700"
            >
              <div>
                <p className="text-slate-900 dark:text-slate-100">
                  ₹{p.amount.toFixed(2)} <span className="text-slate-400">via {p.method}</span>
                </p>
                {p.reference && <p className="text-xs text-slate-400">{p.reference}</p>}
              </div>
              <div className="text-right">
                <p className="text-xs text-slate-400">{new Date(p.paid_at).toLocaleString('en-IN')}</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">Outstanding: ₹{p.outstanding_payable.toFixed(2)}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}