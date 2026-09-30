from shop import Cart


def test_tax_on_subtotal_not_per_line():
    cart = Cart()
    cart.add("A", 199)
    cart.add("B", 199)
    assert cart.tax_cents() == 84


def test_rounds_half_up():
    cart = Cart()
    cart.add("A", 50)  # 50 * 21% = 10.5 cents
    assert cart.tax_cents() == 11


def test_total_includes_rounded_tax():
    cart = Cart()
    cart.add("A", 199, 2)
    assert cart.total_cents() == 482


def test_empty_cart_has_no_tax():
    assert Cart().tax_cents() == 0
