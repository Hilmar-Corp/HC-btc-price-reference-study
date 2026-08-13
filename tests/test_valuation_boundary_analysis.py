from datetime import date

import pandas as pd
import pytest

from scripts.research.valuation_boundary_analysis import (
    bucket_start_for_cutoff,
    cutoff_utc,
    return_difference_bps,
    subperiod_label,
    two_venue_composite,
)


def test_utc_midnight_cutoff() -> None:
    result = cutoff_utc(
        date(
            2026,
            7,
            15,
        ),
        "utc_0000",
    )

    assert result == pd.Timestamp("2026-07-15T00:00:00Z")


def test_london_winter_cutoff() -> None:
    result = cutoff_utc(
        date(
            2026,
            1,
            15,
        ),
        "london_1600",
    )

    assert result == pd.Timestamp("2026-01-15T16:00:00Z")


def test_london_summer_cutoff() -> None:
    result = cutoff_utc(
        date(
            2026,
            7,
            15,
        ),
        "london_1600",
    )

    assert result == pd.Timestamp("2026-07-15T15:00:00Z")


def test_new_york_winter_cutoff() -> None:
    result = cutoff_utc(
        date(
            2026,
            1,
            15,
        ),
        "new_york_1600",
    )

    assert result == pd.Timestamp("2026-01-15T21:00:00Z")


def test_new_york_summer_cutoff() -> None:
    result = cutoff_utc(
        date(
            2026,
            7,
            15,
        ),
        "new_york_1600",
    )

    assert result == pd.Timestamp("2026-07-15T20:00:00Z")


def test_bucket_start_is_previous_hour() -> None:
    cutoff = pd.Timestamp("2026-07-15T15:00:00Z")

    result = bucket_start_for_cutoff(cutoff)

    assert result == pd.Timestamp("2026-07-15T14:00:00Z")


def test_naive_cutoff_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        bucket_start_for_cutoff(pd.Timestamp("2026-07-15T15:00:00"))


def test_two_venue_composite() -> None:
    result = two_venue_composite(
        100.0,
        102.0,
    )

    assert result == pytest.approx(101.0)


def test_missing_composite_is_none() -> None:
    assert (
        two_venue_composite(
            None,
            102.0,
        )
        is None
    )


def test_return_difference_bps() -> None:
    result = return_difference_bps(
        0.02,
        0.01,
    )

    assert result == pytest.approx(100.0)


def test_subperiod_labels() -> None:
    assert (
        subperiod_label(
            date(
                2020,
                1,
                1,
            )
        )
        == "2017-2020"
    )

    assert (
        subperiod_label(
            date(
                2022,
                1,
                1,
            )
        )
        == "2021-2023"
    )

    assert (
        subperiod_label(
            date(
                2026,
                1,
                1,
            )
        )
        == "2024-2026"
    )
