import pytest

from shop import Cart, ShopError, UnknownProduct


def test_remove_some_units():
    cart = Cart()
    cart.add("A", 1000, 3)
    cart.remove("A", 1)
    assert cart.subtotal_cents() == 2000


def test_remove_all_when_quantity_omitted():
    cart = Cart()
    cart.add("A", 1000, 3)
    cart.add("B", 100)
    cart.remove("A")
    assert cart.subtotal_cents() == 100
    assert [i.sku for i in cart.items] == ["B"]


def test_unknown_sku():
    with pytest.raises(UnknownProduct):
        Cart().remove("NOPE")


def test_too_many_leaves_cart_unchanged():
    cart = Cart()
    cart.add("A", 1000, 2)
    with pytest.raises(ShopError):
        cart.remove("A", 5)
    assert cart.subtotal_cents() == 2000


def test_zero_quantity_lines_disappear():
    cart = Cart()
    cart.add("A", 1000, 2)
    cart.remove("A", 2)
    assert cart.items == []


def test_units_across_lines():
    cart = Cart()
    cart.add("A", 100, 1)
    cart.add("A", 100, 2)
    cart.remove("A", 2)
    assert cart.subtotal_cents() == 100
