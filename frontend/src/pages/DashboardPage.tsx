import { useEffect, useState } from 'react'
import { apiClient } from '../api/client'

interface SalesSummary {
  invoice_count: number
  total_taxable_value: number
  total_cgst: number
  total_sgst: number
  total_igst: number
  total_grand_total: number
}

function todayISO() {
  return new Date().toISOString().slice(0, 10)
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<SalesSummary | null>(null)

  useEffect(() => {
    const today = todayISO()
    apiClient
      .get<SalesSummary>('/reports/sales-summary', { params: { start: today, end: today } })
      .then((res) => setSummary(res.data))
      .catch(() => setSummary(null))
  }, [])

  const cards = [
    { label: "Today's Invoices", value: summary?.invoice_count ?? '—' },
    { label: 'Taxable Value', value: summary ? `₹${summary.total_taxable_value.toFixed(2)}` : '—' },
    { label: 'GST Collected', value: summary ? `₹${(summary.total_cgst + summary.total_sgst + summary.total_igst).toFixed(2)}` : '—' },
    { label: 'Grand Total', value: summary ? `₹${summary.total_grand_total.toFixed(2)}` : '—' },
  ]

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold text-slate-900 dark:text-slate-50">Dashboard</h1>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((card) => (
          <div
            key={card.label}
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-800"
          >
            <p className="text-sm text-slate-500 dark:text-slate-400">{card.label}</p>
            <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-slate-50">{card.value}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
