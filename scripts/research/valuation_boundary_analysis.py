from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

COINBASE_PATH = Path("data/cache/coinbase_btcusd_1h_2017-08-17_2026-08-10.csv.gz")

BITSTAMP_PATH = Path("data/cache/bitstamp_btcusd_1h_2017-08-17_2026-08-10.csv.gz")

OUTPUT_DIR = Path("artifacts/valuation_boundary")

LONG_PATH = OUTPUT_DIR / "boundary_prices_and_returns.csv.gz"
COMPLETE_PATH = OUTPUT_DIR / "complete_case_returns.csv.gz"
PAIRWISE_PATH = OUTPUT_DIR / "cutoff_pairwise_summary.csv"
VENUE_PATH = OUTPUT_DIR / "venue_effect_summary.csv"
SUBPERIOD_PATH = OUTPUT_DIR / "subperiod_summary.csv"
DST_PATH = OUTPUT_DIR / "dst_sensitivity.csv"
EXTREMES_PATH = OUTPUT_DIR / "largest_cutoff_effect_dates.csv"
MISSING_PATH = OUTPUT_DIR / "missing_boundary_observations.csv"
SUMMARY_PATH = OUTPUT_DIR / "validation_summary.json"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"

BPS = 10_000.0

FIRST_DAY = date(
    2017,
    8,
    18,
)

LAST_DAY = date(
    2026,
    8,
    10,
)

CONVENTIONS = {
    "utc_0000": {
        "timezone": "UTC",
        "hour": 0,
    },
    "london_1600": {
        "timezone": "Europe/London",
        "hour": 16,
    },
    "new_york_1600": {
        "timezone": "America/New_York",
        "hour": 16,
    },
}


def sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def canonical_sha256(
    payload: Any,
) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        ensure_ascii=False,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def cutoff_utc(
    day: date,
    convention: str,
) -> pd.Timestamp:
    if convention not in CONVENTIONS:
        raise ValueError(f"Unknown convention: {convention}")

    config = CONVENTIONS[convention]

    local_zone = ZoneInfo(config["timezone"])

    local_datetime = datetime.combine(
        day,
        time(hour=int(config["hour"])),
        tzinfo=local_zone,
    )

    utc_datetime = local_datetime.astimezone(UTC)

    return pd.Timestamp(utc_datetime)


def bucket_start_for_cutoff(
    cutoff: pd.Timestamp,
) -> pd.Timestamp:
    if cutoff.tzinfo is None:
        raise ValueError("Cutoff must be timezone-aware.")

    return cutoff - pd.Timedelta(hours=1)


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

    frame["timestamp"] = pd.to_datetime(
        frame["timestamp"],
        utc=True,
    )

    if frame["timestamp"].duplicated().any():
        raise ValueError(f"{name}: duplicate timestamps")

    frame = frame.sort_values("timestamp")

    series = frame.set_index("timestamp")["close"].astype(float)

    values = series.to_numpy()

    if not np.isfinite(values).all():
        raise ValueError(f"{name}: non-finite prices")

    if (values <= 0.0).any():
        raise ValueError(f"{name}: non-positive prices")

    series.name = name

    return series


def exact_price(
    series: pd.Series,
    timestamp: pd.Timestamp,
) -> float | None:
    if timestamp not in series.index:
        return None

    value = float(series.loc[timestamp])

    if not np.isfinite(value) or value <= 0.0:
        raise ValueError("Invalid exact price.")

    return value


def two_venue_composite(
    coinbase: float | None,
    bitstamp: float | None,
) -> float | None:
    if coinbase is None or bitstamp is None:
        return None

    values = np.array(
        [
            float(coinbase),
            float(bitstamp),
        ],
        dtype=float,
    )

    return float(np.median(values))


def return_difference_bps(
    first: float,
    second: float,
) -> float:
    if not np.isfinite(first) or not np.isfinite(second):
        raise ValueError("Returns must be finite.")

    return abs(first - second) * BPS


def sign_disagreement(
    first: pd.Series,
    second: pd.Series,
) -> float:
    pair = pd.concat(
        [
            first,
            second,
        ],
        axis=1,
    ).dropna()

    if pair.empty:
        raise ValueError("No observations for sign comparison.")

    first_sign = np.sign(
        pair.iloc[
            :,
            0,
        ].to_numpy(dtype=float)
    )

    second_sign = np.sign(
        pair.iloc[
            :,
            1,
        ].to_numpy(dtype=float)
    )

    return float(np.mean(first_sign != second_sign))


def percentile(
    series: pd.Series,
    q: float,
) -> float:
    clean = series.dropna().astype(float)

    if clean.empty:
        raise ValueError("Cannot compute percentile on empty sample.")

    return float(
        np.quantile(
            clean.to_numpy(),
            q,
        )
    )


def subperiod_label(
    day_value: date,
) -> str:
    if day_value.year <= 2020:
        return "2017-2020"

    if day_value.year <= 2023:
        return "2021-2023"

    return "2024-2026"


def build_boundary_table(
    coinbase: pd.Series,
    bitstamp: pd.Series,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    rows: list[dict[str, Any]] = []

    missing_rows: list[dict[str, Any]] = []

    days = pd.date_range(
        start=pd.Timestamp(FIRST_DAY),
        end=pd.Timestamp(LAST_DAY),
        freq="D",
    )

    for day_timestamp in days:
        day_value = day_timestamp.date()

        for convention in CONVENTIONS:
            cutoff = cutoff_utc(
                day_value,
                convention,
            )

            bucket_start = bucket_start_for_cutoff(cutoff)

            coinbase_price = exact_price(
                coinbase,
                bucket_start,
            )

            bitstamp_price = exact_price(
                bitstamp,
                bucket_start,
            )

            composite_price = two_venue_composite(
                coinbase_price,
                bitstamp_price,
            )

            if coinbase_price is None:
                missing_rows.append(
                    {
                        "date": (day_value.isoformat()),
                        "convention": convention,
                        "source": "Coinbase",
                        "cutoff_utc": (cutoff.isoformat()),
                        "required_bucket_start_utc": (bucket_start.isoformat()),
                    }
                )

            if bitstamp_price is None:
                missing_rows.append(
                    {
                        "date": (day_value.isoformat()),
                        "convention": convention,
                        "source": "Bitstamp",
                        "cutoff_utc": (cutoff.isoformat()),
                        "required_bucket_start_utc": (bucket_start.isoformat()),
                    }
                )

            rows.append(
                {
                    "date": day_value,
                    "subperiod": (subperiod_label(day_value)),
                    "convention": convention,
                    "timezone": (CONVENTIONS[convention]["timezone"]),
                    "local_hour": (CONVENTIONS[convention]["hour"]),
                    "cutoff_utc": cutoff,
                    "bucket_start_utc": (bucket_start),
                    "coinbase_price": (coinbase_price),
                    "bitstamp_price": (bitstamp_price),
                    "composite_price": (composite_price),
                }
            )

    frame = pd.DataFrame(rows)

    missing = pd.DataFrame(missing_rows)

    return (
        frame,
        missing,
    )


def add_returns(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    result = (
        frame.copy()
        .sort_values(
            [
                "convention",
                "date",
            ]
        )
        .reset_index(drop=True)
    )

    result["previous_cutoff_utc"] = result.groupby("convention")["cutoff_utc"].shift(1)

    result["interval_hours"] = (
        result["cutoff_utc"] - result["previous_cutoff_utc"]
    ) / pd.Timedelta(hours=1)

    for source in [
        "coinbase",
        "bitstamp",
        "composite",
    ]:
        price_column = f"{source}_price"

        return_column = f"{source}_return"

        result[return_column] = result.groupby("convention")[price_column].pct_change(
            fill_method=None
        )

    result["venue_return_difference_bps"] = (
        (result["coinbase_return"] - result["bitstamp_return"]).abs().mul(BPS)
    )

    return result


def build_complete_case(
    long_frame: pd.DataFrame,
) -> pd.DataFrame:
    pivot = long_frame.pivot(
        index="date",
        columns="convention",
        values=[
            "composite_return",
            "coinbase_return",
            "bitstamp_return",
            "venue_return_difference_bps",
            "interval_hours",
        ],
    ).sort_index()

    pivot.columns = [f"{metric}__{convention}" for metric, convention in pivot.columns]

    required = [
        "composite_return__utc_0000",
        "composite_return__london_1600",
        "composite_return__new_york_1600",
    ]

    complete = pivot.dropna(subset=required).copy()

    utc_return = complete["composite_return__utc_0000"]

    london_return = complete["composite_return__london_1600"]

    new_york_return = complete["composite_return__new_york_1600"]

    complete["utc_vs_london_bps"] = utc_return.sub(london_return).abs().mul(BPS)

    complete["utc_vs_new_york_bps"] = utc_return.sub(new_york_return).abs().mul(BPS)

    complete["london_vs_new_york_bps"] = london_return.sub(new_york_return).abs().mul(BPS)

    return_matrix = complete[
        [
            "composite_return__utc_0000",
            "composite_return__london_1600",
            "composite_return__new_york_1600",
        ]
    ]

    complete["cutoff_return_dispersion_bps"] = (
        return_matrix.max(axis=1) - return_matrix.min(axis=1)
    ) * BPS

    complete["subperiod"] = [subperiod_label(day_value) for day_value in complete.index]

    interval_columns = [
        "interval_hours__utc_0000",
        "interval_hours__london_1600",
        "interval_hours__new_york_1600",
    ]

    complete["all_intervals_24h"] = complete[interval_columns].eq(24.0).all(axis=1)

    return complete


def distribution_summary(
    series: pd.Series,
) -> dict[str, float]:
    clean = series.dropna().astype(float)

    if clean.empty:
        raise ValueError("Distribution sample empty.")

    return {
        "observations": len(clean),
        "mean": float(clean.mean()),
        "median": float(clean.median()),
        "p90": percentile(
            clean,
            0.90,
        ),
        "p95": percentile(
            clean,
            0.95,
        ),
        "p99": percentile(
            clean,
            0.99,
        ),
        "maximum": float(clean.max()),
    }


def build_pairwise_summary(
    complete: pd.DataFrame,
) -> pd.DataFrame:
    definitions = [
        (
            "UTC 00:00 vs London 16:00",
            "utc_vs_london_bps",
            "composite_return__utc_0000",
            "composite_return__london_1600",
        ),
        (
            "UTC 00:00 vs New York 16:00",
            "utc_vs_new_york_bps",
            "composite_return__utc_0000",
            "composite_return__new_york_1600",
        ),
        (
            "London 16:00 vs New York 16:00",
            "london_vs_new_york_bps",
            "composite_return__london_1600",
            "composite_return__new_york_1600",
        ),
    ]

    rows = []

    for (
        label,
        difference_column,
        first_return,
        second_return,
    ) in definitions:
        stats = distribution_summary(complete[difference_column])

        rows.append(
            {
                "comparison": label,
                **stats,
                "sign_disagreement": (
                    sign_disagreement(
                        complete[first_return],
                        complete[second_return],
                    )
                ),
            }
        )

    return pd.DataFrame(rows)


def build_venue_summary(
    long_frame: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for convention in CONVENTIONS:
        sample = long_frame.loc[
            long_frame["convention"] == convention,
            "venue_return_difference_bps",
        ]

        stats = distribution_summary(sample)

        convention_frame = long_frame.loc[long_frame["convention"] == convention]

        rows.append(
            {
                "convention": convention,
                **stats,
                "return_sign_disagreement": (
                    sign_disagreement(
                        convention_frame["coinbase_return"],
                        convention_frame["bitstamp_return"],
                    )
                ),
            }
        )

    return pd.DataFrame(rows)


def build_subperiod_summary(
    complete: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for period in [
        "2017-2020",
        "2021-2023",
        "2024-2026",
    ]:
        sample = complete.loc[
            complete["subperiod"] == period,
            "cutoff_return_dispersion_bps",
        ]

        if sample.empty:
            continue

        stats = distribution_summary(sample)

        period_frame = complete.loc[complete["subperiod"] == period]

        rows.append(
            {
                "subperiod": period,
                **stats,
                "share_ge_25bps": float((sample >= 25.0).mean()),
                "share_ge_50bps": float((sample >= 50.0).mean()),
                "share_ge_100bps": float((sample >= 100.0).mean()),
                "share_ge_250bps": float((sample >= 250.0).mean()),
                "share_ge_500bps": float((sample >= 500.0).mean()),
                "all_24h_share": float(period_frame["all_intervals_24h"].mean()),
            }
        )

    return pd.DataFrame(rows)


def build_dst_sensitivity(
    complete: pd.DataFrame,
) -> pd.DataFrame:
    all_sample = complete["cutoff_return_dispersion_bps"]

    non_dst = complete.loc[
        complete["all_intervals_24h"],
        "cutoff_return_dispersion_bps",
    ]

    rows = []

    for label, sample in [
        (
            "all_complete_dates",
            all_sample,
        ),
        (
            "all_intervals_exactly_24h",
            non_dst,
        ),
    ]:
        stats = distribution_summary(sample)

        rows.append(
            {
                "sample": label,
                **stats,
            }
        )

    return pd.DataFrame(rows)


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

    boundary, missing = build_boundary_table(
        coinbase,
        bitstamp,
    )

    long_frame = add_returns(boundary)

    complete = build_complete_case(long_frame)

    if len(complete) < 3000:
        raise RuntimeError("Complete-case boundary sample unexpectedly small.")

    pairwise = build_pairwise_summary(complete)

    venue = build_venue_summary(long_frame)

    subperiod = build_subperiod_summary(complete)

    dst = build_dst_sensitivity(complete)

    extremes = (
        complete.sort_values(
            "cutoff_return_dispersion_bps",
            ascending=False,
        )
        .head(50)
        .reset_index()
    )

    long_frame.to_csv(
        LONG_PATH,
        index=False,
        compression="gzip",
        float_format="%.12g",
        date_format=("%Y-%m-%dT%H:%M:%SZ"),
    )

    complete.to_csv(
        COMPLETE_PATH,
        compression="gzip",
        float_format="%.12g",
        date_format=("%Y-%m-%d"),
    )

    pairwise.to_csv(
        PAIRWISE_PATH,
        index=False,
        float_format="%.10f",
    )

    venue.to_csv(
        VENUE_PATH,
        index=False,
        float_format="%.10f",
    )

    subperiod.to_csv(
        SUBPERIOD_PATH,
        index=False,
        float_format="%.10f",
    )

    dst.to_csv(
        DST_PATH,
        index=False,
        float_format="%.10f",
    )

    extremes.to_csv(
        EXTREMES_PATH,
        index=False,
        float_format="%.10f",
    )

    missing.to_csv(
        MISSING_PATH,
        index=False,
    )

    cutoff_dispersion = complete["cutoff_return_dispersion_bps"]

    venue_medians = venue["median"]

    median_venue_effect = float(venue_medians.median())

    median_cutoff_effect = float(cutoff_dispersion.median())

    interval_counts = {}

    for convention in CONVENTIONS:
        series = long_frame.loc[
            long_frame["convention"] == convention,
            "interval_hours",
        ].dropna()

        counts = series.value_counts().sort_index()

        interval_counts[convention] = {
            str(float(interval)): int(count) for interval, count in counts.items()
        }

    summary_core = {
        "study_id": ("HILMARCORP-BTC-PRICE-REFERENCE"),
        "stage": ("VALUATION_BOUNDARY_SENSITIVITY"),
        "first_day": (FIRST_DAY.isoformat()),
        "last_day": (LAST_DAY.isoformat()),
        "complete_return_dates": len(complete),
        "missing_boundary_observations": len(missing),
        "cutoff_return_dispersion_bps": (distribution_summary(cutoff_dispersion)),
        "median_venue_effect_bps": (median_venue_effect),
        "median_cutoff_effect_bps": (median_cutoff_effect),
        "median_cutoff_to_venue_effect_ratio": (
            (median_cutoff_effect / median_venue_effect) if median_venue_effect > 0.0 else None
        ),
        "interval_hour_counts": (interval_counts),
        "pairwise_cutoff_results": (pairwise.to_dict(orient="records")),
        "venue_effect_results": (venue.to_dict(orient="records")),
        "interpretation_limits": [
            (
                "Different valuation cutoffs define different "
                "24-hour market windows and are not trading strategies."
            ),
            (
                "Local-clock cutoffs can create 23-hour or 25-hour "
                "intervals around daylight-saving transitions."
            ),
            (
                "Hourly candle closes represent the final trade "
                "observed inside the preceding hourly bucket, "
                "not a synchronized top-of-book snapshot."
            ),
            (
                "The primary composite uses Coinbase and Bitstamp "
                "only and is a research construction, not an "
                "official benchmark."
            ),
        ],
    }

    summary = {
        **summary_core,
        "generated_at_utc": (datetime.now(UTC).isoformat()),
        "summary_sha256": (canonical_sha256(summary_core)),
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
        PAIRWISE_PATH,
        VENUE_PATH,
        SUBPERIOD_PATH,
        DST_PATH,
        EXTREMES_PATH,
        MISSING_PATH,
        SUMMARY_PATH,
    ]

    manifest = {
        "study_id": ("HILMARCORP-BTC-PRICE-REFERENCE"),
        "stage": ("VALUATION_BOUNDARY_SENSITIVITY"),
        "artifacts": [
            {
                "path": str(path),
                "sha256": (sha256_file(path)),
                "size_bytes": (path.stat().st_size),
            }
            for path in controlled
        ],
        "local_uncommitted_artifacts": [
            {
                "path": str(LONG_PATH),
                "sha256": (sha256_file(LONG_PATH)),
                "size_bytes": (LONG_PATH.stat().st_size),
            },
            {
                "path": str(COMPLETE_PATH),
                "sha256": (sha256_file(COMPLETE_PATH)),
                "size_bytes": (COMPLETE_PATH.stat().st_size),
            },
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

    print("VALUATION BOUNDARY SENSITIVITY")

    print("=" * 76)

    print(
        "Complete return dates:",
        len(complete),
    )

    print(
        "Missing boundary observations:",
        len(missing),
    )

    print()
    print("CUTOFF RETURN DISPERSION")

    stats = distribution_summary(cutoff_dispersion)

    for key in [
        "mean",
        "median",
        "p90",
        "p95",
        "p99",
        "maximum",
    ]:
        print(
            f"{key}:",
            f"{stats[key]:.4f} bps",
        )

    print()
    print("PAIRWISE CUTOFF COMPARISONS")

    print(pairwise.to_string(index=False))

    print()
    print("VENUE EFFECT AT FIXED CUTOFF")

    print(venue.to_string(index=False))

    print()
    print("SUBPERIODS")

    print(subperiod.to_string(index=False))

    print()
    print("DST SENSITIVITY")

    print(dst.to_string(index=False))

    print()
    print(
        "Median cutoff effect:",
        f"{median_cutoff_effect:.4f} bps",
    )

    print(
        "Median venue effect:",
        f"{median_venue_effect:.4f} bps",
    )

    if median_venue_effect > 0.0:
        print(
            "Median cutoff / venue ratio:",
            f"{median_cutoff_effect / median_venue_effect:.4f}x",
        )

    print()
    print(
        "Summary:",
        SUMMARY_PATH,
    )

    print(
        "Manifest:",
        MANIFEST_PATH,
    )


if __name__ == "__main__":
    main()
