import { useEffect, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'
import type { Plan, Subscription } from '../types'

function daysLeft(isoDate: string | null): number | null {
  if (!isoDate) return null
  const ms = new Date(isoDate).getTime() - Date.now()
  return Math.max(0, Math.ceil(ms / (1000 * 60 * 60 * 24)))
}

const STATUS_STYLE: Record<string, string> = {
  trialing: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300',
  active: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300',
  past_due: 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300',
  canceled: 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400',
}

export default function BillingPage() {
  const [subscription, setSubscription] = useState<Subscription | null>(null)
  const [plans, setPlans] = useState<Plan[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  async function refresh() {
    const [sub, planList] = await Promise.all([
      apiClient.get<Subscription>('/subscriptions/me'),
      apiClient.get<Plan[]>('/subscriptions/plans'),
    ])
    setSubscription(sub.data)
    setPlans(planList.data)
  }

  useEffect(() => {
    refresh().catch((err) => setError(apiErrorMessage(err)))
  }, [])

  async function changePlan(planCode: string) {
    setError(null)
    setBusy(planCode)
    try {
      const resp = await apiClient.post('/subscriptions/checkout', { plan_code: planCode })
      const checkoutUrl = resp.data.checkout_url as string
      // The mock adapter (dev/CI, no live Razorpay account) marks the plan
      // active immediately and returns a placeholder url -- nothing to
      // redirect to. A real Razorpay checkout returns a hosted page where
      // the customer authorizes payment; only then does the plan change.
      if (checkoutUrl.startsWith('#')) {
        await refresh()
      } else {
        window.location.href = checkoutUrl
      }
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function cancelSubscription() {
    if (!window.confirm('Cancel your subscription? You will lose access once your current period ends.')) return
    setError(null)
    setBusy('cancel')
    try {
      await apiClient.post('/subscriptions/cancel')
      await refresh()
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  if (!subscription) {
    return <div>{error ? <p className="text-sm text-red-600">{error}</p> : 'Loading...'}</div>
  }

  const trialDays = subscription.status === 'trialing' ? daysLeft(subscription.trial_ends_at) : null

  return (
    <div className="max-w-3xl">
      <h1 className="mb-6 text-2xl font-semibold text-slate-900 dark:text-slate-50">Billing</h1>

      {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

      <div className="mb-6 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-800">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <p className="text-sm text-slate-500 dark:text-slate-400">Current plan</p>
            <p className="text-xl font-semibold text-slate-900 dark:text-slate-50">{subscription.plan.name}</p>
          </div>
          <span className={`rounded-full px-3 py-1 text-xs font-medium ${STATUS_STYLE[subscription.status]}`}>
            {subscription.status.replace('_', ' ')}
          </span>
        </div>

        {subscription.status === 'trialing' && trialDays !== null && (
          <p className="mb-3 text-sm text-slate-600 dark:text-slate-300">
            {trialDays > 0 ? `${trialDays} day(s) left in your free trial.` : 'Your trial ends today.'} Pick a plan
            below to keep going without interruption.
          </p>
        )}
        {subscription.status === 'past_due' && (
          <p className="mb-3 text-sm text-amber-700 dark:text-amber-400">
            Your subscription needs attention -- billing has lapsed. Pick a plan below to restore access.
          </p>
        )}
        {subscription.status === 'canceled' && (
          <p className="mb-3 text-sm text-slate-600 dark:text-slate-300">
            Your subscription is canceled. Pick a plan below to reactivate.
          </p>
        )}
        {subscription.current_period_end && subscription.status === 'active' && (
          <p className="mb-3 text-sm text-slate-600 dark:text-slate-300">
            Renews on {new Date(subscription.current_period_end).toLocaleDateString()}.
          </p>
        )}

        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-slate-500 dark:text-slate-400">Branches</p>
            <p className="font-medium text-slate-900 dark:text-slate-100">
              {subscription.branches_used} / {subscription.plan.max_branches ?? 'Unlimited'}
            </p>
          </div>
          <div>
            <p className="text-slate-500 dark:text-slate-400">Users</p>
            <p className="font-medium text-slate-900 dark:text-slate-100">
              {subscription.users_used} / {subscription.plan.max_users ?? 'Unlimited'}
            </p>
          </div>
        </div>

        {subscription.status !== 'canceled' && (
          <button
            onClick={cancelSubscription}
            disabled={busy === 'cancel'}
            className="mt-4 text-sm font-medium text-red-600 hover:text-red-500 disabled:opacity-50"
          >
            {busy === 'cancel' ? 'Canceling...' : 'Cancel subscription'}
          </button>
        )}
      </div>

      <h2 className="mb-3 text-lg font-semibold text-slate-900 dark:text-slate-50">Plans</h2>
      <div className="grid grid-cols-3 gap-4">
        {plans.map((p) => {
          const isCurrent = p.code === subscription.plan.code && subscription.status !== 'canceled'
          return (
            <div
              key={p.code}
              className={`rounded-xl border p-4 ${
                isCurrent ? 'border-indigo-500' : 'border-slate-200 dark:border-slate-700'
              } bg-white dark:bg-slate-800`}
            >
              <p className="font-semibold text-slate-900 dark:text-slate-100">{p.name}</p>
              <p className="mb-2 text-sm text-slate-500 dark:text-slate-400">₹{p.price_monthly}/mo</p>
              <p className="mb-1 text-xs text-slate-500 dark:text-slate-400">
                {p.max_branches ?? 'Unlimited'} branches
              </p>
              <p className="mb-3 text-xs text-slate-500 dark:text-slate-400">{p.max_users ?? 'Unlimited'} users</p>
              <button
                onClick={() => changePlan(p.code)}
                disabled={isCurrent || busy === p.code}
                className="w-full rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
              >
                {isCurrent ? 'Current plan' : busy === p.code ? 'Please wait...' : 'Choose plan'}
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}
