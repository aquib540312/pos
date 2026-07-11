import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import CreditLimitExceededError, NotFoundError
from app.models.party import Customer, Supplier
from app.modules.party.repository import CustomerRepository, SupplierRepository


class PartyService:
    def __init__(self, db: Session):
        self.db = db
        self.customers = CustomerRepository(db)
        self.suppliers = SupplierRepository(db)

    def create_customer(self, organization_id: uuid.UUID, **fields) -> Customer:
        return self.customers.add(Customer(organization_id=organization_id, **fields))

    def create_supplier(self, organization_id: uuid.UUID, **fields) -> Supplier:
        return self.suppliers.add(Supplier(organization_id=organization_id, **fields))

    def get_customer_or_404(self, customer_id: uuid.UUID) -> Customer:
        customer = self.customers.get(customer_id)
        if customer is None:
            raise NotFoundError(f"Customer {customer_id} not found")
        return customer

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

    def record_credit_payment(self, customer: Customer, amount: float) -> None:
        customer.credit_balance = max(0.0, float(customer.credit_balance) - amount)
        self.db.flush()
