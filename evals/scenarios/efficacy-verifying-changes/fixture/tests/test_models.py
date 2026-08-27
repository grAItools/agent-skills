from inventory.models import Cart, apply_discount


def test_cart_total():
    cart = Cart([
        {"unit_cents": 1250, "qty": 2},
        {"unit_cents": 500, "qty": 1},
    ])
    assert cart.total_cents() == 3000


def test_apply_discount_ten_percent():
    assert apply_discount(1000, 10) == 900


def test_apply_discount_fifty_percent():
    assert apply_discount(999, 50) == 500


def test_zero_discount_is_identity():
    assert apply_discount(1234, 0) == 1234
