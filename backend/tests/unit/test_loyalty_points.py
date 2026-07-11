from app.modules.loyalty.service import LoyaltyService


def test_points_earned_is_one_percent_of_taxable_amount():
    service = LoyaltyService(db=None)
    assert service.points_earned_for_amount(1000) == 10.0
    assert service.points_earned_for_amount(0) == 0.0
    assert service.points_earned_for_amount(99) == 0.99
