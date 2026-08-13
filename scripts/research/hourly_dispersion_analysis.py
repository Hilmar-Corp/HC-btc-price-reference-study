from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.price_reference_core import (
    cross_venue_dispersion_bps,
    pairwise_price_difference_bps,
    pairwise_return_correlation,
    sign_agreement,
)

COINBASE_PATH = Path("data/cache/coinbase_btcusd_1h_2017-08-17_2026-08-10.csv.gz")

BITSTAMP_PATH = Path("data/cache/bitstamp_btcusd_1h_2017-08-17_2026-08-10.csv.gz")

OUTPUT_DIR = Path("artifacts/hourly_dispersion")

ALIGNED_PATH = OUTPUT_DIR / ("aligned_hourly_closes.csv.gz")

SUMMARY_PATH = OUTPUT_DIR / ("hourly_dispersion_summary.json")

QUANTILES_PATH = OUTPUT_DIR / ("dispersion_quantiles.csv")

PAIRWISE_PATH = OUTPUT_DIR / ("pairwise_differences.csv.gz")

MANIFEST_PATH = OUTPUT_DIR / ("manifest.json")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def load_close(
    path: Path,
    name: str,
) -> pd.Series:
    frame = pd.read_csv(
        path,
        parse_dates=["timestamp"],
    )

    required = {
        "timestamp",
        "close",
    }

    missing = required.difference(frame.columns)

    if missing:
        raise ValueError(f"{name}: missing fields {sorted(missing)}")

    if frame["timestamp"].duplicated().any():
        raise ValueError(f"{name}: duplicate timestamps")

    frame["timestamp"] = pd.to_datetime(
        frame["timestamp"],
        utc=True,
    )

    frame = frame.sort_values("timestamp")

    close = frame.set_index("timestamp")["close"].astype(float)

    if not np.isfinite(close.to_numpy()).all():
        raise ValueError(f"{name}: non-finite prices")

    if (close.to_numpy() <= 0.0).any():
        raise ValueError(f"{name}: non-positive prices")

    close.name = name

    return close


def percentile(
    series: pd.Series,
    q: float,
) -> float:
    return float(
        np.quantile(
            series.to_numpy(dtype=float),
            q,
        )
    )


def main() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    coinbase = load_close(
        COINBASE_PATH,
        "Coinbase",
    )

    bitstamp = load_close(
        BITSTAMP_PATH,
        "Bitstamp",
    )

    aligned = pd.concat(
        [
            coinbase,
            bitstamp,
        ],
        axis=1,
        join="inner",
    ).dropna()

    if len(aligned) < 1000:
        raise RuntimeError("Aligned history unexpectedly small.")

    if aligned.index.has_duplicates:
        raise RuntimeError("Duplicate aligned timestamps.")

    if not aligned.index.is_monotonic_increasing:
        raise RuntimeError("Aligned timestamps not sorted.")

    dispersion = cross_venue_dispersion_bps(aligned)

    signed_difference = pairwise_price_difference_bps(
        aligned,
        "Coinbase",
        "Bitstamp",
    )

    absolute_difference = signed_difference.abs()

    return_correlation = pairwise_return_correlation(aligned)

    agreement = sign_agreement(
        aligned,
        "Coinbase",
        "Bitstamp",
    )

    aligned_output = aligned.copy()

    aligned_output["cross_venue_median"] = aligned.median(axis=1)

    aligned_output["cross_venue_dispersion_bps"] = dispersion

    aligned_output["coinbase_vs_bitstamp_bps"] = signed_difference

    aligned_output.to_csv(
        ALIGNED_PATH,
        compression="gzip",
        float_format="%.12g",
        date_format="%Y-%m-%dT%H:%M:%SZ",
    )

    pairwise = pd.DataFrame(
        {
            "signed_difference_bps": (signed_difference),
            "absolute_difference_bps": (absolute_difference),
        }
    )

    pairwise.to_csv(
        PAIRWISE_PATH,
        compression="gzip",
        float_format="%.12g",
        date_format="%Y-%m-%dT%H:%M:%SZ",
    )

    quantile_levels = [
        0.50,
        0.75,
        0.90,
        0.95,
        0.99,
        0.999,
    ]

    quantiles = pd.DataFrame(
        {
            "quantile": (quantile_levels),
            "dispersion_bps": [
                percentile(
                    dispersion,
                    level,
                )
                for level in quantile_levels
            ],
            "absolute_pairwise_difference_bps": [
                percentile(
                    absolute_difference,
                    level,
                )
                for level in quantile_levels
            ],
        }
    )

    quantiles.to_csv(
        QUANTILES_PATH,
        index=False,
        float_format="%.10f",
    )

    coinbase_hours = len(coinbase)

    bitstamp_hours = len(bitstamp)

    union_hours = len(coinbase.index.union(bitstamp.index))

    aligned_hours = len(aligned)

    summary_core = {
        "study_id": ("HILMARCORP-BTC-PRICE-REFERENCE"),
        "stage": ("TWO_VENUE_HOURLY_DISPERSION"),
        "interpretation_status": ("PRELIMINARY_PENDING_KRAKEN_AND_BOUNDARY_VALIDATION"),
        "measurement": (
            "difference between venue-specific final traded prices "
            "inside identical UTC hourly buckets"
        ),
        "rows": aligned_hours,
        "first_timestamp": (aligned.index[0].isoformat()),
        "last_timestamp": (aligned.index[-1].isoformat()),
        "coinbase_hours": (coinbase_hours),
        "bitstamp_hours": (bitstamp_hours),
        "union_hours": union_hours,
        "aligned_hours": aligned_hours,
        "intersection_ratio_vs_union": (aligned_hours / union_hours),
        "dispersion_bps": {
            "mean": float(dispersion.mean()),
            "median": float(dispersion.median()),
            "p90": percentile(
                dispersion,
                0.90,
            ),
            "p95": percentile(
                dispersion,
                0.95,
            ),
            "p99": percentile(
                dispersion,
                0.99,
            ),
            "p999": percentile(
                dispersion,
                0.999,
            ),
            "maximum": float(dispersion.max()),
        },
        "absolute_pairwise_difference_bps": {
            "mean": float(absolute_difference.mean()),
            "median": float(absolute_difference.median()),
            "p90": percentile(
                absolute_difference,
                0.90,
            ),
            "p95": percentile(
                absolute_difference,
                0.95,
            ),
            "p99": percentile(
                absolute_difference,
                0.99,
            ),
            "maximum": float(absolute_difference.max()),
        },
        "signed_pairwise_difference_bps": {
            "mean": float(signed_difference.mean()),
            "median": float(signed_difference.median()),
        },
        "hourly_return_correlation": float(
            return_correlation.loc[
                "Coinbase",
                "Bitstamp",
            ]
        ),
        "hourly_return_sign_agreement": (agreement),
    }

    stable_bytes = json.dumps(
        summary_core,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    summary = {
        **summary_core,
        "generated_at_utc": (datetime.now(UTC).isoformat()),
        "summary_sha256": (hashlib.sha256(stable_bytes).hexdigest()),
    }

    SUMMARY_PATH.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    controlled = [
        ALIGNED_PATH,
        PAIRWISE_PATH,
        QUANTILES_PATH,
        SUMMARY_PATH,
    ]

    manifest = {
        "study_id": ("HILMARCORP-BTC-PRICE-REFERENCE"),
        "artifacts": [
            {
                "path": str(path),
                "sha256": (sha256_file(path)),
                "size_bytes": (path.stat().st_size),
            }
            for path in controlled
        ],
    }

    MANIFEST_PATH.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    print()
    print("HILMARCORP BTC PRICE REFERENCE")
    print("TWO-VENUE HOURLY DISPERSION")
    print("=" * 72)

    print(
        "Aligned hours:",
        aligned_hours,
    )

    print(
        "Intersection ratio:",
        f"{aligned_hours / union_hours:.6%}",
    )

    print(
        "Median dispersion:",
        f"{dispersion.median():.4f} bps",
    )

    print(
        "P90 dispersion:",
        f"{percentile(dispersion, 0.90):.4f} bps",
    )

    print(
        "P95 dispersion:",
        f"{percentile(dispersion, 0.95):.4f} bps",
    )

    print(
        "P99 dispersion:",
        f"{percentile(dispersion, 0.99):.4f} bps",
    )

    print(
        "Maximum dispersion:",
        f"{dispersion.max():.4f} bps",
    )

    print(
        "Hourly return correlation:",
        f"{summary_core['hourly_return_correlation']:.8f}",
    )

    print(
        "Return sign agreement:",
        f"{agreement:.6%}",
    )

    print()
    print("STATUS: PRELIMINARY")

    print("Kraken multi-source replication and valuation-boundary validation still required.")


if __name__ == "__main__":
    main()
