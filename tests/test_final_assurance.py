from itertools import pairwise

import numpy as np
import pandas as pd
import pytest

from scripts.research.final_assurance import (
    quintile_ratio,
    spearman,
    strict_calendar_rv24,
)


def test_strict_calendar_rv_detects_missing_hour() -> None:
    full_index = pd.date_range(
        "2026-01-01T00:00:00Z",
        periods=40,
        freq="h",
    )

    prices = pd.Series(
        np.linspace(
            100.0,
            120.0,
            40,
        ),
        index=full_index,
    )

    prices = prices.drop(full_index[10])

    rv = strict_calendar_rv24(prices)

    affected = full_index[11:35].intersection(rv.index)

    assert rv.loc[affected].isna().any()


def test_strict_calendar_rv_regular_data() -> None:
    index = pd.date_range(
        "2026-01-01T00:00:00Z",
        periods=40,
        freq="h",
    )

    prices = pd.Series(
        np.linspace(
            100.0,
            120.0,
            40,
        ),
        index=index,
    )

    rv = strict_calendar_rv24(prices)

    assert rv.notna().sum() > 0


def test_spearman_positive() -> None:
    first = pd.Series(
        [
            1.0,
            2.0,
            3.0,
            4.0,
        ]
    )

    second = pd.Series(
        [
            10.0,
            20.0,
            30.0,
            40.0,
        ]
    )

    assert spearman(
        first,
        second,
    ) == pytest.approx(1.0)


def test_quintile_ratio_monotonic_fixture() -> None:
    index = pd.date_range(
        "2026-01-01T00:00:00Z",
        periods=100,
        freq="h",
    )

    volatility = pd.Series(
        np.arange(
            1,
            101,
            dtype=float,
        ),
        index=index,
    )

    dispersion = pd.Series(
        np.arange(
            1,
            101,
            dtype=float,
        ),
        index=index,
    )

    ratio, medians = quintile_ratio(
        dispersion,
        volatility,
    )

    assert ratio > 1.0

    assert all(right > left for left, right in pairwise(medians))
