import pandas as pd
import pytest

from scripts.research.hourly_history import (
    deduplicate_identical,
    normalize_timestamp_column,
    validate_ohlc,
)


def sample_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-08-10T00:00:00Z",
                    "2026-08-10T01:00:00Z",
                ],
                utc=True,
            ),
            "open": [
                100.0,
                101.0,
            ],
            "high": [
                102.0,
                103.0,
            ],
            "low": [
                99.0,
                100.0,
            ],
            "close": [
                101.0,
                102.0,
            ],
            "volume": [
                10.0,
                11.0,
            ],
        }
    )


def test_validate_clean_ohlc() -> None:
    validate_ohlc(sample_frame())


def test_invalid_high_low_fails() -> None:
    frame = sample_frame()
    frame.loc[0, "low"] = 103.0

    with pytest.raises(
        ValueError,
        match="Invalid OHLC",
    ):
        validate_ohlc(frame)


def test_duplicate_timestamp_fails() -> None:
    frame = sample_frame()
    frame.loc[
        1,
        "timestamp",
    ] = frame.loc[
        0,
        "timestamp",
    ]

    with pytest.raises(
        ValueError,
        match="Duplicate timestamps",
    ):
        validate_ohlc(frame)


def test_identical_duplicates_are_collapsed() -> None:
    frame = sample_frame()

    duplicate = pd.concat(
        [
            frame,
            frame.iloc[[0]],
        ],
        ignore_index=True,
    )

    result = deduplicate_identical(duplicate)

    assert len(result) == 2


def test_conflicting_duplicates_fail() -> None:
    frame = sample_frame()

    extra = frame.iloc[[0]].copy()

    extra["close"] = 100.5

    duplicate = pd.concat(
        [
            frame,
            extra,
        ],
        ignore_index=True,
    )

    with pytest.raises(
        ValueError,
        match="Conflicting duplicated",
    ):
        deduplicate_identical(duplicate)


def test_normalization_sorts() -> None:
    frame = sample_frame().iloc[::-1].reset_index(drop=True)

    result = normalize_timestamp_column(frame)

    assert result["timestamp"].is_monotonic_increasing
