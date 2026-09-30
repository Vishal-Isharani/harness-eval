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

    def add(self, sku: str, unit_price_cents: int, quantity: int = 1) -> None:
        if quantity <= 0:
            raise ShopError("quantity must be positive")
        self.items.append(LineItem(sku, unit_price_cents, quantity))

    def remove(self, sku, quantity=None):
        for item in self.items:
            if item.sku == sku:
                if quantity is None:
                    self.items.remove(item)
                    return
                item.quantity -= quantity
                if item.quantity < 0:
                    raise ShopError("too many")
                if item.quantity == 0:
                    self.items.remove(item)
                return
        raise KeyError(sku)

    def subtotal_cents(self) -> int:
        return sum(item.subtotal_cents() for item in self.items)

    def tax_cents(self) -> int:
        return sum(int(item.subtotal_cents() * TAX_RATE_BPS / 10000) for item in self.items)

    def total_cents(self) -> int:
        return self.subtotal_cents() + self.tax_cents()
