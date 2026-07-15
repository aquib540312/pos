import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'
import { useAuthStore } from '../store/auth'
import type { Subscription } from '../types'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/pos', label: 'Billing (POS)' },
  { to: '/quotations', label: 'Quotations' },
  { to: '/shift', label: 'Shift & Cash' },
  { to: '/products', label: 'Products' },
  { to: '/customers', label: 'Customers' },
  { to: '/suppliers', label: 'Suppliers' },
  { to: '/purchasing', label: 'Purchasing' },
  { to: '/stock-transfer', label: 'Stock Transfer' },
  { to: '/staff', label: 'Staff' },
  { to: '/branches', label: 'Branches & Warehouses' },
  { to: '/audit-log', label: 'Audit Log' },
  { to: '/reports', label: 'Reports' },
  { to: '/sync', label: 'Sync Status' },
  { to: '/billing', label: 'Billing (Subscription)' },
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

  useEffect(() => {
    // A 404 here just means this org predates the subscriptions feature
    // (e.g. the demo/seed org) -- no banner is the correct behavior for
    // those, not an error.
    apiClient
      .get<Subscription>('/subscriptions/me')
      .then((res) => setSubscription(res.data))
      .catch(() => setSubscription(null))
  }, [])

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
