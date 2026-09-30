from __future__ import annotations

from dataclasses import dataclass, field

from .errors import InvalidDiscountCode, ShopError

TAX_RATE_BPS = 2100  # 21% VAT, in basis points
PERCENT_CODES_BPS = {"SAVE10": 1_000}
FLAT_CODES_CENTS = {"FLAT500": 500}


@dataclass
class LineItem:
    sku: str
    unit_price_cents: int
    quantity: int = 1

    def subtotal_cents(self) -> int:
        return self.unit_price_cents * self.quantity


@dataclass
class Cart:
    items: list[LineItem] = field(default_factory=list)
    discount_code: str | None = None

    def add(self, sku: str, unit_price_cents: int, quantity: int = 1) -> None:
        if quantity <= 0:
            raise ShopError("quantity must be positive")
        self.items.append(LineItem(sku, unit_price_cents, quantity))

    def apply_discount(self, code: str) -> None:
        normalized = code.strip().upper()
        if normalized not in PERCENT_CODES_BPS and normalized not in FLAT_CODES_CENTS:
            raise InvalidDiscountCode(code)
        self.discount_code = normalized

    def subtotal_cents(self) -> int:
        return sum(item.subtotal_cents() for item in self.items)

    def discount_cents(self) -> int:
        subtotal = self.subtotal_cents()
        if self.discount_code in PERCENT_CODES_BPS:
            raw = subtotal * PERCENT_CODES_BPS[self.discount_code] // 10_000
        elif self.discount_code in FLAT_CODES_CENTS:
            raw = FLAT_CODES_CENTS[self.discount_code]
        else:
            raw = 0
        return min(raw, subtotal)

    def discounted_subtotal_cents(self) -> int:
        return self.subtotal_cents() - self.discount_cents()

    def tax_cents(self) -> int:
        return self.discounted_subtotal_cents() * TAX_RATE_BPS // 10_000

    def total_cents(self) -> int:
        return self.discounted_subtotal_cents() + self.tax_cents()
