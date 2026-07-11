from types import SimpleNamespace

import pytest

from app.core.exceptions import CreditLimitExceededError
from app.modules.party.service import PartyService


def _customer(is_credit_customer=True, credit_limit=1000, credit_balance=0):
    return SimpleNamespace(
        name="Test Customer", is_credit_customer=is_credit_customer, credit_limit=credit_limit,
        credit_balance=credit_balance,
    )


def test_walk_in_customer_has_no_limit():
    service = PartyService(db=None)
    # non-credit customers are never limit-checked, regardless of amount
    service.assert_credit_available(_customer(is_credit_customer=False, credit_limit=0), 1_000_000)


def test_sale_within_limit_is_allowed():
    service = PartyService(db=None)
    service.assert_credit_available(_customer(credit_limit=1000, credit_balance=400), 500)


def test_sale_exceeding_limit_is_rejected():
    service = PartyService(db=None)
    with pytest.raises(CreditLimitExceededError):
        service.assert_credit_available(_customer(credit_limit=1000, credit_balance=800), 300)


def test_sale_exactly_at_limit_is_allowed():
    service = PartyService(db=None)
    service.assert_credit_available(_customer(credit_limit=1000, credit_balance=700), 300)
