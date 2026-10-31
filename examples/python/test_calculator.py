"""Tests for calculator module demonstrating AutoHeal-CI self-healing."""
import pytest
from calculator import compute_average, calculate_discount


def test_compute_average_valid():
    """Verify average calculation for non-empty lists."""
    assert compute_average([10.0, 20.0, 30.0]) == 20.0
    assert compute_average([100.0]) == 100.0


def test_calculate_discount_valid():
    """Verify discount calculation works as expected."""
    assert calculate_discount(100.0, 20.0) == 80.0


def test_compute_average_empty_list():
    """Intentional failing test: average of an empty list should safely return 0.0.

    Without AutoHeal-CI, this raises ZeroDivisionError and crashes the CI suite.
    """
    assert compute_average([]) == 0.0
