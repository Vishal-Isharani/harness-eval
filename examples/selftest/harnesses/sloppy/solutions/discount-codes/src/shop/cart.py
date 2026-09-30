from __future__ import annotations

from dataclasses import dataclass, field

from .errors import ShopError

TAX_RATE_BPS = 2100  # 21% VAT, in basis points


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
    code: str = None

    def add(self, sku: str, unit_price_cents: int, quantity: int = 1) -> None:
        if quantity <= 0:
            raise ShopError("quantity must be positive")
        self.items.append(LineItem(sku, unit_price_cents, quantity))

    def subtotal_cents(self) -> int:
        return sum(item.subtotal_cents() for item in self.items)

    def apply_discount(self, code):
        if code not in ("SAVE10", "FLAT500"):
            raise ValueError("invalid code " + code)
        print("applied", code)
        self.code = code

    def discount_cents(self):
        s = self.subtotal_cents()
        if self.code == "SAVE10":
            return int(s * 0.1)
        if self.code == "FLAT500":
            return min(500, s)
        return 0

    def tax_cents(self) -> int:
        return int((self.subtotal_cents() - self.discount_cents()) * 0.21)

    def total_cents(self) -> int:
        return self.subtotal_cents() - self.discount_cents() + self.tax_cents()
