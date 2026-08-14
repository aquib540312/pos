import { useEffect, useState } from 'react'
import { apiClient, apiErrorMessage } from '../api/client'
import type {
  BalanceSheetReport,
  CashierSalesReportRow,
  ExpiringStockRow,
  GSTR1ReportRow,
  PaymentBreakdownReportRow,
  ProfitAndLossReport,
  SalesSummaryReport,
  StockSummaryReportRow,
  StockValuationRow,
  TopProductReportRow,
} from '../types'

type TabKey =
  | 'sales-summary'
  | 'top-products'
  | 'payment-breakdown'
  | 'sales-by-cashier'
  | 'stock-summary'
  | 'expiring-stock'
  | 'stock-valuation'
  | 'gstr1'
  | 'profit-and-loss'
  | 'balance-sheet'

const TABS: { key: TabKey; label: string; needsDateRange: boolean; needsAsOf?: boolean }[] = [
  { key: 'sales-summary', label: 'Sales Summary', needsDateRange: true },
  { key: 'top-products', label: 'Top Products', needsDateRange: true },
  { key: 'payment-breakdown', label: 'Payment Breakdown', needsDateRange: true },
  { key: 'sales-by-cashier', label: 'Sales by Cashier', needsDateRange: true },
  { key: 'stock-summary', label: 'Stock Summary', needsDateRange: false },
  { key: 'expiring-stock', label: 'Expiring Stock', needsDateRange: false },
  { key: 'stock-valuation', label: 'Stock Valuation', needsDateRange: false },
  { key: 'gstr1', label: 'GSTR-1', needsDateRange: true },
  { key: 'profit-and-loss', label: 'Profit & Loss', needsDateRange: true },
  { key: 'balance-sheet', label: 'Balance Sheet', needsDateRange: false, needsAsOf: true },
]

function todayISO() {
  return new Date().toISOString().slice(0, 10)
}

function inr(n: number) {
  return `₹${n.toFixed(2)}`
}

export default function ReportsPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('sales-summary')
  const [start, setStart] = useState(todayISO())
  const [end, setEnd] = useState(todayISO())
  const [asOf, setAsOf] = useState(todayISO())
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [salesSummary, setSalesSummary] = useState<SalesSummaryReport | null>(null)
  const [topProducts, setTopProducts] = useState<TopProductReportRow[]>([])
  const [paymentBreakdown, setPaymentBreakdown] = useState<PaymentBreakdownReportRow[]>([])
  const [cashierSales, setCashierSales] = useState<CashierSalesReportRow[]>([])
  const [stockSummary, setStockSummary] = useState<StockSummaryReportRow[]>([])
  const [expiringStock, setExpiringStock] = useState<ExpiringStockRow[]>([])
  const [stockValuation, setStockValuation] = useState<StockValuationRow[]>([])
  const [gstr1, setGstr1] = useState<GSTR1ReportRow[]>([])
  const [profitAndLoss, setProfitAndLoss] = useState<ProfitAndLossReport | null>(null)
  const [balanceSheet, setBalanceSheet] = useState<BalanceSheetReport | null>(null)

  async function load(tab: TabKey) {
    setError(null)
    setLoading(true)
    try {
      switch (tab) {
        case 'sales-summary': {
          const res = await apiClient.get<SalesSummaryReport>('/reports/sales-summary', { params: { start, end } })
          setSalesSummary(res.data)
          break
        }
        case 'top-products': {
          const res = await apiClient.get<TopProductReportRow[]>('/reports/top-products', { params: { start, end, limit: 20 } })
          setTopProducts(res.data)
          break
        }
        case 'payment-breakdown': {
          const res = await apiClient.get<PaymentBreakdownReportRow[]>('/reports/payment-breakdown', { params: { start, end } })
          setPaymentBreakdown(res.data)
          break
        }
        case 'sales-by-cashier': {
          const res = await apiClient.get<CashierSalesReportRow[]>('/reports/sales-by-cashier', { params: { start, end } })
          setCashierSales(res.data)
          break
        }
        case 'stock-summary': {
          const res = await apiClient.get<StockSummaryReportRow[]>('/reports/stock-summary')
          setStockSummary(res.data)
          break
        }
        case 'expiring-stock': {
          const res = await apiClient.get<ExpiringStockRow[]>('/reports/expiring-stock')
          setExpiringStock(res.data)
          break
        }
        case 'stock-valuation': {
          const res = await apiClient.get<StockValuationRow[]>('/reports/stock-valuation')
          setStockValuation(res.data)
          break
        }
        case 'gstr1': {
          const res = await apiClient.get<GSTR1ReportRow[]>('/reports/gstr1', { params: { start, end } })
          setGstr1(res.data)
          break
        }
        case 'profit-and-loss': {
          const res = await apiClient.get<ProfitAndLossReport>('/reports/profit-and-loss', { params: { start, end } })
          setProfitAndLoss(res.data)
          break
        }
        case 'balance-sheet': {
          const res = await apiClient.get<BalanceSheetReport>('/reports/balance-sheet', { params: { as_of: asOf } })
          setBalanceSheet(res.data)
          break
        }
      }
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load(activeTab)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab])

  const tab = TABS.find((t) => t.key === activeTab)!

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold text-slate-900 dark:text-slate-50">Reports</h1>

      <div className="mb-4 flex flex-wrap gap-2 border-b border-slate-200 pb-2 dark:border-slate-700">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
              activeTab === t.key
                ? 'bg-indigo-600 text-white'
                : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="mb-6 flex flex-wrap items-end gap-3">
        {tab.needsDateRange && (
          <>
            <label className="text-sm text-slate-600 dark:text-slate-300">
              From
              <input
                type="date"
                value={start}
                onChange={(e) => setStart(e.target.value)}
                className="mt-1 block rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
              />
            </label>
            <label className="text-sm text-slate-600 dark:text-slate-300">
              To
              <input
                type="date"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
                className="mt-1 block rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
              />
            </label>
          </>
        )}
        {tab.needsAsOf && (
          <label className="text-sm text-slate-600 dark:text-slate-300">
            As of
            <input
              type="date"
              value={asOf}
              onChange={(e) => setAsOf(e.target.value)}
              className="mt-1 block rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
            />
          </label>
        )}
        <button
          onClick={() => load(activeTab)}
          disabled={loading}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {loading ? 'Loading...' : 'Run Report'}
        </button>
      </div>

      {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

      {activeTab === 'sales-summary' && salesSummary && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { label: 'Invoices', value: salesSummary.invoice_count.toString() },
            { label: 'Taxable Value', value: inr(salesSummary.total_taxable_value) },
            { label: 'GST Collected', value: inr(salesSummary.total_cgst + salesSummary.total_sgst + salesSummary.total_igst + salesSummary.total_cess) },
            { label: 'Grand Total', value: inr(salesSummary.total_grand_total) },
          ].map((card) => (
            <div key={card.label} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-800">
              <p className="text-sm text-slate-500 dark:text-slate-400">{card.label}</p>
              <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-slate-50">{card.value}</p>
            </div>
          ))}
        </div>
      )}

      {activeTab === 'top-products' && (
        <Table
          columns={['Product', 'SKU', 'Qty Sold', 'Revenue']}
          rows={topProducts.map((r) => [r.product_name, r.sku, r.quantity_sold.toString(), inr(r.revenue)])}
          emptyText="No sales in this period."
        />
      )}

      {activeTab === 'payment-breakdown' && (
        <Table
          columns={['Method', 'Payment Count', 'Total Amount']}
          rows={paymentBreakdown.map((r) => [r.method.toUpperCase(), r.payment_count.toString(), inr(r.total_amount)])}
          emptyText="No payments in this period."
        />
      )}

      {activeTab === 'sales-by-cashier' && (
        <Table
          columns={['Cashier', 'Invoices', 'Total Sales']}
          rows={cashierSales.map((r) => [r.user_name, r.invoice_count.toString(), inr(r.total_grand_total)])}
          emptyText="No shift-attributed sales in this period."
        />
      )}

      {activeTab === 'stock-summary' && (
        <Table
          columns={['Product', 'SKU', 'Qty on Hand', 'Reorder Level', 'Status']}
          rows={stockSummary.map((r) => [
            r.product_name,
            r.sku,
            r.quantity_on_hand.toString(),
            r.reorder_level.toString(),
            r.below_reorder ? '⚠ Below reorder' : 'OK',
          ])}
          emptyText="No products found."
        />
      )}

      {activeTab === 'expiring-stock' && (
        <Table
          columns={['Product', 'SKU', 'Batch', 'Warehouse', 'Qty', 'Expiry', 'Days Left']}
          rows={expiringStock.map((r) => [
            r.product_name,
            r.sku,
            r.batch_number,
            r.warehouse_name ?? r.warehouse_id.slice(0, 8),
            r.quantity_on_hand.toString(),
            r.expiry_date,
            r.days_to_expiry === null ? '—' : r.days_to_expiry.toString(),
          ])}
          emptyText="No expiring stock."
        />
      )}

      {activeTab === 'stock-valuation' && (
        <div>
          <p className="mb-3 text-sm text-slate-600 dark:text-slate-300">
            Total valuation:{' '}
            <span className="font-semibold text-slate-900 dark:text-slate-50">
              {inr(stockValuation.reduce((sum, r) => sum + r.valuation, 0))}
            </span>
          </p>
          <Table
            columns={['Product', 'SKU', 'Qty on Hand', 'Avg Cost', 'Valuation']}
            rows={stockValuation.map((r) => [
              r.product_name,
              r.sku,
              r.quantity_on_hand.toString(),
              inr(r.average_cost),
              inr(r.valuation),
            ])}
            emptyText="No stock valuation data."
          />
        </div>
      )}

      {activeTab === 'gstr1' && (
        <Table
          columns={['HSN Code', 'Rate %', 'Taxable Value', 'CGST', 'SGST', 'IGST', 'Cess', 'Invoices']}
          rows={gstr1.map((r) => [
            r.hsn_code, r.tax_rate_percent.toString(), inr(r.taxable_value), inr(r.cgst), inr(r.sgst), inr(r.igst),
            inr(r.cess), r.invoice_count.toString(),
          ])}
          emptyText="No GST data in this period."
        />
      )}

      {activeTab === 'profit-and-loss' && profitAndLoss && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-800">
              <p className="text-sm text-slate-500 dark:text-slate-400">Total Income</p>
              <p className="mt-2 text-2xl font-semibold text-emerald-600">{inr(profitAndLoss.total_income)}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-800">
              <p className="text-sm text-slate-500 dark:text-slate-400">Total Expense</p>
              <p className="mt-2 text-2xl font-semibold text-red-600">{inr(profitAndLoss.total_expense)}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-800">
              <p className="text-sm text-slate-500 dark:text-slate-400">Net Profit</p>
              <p className={`mt-2 text-2xl font-semibold ${profitAndLoss.net_profit >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                {inr(profitAndLoss.net_profit)}
              </p>
            </div>
          </div>
          <div>
            <h2 className="mb-2 text-lg font-semibold text-slate-800 dark:text-slate-200">Income</h2>
            <Table
              columns={['Code', 'Account', 'Amount']}
              rows={profitAndLoss.income_lines.map((l) => [l.account_code, l.account_name, inr(l.amount)])}
              emptyText="No income lines."
            />
          </div>
          <div>
            <h2 className="mb-2 text-lg font-semibold text-slate-800 dark:text-slate-200">Expenses</h2>
            <Table
              columns={['Code', 'Account', 'Amount']}
              rows={profitAndLoss.expense_lines.map((l) => [l.account_code, l.account_name, inr(l.amount)])}
              emptyText="No expense lines."
            />
          </div>
        </div>
      )}

      {activeTab === 'balance-sheet' && balanceSheet && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-800">
              <p className="text-sm text-slate-500 dark:text-slate-400">Total Assets</p>
              <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-slate-50">{inr(balanceSheet.total_assets)}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-800">
              <p className="text-sm text-slate-500 dark:text-slate-400">Total Liabilities</p>
              <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-slate-50">{inr(balanceSheet.total_liabilities)}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-800">
              <p className="text-sm text-slate-500 dark:text-slate-400">Total Equity</p>
              <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-slate-50">{inr(balanceSheet.total_equity)}</p>
            </div>
          </div>
          <div>
            <h2 className="mb-2 text-lg font-semibold text-slate-800 dark:text-slate-200">Assets</h2>
            <Table
              columns={['Code', 'Account', 'Amount']}
              rows={balanceSheet.asset_lines.map((l) => [l.account_code, l.account_name, inr(l.amount)])}
              emptyText="No asset lines."
            />
          </div>
          <div>
            <h2 className="mb-2 text-lg font-semibold text-slate-800 dark:text-slate-200">Liabilities</h2>
            <Table
              columns={['Code', 'Account', 'Amount']}
              rows={balanceSheet.liability_lines.map((l) => [l.account_code, l.account_name, inr(l.amount)])}
              emptyText="No liability lines."
            />
          </div>
          <div>
            <h2 className="mb-2 text-lg font-semibold text-slate-800 dark:text-slate-200">
              Equity <span className="font-normal text-slate-400">(incl. retained earnings {inr(balanceSheet.retained_earnings)})</span>
            </h2>
            <Table
              columns={['Code', 'Account', 'Amount']}
              rows={balanceSheet.equity_lines.map((l) => [l.account_code, l.account_name, inr(l.amount)])}
              emptyText="No equity lines."
            />
          </div>
        </div>
      )}
    </div>
  )
}

function Table({ columns, rows, emptyText }: { columns: string[]; rows: string[][]; emptyText: string }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-800">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
          <tr>
            {columns.map((c) => (
              <th key={c} className="px-4 py-3">{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-slate-100 last:border-0 dark:border-slate-700">
              {row.map((cell, j) => (
                <td key={j} className={`px-4 py-3 ${j === 0 ? 'font-medium text-slate-900 dark:text-slate-100' : 'text-slate-600 dark:text-slate-300'}`}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="px-4 py-6 text-center text-slate-400">{emptyText}</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
