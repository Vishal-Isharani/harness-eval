import pytest

from shop import Cart, ShopError, UnknownProduct


def test_remove_across_lines_and_unknown():
    cart = Cart()
    cart.add("A", 100, 1)
    cart.add("A", 100, 2)
    cart.remove("A", 2)
    assert cart.subtotal_cents() == 100
    with pytest.raises(UnknownProduct):
        cart.remove("Z")


def test_too_many_is_atomic():
    cart = Cart()
    cart.add("A", 100, 1)
    with pytest.raises(ShopError):
        cart.remove("A", 3)
    assert cart.subtotal_cents() == 100
