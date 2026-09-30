import pytest

from shop import Cart, InvalidDiscountCode


def test_save10_and_tax_on_discounted_subtotal():
    cart = Cart()
    cart.add("A", 1000)
    cart.apply_discount("save10")
    assert cart.discount_cents() == 100
    assert cart.total_cents() == 1089


def test_flat_is_capped_and_unknown_raises():
    cart = Cart()
    cart.add("A", 300)
    cart.apply_discount("FLAT500")
    assert cart.total_cents() == 0
    with pytest.raises(InvalidDiscountCode):
        cart.apply_discount("NOPE")
