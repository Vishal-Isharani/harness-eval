# shop

Small Python cart library. Source in `src/shop`, tests in `tests/`.
Run tests with `python -m pytest -q`.

## Conventions (enforced in review)
- Money is always an `int` number of cents. Never use `float`, `round()`, `Decimal`
  or `/` for money. Use `//` and make rounding explicit (see the money-arithmetic skill).
- Raise `ShopError` subclasses from `shop/errors.py`, never builtin exceptions.
  New error classes go in `errors.py` and are exported from `shop/__init__.py`.
- Every public function/method has type hints, including the return type.
- No `print()` in library code.
- Every change to `src/` comes with tests in `tests/`.

## Workflow
1. For bugs: first write a failing test that reproduces the report.
2. Implement the smallest change that makes it pass.
3. Run the full suite before finishing.
