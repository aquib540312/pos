export interface Product {
  id: string
  sku: string
  barcode: string | null
  name: string
  mrp: number
  sale_price: number
  purchase_price: number
  tax_rate_percent: number | null
  tracks_batches: boolean
  tracks_serials: boolean
  tracks_expiry: boolean
  is_active: boolean
}

export interface BulkImportRowResult {
  row: number
  sku: string | null
  status: 'created' | 'updated' | 'error'
  error: string | null
}

export interface BulkImportResponse {
  total: number
  created: number
  updated: number
  failed: number
  rows: BulkImportRowResult[]
}

export interface Customer {
  id: string
  name: string
  phone: string | null
  email: string | null
  gstin: string | null
  state_code: string | null
  is_credit_customer: boolean
  credit_limit: number
  credit_balance: number
  loyalty_points_balance: number
}

export interface Supplier {
  id: string
  name: string
  phone: string | null
  email: string | null
  gstin: string | null
  state_code: string | null
  payable_balance: number
}

export interface PurchaseOrderItem {
  id: string
  product_id: string
  quantity_ordered: number
  quantity_received: number
  unit_cost: number
}

export interface PurchaseOrder {
  id: string
  po_number: string
  supplier_id: string
  order_date: string
  status: string
  items: PurchaseOrderItem[]
}

export interface GoodsReceiptItem {
  id: string
  product_id: string
  batch_id: string | null
  quantity: number
  free_quantity: number
  unit_cost: number
}

export interface GoodsReceipt {
  id: string
  grn_number: string
  supplier_id: string
  received_at: string
  items: GoodsReceiptItem[]
}

export interface UOM {
  id: string
  code: string
  name: string
}

export interface HSN {
  id: string
  code: string
  description: string | null
  is_service: boolean
  current_rate_percent: number | null
}

export interface CartLine {
  product: Product
  quantity: number
  discountAmount: number
}

export interface PaymentLine {
  method: 'cash' | 'card' | 'upi' | 'wallet' | 'credit'
  amount: number
  reference?: string
}

export interface SaleInvoiceItem {
  id: string
  product_id: string
  quantity: number
  unit_price: number
  discount_amount: number
  taxable_value: number
  tax_rate_percent: number
  cgst_amount: number
  sgst_amount: number
  igst_amount: number
  cess_amount: number
  line_total: number
}

export interface PaymentResponse {
  id: string
  method: string
  amount: number
  reference: string | null
}

export interface PaymentGatewayTransaction {
  id: string
  provider: string
  gateway_reference: string
  amount: number
  status: 'created' | 'paid' | 'closed' | 'expired'
  receipt_reference: string | null
  qr_image_url: string | null
  close_by: string | null
  paid_at: string | null
  invoice_id: string | null
}

export interface FeatureFlags {
  razorpay_upi_enabled: boolean
  printer_enabled: boolean
}

export interface SyncTerminalStatus {
  id: string
  name: string
  branch_id: string
  is_active: boolean
  last_seen_at: string | null
}

export interface SyncStatus {
  terminals: SyncTerminalStatus[]
  open_conflicts: number
  latest_change_log_id: number
}

export interface SyncConflict {
  id: string
  terminal_id: string
  offline_sale_id: string | null
  conflict_type: string
  details: Record<string, unknown>
  status: string
  resolution: string | null
  resolution_notes: string | null
  created_at: string
  resolved_at: string | null
}

export interface SalesSummaryReport {
  period_start: string
  period_end: string
  invoice_count: number
  total_taxable_value: number
  total_cgst: number
  total_sgst: number
  total_igst: number
  total_cess: number
  total_grand_total: number
}

export interface StockSummaryReportRow {
  product_id: string
  product_name: string
  sku: string
  quantity_on_hand: number
  reorder_level: number
  below_reorder: boolean
}

export interface GSTR1ReportRow {
  hsn_code: string
  tax_rate_percent: number
  taxable_value: number
  cgst: number
  sgst: number
  igst: number
  cess: number
  invoice_count: number
}

export interface LedgerAccountLine {
  account_code: string
  account_name: string
  amount: number
}

export interface ProfitAndLossReport {
  period_start: string
  period_end: string
  income_lines: LedgerAccountLine[]
  expense_lines: LedgerAccountLine[]
  total_income: number
  total_expense: number
  net_profit: number
}

export interface BalanceSheetReport {
  as_of: string
  asset_lines: LedgerAccountLine[]
  liability_lines: LedgerAccountLine[]
  equity_lines: LedgerAccountLine[]
  total_assets: number
  total_liabilities: number
  total_equity: number
  retained_earnings: number
}

export interface TopProductReportRow {
  product_id: string
  product_name: string
  sku: string
  quantity_sold: number
  revenue: number
}

export interface PaymentBreakdownReportRow {
  method: string
  payment_count: number
  total_amount: number
}

export interface CashierSalesReportRow {
  user_id: string
  user_name: string
  invoice_count: number
  total_grand_total: number
}

export interface SaleInvoice {
  id: string
  invoice_number: string
  invoice_date: string
  branch_id: string
  customer_id: string | null
  is_inter_state: boolean
  subtotal: number
  discount_total: number
  taxable_total: number
  cgst_total: number
  sgst_total: number
  igst_total: number
  cess_total: number
  round_off: number
  grand_total: number
  is_credit_sale: boolean
  status: string
  loyalty_points_earned: number
  loyalty_points_redeemed: number
  coupon_code: string | null
  coupon_discount_amount: number
  items: SaleInvoiceItem[]
  payments: PaymentResponse[]
}
