"""tests/test_methodology.py — Tests for methodology documentation consistency"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestLRMESMethodology:
    """Verify that MCP methodology documentation matches the actual implementation."""

    def test_methodology_lrmes_formula_no_rho(self):
        """
        The LRMES methodology formula must NOT contain ρ as a separate factor.
        β_OLS already encodes ρ·σ_i/σ_m; multiplying ρ again would inflate LRMES
        by ~5-10x.
        """
        # We test the methodology dict structure directly to avoid importing
        # mcp.server which conflicts with the installed mcp package.
        from src.config import cfg

        # Replicate the LRMES entry from mcp/server.py get_methodology()
        # If server.py is refactored, this test should be updated to call it.
        formula_file = Path(__file__).parent.parent / "mcp" / "server.py"
        source = formula_file.read_text(encoding="utf-8")

        # The correct formula uses β_OLS (no separate ρ, no √h)
        assert "β_OLS" in source, (
            "Methodology LRMES formula should reference β_OLS"
        )
        # Ensure the old incorrect formula is NOT present
        assert "ρ · β · √h" not in source, (
            "Methodology still contains incorrect LRMES formula with ρ · β · √h; "
            "should be: LRMES ≈ 1 - exp(log(1-D) · β_OLS)"
        )

    def test_methodology_lrmes_no_separate_rho_parameter(self):
        """
        The LRMES parameters section must NOT list ρ as a separate parameter.
        """
        formula_file = Path(__file__).parent.parent / "mcp" / "server.py"
        source = formula_file.read_text(encoding="utf-8")

        # The parameters dict should not have a "ρ" key for LRMES
        # Check that we don't have the old pattern
        assert '"ρ": "Rolling Pearson correlation' not in source, (
            "LRMES parameters should not list ρ as a separate input; "
            "it is already encoded in β_OLS"
        )

    def test_methodology_documents_tail_adjusted_beta(self):
        """
        The LRMES methodology should document the tail-adjusted beta
        (β_tail) used in the actual implementation: β = max(β_OLS, β_tail).
        """
        formula_file = Path(__file__).parent.parent / "mcp" / "server.py"
        source = formula_file.read_text(encoding="utf-8")

        assert "β_tail" in source, (
            "Methodology should document β_tail (tail-adjusted beta) "
            "used in the LRMES implementation"
        )

    def test_methodology_lrmes_six_month_horizon(self):
        """
        The LRMES/SRISK methodology should reference a 6-month horizon
        for the 40% market drop scenario (Brownlees & Engle 2017).
        """
        formula_file = Path(__file__).parent.parent / "mcp" / "server.py"
        source = formula_file.read_text(encoding="utf-8")

        assert "6-month" in source, (
            "Methodology should reference the 6-month crisis horizon "
            "per Brownlees & Engle (2017)"
        )
