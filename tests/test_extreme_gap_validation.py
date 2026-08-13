import pandas as pd
import pytest

from scripts.research.extreme_gap_validation import (
    absolute_pairwise_bps,
    dispersion_bps,
    subperiod_label,
)


def test_dispersion_bps() -> None:
    result = dispersion_bps(
        [
            99.0,
            100.0,
            101.0,
        ]
    )

    assert result == pytest.approx(200.0)


def test_two_price_dispersion_is_positive() -> None:
    result = dispersion_bps(
        [
            100.0,
            101.0,
        ]
    )

    assert result > 0.0


def test_pairwise_bps() -> None:
    result = absolute_pairwise_bps(
        101.0,
        100.0,
    )

    assert result == pytest.approx(100.0)


def test_pairwise_order_is_absolute() -> None:
    first = absolute_pairwise_bps(
        101.0,
        100.0,
    )

    second = absolute_pairwise_bps(
        100.0,
        101.0,
    )

    assert first > 0.0
    assert second > 0.0


def test_invalid_dispersion_rejected() -> None:
    with pytest.raises(ValueError):
        dispersion_bps(
            [
                0.0,
                100.0,
            ]
        )


def test_invalid_pairwise_rejected() -> None:
    with pytest.raises(ValueError):
        absolute_pairwise_bps(
            -1.0,
            100.0,
        )


def test_subperiod_2017_2020() -> None:
    assert subperiod_label(pd.Timestamp("2020-12-31T00:00:00Z")) == "2017-2020"


def test_subperiod_2021_2023() -> None:
    assert subperiod_label(pd.Timestamp("2022-06-01T00:00:00Z")) == "2021-2023"


def test_subperiod_2024_2026() -> None:
    assert subperiod_label(pd.Timestamp("2026-08-10T00:00:00Z")) == "2024-2026"
