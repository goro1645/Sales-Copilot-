"""Sales Copilot offline evaluation package."""

from .cases import ExpectedParse, ExpectedWorkflow, GoldenCase, load_golden_cases

__all__ = [
    "ExpectedParse",
    "ExpectedWorkflow",
    "GoldenCase",
    "load_golden_cases",
]
