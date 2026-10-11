"""Regression tests of PR #44 that still apply: ``context_utilization`` of the
token tracker must not divide by zero when the context window is 0."""

from app.core.token_tracker import TokenTracker


def test_context_utilization_handles_zero_max_context() -> None:
    """A 0-token context window must yield 0.0, not raise ZeroDivisionError."""
    tracker = TokenTracker(
        total_input_tokens=100,
        total_output_tokens=50,
        max_context_tokens=0,
    )
    # Regression: previously ``total_tokens / max_context_tokens`` raised.
    assert tracker.context_utilization == 0.0


def test_context_utilization_normal_window() -> None:
    """Sanity check that the guard did not break the happy path."""
    tracker = TokenTracker(
        total_input_tokens=50_000,
        total_output_tokens=50_000,
        max_context_tokens=200_000,
    )
    # 100_000 / 200_000 is exactly representable in float.
    assert tracker.context_utilization == 0.5
