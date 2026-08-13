import numpy as np
import pandas as pd
import pytest

from scripts.research.volatility_dispersion_analysis import (
    assign_quintiles,
    cross_venue_dispersion_bps,
    newey_west_regression,
    past_24h_realized_volatility,
    spearman_correlation,
)


def test_dispersion() -> None:
    index = pd.date_range(
        "2026-01-01T00:00:00Z",
        periods=2,
        freq="h",
    )

    frame = pd.DataFrame(
        {
            "Coinbase": [
                99.0,
                100.0,
            ],
            "Bitstamp": [
                101.0,
                102.0,
            ],
        },
        index=index,
    )

    result = cross_venue_dispersion_bps(frame)

    assert result.iloc[0] == pytest.approx(200.0)


def test_realized_vol_excludes_current_hour() -> None:
    index = pd.date_range(
        "2026-01-01T00:00:00Z",
        periods=30,
        freq="h",
    )

    values = np.full(
        30,
        100.0,
    )

    values[25:] = 200.0

    prices = pd.Series(
        values,
        index=index,
    )

    rv = past_24h_realized_volatility(prices)

    assert rv.iloc[25] == pytest.approx(0.0)

    assert rv.iloc[26] > 0.0


def test_realized_vol_window_rejected() -> None:
    index = pd.date_range(
        "2026-01-01T00:00:00Z",
        periods=3,
        freq="h",
    )

    prices = pd.Series(
        [
            100.0,
            101.0,
            102.0,
        ],
        index=index,
    )

    with pytest.raises(
        ValueError,
        match="positive",
    ):
        past_24h_realized_volatility(
            prices,
            window=0,
        )


def test_assign_quintiles_balanced() -> None:
    index = pd.date_range(
        "2026-01-01T00:00:00Z",
        periods=100,
        freq="h",
    )

    series = pd.Series(
        np.arange(
            1,
            101,
            dtype=float,
        ),
        index=index,
    )

    quintiles = assign_quintiles(series)

    counts = quintiles.value_counts().sort_index()

    assert counts.tolist() == [
        20,
        20,
        20,
        20,
        20,
    ]


def test_spearman_perfect_positive() -> None:
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

    result = spearman_correlation(
        first,
        second,
    )

    assert result == pytest.approx(1.0)


def test_newey_west_positive_slope() -> None:
    x = pd.Series(
        np.linspace(
            -2.0,
            2.0,
            200,
        )
    )

    y = 3.0 + 2.0 * x

    result = newey_west_regression(
        y,
        x,
        lags=12,
    )

    assert result["slope"] == pytest.approx(
        2.0,
        abs=1e-10,
    )

    assert result["intercept"] == pytest.approx(
        3.0,
        abs=1e-10,
    )

    assert result["r_squared"] == pytest.approx(1.0)


def test_newey_west_small_sample_rejected() -> None:
    x = pd.Series(
        np.arange(
            10,
            dtype=float,
        )
    )

    y = x.copy()

    with pytest.raises(
        ValueError,
        match="too small",
    ):
        newey_west_regression(
            y,
            x,
            lags=8,
        )
