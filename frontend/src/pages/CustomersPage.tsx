import { useEffect, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'
import type { Customer, CustomerPayment } from '../types'

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([])
  const [search, setSearch] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'customers' | 'payments'>('customers')
  const [selectedCustomer, setSelectedCustomer] = useState<string>('')
  const [payments, setPayments] = useState<CustomerPayment[]>([])
  const [showPaymentForm, setShowPaymentForm] = useState(false)
  const [paymentForm, setPaymentForm] = useState({ amount: '', method: 'cash', reference: '' })
  const [form, setForm] = useState({
    name: '', name_arabic: '', phone: '', vat_number: '', cr_number: '', address: '',
    customer_type: 'walk_in', price_level: 'retail', isCredit: false,
    creditLimit: '', payment_terms_days: '',
  })

  async function load(q?: string) {
    const res = await apiClient.get<Customer[]>('/party/customers', { params: q ? { search: q } : {} })
    setCustomers(res.data)
  }

  async function loadPayments(customerId: string) {
    const res = await apiClient.get<CustomerPayment[]>(`/party/customers/${customerId}/payments`)
    setPayments(res.data)
  }

  useEffect(() => { load() }, [])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await apiClient.post('/party/customers', {
        name: form.name, name_arabic: form.name_arabic || null, phone: form.phone || null,
        vat_number: form.vat_number || null, cr_number: form.cr_number || null,
        address: form.address || null, customer_type: form.customer_type,
        price_level: form.price_level, is_credit_customer: form.isCredit,
        credit_limit: form.isCredit ? Number(form.creditLimit || 0) : 0,
        payment_terms_days: Number(form.payment_terms_days || 0),
      })
      setForm({ name: '', name_arabic: '', phone: '', vat_number: '', cr_number: '', address: '', customer_type: 'walk_in', price_level: 'retail', isCredit: false, creditLimit: '', payment_terms_days: '' })
      setShowForm(false)
      load(search)
    } catch (err) { setError(apiErrorMessage(err)) }
  }

  async function handleAddPayment(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await apiClient.post(`/party/customers/${selectedCustomer}/collect`, {
        amount: Number(paymentForm.amount), method: paymentForm.method,
        reference: paymentForm.reference || null,
      })
      setShowPaymentForm(false)
      setPaymentForm({ amount: '', method: 'cash', reference: '' })
      loadPayments(selectedCustomer)
      load()
    } catch (err) { setError(apiErrorMessage(err)) }
  }

  function openPaymentsTab(customerId: string) {
    setActiveTab('payments')
    setSelectedCustomer(customerId)
    loadPayments(customerId)
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-50">Customers</h1>
        <button onClick={() => setShowForm((v) => !v)} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500">
          {showForm ? 'Cancel' : '+ New Customer'}
        </button>
      </div>

      <div className="mb-4 flex gap-4">
        <button onClick={() => setActiveTab('customers')} className={`px-4 py-2 text-sm font-semibold rounded-lg ${activeTab === 'customers' ? 'bg-indigo-600 text-white' : 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-300'}`}>Customers</button>
        <button onClick={() => setActiveTab('payments')} className={`px-4 py-2 text-sm font-semibold rounded-lg ${activeTab === 'payments' ? 'bg-indigo-600 text-white' : 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-300'}`}>Credit Payments</button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="mb-6 grid grid-cols-2 gap-3 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-800 md:grid-cols-4 lg:grid-cols-6">
          <input required placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <input placeholder="Arabic name" value={form.name_arabic} onChange={(e) => setForm({ ...form, name_arabic: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <input placeholder="Phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <input placeholder="VAT Number" value={form.vat_number} onChange={(e) => setForm({ ...form, vat_number: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <input placeholder="CR Number" value={form.cr_number} onChange={(e) => setForm({ ...form, cr_number: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <select value={form.customer_type} onChange={(e) => setForm({ ...form, customer_type: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100">
            <option value="walk_in">Walk-in</option><option value="restaurant">Restaurant</option><option value="hotel">Hotel</option><option value="catering">Catering</option><option value="regular">Regular</option><option value="wholesale">Wholesale</option>
          </select>
          <select value={form.price_level} onChange={(e) => setForm({ ...form, price_level: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100">
            <option value="retail">Retail</option><option value="wholesale">Wholesale</option><option value="restaurant">Restaurant</option><option value="vip">VIP</option><option value="custom">Custom</option>
          </select>
          <input placeholder="Address" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300"><input type="checkbox" checked={form.isCredit} onChange={(e) => setForm({ ...form, isCredit: e.target.checked })} /> Credit customer</label>
          {form.isCredit && <input type="number" step="0.01" placeholder="Credit limit" value={form.creditLimit} onChange={(e) => setForm({ ...form, creditLimit: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />}
          <input type="number" placeholder="Payment terms (days)" value={form.payment_terms_days} onChange={(e) => setForm({ ...form, payment_terms_days: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
          {error && <p className="col-span-full text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button type="submit" className="col-span-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500">Save customer</button>
        </form>
      )}

      {activeTab === 'customers' && (
        <>
          <div className="mb-4">
            <input placeholder="Search by name or phone..." value={search} onChange={(e) => { setSearch(e.target.value); load(e.target.value) }} className="w-full max-w-sm rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100" />
          </div>
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
                <tr>
                  <th className="px-4 py-3">Name</th><th className="px-4 py-3">Phone</th><th className="px-4 py-3">VAT Number</th>
                  <th className="px-4 py-3">Type</th><th className="px-4 py-3">Price Level</th><th className="px-4 py-3">Credit Limit</th>
                  <th className="px-4 py-3">Outstanding</th><th className="px-4 py-3">Loyalty Points</th><th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {customers.map((c) => (
                  <tr key={c.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                    <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">{c.name}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{c.phone ?? '—'}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{c.vat_number ?? '—'}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{c.customer_type ?? '—'}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{c.price_level ?? '—'}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{c.is_credit_customer ? `SAR ${c.credit_limit.toFixed(2)}` : '—'}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{c.is_credit_customer ? `SAR ${c.credit_balance.toFixed(2)}` : '—'}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{c.loyalty_points_balance}</td>
                    <td className="px-4 py-3">{c.is_credit_customer ? <button onClick={() => openPaymentsTab(c.id)} className="text-indigo-600 hover:underline text-sm">View Payments</button> : <span className="text-slate-400 text-sm">—</span>}</td>
                  </tr>
                ))}
                {customers.length === 0 && <tr><td colSpan={9} className="px-4 py-6 text-center text-slate-400">No customers found.</td></tr>}
              </tbody>
            </table>
          </div>
        </>
      )}

      {activeTab === 'payments' && (
        <div>
          <div className="mb-4">
            <select value={selectedCustomer} onChange={(e) => { setSelectedCustomer(e.target.value); loadPayments(e.target.value) }} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100">
              <option value="">Select a customer...</option>
              {customers.filter(c => c.is_credit_customer).map(c => (
                <option key={c.id} value={c.id}>{c.name} (Balance: SAR {c.credit_balance.toFixed(2)})</option>
              ))}
            </select>
          </div>
          {selectedCustomer && (
            <>
              <button onClick={() => setShowPaymentForm(true)} className="mb-4 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500">+ Add Payment</button>
              {showPaymentForm && (
                <form onSubmit={handleAddPayment} className="mb-6 grid grid-cols-3 gap-3 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-800">
                  <input type="number" step="0.01" required placeholder="Amount" value={paymentForm.amount} onChange={(e) => setPaymentForm({ ...paymentForm, amount: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
                  <select value={paymentForm.method} onChange={(e) => setPaymentForm({ ...paymentForm, method: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100">
                    <option value="cash">Cash</option><option value="card">Card</option><option value="bank_transfer">Bank Transfer</option>
                  </select>
                  <input placeholder="Reference (optional)" value={paymentForm.reference} onChange={(e) => setPaymentForm({ ...paymentForm, reference: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
                  <button type="submit" className="col-span-3 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500">Record Payment</button>
                  {error && <p className="col-span-3 text-sm text-red-600 dark:text-red-400">{error}</p>}
                </form>
              )}
              <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
                    <tr><th className="px-4 py-3">Date</th><th className="px-4 py-3">Method</th><th className="px-4 py-3">Amount</th><th className="px-4 py-3">Reference</th></tr>
                  </thead>
                  <tbody>
                    {payments.map((p) => (
                      <tr key={p.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                        <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{new Date(p.paid_at).toLocaleString('en-SA')}</td>
                        <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{p.method}</td>
                        <td className="px-4 py-3 font-medium text-emerald-600">SAR {p.amount.toFixed(2)}</td>
                        <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{p.reference ?? '—'}</td>
                      </tr>
                    ))}
                    {payments.length === 0 && <tr><td colSpan={4} className="px-4 py-6 text-center text-slate-400">No payments recorded.</td></tr>}
                  </tbody>
                </table>
              </div>
            </>
          )}
          {!selectedCustomer && <p className="text-center text-slate-400 py-8">Select a customer to view their payment history.</p>}
        </div>
      )}
    </div>
  )
}
