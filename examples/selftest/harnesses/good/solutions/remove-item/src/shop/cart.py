from __future__ import annotations

from dataclasses import dataclass, field

from .errors import ShopError, UnknownProduct

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

    def remove(self, sku: str, quantity: int | None = None) -> None:
        present = sum(item.quantity for item in self.items if item.sku == sku)
        if present == 0:
            raise UnknownProduct(sku)
        to_remove = present if quantity is None else quantity
        if to_remove <= 0:
            raise ShopError("quantity must be positive")
        if to_remove > present:
            raise ShopError(f"cannot remove {to_remove} of {sku}: only {present} in cart")
        kept: list[LineItem] = []
        for item in self.items:
            if item.sku == sku and to_remove > 0:
                taken = min(item.quantity, to_remove)
                item.quantity -= taken
                to_remove -= taken
            if item.quantity > 0:
                kept.append(item)
        self.items = kept

    def subtotal_cents(self) -> int:
        return sum(item.subtotal_cents() for item in self.items)

    def tax_cents(self) -> int:
        return sum(int(item.subtotal_cents() * TAX_RATE_BPS / 10000) for item in self.items)

    def total_cents(self) -> int:
        return self.subtotal_cents() + self.tax_cents()
