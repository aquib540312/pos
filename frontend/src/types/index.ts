export interface Product {
  id: string
  sku: string
  barcode: string | null
  name: string
  name_arabic: string | null
  brand: string | null
  category_id: string | null
  category_name: string | null
  uom_id: string
  hsn_code_id: string | null
  supplier_id: string | null
  mrp: number
  sale_price: number
  wholesale_price: number
  restaurant_price: number
  vip_price: number
  purchase_price: number
  cost_per_kg: number
  selling_price_per_kg: number
  minimum_selling_quantity: number
  tax_rate_percent: number | null
  tracks_batches: boolean
  tracks_serials: boolean
  tracks_expiry: boolean
  is_weighted: boolean
  low_stock_notify: boolean
  reorder_level: number
  is_active: boolean
  is_combo: boolean
  combo_components: { component_product_id: string; component_product_name: string; quantity: number }[]
  prices_gst_inclusive: boolean
  loyalty_exempt: boolean
  parent_product_id: string | null
  variant_label: string | null
  image_path: string | null
  aliases: string[]
  beef_cut: string | null
  fresh_frozen: string | null
  local_imported: string | null
  country_of_origin: string | null
  storage_location: string | null
}

export interface Category {
  id: string
  name: string
  parent_id: string | null
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
  name_arabic: string | null
  phone: string | null
  email: string | null
  vat_number: string | null
  cr_number: string | null
  state_code: string | null
  address: string | null
  customer_type: string
  price_level: string
  is_credit_customer: boolean
  credit_limit: number
  credit_balance: number
  payment_terms_days: number
  outstanding_balance: number
  total_purchases: number
  last_purchase_date: string | null
  loyalty_points_balance: number
  is_active: boolean
}

export interface CustomerPayment {
  id: string
  customer_id: string
  amount: number
  method: string
  reference: string | null
  paid_at: string
  note: string | null
}

export interface Supplier {
  id: string
  name: string
  name_arabic: string | null
  phone: string | null
  email: string | null
  vat_number: string | null
  cr_number: string | null
  state_code: string | null
  address: string | null
  payable_balance: number
  is_active: boolean
}

export interface SupplierPurchaseReturnRow {
  supplier_id: string
  supplier_name: string
  purchase_count: number
  purchase_value: number
  return_count: number
  return_value: number
  net_value: number
}

export interface SupplierPurchaseReturnLedgerRow {
  date: string
  purchase_value: number
  return_value: number
  net_value: number
}

export interface PurchaseOrderItem {
  id: string
  product_id: string
  quantity_ordered: number
  quantity_received: number
  unit_cost: number
  discount_amount: number
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
  discount_amount: number
  hsn_code_id?: string | null
  tax_rate_percent?: number
  vat_amount?: number
}

export interface GoodsReceipt {
  id: string
  grn_number: string
  supplier_id: string
  warehouse_id?: string
  purchase_order_id?: string | null
  received_at: string
  supplier_invoice_number?: string | null
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
  unitPrice: number
}

export interface PaymentLine {
  method: 'cash' | 'card' | 'bank_transfer' | 'credit' | 'split'
  amount: number
  reference?: string
}

export interface SaleInvoiceItem {
  id: string
  product_id: string
  product_name?: string
  quantity: number
  unit_price: number
  discount_amount: number
  taxable_value: number
  tax_rate_percent: number
  vat_amount: number
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
  total_vat: number
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
  vat: number
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
  subtotal: number
  discount_total: number
  taxable_total: number
  vat_total: number
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
  vat_amount: number
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
  today_vat_total: number
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
  vat_amount: number
  line_total: number
}

export interface PurchaseReturn {
  id: string
  return_number: string
  supplier_id: string
  goods_receipt_id?: string | null
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

export interface OrgProfile {
  id: string
  legal_name: string
  trade_name: string
  gstin: string | null
  pan: string | null
  default_state_code: string
  vat_number: string | null
  phone: string | null
  address: string | null
  footer_note: string | null
  tax_mode: string
  has_logo: boolean
}

export interface DiningTable {
  id: string
  table_number: string
  name: string | null
  capacity: number
  status: 'available' | 'occupied' | 'reserved' | 'cleaning'
  is_active: boolean
  active_order_id: string | null
}

export interface DiningOrderItem {
  id: string
  product_id: string
  product_name: string
  quantity: number
  unit_price: number
  discount_amount: number
  line_total: number
  status: 'pending' | 'preparing' | 'ready' | 'served' | 'cancelled'
  kot_number: string | null
  note: string | null
}

export interface DiningOrder {
  id: string
  table_id: string | null
  table_number: string
  table_name: string | null
  customer_id: string | null
  customer_name: string | null
  status: 'open' | 'paid' | 'cancelled'
  order_type: 'dine_in' | 'parcel'
  opened_at: string
  closed_at: string | null
  kot_counter: number
  sales_invoice_id: string | null
  note: string | null
  subtotal: number
  discount_total: number
  items: DiningOrderItem[]
}

export interface DiningOrderEstimate {
  order_id: string
  subtotal: number
  taxable_total: number
  discount_total: number
  vat_total: number
  round_off: number
  grand_total: number
  items: DiningOrderItem[]
}

export interface WasteEntry {
  id: string
  product_id: string
  product_name: string
  quantity: number
  unit_cost: number
  total_cost: number
  reason: string
  notes: string | null
  recorded_by: string | null
  created_at: string
}

export interface CuttingOrderItem {
  id: string
  product_id: string
  product_name: string
  output_weight: number
  waste_weight: number
}

export interface CuttingOrder {
  id: string
  source_product_id: string
  source_product_name: string
  input_weight: number
  butcher_name: string | null
  cutting_date: string | null
  status: string
  notes: string | null
  items: CuttingOrderItem[]
  created_at: string
}

export interface SalesByBeefCutRow {
  beef_cut: string
  product_count: number
  quantity_sold: number
  revenue: number
}

export interface SalesByCustomerTypeRow {
  customer_type: string
  invoice_count: number
  total_revenue: number
  total_vat: number
}

export interface WasteReportRow {
  product_id: string
  product_name: string
  reason: string
  total_quantity: number
  total_cost: number
  entry_count: number
}

export interface CustomerStatementRow {
  invoice_id: string
  invoice_number: string
  invoice_date: string
  grand_total: number
  paid_amount: number
  outstanding: number
  payment_method: string
}
