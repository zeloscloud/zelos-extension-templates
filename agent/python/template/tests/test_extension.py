"""Tests showcasing the Zelos checker framework.

This file demonstrates all available checker operators.
Users can run these tests to see the "checkerboard" output format.
"""


def test_checker_equality(check) -> None:
    """Equality and inequality operators."""
    check.that(10, "==", 10)
    check.that(10, "is equal to", 10)
    check.that("hello", "!=", "goodbye")


def test_checker_comparison(check) -> None:
    """Comparison operators."""
    check.that(10, ">", 5)
    check.that(10, ">=", 10)
    check.that(5, "<", 10)
    check.that(5, "<=", 10)


def test_checker_membership(check) -> None:
    """Membership operators."""
    check.that(2, "in", [1, 2, 3])
    check.that(4, "not in", [1, 2, 3])


def test_checker_approximation(check) -> None:
    """Approximation operators."""
    check.that(3.14159, "is_close", 3.14, rel_tol=0.01)
    check.that(3.14159, "~=", 3.14, abs_tol=0.01)


def test_checker_strings(check) -> None:
    """String operators."""
    check.that("hello world", "starts with", "hello")
    check.that("hello world", "ends with", "world")
    check.that("hello world", "contains", "world")


def test_checker_empty(check) -> None:
    """Emptiness."""
    check.that("", "is_empty")


def test_checker_numeric(check) -> None:
    """Numeric operators."""
    check.that(42, "is_positive")
    check.that(-42, "is_negative")
    check.that(10, "is_divisible_by", 5)


def test_checker_boolean(check) -> None:
    """Boolean checking (strict, not truthy/falsy)."""
    check.that(True, "is_true")
    check.that(False, "is_false")
