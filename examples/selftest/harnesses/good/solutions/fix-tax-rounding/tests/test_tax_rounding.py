from shop import Cart


def test_reported_case_two_items_at_199():
    cart = Cart()
    cart.add("A", 199)
    cart.add("B", 199)
    assert cart.tax_cents() == 84


def test_half_up():
    cart = Cart()
    cart.add("A", 50)
    assert cart.tax_cents() == 11
