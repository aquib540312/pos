import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.core.numbering import next_document_number
from app.models.billing import Payment
from app.models.organization import Branch
from app.models.sales import SalesInvoice, SalesInvoiceItem, SalesReturn, SalesReturnItem
from app.modules.accounting.service import AccountingService
from app.modules.catalog.repository import HSNRepository, ProductRepository
from app.modules.gst.service import compute_line_tax, is_inter_state_supply, round_invoice_total
from app.modules.inventory.service import InventoryService
from app.modules.loyalty.service import LoyaltyService
from app.modules.party.repository import CustomerRepository
from app.modules.party.service import PartyService
from app.modules.sales.repository import SalesInvoiceRepository, SalesReturnRepository


class SalesService:
    """Owns the checkout transaction: pricing, GST, stock issuance, payment
    reconciliation, credit-limit enforcement, and loyalty accrual all
    happen inside `create_sale` as one DB transaction (the caller commits
    once at the end) -- a half-posted sale (stock deducted but no invoice
    row, or vice versa) must never be observable."""

    def __init__(self, db: Session):
        self.db = db
        self.invoices = SalesInvoiceRepository(db)
        self.returns = SalesReturnRepository(db)
        self.products = ProductRepository(db)
        self.hsn = HSNRepository(db)
        self.customers = CustomerRepository(db)
        self.inventory = InventoryService(db)
        self.loyalty = LoyaltyService(db)
        self.party = PartyService(db)
        self.accounting = AccountingService(db)

    def create_sale(
        self,
        organization_id: uuid.UUID,
        branch_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        customer_id: uuid.UUID | None,
        shift_id: uuid.UUID | None,
        items: list[dict],
        payments: list[dict],
        redeem_loyalty_points: float,
        is_credit_sale: bool,
    ) -> SalesInvoice:
        branch = self.db.get(Branch, branch_id)
        if branch is None:
            raise NotFoundError(f"Branch {branch_id} not found")

        customer = self.customers.get(customer_id) if customer_id else None
        if is_credit_sale and (customer is None or not customer.is_credit_customer):
            raise ValidationError("A credit sale requires a customer flagged as a credit customer")

        buyer_state_code = customer.state_code if customer else None
        inter_state = is_inter_state_supply(branch.state_code, buyer_state_code)

        invoice = SalesInvoice(
            organization_id=organization_id,
            branch_id=branch_id,
            customer_id=customer_id,
            shift_id=shift_id,
            invoice_number=next_document_number(self.db, SalesInvoice, "INV"),
            invoice_date=datetime.now(timezone.utc),
            place_of_supply_state_code=buyer_state_code or branch.state_code,
            is_inter_state=inter_state,
            is_credit_sale=is_credit_sale,
            status="posted",
        )
        self.invoices.add(invoice)

        subtotal = discount_total = taxable_total = 0.0
        cgst_total = sgst_total = igst_total = cess_total = 0.0

        for line in items:
            product = self.products.get(line["product_id"])
            if product is None:
                raise NotFoundError(f"Product {line['product_id']} not found")
            if product.hsn_code_id is None:
                raise ValidationError(f"Product '{product.name}' has no HSN/SAC code configured for GST")

            tax_rate = self.hsn.get_effective_tax_rate(product.hsn_code_id, invoice.invoice_date.date())
            if tax_rate is None:
                raise ValidationError(f"No effective GST rate configured for product '{product.name}'")

            unit_price = line.get("unit_price") if line.get("unit_price") is not None else float(product.sale_price)
            try:
                breakdown = compute_line_tax(
                    quantity=line["quantity"],
                    unit_price=unit_price,
                    discount_amount=line.get("discount_amount", 0),
                    tax_rate_percent=float(tax_rate.rate_percent),
                    is_inter_state=inter_state,
                    cess_percent=float(tax_rate.cess_percent),
                )
            except ValueError as exc:
                raise ValidationError(f"Invalid line for product '{product.name}': {exc}") from exc

            allocations = self.inventory.issue_fefo(
                organization_id, warehouse_id, product.id, line["quantity"], "sale", "sales_invoice", invoice.id
            )
            primary_batch_id = allocations[0][0] if allocations else None

            self.invoices.add_item(
                SalesInvoiceItem(
                    invoice_id=invoice.id,
                    product_id=product.id,
                    batch_id=primary_batch_id,
                    hsn_code_id=product.hsn_code_id,
                    quantity=line["quantity"],
                    unit_price=unit_price,
                    discount_amount=line.get("discount_amount", 0),
                    taxable_value=breakdown.taxable_value,
                    tax_rate_percent=breakdown.tax_rate_percent,
                    cgst_amount=breakdown.cgst_amount,
                    sgst_amount=breakdown.sgst_amount,
                    igst_amount=breakdown.igst_amount,
                    cess_amount=breakdown.cess_amount,
                    line_total=breakdown.line_total,
                )
            )

            subtotal += line["quantity"] * unit_price
            discount_total += line.get("discount_amount", 0)
            taxable_total += breakdown.taxable_value
            cgst_total += breakdown.cgst_amount
            sgst_total += breakdown.sgst_amount
            igst_total += breakdown.igst_amount
            cess_total += breakdown.cess_amount

        loyalty_discount = 0.0
        if redeem_loyalty_points > 0:
            if customer is None:
                raise ValidationError("Loyalty point redemption requires a customer")
            loyalty_discount = self.loyalty.redeem(customer, invoice.id, redeem_loyalty_points)

        pre_round_total = taxable_total + cgst_total + sgst_total + igst_total + cess_total - loyalty_discount
        grand_total, round_off = round_invoice_total(pre_round_total)

        invoice.subtotal = subtotal
        invoice.discount_total = discount_total
        invoice.taxable_total = taxable_total
        invoice.cgst_total = cgst_total
        invoice.sgst_total = sgst_total
        invoice.igst_total = igst_total
        invoice.cess_total = cess_total
        invoice.round_off = round_off
        invoice.grand_total = grand_total
        invoice.loyalty_points_redeemed = redeem_loyalty_points

        payment_total = sum(p["amount"] for p in payments)
        shortfall = round(grand_total - payment_total, 2)
        if shortfall < -0.01:
            raise ValidationError(
                f"Payments ({payment_total}) exceed grand total ({grand_total}) -- "
                "tender only the amount actually retained; hand back change separately"
            )
        if shortfall > 0.01 and not is_credit_sale:
            raise ValidationError(f"Payments ({payment_total}) do not cover grand total ({grand_total})")
        if shortfall > 0.01 and is_credit_sale:
            self.party.assert_credit_available(customer, shortfall)
            self.party.record_credit_sale(customer, shortfall)

        payment_rows: list[Payment] = []
        for payment in payments:
            row = Payment(
                organization_id=organization_id,
                invoice_id=invoice.id,
                shift_id=shift_id,
                method=payment["method"],
                amount=payment["amount"],
                reference=payment.get("reference"),
            )
            self.db.add(row)
            payment_rows.append(row)

        if customer is not None:
            self.loyalty.earn(customer, invoice.id, taxable_total)

        self.db.flush()
        credit_shortfall = shortfall if (is_credit_sale and shortfall > 0.01) else 0.0
        self.accounting.post_sale_invoice(invoice, payment_rows, credit_shortfall)

        self.db.flush()
        return self.invoices.get(invoice.id)

    def create_return(
        self,
        organization_id: uuid.UUID,
        branch_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        original_invoice_id: uuid.UUID,
        reason: str | None,
        refund_mode: str,
        items: list[dict],
    ) -> SalesReturn:
        """Reverses stock (back into the batch it was issued from) and
        GST proportionally to the fraction of the original line quantity
        being returned. Loyalty points earned on the returned portion are
        intentionally not clawed back in Phase 1 (see ROADMAP.md) -- flag
        for follow-up if that matters for your loyalty program design."""
        original_invoice = self.invoices.get(original_invoice_id)
        if original_invoice is None:
            raise NotFoundError(f"Invoice {original_invoice_id} not found")

        sales_return = SalesReturn(
            organization_id=organization_id,
            branch_id=branch_id,
            original_invoice_id=original_invoice_id,
            return_number=next_document_number(self.db, SalesReturn, "RET"),
            return_date=datetime.now(timezone.utc),
            reason=reason,
            refund_mode=refund_mode,
        )
        self.returns.add(sales_return)

        refund_total = 0.0
        for line in items:
            original_item = self.invoices.get_item(line["original_invoice_item_id"])
            if original_item is None or original_item.invoice_id != original_invoice_id:
                raise NotFoundError(f"Invoice line {line['original_invoice_item_id']} not found on this invoice")
            if line["quantity"] > float(original_item.quantity):
                raise ValidationError("Cannot return more than the originally sold quantity")

            fraction = line["quantity"] / float(original_item.quantity)
            taxable_value = round(float(original_item.taxable_value) * fraction, 2)
            cgst = round(float(original_item.cgst_amount) * fraction, 2)
            sgst = round(float(original_item.sgst_amount) * fraction, 2)
            igst = round(float(original_item.igst_amount) * fraction, 2)
            line_total = round(taxable_value + cgst + sgst + igst, 2)

            self.inventory.receive(
                organization_id, warehouse_id, original_item.product_id, original_item.batch_id, line["quantity"],
                "sale_return", "sales_return", sales_return.id,
            )

            self.db.add(
                SalesReturnItem(
                    sales_return_id=sales_return.id,
                    original_invoice_item_id=original_item.id,
                    quantity=line["quantity"],
                    taxable_value=taxable_value,
                    cgst_amount=cgst,
                    sgst_amount=sgst,
                    igst_amount=igst,
                    line_total=line_total,
                )
            )
            refund_total += line_total

        sales_return.refund_total = round(refund_total, 2)

        if refund_mode == "credit_note" and original_invoice.customer_id:
            customer = self.customers.get(original_invoice.customer_id)
            if customer is not None:
                self.party.record_credit_payment(customer, refund_total)

        self.db.flush()
        return self.returns.get(sales_return.id)
