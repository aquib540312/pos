import { useEffect, useRef, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'
import type { PaymentGatewayTransaction } from '../types'

const POLL_INTERVAL_MS = 3000
const MAX_CONSECUTIVE_POLL_FAILURES = 5

type PanelState = 'idle' | 'creating' | 'awaiting' | 'paid' | 'expired' | 'cancelled' | 'error'

interface Props {
  amount: number
  receiptReference: string
  disabled?: boolean
  onPaid: (transaction: PaymentGatewayTransaction) => void
}

export default function UpiQrPanel({ amount, receiptReference, disabled, onPaid }: Props) {
  const [state, setState] = useState<PanelState>('idle')
  const [transaction, setTransaction] = useState<PaymentGatewayTransaction | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [secondsLeft, setSecondsLeft] = useState(0)
  const [reconnecting, setReconnecting] = useState(false)

  const pollRef = useRef<number | null>(null)
  const countdownRef = useRef<number | null>(null)
  const failureCountRef = useRef(0)
  // Guards against onPaid firing twice (e.g. one poll tick sees "paid" right
  // before stopPolling() takes effect on the next tick) -- that would submit
  // two POST /sales for the same money, and the second would only be caught
  // by the backend's 409 after the fact.
  const paidHandledRef = useRef(false)

  function stopPolling() {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current)
      pollRef.current = null
    }
    if (countdownRef.current !== null) {
      window.clearInterval(countdownRef.current)
      countdownRef.current = null
    }
  }

  useEffect(() => stopPolling, [])

  function startCountdown(closeBy: string | null) {
    if (!closeBy) return
    const target = new Date(closeBy).getTime()
    const tick = () => setSecondsLeft(Math.max(0, Math.round((target - Date.now()) / 1000)))
    tick()
    countdownRef.current = window.setInterval(tick, 1000)
  }

  async function poll(transactionId: string) {
    try {
      const res = await apiClient.get<PaymentGatewayTransaction>(`/payments/razorpay/qr/${transactionId}`)
      failureCountRef.current = 0
      setReconnecting(false)
      setTransaction(res.data)
      if (res.data.status === 'paid') {
        if (paidHandledRef.current) return
        paidHandledRef.current = true
        stopPolling()
        setState('paid')
        onPaid(res.data)
      } else if (res.data.status === 'expired') {
        stopPolling()
        setState('expired')
      } else if (res.data.status === 'closed') {
        stopPolling()
        setState('cancelled')
      }
    } catch {
      // A dropped connection while waiting for a customer's UPI payment is
      // not fatal -- the QR is still valid on Razorpay's side, so keep
      // retrying silently until a cap is hit, rather than aborting the sale.
      failureCountRef.current += 1
      if (failureCountRef.current >= MAX_CONSECUTIVE_POLL_FAILURES) {
        stopPolling()
        setState('error')
        setError(
          'Lost connection while waiting for payment confirmation. If the customer already paid, wait a moment and check again before retrying.',
        )
      } else {
        setReconnecting(true)
      }
    }
  }

  async function createQr() {
    setError(null)
    setState('creating')
    paidHandledRef.current = false
    failureCountRef.current = 0
    try {
      const res = await apiClient.post<PaymentGatewayTransaction>('/payments/razorpay/qr', {
        amount,
        receipt_reference: receiptReference,
      })
      setTransaction(res.data)
      setState('awaiting')
      startCountdown(res.data.close_by)
      pollRef.current = window.setInterval(() => poll(res.data.id), POLL_INTERVAL_MS)
    } catch (err) {
      setError(apiErrorMessage(err))
      setState('error')
    }
  }

  async function cancel() {
    const current = transaction
    stopPolling()
    setTransaction(null)
    setState('idle')
    setError(null)
    if (!current) return
    try {
      await apiClient.post(`/payments/razorpay/qr/${current.id}/cancel`)
    } catch {
      // Best-effort: even if this call fails (e.g. network drop), abandoning
      // the panel is still safe -- the QR simply expires server-side on its
      // own and can never be double-spent onto an invoice either way.
    }
  }

  function retry() {
    stopPolling()
    setTransaction(null)
    setError(null)
    createQr()
  }

  if (disabled) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-400 dark:border-slate-800 dark:bg-slate-800">
        Add items to the cart to generate a UPI QR.
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-800">
      <h2 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-300">Pay via UPI QR</h2>

      {state === 'idle' && (
        <button
          onClick={createQr}
          className="w-full rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
        >
          Generate QR (₹{amount.toFixed(2)})
        </button>
      )}

      {state === 'creating' && <p className="text-sm text-slate-500">Generating QR...</p>}

      {state === 'awaiting' && transaction && (
        <div className="text-center">
          {transaction.qr_image_url && (
            <img
              src={transaction.qr_image_url}
              alt="Scan to pay via UPI"
              className="mx-auto mb-2 h-40 w-40 rounded border border-slate-200 dark:border-slate-600"
            />
          )}
          <p className="text-sm font-medium text-slate-900 dark:text-slate-100">₹{transaction.amount.toFixed(2)}</p>
          <p className="text-xs text-slate-400">
            {secondsLeft > 0
              ? `Expires in ${Math.floor(secondsLeft / 60)}:${String(secondsLeft % 60).padStart(2, '0')}`
              : 'Expiring...'}
          </p>
          {reconnecting && <p className="mt-1 text-xs text-amber-600">Reconnecting...</p>}
          <button onClick={cancel} className="mt-3 text-sm font-medium text-red-500 hover:text-red-600">
            Cancel
          </button>
        </div>
      )}

      {state === 'paid' && <p className="text-sm text-emerald-600">Payment received -- completing sale...</p>}

      {state === 'expired' && (
        <div className="text-center">
          <p className="mb-2 text-sm text-amber-600">QR expired before payment was received.</p>
          <button
            onClick={retry}
            className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
          >
            Generate New QR
          </button>
        </div>
      )}

      {state === 'cancelled' && (
        <div className="text-center">
          <p className="mb-2 text-sm text-slate-500">Payment cancelled.</p>
          <button
            onClick={retry}
            className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
          >
            Generate New QR
          </button>
        </div>
      )}

      {state === 'error' && (
        <div className="text-center">
          <p className="mb-2 text-sm text-red-600">{error}</p>
          <button
            onClick={retry}
            className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
          >
            Retry
          </button>
        </div>
      )}
    </div>
  )
}
