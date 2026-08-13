from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.research.price_reference_core import (
    DataContractError,
    compute_price_metrics,
    cross_venue_dispersion_bps,
    cross_venue_median,
    pairwise_price_difference_bps,
    pairwise_return_correlation,
    sha256_path,
    sign_agreement,
    validate_price_frame,
    venue_deviation_bps,
)


def sample_frame() -> pd.DataFrame:
    index = pd.date_range(
        "2026-08-10T00:00:00Z",
        periods=4,
        freq="min",
    )

    return pd.DataFrame(
        {
            "Coinbase": [
                100.0,
                101.0,
                102.0,
                101.0,
            ],
            "Bitstamp": [
                101.0,
                102.0,
                103.0,
                102.0,
            ],
            "Kraken": [
                99.0,
                100.0,
                101.0,
                100.0,
            ],
        },
        index=index,
    )


def test_validate_price_frame_accepts_clean_frame() -> None:
    frame = sample_frame()

    clean = validate_price_frame(frame)

    assert clean.shape == (4, 3)
    assert clean.index.tz is not None


def test_cross_venue_median() -> None:
    frame = sample_frame()

    median = cross_venue_median(frame)

    assert median.iloc[0] == pytest.approx(100.0)
    assert median.iloc[3] == pytest.approx(101.0)


def test_venue_deviation_bps() -> None:
    frame = sample_frame()

    deviations = venue_deviation_bps(frame)

    assert deviations.loc[
        frame.index[0],
        "Coinbase_deviation_bps",
    ] == pytest.approx(0.0)

    assert deviations.loc[
        frame.index[0],
        "Bitstamp_deviation_bps",
    ] == pytest.approx(100.0)

    assert deviations.loc[
        frame.index[0],
        "Kraken_deviation_bps",
    ] == pytest.approx(-100.0)


def test_cross_venue_dispersion_bps() -> None:
    frame = sample_frame()

    dispersion = cross_venue_dispersion_bps(frame)

    assert dispersion.iloc[0] == pytest.approx(200.0)


def test_pairwise_price_difference_bps() -> None:
    frame = sample_frame()

    result = pairwise_price_difference_bps(
        frame,
        "Bitstamp",
        "Coinbase",
    )

    assert result.iloc[0] == pytest.approx(100.0)


def test_pairwise_return_correlation_is_square() -> None:
    frame = sample_frame()

    correlation = pairwise_return_correlation(frame)

    assert correlation.shape == (3, 3)
    assert np.allclose(
        np.diag(correlation),
        np.ones(3),
    )


def test_sign_agreement() -> None:
    frame = sample_frame()

    agreement = sign_agreement(
        frame,
        "Coinbase",
        "Bitstamp",
    )

    assert agreement == pytest.approx(1.0)


def test_compute_price_metrics() -> None:
    frame = sample_frame()

    metrics = compute_price_metrics(frame)

    assert "cross_venue_median" in metrics.columns
    assert "cross_venue_dispersion_bps" in metrics.columns
    assert "Coinbase_deviation_bps" in metrics.columns
    assert len(metrics) == len(frame)


def test_empty_frame_rejected() -> None:
    with pytest.raises(
        DataContractError,
        match="empty",
    ):
        validate_price_frame(pd.DataFrame())


def test_single_venue_rejected() -> None:
    frame = sample_frame()[["Coinbase"]]

    with pytest.raises(
        DataContractError,
        match="two venues",
    ):
        validate_price_frame(frame)


def test_non_datetime_index_rejected() -> None:
    frame = sample_frame().reset_index(drop=True)

    with pytest.raises(
        DataContractError,
        match="DatetimeIndex",
    ):
        validate_price_frame(frame)


def test_naive_timestamp_rejected() -> None:
    frame = sample_frame()
    frame.index = frame.index.tz_localize(None)

    with pytest.raises(
        DataContractError,
        match="timezone-aware",
    ):
        validate_price_frame(frame)


def test_duplicate_timestamp_rejected() -> None:
    frame = sample_frame()
    frame.index = pd.DatetimeIndex(
        [
            frame.index[0],
            frame.index[0],
            frame.index[2],
            frame.index[3],
        ]
    )

    with pytest.raises(
        DataContractError,
        match="Duplicate timestamps",
    ):
        validate_price_frame(frame)


def test_unsorted_timestamp_rejected() -> None:
    frame = sample_frame().iloc[::-1]

    with pytest.raises(
        DataContractError,
        match="sorted chronologically",
    ):
        validate_price_frame(frame)


def test_duplicate_venue_rejected() -> None:
    frame = sample_frame()
    frame.columns = [
        "Coinbase",
        "Coinbase",
        "Kraken",
    ]

    with pytest.raises(
        DataContractError,
        match="Duplicate venue",
    ):
        validate_price_frame(frame)


def test_non_numeric_price_rejected() -> None:
    frame = sample_frame().astype(object)
    frame.iloc[0, 0] = "bad"

    with pytest.raises(
        DataContractError,
        match="numeric",
    ):
        validate_price_frame(frame)


def test_nan_rejected() -> None:
    frame = sample_frame()
    frame.iloc[0, 0] = np.nan

    with pytest.raises(
        DataContractError,
        match="Non-finite",
    ):
        validate_price_frame(frame)


def test_infinite_price_rejected() -> None:
    frame = sample_frame()
    frame.iloc[0, 0] = np.inf

    with pytest.raises(
        DataContractError,
        match="Non-finite",
    ):
        validate_price_frame(frame)


def test_zero_price_rejected() -> None:
    frame = sample_frame()
    frame.iloc[0, 0] = 0.0

    with pytest.raises(
        DataContractError,
        match="strictly positive",
    ):
        validate_price_frame(frame)


def test_unknown_pairwise_venue_rejected() -> None:
    frame = sample_frame()

    with pytest.raises(
        DataContractError,
        match="Unknown venue",
    ):
        pairwise_price_difference_bps(
            frame,
            "Unknown",
            "Coinbase",
        )


def test_same_pairwise_venue_rejected() -> None:
    frame = sample_frame()

    with pytest.raises(
        DataContractError,
        match="different",
    ):
        pairwise_price_difference_bps(
            frame,
            "Coinbase",
            "Coinbase",
        )


def test_unknown_sign_agreement_venue_rejected() -> None:
    frame = sample_frame()

    with pytest.raises(
        DataContractError,
        match="Unknown venue",
    ):
        sign_agreement(
            frame,
            "Coinbase",
            "Unknown",
        )


def test_return_correlation_requires_two_timestamps() -> None:
    frame = sample_frame().iloc[:1]

    with pytest.raises(
        DataContractError,
        match="two timestamps",
    ):
        pairwise_return_correlation(frame)


def test_sign_agreement_requires_two_timestamps() -> None:
    frame = sample_frame().iloc[:1]

    with pytest.raises(
        DataContractError,
        match="two timestamps",
    ):
        sign_agreement(
            frame,
            "Coinbase",
            "Bitstamp",
        )


def test_sha256_path(tmp_path: Path) -> None:
    path = tmp_path / "fixture.txt"
    path.write_text(
        "HilmarCorp",
        encoding="utf-8",
    )

    digest = sha256_path(path)

    assert len(digest) == 64
    assert digest == sha256_path(path)


def test_sha256_missing_file_rejected(
    tmp_path: Path,
) -> None:
    with pytest.raises(FileNotFoundError):
        sha256_path(tmp_path / "missing.txt")
