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
  items: SaleInvoiceItem[]
  payments: PaymentResponse[]
}
