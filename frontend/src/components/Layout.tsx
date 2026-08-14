import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'
import { useAuthStore } from '../store/auth'
import type { AppNotification, Subscription } from '../types'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/pos', label: 'Billing (POS)' },
  { to: '/quotations', label: 'Quotations' },
  { to: '/shift', label: 'Shift & Cash' },
  { to: '/sales-history', label: 'Sales & Returns' },
  { to: '/products', label: 'Products' },
  { to: '/customers', label: 'Customers' },
  { to: '/suppliers', label: 'Suppliers' },
  { to: '/purchasing', label: 'Purchasing' },
  { to: '/stock', label: 'Stock' },
  { to: '/stock-transfer', label: 'Stock Transfer' },
  { to: '/staff', label: 'Staff' },
  { to: '/branches', label: 'Branches & Warehouses' },
  { to: '/offers', label: 'Coupons & Gift Cards' },
  { to: '/audit-log', label: 'Audit Log' },
  { to: '/reports', label: 'Reports' },
  { to: '/sync', label: 'Sync Status' },
  { to: '/billing', label: 'Billing (Subscription)' },
  { to: '/settings', label: 'Settings' },
]

function daysLeft(isoDate: string | null): number | null {
  if (!isoDate) return null
  const ms = new Date(isoDate).getTime() - Date.now()
  return Math.max(0, Math.ceil(ms / (1000 * 60 * 60 * 24)))
}

export default function Layout() {
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const navigate = useNavigate()
  const [subscription, setSubscription] = useState<Subscription | null>(null)
  const [notifications, setNotifications] = useState<AppNotification[]>([])
  const [showBell, setShowBell] = useState(false)

  useEffect(() => {
    // A 404 here just means this org predates the subscriptions feature
    // (e.g. the demo/seed org) -- no banner is the correct behavior for
    // those, not an error.
    apiClient
      .get<Subscription>('/subscriptions/me')
      .then((res) => setSubscription(res.data))
      .catch(() => setSubscription(null))
    loadNotifications()
  }, [])

  async function loadNotifications() {
    try {
      const res = await apiClient.get<AppNotification[]>('/notifications', { params: { limit: 20 } })
      setNotifications(res.data)
    } catch {
      setNotifications([])
    }
  }

  async function markRead(id: string) {
    await apiClient.post(`/notifications/${id}/read`)
    loadNotifications()
  }

  const unreadCount = notifications.filter((n) => !n.is_read).length

  const trialDays = subscription?.status === 'trialing' ? daysLeft(subscription.trial_ends_at) : null
  const showTrialBanner = trialDays !== null && trialDays <= 3
  const showPastDueBanner = subscription?.status === 'past_due'

  return (
    <div className="flex min-h-screen bg-slate-50 dark:bg-slate-900">
      <aside className="flex w-56 shrink-0 flex-col border-r border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950">
        <div className="border-b border-slate-200 px-4 py-4 dark:border-slate-800">
          <span className="text-lg font-semibold text-slate-900 dark:text-slate-50">Retail POS</span>
        </div>
        <nav className="flex-1 space-y-1 p-3">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `block rounded-lg px-3 py-2 text-sm font-medium ${
                  isActive
                    ? 'bg-indigo-600 text-white'
                    : 'text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-200 p-3 dark:border-slate-800">
          <p className="mb-2 truncate text-xs text-slate-500 dark:text-slate-400">{user?.email}</p>
          <button
            onClick={() => {
              logout()
              navigate('/login')
            }}
            className="w-full rounded-lg px-3 py-2 text-left text-sm font-medium text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/40"
          >
            Sign out
          </button>
        </div>
      </aside>
      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex items-center justify-end gap-3 border-b border-slate-200 bg-white px-6 py-2 dark:border-slate-800 dark:bg-slate-950">
          <div className="relative">
            <button
              onClick={() => setShowBell((v) => !v)}
              className="relative rounded-lg p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
              aria-label="Notifications"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                <path d="M13.73 21a2 2 0 0 1-3.46 0" />
              </svg>
              {unreadCount > 0 && (
                <span className="absolute -right-0.5 -top-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-red-600 px-1 text-xs font-bold text-white">
                  {unreadCount}
                </span>
              )}
            </button>
            {showBell && (
              <div className="absolute right-0 z-20 mt-2 w-96 rounded-xl border border-slate-200 bg-white shadow-xl dark:border-slate-700 dark:bg-slate-800">
                <div className="flex items-center justify-between border-b border-slate-200 px-4 py-2 dark:border-slate-700">
                  <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">Notifications</p>
                  <button
                    onClick={() => setShowBell(false)}
                    className="text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                  >
                    Close
                  </button>
                </div>
                <div className="max-h-96 overflow-y-auto">
                  {notifications.length === 0 && (
                    <p className="px-4 py-6 text-center text-sm text-slate-400">No notifications.</p>
                  )}
                  {notifications.map((n) => (
                    <button
                      key={n.id}
                      onClick={() => markRead(n.id)}
                      className={`block w-full border-b border-slate-100 px-4 py-3 text-left last:border-0 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-700 ${
                        n.is_read ? 'opacity-60' : ''
                      }`}
                    >
                      <p className="text-sm font-medium text-slate-900 dark:text-slate-100">{n.title}</p>
                      {n.body && <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{n.body}</p>}
                      <p className="mt-1 text-[11px] text-slate-400">{new Date(n.created_at).toLocaleString('en-IN')}</p>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </header>
        {(showTrialBanner || showPastDueBanner) && (
          <div
            className={`px-6 py-2 text-center text-sm font-medium ${
              showPastDueBanner
                ? 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                : 'bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300'
            }`}
          >
            {showPastDueBanner
              ? 'Your subscription needs attention -- billing has lapsed.'
              : `Your free trial ends in ${trialDays} day(s).`}{' '}
            <Link to="/billing" className="underline">
              Manage billing
            </Link>
          </div>
        )}
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
