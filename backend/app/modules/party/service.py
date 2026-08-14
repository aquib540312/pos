import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.exceptions import CreditLimitExceededError, NotFoundError
from app.models.party import Customer, Supplier, SupplierPayment
from app.modules.accounting.service import AccountingService
from app.modules.party.repository import CustomerRepository, SupplierPaymentRepository, SupplierRepository


class PartyService:
    def __init__(self, db: Session):
        self.db = db
        self.customers = CustomerRepository(db)
        self.suppliers = SupplierRepository(db)
        self.supplier_payments = SupplierPaymentRepository(db)
        self.accounting = AccountingService(db)

    def create_customer(self, organization_id: uuid.UUID, **fields) -> Customer:
        return self.customers.add(Customer(organization_id=organization_id, **fields))

    def create_supplier(self, organization_id: uuid.UUID, **fields) -> Supplier:
        return self.suppliers.add(Supplier(organization_id=organization_id, **fields))

    def get_customer_or_404(self, customer_id: uuid.UUID) -> Customer:
        customer = self.customers.get(customer_id)
        if customer is None:
            raise NotFoundError(f"Customer {customer_id} not found")
        return customer

    def get_supplier_or_404(self, supplier_id: uuid.UUID) -> Supplier:
        supplier = self.suppliers.get(supplier_id)
        if supplier is None:
            raise NotFoundError(f"Supplier {supplier_id} not found")
        return supplier

    def _apply_nullable_fields(self, obj, fields: dict, nullable_cols: tuple[str, ...]) -> None:
        for key in nullable_cols:
            if fields.get(key) is not None:
                setattr(obj, key, fields[key])
            elif fields.get(f"remove_{key}"):
                setattr(obj, key, None)

    def update_customer(self, organization_id: uuid.UUID, customer_id: uuid.UUID, fields: dict) -> Customer:
        customer = self.get_customer_or_404(customer_id)
        if customer.organization_id != organization_id:
            raise NotFoundError(f"Customer {customer_id} not found")
        if fields.get("name") is not None:
            customer.name = fields["name"]
        if fields.get("is_active") is not None:
            customer.is_active = fields["is_active"]
        if fields.get("is_credit_customer") is not None:
            customer.is_credit_customer = fields["is_credit_customer"]
        if fields.get("credit_limit") is not None:
            customer.credit_limit = fields["credit_limit"]
        self._apply_nullable_fields(
            customer, fields, ("phone", "email", "gstin", "state_code", "address")
        )
        self.db.flush()
        return customer

    def update_supplier(self, organization_id: uuid.UUID, supplier_id: uuid.UUID, fields: dict) -> Supplier:
        supplier = self.get_supplier_or_404(supplier_id)
        if supplier.organization_id != organization_id:
            raise NotFoundError(f"Supplier {supplier_id} not found")
        if fields.get("name") is not None:
            supplier.name = fields["name"]
        if fields.get("is_active") is not None:
            supplier.is_active = fields["is_active"]
        self._apply_nullable_fields(
            supplier, fields, ("phone", "email", "gstin", "state_code", "address")
        )
        self.db.flush()
        return supplier

    def record_credit_payment(self, customer: Customer, amount: float) -> None:
        customer.credit_balance = max(0.0, float(customer.credit_balance) - amount)
        self.db.flush()

    def assert_credit_available(self, customer: Customer, additional_amount: float) -> None:
        """Enforced at invoice-post time for credit sales. Walk-in
        (non-credit) customers are never subject to a limit -- they pay in
        full at checkout by definition."""
        if not customer.is_credit_customer:
            return
        projected = float(customer.credit_balance) + additional_amount
        if projected > float(customer.credit_limit):
            raise CreditLimitExceededError(
                f"Credit limit exceeded for {customer.name}: "
                f"balance {customer.credit_balance} + {additional_amount} > limit {customer.credit_limit}"
            )

    def record_credit_sale(self, customer: Customer, amount: float) -> None:
        customer.credit_balance = float(customer.credit_balance) + amount
        self.db.flush()

    def collect_credit(
        self, organization_id: uuid.UUID, customer_id: uuid.UUID, amount: float, method: str, reference: str | None
    ) -> tuple[Customer, float]:
        """Collection of a cash/card/UPI amount against an outstanding
        customer credit balance (reduces Accounts Receivable). The Payment
        table is invoice-scoped (invoice_id is NOT NULL), so a collection is
        recorded directly against the customer's credit_balance only -- a
        full standalone-payment/ledger integration is a Phase-2 accounting
        refinement (see ROADMAP.md). Returns the customer and the amount
        actually applied (capped at the outstanding balance)."""
        customer = self.get_customer_or_404(customer_id)
        if customer.organization_id != organization_id:
            raise NotFoundError(f"Customer {customer_id} not found")
        if amount <= 0:
            raise CreditLimitExceededError("Collection amount must be positive")
        available = float(customer.credit_balance)
        applied = min(amount, available)
        if applied <= 0:
            raise NotFoundError(f"Customer '{customer.name}' has no outstanding credit to collect")
        self.record_credit_payment(customer, applied)
        self.db.flush()
        return customer, applied

    def pay_supplier(
        self, organization_id: uuid.UUID, supplier_id: uuid.UUID, amount: float,
        method: str, reference: str | None, note: str | None,
    ) -> tuple[Supplier, SupplierPayment, float]:
        """A cash/bank/card/UPI payment settling part or all of a supplier's
        payable balance. Debits Accounts Payable, credits cash/bank in the
        ledger, and reduces the supplier's payable_balance by the applied
        amount (capped at the outstanding balance)."""
        supplier = self.get_supplier_or_404(supplier_id)
        if supplier.organization_id != organization_id:
            raise NotFoundError(f"Supplier {supplier_id} not found")
        if amount <= 0:
            raise CreditLimitExceededError("Payment amount must be positive")
        applied = min(amount, float(supplier.payable_balance))
        if applied <= 0:
            raise NotFoundError(f"Supplier '{supplier.name}' has no outstanding payable to settle")
        payment = SupplierPayment(
            organization_id=organization_id,
            supplier_id=supplier.id,
            amount=applied,
            method=method,
            reference=reference,
            paid_at=datetime.utcnow(),
            note=note,
        )
        self.supplier_payments.add(payment)
        supplier.payable_balance = max(0.0, float(supplier.payable_balance) - applied)
        self.accounting.post_supplier_payment(
            organization_id, supplier.id, payment.id, payment.paid_at.date(),
            applied, method, f"Payment to {supplier.name}{(' (' + reference + ')') if reference else ''}",
        )
        self.db.flush()
        return supplier, payment, applied
