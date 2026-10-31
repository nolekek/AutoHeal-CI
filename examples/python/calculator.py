"""Example Python module for AutoHeal-CI live demonstration."""


def compute_average(scores: list[float]) -> float:
    """Compute the mathematical average of numerical scores.

    BUG: Does not check for empty list, raising ZeroDivisionError.
    AutoHeal-CI will detect this failure, slice the AST, generate a guard clause,
    verify in git worktree, and submit a pull request with a regression test.
    """
    return sum(scores) / len(scores)


def calculate_discount(price: float, discount_percent: float) -> float:
    """Calculate discounted price with validation."""
    if discount_percent < 0 or discount_percent > 100:
        raise ValueError("Discount must be between 0 and 100")
    return price * (1.0 - (discount_percent / 100.0))
