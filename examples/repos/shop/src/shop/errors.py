class ShopError(Exception):
    """Base class for all domain errors raised by the shop package."""


class UnknownProduct(ShopError):
    """Raised when a SKU is not present where it is expected."""
