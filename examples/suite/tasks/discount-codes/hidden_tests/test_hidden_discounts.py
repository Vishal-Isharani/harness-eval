import pytest

from shop import Cart


def _cart(cents):
    cart = Cart()
    cart.add("A", cents)
    return cart


def test_no_discount_by_default():
    assert _cart(1000).discount_cents() == 0


def test_save10():
    cart = _cart(1000)
    cart.apply_discount("SAVE10")
    assert cart.discount_cents() == 100
    assert cart.total_cents() == 900 + 189


def test_save10_rounds_down():
    cart = _cart(999)
    cart.apply_discount("SAVE10")
    assert cart.discount_cents() == 99


def test_flat500_never_negative():
    cart = _cart(300)
    cart.apply_discount("FLAT500")
    assert cart.discount_cents() == 300
    assert cart.total_cents() == 0


def test_case_insensitive():
    cart = _cart(1000)
    cart.apply_discount("save10")
    assert cart.discount_cents() == 100


def test_new_code_replaces_previous():
    cart = _cart(1000)
    cart.apply_discount("SAVE10")
    cart.apply_discount("FLAT500")
    assert cart.discount_cents() == 500


def test_unknown_code_raises_named_error():
    with pytest.raises(Exception) as exc:
        _cart(1000).apply_discount("FREEBIE")
    assert type(exc.value).__name__ == "InvalidDiscountCode"
