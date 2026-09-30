import pytest

from shop import Cart, ShopError


def test_add_and_subtotal():
    cart = Cart()
    cart.add("A", 1000, 2)
    cart.add("B", 250)
    assert cart.subtotal_cents() == 2250


def test_rejects_non_positive_quantity():
    with pytest.raises(ShopError):
        Cart().add("A", 100, 0)


def test_tax_simple():
    cart = Cart()
    cart.add("A", 1000)
    assert cart.tax_cents() == 210
    assert cart.total_cents() == 1210
