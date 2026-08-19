import { useEffect, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'
import type { Coupon, Customer, GiftCard } from '../types'

export default function OffersPage() {
  const [tab, setTab] = useState<'coupons' | 'giftcards'>('coupons')
  const [coupons, setCoupons] = useState<Coupon[]>([])
  const [giftCards, setGiftCards] = useState<GiftCard[]>([])
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [showCouponForm, setShowCouponForm] = useState(false)
  const [showGiftCardForm, setShowGiftCardForm] = useState(false)

  async function load() {
    try {
      const [c, g] = await Promise.all([
        apiClient.get<Coupon[]>('/loyalty/coupons'),
        apiClient.get<GiftCard[]>('/loyalty/gift-cards'),
      ])
      setCoupons(c.data)
      setGiftCards(g.data)
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function toggleCoupon(id: string, isActive: boolean) {
    setMessage(null)
    setError(null)
    try {
      await apiClient.post(`/loyalty/coupons/${id}/deactivate`)
      setMessage(isActive ? 'Coupon deactivated.' : 'Coupon activated.')
      await load()
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  async function toggleGiftCard(id: string, isActive: boolean) {
    setMessage(null)
    setError(null)
    try {
      await apiClient.post(`/loyalty/gift-cards/${id}/deactivate`)
      setMessage(isActive ? 'Gift card deactivated.' : 'Gift card activated.')
      await load()
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-50">Coupons & Gift Cards</h1>
        <div className="flex gap-2">
          <button
            onClick={() => setTab('coupons')}
            className={`rounded-lg px-4 py-2 text-sm font-semibold ${
              tab === 'coupons' ? 'bg-indigo-600 text-white' : 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200'
            }`}
          >
            Coupons
          </button>
          <button
            onClick={() => setTab('giftcards')}
            className={`rounded-lg px-4 py-2 text-sm font-semibold ${
              tab === 'giftcards' ? 'bg-indigo-600 text-white' : 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200'
            }`}
          >
            Gift Cards
          </button>
        </div>
      </div>

      {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}
      {message && <p className="mb-4 text-sm text-emerald-600 dark:text-emerald-400">{message}</p>}

      <div className="mb-4 flex justify-end">
        {tab === 'coupons' ? (
          <button
            onClick={() => {
              setError(null)
              setShowCouponForm((v) => !v)
            }}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
          >
            + New Coupon
          </button>
        ) : (
          <button
            onClick={() => {
              setError(null)
              setShowGiftCardForm((v) => !v)
            }}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
          >
            + Issue Gift Card
          </button>
        )}
      </div>

      {showCouponForm && (
        <CouponCreateForm
          onDone={async () => {
            setShowCouponForm(false)
            setMessage('Coupon created.')
            await load()
          }}
          onError={setError}
        />
      )}
      {showGiftCardForm && (
        <GiftCardCreateForm
          onDone={async () => {
            setShowGiftCardForm(false)
            setMessage('Gift card issued and activated.')
            await load()
          }}
          onError={setError}
        />
      )}

      {tab === 'coupons' ? (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
              <tr>
                <th className="px-4 py-3">Code</th>
                <th className="px-4 py-3">Discount</th>
                <th className="px-4 py-3">Min Order</th>
                <th className="px-4 py-3">Redeemed</th>
                <th className="px-4 py-3">Max Uses</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Action</th>
              </tr>
            </thead>
            <tbody>
              {coupons.map((c) => (
                <tr key={c.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                  <td className="px-4 py-3 font-mono font-medium text-slate-900 dark:text-slate-100">{c.code}</td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                    {c.discount_type === 'percent' ? `${c.discount_value}%` : `₹${c.discount_value.toFixed(2)}`}
                  </td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-300">₹{c.min_order_value.toFixed(2)}</td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{c.times_redeemed}</td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{c.max_redemptions ?? '∞'}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        c.is_active
                          ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                          : 'bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
                      }`}
                    >
                      {c.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => toggleCoupon(c.id, c.is_active)}
                      className={`text-sm hover:underline ${
                        c.is_active ? 'text-red-600 dark:text-red-400' : 'text-emerald-600 dark:text-emerald-400'
                      }`}
                    >
                      {c.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                  </td>
                </tr>
              ))}
              {coupons.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-6 text-center text-slate-400">
                    No coupons created yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
              <tr>
                <th className="px-4 py-3">Card #</th>
                <th className="px-4 py-3">Initial Value</th>
                <th className="px-4 py-3">Balance</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Action</th>
              </tr>
            </thead>
            <tbody>
              {giftCards.map((g) => (
                <tr key={g.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
                  <td className="px-4 py-3 font-mono font-medium text-slate-900 dark:text-slate-100">{g.card_number}</td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-300">₹{g.initial_value.toFixed(2)}</td>
                  <td className="px-4 py-3 text-slate-900 dark:text-slate-100">₹{g.balance.toFixed(2)}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        g.is_active
                          ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                          : 'bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
                      }`}
                    >
                      {g.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => toggleGiftCard(g.id, g.is_active)}
                      className={`text-sm hover:underline ${
                        g.is_active ? 'text-red-600 dark:text-red-400' : 'text-emerald-600 dark:text-emerald-400'
                      }`}
                    >
                      {g.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                  </td>
                </tr>
              ))}
              {giftCards.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                    No gift cards created yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

const inputCls =
  'rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100'
const labelCls = 'mb-1 block text-xs font-medium text-slate-500 dark:text-slate-400'

function CouponCreateForm({ onDone, onError }: { onDone: () => void; onError: (msg: string | null) => void }) {
  const [code, setCode] = useState('')
  const [discountType, setDiscountType] = useState<'percent' | 'flat'>('percent')
  const [discountValue, setDiscountValue] = useState('10')
  const [minOrderValue, setMinOrderValue] = useState('0')
  const [maxRedemptions, setMaxRedemptions] = useState('')
  const [validFrom, setValidFrom] = useState(todayIso())
  const [validUntil, setValidUntil] = useState('')
  const [busy, setBusy] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    onError(null)
    if (discountType === 'percent' && Number(discountValue) > 100) {
      onError('Percentage discount cannot exceed 100%.')
      return
    }
    setBusy(true)
    try {
      await apiClient.post('/loyalty/coupons', {
        code: code.trim(),
        discount_type: discountType,
        discount_value: Number(discountValue),
        min_order_value: Number(minOrderValue || 0),
        max_redemptions: maxRedemptions ? Number(maxRedemptions) : null,
        valid_from: validFrom,
        valid_until: validUntil || null,
      })
      onDone()
    } catch (err) {
      onError(apiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mb-6 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-800">
      <h2 className="mb-3 text-sm font-semibold text-slate-900 dark:text-slate-50">New Coupon</h2>
      <div className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <div>
          <label className={labelCls}>Code</label>
          <input required value={code} onChange={(e) => setCode(e.target.value)} placeholder="SAVE10" className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>Discount Type</label>
          <select value={discountType} onChange={(e) => setDiscountType(e.target.value as 'percent' | 'flat')} className={inputCls}>
            <option value="percent">Percent (%)</option>
            <option value="flat">Flat (₹)</option>
          </select>
        </div>
        <div>
          <label className={labelCls}>
            {discountType === 'percent' ? 'Discount %' : 'Discount (₹)'}
          </label>
          <input
            required
            type="number"
            min="0.01"
            step="0.01"
            value={discountValue}
            onChange={(e) => setDiscountValue(e.target.value)}
            className={inputCls}
          />
        </div>
        <div>
          <label className={labelCls}>Min Order Value (₹)</label>
          <input type="number" min="0" step="0.01" value={minOrderValue} onChange={(e) => setMinOrderValue(e.target.value)} className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>Max Uses (blank = unlimited)</label>
          <input type="number" min="1" step="1" value={maxRedemptions} onChange={(e) => setMaxRedemptions(e.target.value)} className={inputCls} />
        </div>
        <div className="col-span-2 sm:col-span-3 grid grid-cols-2 gap-3">
          <div>
            <label className={labelCls}>Valid From</label>
            <input required type="date" value={validFrom} onChange={(e) => setValidFrom(e.target.value)} className={inputCls} />
          </div>
          <div>
            <label className={labelCls}>Valid Until (blank = no expiry)</label>
            <input type="date" value={validUntil} onChange={(e) => setValidUntil(e.target.value)} className={inputCls} />
          </div>
        </div>
      </div>
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={() => onDone()}
          className="rounded-lg bg-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-300 dark:bg-slate-700 dark:text-slate-100"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={busy}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {busy ? 'Saving...' : 'Create Coupon'}
        </button>
      </div>
    </form>
  )
}

function GiftCardCreateForm({ onDone, onError }: { onDone: () => void; onError: (msg: string | null) => void }) {
  const [cardNumber, setCardNumber] = useState('')
  const [initialValue, setInitialValue] = useState('')
  const [customerId, setCustomerId] = useState('')
  const [expiresOn, setExpiresOn] = useState('')
  const [customers, setCustomers] = useState<Customer[]>([])
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    apiClient
      .get<Customer[]>('/party/customers')
      .then((r) => setCustomers(r.data))
      .catch(() => {})
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    onError(null)
    setBusy(true)
    try {
      await apiClient.post('/loyalty/gift-cards', {
        card_number: cardNumber.trim(),
        initial_value: Number(initialValue),
        issued_to_customer_id: customerId || null,
        expires_on: expiresOn || null,
      })
      onDone()
    } catch (err) {
      onError(apiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mb-6 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-800">
      <h2 className="mb-3 text-sm font-semibold text-slate-900 dark:text-slate-50">Issue Gift Card</h2>
      <div className="mb-3 grid grid-cols-2 gap-3">
        <div>
          <label className={labelCls}>Card Number</label>
          <input required value={cardNumber} onChange={(e) => setCardNumber(e.target.value)} placeholder="GC-000001" className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>Initial Value (₹)</label>
          <input required type="number" min="1" step="0.01" value={initialValue} onChange={(e) => setInitialValue(e.target.value)} className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>Customer (optional)</label>
          <select value={customerId} onChange={(e) => setCustomerId(e.target.value)} className={inputCls}>
            <option value="">No customer</option>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelCls}>Expires On (optional)</label>
          <input type="date" value={expiresOn} onChange={(e) => setExpiresOn(e.target.value)} className={inputCls} />
        </div>
      </div>
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={() => onDone()}
          className="rounded-lg bg-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-300 dark:bg-slate-700 dark:text-slate-100"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={busy}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {busy ? 'Issuing...' : 'Issue Gift Card'}
        </button>
      </div>
    </form>
  )
}