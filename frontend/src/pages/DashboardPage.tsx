import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiClient } from '../api/client'
import type { StockSummaryReportRow } from '../types'

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
  const [lowStock, setLowStock] = useState<StockSummaryReportRow[] | null>(null)

  useEffect(() => {
    const today = todayISO()
    apiClient
      .get<SalesSummary>('/reports/sales-summary', { params: { start: today, end: today } })
      .then((res) => setSummary(res.data))
      .catch(() => setSummary(null))
    apiClient
      .get<StockSummaryReportRow[]>('/reports/stock-summary')
      .then((res) => setLowStock(res.data.filter((r) => r.below_reorder)))
      .catch(() => setLowStock(null))
  }, [])

  const cards = [
    { label: "Today's Invoices", value: summary?.invoice_count ?? '—' },
    { label: 'Taxable Value', value: summary ? `₹${summary.total_taxable_value.toFixed(2)}` : '—' },
    { label: 'GST Collected', value: summary ? `₹${(summary.total_cgst + summary.total_sgst + summary.total_igst).toFixed(2)}` : '—' },
    { label: 'Grand Total', value: summary ? `₹${summary.total_grand_total.toFixed(2)}` : '—' },
    {
      label: 'Low Stock Items',
      value: lowStock?.length ?? '—',
      warn: Boolean(lowStock && lowStock.length > 0),
    },
  ]

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold text-slate-900 dark:text-slate-50">Dashboard</h1>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {cards.map((card) => (
          <div
            key={card.label}
            className={`rounded-xl border p-5 shadow-sm ${
              card.warn
                ? 'border-amber-300 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/40'
                : 'border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800'
            }`}
          >
            <p className={`text-sm ${card.warn ? 'text-amber-700 dark:text-amber-300' : 'text-slate-500 dark:text-slate-400'}`}>
              {card.label}
            </p>
            <p
              className={`mt-2 text-2xl font-semibold ${
                card.warn ? 'text-amber-700 dark:text-amber-300' : 'text-slate-900 dark:text-slate-50'
              }`}
            >
              {card.value}
            </p>
          </div>
        ))}
      </div>

      {lowStock && lowStock.length > 0 && (
        <div className="mt-6 rounded-xl border border-amber-300 bg-white dark:border-amber-800 dark:bg-slate-800">
          <div className="flex items-center justify-between border-b border-amber-200 px-4 py-3 dark:border-amber-900">
            <h2 className="text-sm font-semibold text-amber-800 dark:text-amber-300">
              Products at or below reorder level
            </h2>
            <Link to="/reports" className="text-sm font-medium text-indigo-600 hover:text-indigo-500">
              View full stock report
            </Link>
          </div>
          <table className="w-full text-left text-sm">
            <thead className="text-slate-500 dark:text-slate-400">
              <tr>
                <th className="px-4 py-2">SKU</th>
                <th className="px-4 py-2">Product</th>
                <th className="px-4 py-2">On Hand</th>
                <th className="px-4 py-2">Reorder Level</th>
              </tr>
            </thead>
            <tbody>
              {lowStock.slice(0, 10).map((r) => (
                <tr key={r.product_id} className="border-t border-slate-100 dark:border-slate-700">
                  <td className="px-4 py-2 text-slate-600 dark:text-slate-300">{r.sku}</td>
                  <td className="px-4 py-2 font-medium text-slate-900 dark:text-slate-100">{r.product_name}</td>
                  <td className="px-4 py-2 text-red-600 dark:text-red-400">{r.quantity_on_hand}</td>
                  <td className="px-4 py-2 text-slate-600 dark:text-slate-300">{r.reorder_level}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {lowStock.length > 10 && (
            <p className="border-t border-amber-200 px-4 py-2 text-xs text-slate-500 dark:border-amber-900 dark:text-slate-400">
              +{lowStock.length - 10} more -- see the full stock report.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
