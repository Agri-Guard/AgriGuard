"""
backend/app/services/aliases.py — market and commodity name aliases
====================================================================
The WFP Uganda feed doesn't use the names a farmer (or a judge) types:

  * Kampala's price series is recorded under the market name "Owino".
  * "Maize" (plain) only exists in a handful of markets (Owino, Lira, Busia,
    Kabale, Masindi); most others, e.g. Mbarara, record it as "Maize (white)".

`resolve_series()` is the single lookup used by both routers. The typed
market is tried first, then its aliases; within a market the FRESHEST variant
of the crop wins (ties -> typed name). Every alias hit is reported via
`aliased=True`. All comparisons are case-insensitive.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

# lower-case typed name -> lower-case name as recorded in the WFP feed
MARKET_ALIASES: dict[str, tuple[str, ...]] = {
    "kampala": ("owino",),
}

# lower-case typed name -> other recorded names for the same crop, in order
COMMODITY_ALIASES: dict[str, tuple[str, ...]] = {
    "maize": ("maize (white)",),
    "maize (white)": ("maize",),
}


@dataclass(frozen=True)
class ResolvedSeries:
    subset: pd.DataFrame
    commodity: str          # name as recorded in the data
    market: str             # name as recorded in the data
    aliased: bool           # True if an alias (not the typed name) matched


def _market_candidates(market: str) -> list[str]:
    m = market.strip().lower()
    return [m, *MARKET_ALIASES.get(m, ())]


def _commodity_candidates(commodity: str) -> list[str]:
    c = commodity.strip().lower()
    return [c, *COMMODITY_ALIASES.get(c, ())]


def commodity_variants(commodity: str) -> list[str]:
    """Lower-case names that count as the same crop (typed name first)."""
    return _commodity_candidates(commodity)


def resolve_series(
    df: pd.DataFrame, commodity: str, market: str
) -> Optional[ResolvedSeries]:
    """Price series for commodity x market, or None (caller decides what next)."""
    if df is None or df.empty:
        return None

    c_col = df["commodity"].str.lower()
    m_col = df["market"].str.lower()
    c_cands = _commodity_candidates(commodity)

    # Typed market first, then aliases. Within a market, pick the freshest
    # variant: WFP stopped recording plain "Maize" in May 2022 and moved to
    # "Maize (White)", so "exact name first" would serve 4-year-old prices.
    for mi, m in enumerate(_market_candidates(market)):
        best = None
        for ci, c in enumerate(c_cands):
            subset = df[(c_col == c) & (m_col == m)]
            if subset.empty:
                continue
            last = subset["date"].max()
            if best is None or last > best[0]:
                best = (last, ci, subset)
        if best is not None:
            _, ci, subset = best
            return ResolvedSeries(
                subset=subset.sort_values("date").reset_index(drop=True),
                commodity=str(subset["commodity"].iloc[0]),
                market=str(subset["market"].iloc[0]),
                aliased=(ci > 0 or mi > 0),
            )
    return None