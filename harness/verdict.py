"""
harness/verdict.py – compute GALVANI verdict from per-sub-domain stats.

Verdicts (spec step 7):
  DISQUALIFIED  : port crashed or AST check failed (disqualified=True)
  RESURRECTED   : port pass_rate >= 99.0% on EVERY sub-domain
  HEALED        : RESURRECTED port AND original pass_rate < 95% on >= 1 sub-domain
  UNDEAD        : port pass_rate >= 90.0% on every sub-domain (but not RESURRECTED)
  STILL DEAD    : otherwise
"""

from __future__ import annotations


def compute_verdict(
    port_stats: dict | None,
    original_stats: dict | None,
    disqualified: bool = False,
) -> str:
    """Return the verdict string.

    port_stats: dict of {domain_name: {"pass_rate": float, ...}}
    original_stats: same shape, or None (then HEALED is not awarded)
    disqualified: if True, always returns "DISQUALIFIED"
    """
    if disqualified or port_stats is None:
        return "DISQUALIFIED"

    rates = [v["pass_rate"] for v in port_stats.values()]
    if not rates:
        return "STILL DEAD"

    all_resurrected = all(r >= 99.0 for r in rates)
    all_undead      = all(r >= 90.0 for r in rates)

    if all_resurrected:
        # Check for HEALED: original < 95% on at least one sub-domain
        if original_stats:
            orig_rates = [v["pass_rate"] for v in original_stats.values()]
            if any(r < 95.0 for r in orig_rates):
                return "HEALED"
        return "RESURRECTED"

    if all_undead:
        return "UNDEAD"

    return "STILL DEAD"
