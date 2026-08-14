import { useEffect, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'
import type { Coupon, GiftCard } from '../types'

export default function OffersPage() {
  const [tab, setTab] = useState<'coupons' | 'giftcards'>('coupons')
  const [coupons, setCoupons] = useState<Coupon[]>([])
  const [giftCards, setGiftCards] = useState<GiftCard[]>([])
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

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
