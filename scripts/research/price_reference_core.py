from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

BPS = 10_000.0


class DataContractError(ValueError):
    pass


def validate_price_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame):
        raise DataContractError("Price input must be a pandas DataFrame.")

    if frame.empty:
        raise DataContractError("Price frame is empty.")

    if frame.shape[1] < 2:
        raise DataContractError("At least two venues are required.")

    if not isinstance(frame.index, pd.DatetimeIndex):
        raise DataContractError("Price frame index must be a DatetimeIndex.")

    if frame.index.tz is None:
        raise DataContractError("Price timestamps must be timezone-aware.")

    if frame.index.has_duplicates:
        raise DataContractError("Duplicate timestamps are forbidden.")

    if not frame.index.is_monotonic_increasing:
        raise DataContractError("Timestamps must be sorted chronologically.")

    if frame.columns.has_duplicates:
        raise DataContractError("Duplicate venue columns are forbidden.")

    try:
        numeric = frame.astype(float)
    except (TypeError, ValueError) as exc:
        raise DataContractError("All venue prices must be numeric.") from exc

    values = numeric.to_numpy(dtype=float)

    if not np.isfinite(values).all():
        raise DataContractError("Non-finite prices are forbidden.")

    if (values <= 0.0).any():
        raise DataContractError("Prices must be strictly positive.")

    return numeric


def cross_venue_median(frame: pd.DataFrame) -> pd.Series:
    clean = validate_price_frame(frame)
    result = clean.median(axis=1)
    result.name = "cross_venue_median"
    return result


def venue_deviation_bps(frame: pd.DataFrame) -> pd.DataFrame:
    clean = validate_price_frame(frame)
    median = cross_venue_median(clean)
    result = clean.div(median, axis=0).sub(1.0).mul(BPS)
    result.columns = [f"{column}_deviation_bps" for column in result.columns]
    return result


def cross_venue_dispersion_bps(frame: pd.DataFrame) -> pd.Series:
    clean = validate_price_frame(frame)
    median = cross_venue_median(clean)
    high = clean.max(axis=1)
    low = clean.min(axis=1)
    result = high.sub(low).div(median).mul(BPS)
    result.name = "cross_venue_dispersion_bps"
    return result


def pairwise_price_difference_bps(
    frame: pd.DataFrame,
    venue_a: str,
    venue_b: str,
) -> pd.Series:
    clean = validate_price_frame(frame)

    if venue_a not in clean.columns:
        raise DataContractError(f"Unknown venue: {venue_a}")

    if venue_b not in clean.columns:
        raise DataContractError(f"Unknown venue: {venue_b}")

    if venue_a == venue_b:
        raise DataContractError("Pairwise venues must be different.")

    result = clean[venue_a].div(clean[venue_b]).sub(1.0).mul(BPS)
    result.name = f"{venue_a}_vs_{venue_b}_bps"
    return result


def pairwise_return_correlation(frame: pd.DataFrame) -> pd.DataFrame:
    clean = validate_price_frame(frame)
    returns = clean.pct_change().dropna(how="any")

    if returns.empty:
        raise DataContractError("At least two timestamps are required for returns.")

    return returns.corr(method="pearson")


def sign_agreement(frame: pd.DataFrame, venue_a: str, venue_b: str) -> float:
    clean = validate_price_frame(frame)

    if venue_a not in clean.columns or venue_b not in clean.columns:
        raise DataContractError("Unknown venue in sign-agreement request.")

    returns = clean[[venue_a, venue_b]].pct_change().dropna(how="any")

    if returns.empty:
        raise DataContractError("At least two timestamps are required for returns.")

    sign_a = np.sign(returns[venue_a].to_numpy())
    sign_b = np.sign(returns[venue_b].to_numpy())

    return float(np.mean(sign_a == sign_b))


def compute_price_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    clean = validate_price_frame(frame)

    result = pd.DataFrame(index=clean.index)
    result["cross_venue_median"] = cross_venue_median(clean)
    result["cross_venue_dispersion_bps"] = cross_venue_dispersion_bps(clean)

    deviations = venue_deviation_bps(clean)

    return result.join(deviations)


def sha256_path(path: str | Path) -> str:
    file_path = Path(path)

    if not file_path.is_file():
        raise FileNotFoundError(file_path)

    digest = hashlib.sha256()

    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()
