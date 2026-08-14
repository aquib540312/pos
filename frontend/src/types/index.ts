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

export interface QuotationItem {
  id: string
  product_id: string
  quantity: number
  unit_price: number
  discount_amount: number
  line_total: number
}

export interface Quotation {
  id: string
  quotation_number: string
  branch_id: string
  customer_id: string | null
  quotation_date: string
  valid_until: string | null
  status: 'draft' | 'sent' | 'converted' | 'expired'
  grand_total: number
  converted_invoice_id: string | null
  items: QuotationItem[]
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

export interface Plan {
  id: string
  code: string
  name: string
  price_monthly: number
  max_branches: number | null
  max_users: number | null
}

export interface Subscription {
  id: string
  plan: Plan
  status: 'trialing' | 'active' | 'past_due' | 'canceled'
  trial_ends_at: string | null
  current_period_end: string | null
  cancel_at_period_end: boolean
  branches_used: number
  users_used: number
}

export interface SalesReturnItem {
  id: string
  original_invoice_item_id: string
  quantity: number
  taxable_value: number
  cgst_amount: number
  sgst_amount: number
  igst_amount: number
  line_total: number
}

export interface SalesReturn {
  id: string
  return_number: string
  original_invoice_id: string
  refund_total: number
  refund_mode: string
  reason: string | null
  return_date: string
  items: SalesReturnItem[]
}

export interface StockItem {
  warehouse_id: string
  product_id: string
  batch_id: string | null
  quantity_on_hand: number
}

export interface StockLedgerRow {
  id: string
  created_at: string
  warehouse_id: string
  product_id: string
  batch_id: string | null
  movement_type: string
  quantity_delta: number
  reference_type: string
  reference_id: string
  notes: string | null
}

export interface Coupon {
  id: string
  code: string
  discount_type: 'percent' | 'flat'
  discount_value: number
  min_order_value: number
  times_redeemed: number
  max_redemptions: number | null
  is_active: boolean
}

export interface GiftCard {
  id: string
  card_number: string
  initial_value: number
  balance: number
  is_active: boolean
}

export interface DashboardStats {
  today_invoice_count: number
  today_taxable_value: number
  today_gst_total: number
  today_grand_total: number
  today_cash_sales: number
  low_stock_count: number
  expiring_soon_count: number
  open_shifts: number
  open_credit_outstanding: number
  open_conflicts: number
}

export interface LowStockRow {
  product_id: string
  product_name: string
  sku: string
  barcode: string | null
  uom_code: string | null
  quantity_on_hand: number
  reorder_level: number
  below_reorder: boolean
}

export interface ExpiringStockRow {
  product_id: string
  product_name: string
  sku: string
  warehouse_id: string
  warehouse_name: string | null
  batch_id: string
  batch_number: string
  quantity_on_hand: number
  expiry_date: string
  days_to_expiry: number | null
}

export interface StockValuationRow {
  product_id: string
  product_name: string
  sku: string
  quantity_on_hand: number
  average_cost: number
  valuation: number
}

export interface AppNotification {
  id: string
  category: string
  title: string
  body: string | null
  reference_type: string | null
  reference_id: string | null
  is_read: boolean
  created_at: string
}

export interface PendingGRNItem {
  po_id: string
  po_number: string
  supplier_id: string
  order_date: string
  status: string
  product_id: string
  product_name: string
  sku: string
  quantity_ordered: number
  quantity_received: number
  outstanding_quantity: number
}

export interface PurchaseReturnItem {
  id: string
  product_id: string
  batch_id: string | null
  quantity: number
  unit_cost: number
  taxable_value: number
  cgst_amount: number
  sgst_amount: number
  igst_amount: number
  line_total: number
}

export interface PurchaseReturn {
  id: string
  return_number: string
  supplier_id: string
  return_date: string
  reason: string | null
  return_total: number
  is_debit_note: boolean
  items: PurchaseReturnItem[]
}

export interface SupplierPayment {
  id: string
  supplier_id: string
  amount: number
  method: string
  reference: string | null
  paid_at: string
  note: string | null
  outstanding_payable: number
}
