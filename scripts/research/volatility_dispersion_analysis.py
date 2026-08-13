from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

COINBASE_PATH = Path("data/cache/coinbase_btcusd_1h_2017-08-17_2026-08-10.csv.gz")

BITSTAMP_PATH = Path("data/cache/bitstamp_btcusd_1h_2017-08-17_2026-08-10.csv.gz")

OUTPUT_DIR = Path("artifacts/volatility_dispersion")

PANEL_PATH = OUTPUT_DIR / "hourly_panel.csv.gz"
QUINTILE_PATH = OUTPUT_DIR / "volatility_quintiles.csv"
SUBPERIOD_QUINTILE_PATH = OUTPUT_DIR / "subperiod_volatility_quintiles.csv"
CORRELATION_PATH = OUTPUT_DIR / "spearman_correlations.csv"
REGRESSION_PATH = OUTPUT_DIR / "newey_west_regressions.csv"
SENSITIVITY_PATH = OUTPUT_DIR / "sensitivity_summary.csv"
SUMMARY_PATH = OUTPUT_DIR / "validation_summary.json"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"

BPS = 10_000.0
RV_WINDOW = 24
HAC_LAGS = 24


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


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

    close = frame.set_index("timestamp")["close"].astype(float)

    values = close.to_numpy(dtype=float)

    if not np.isfinite(values).all():
        raise ValueError(f"{name}: non-finite close")

    if (values <= 0.0).any():
        raise ValueError(f"{name}: non-positive close")

    close.name = name

    return close


def cross_venue_dispersion_bps(
    frame: pd.DataFrame,
) -> pd.Series:
    if frame.shape[1] < 2:
        raise ValueError("At least two venues required.")

    values = frame.to_numpy(dtype=float)

    if not np.isfinite(values).all():
        raise ValueError("Non-finite venue prices.")

    if (values <= 0.0).any():
        raise ValueError("Non-positive venue prices.")

    median = frame.median(axis=1)

    result = frame.max(axis=1).sub(frame.min(axis=1)).div(median).mul(BPS)

    result.name = "cross_venue_dispersion_bps"

    return result


def past_24h_realized_volatility(
    prices: pd.Series,
    window: int = RV_WINDOW,
) -> pd.Series:
    if window <= 0:
        raise ValueError("window must be positive.")

    values = prices.to_numpy(dtype=float)

    if not np.isfinite(values).all():
        raise ValueError("Prices contain non-finite values.")

    if (values <= 0.0).any():
        raise ValueError("Prices must be positive.")

    log_price = np.log(prices)

    log_return = log_price.diff()

    lagged_squared_return = log_return.pow(2).shift(1)

    realized_variance = lagged_squared_return.rolling(
        window=window,
        min_periods=window,
    ).sum()

    result = realized_variance.pow(0.5)

    result.name = "past_24h_realized_vol"

    return result


def assign_quintiles(
    series: pd.Series,
) -> pd.Series:
    clean = series.dropna()

    if len(clean) < 5:
        raise ValueError("Not enough observations for quintiles.")

    deterministic_rank = clean.rank(method="first")

    labels = pd.qcut(
        deterministic_rank,
        q=5,
        labels=[
            1,
            2,
            3,
            4,
            5,
        ],
    )

    result = pd.Series(
        pd.NA,
        index=series.index,
        dtype="Int64",
        name="volatility_quintile",
    )

    result.loc[clean.index] = labels.astype(int)

    return result


def percentile(
    series: pd.Series,
    q: float,
) -> float:
    clean = series.dropna().astype(float)

    if clean.empty:
        raise ValueError("Empty percentile sample.")

    return float(
        np.quantile(
            clean.to_numpy(),
            q,
        )
    )


def spearman_correlation(
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

    if len(pair) < 3:
        raise ValueError("Not enough observations for correlation.")

    first_rank = pair.iloc[:, 0].rank(method="average")

    second_rank = pair.iloc[:, 1].rank(method="average")

    correlation = first_rank.corr(
        second_rank,
        method="pearson",
    )

    if correlation is None or not np.isfinite(correlation):
        raise ValueError("Invalid Spearman correlation.")

    return float(correlation)


def newey_west_regression(
    y: pd.Series,
    x: pd.Series,
    lags: int = HAC_LAGS,
) -> dict[str, float | int]:
    pair = pd.concat(
        [
            y.rename("y"),
            x.rename("x"),
        ],
        axis=1,
    ).dropna()

    if len(pair) <= lags + 5:
        raise ValueError("Regression sample too small.")

    y_array = pair["y"].to_numpy(dtype=float)

    x_raw = pair["x"].to_numpy(dtype=float)

    if not np.isfinite(y_array).all():
        raise ValueError("Regression y is non-finite.")

    if not np.isfinite(x_raw).all():
        raise ValueError("Regression x is non-finite.")

    n = len(pair)

    design = np.column_stack(
        [
            np.ones(n),
            x_raw,
        ]
    )

    xtx_inverse = np.linalg.pinv(design.T @ design)

    beta = xtx_inverse @ design.T @ y_array

    residual = y_array - design @ beta

    meat = np.zeros(
        (
            2,
            2,
        ),
        dtype=float,
    )

    for index in range(n):
        vector = design[index] * residual[index]

        meat += np.outer(
            vector,
            vector,
        )

    maximum_lag = min(
        lags,
        n - 1,
    )

    for lag in range(
        1,
        maximum_lag + 1,
    ):
        weight = 1.0 - lag / (maximum_lag + 1.0)

        gamma = np.zeros(
            (
                2,
                2,
            ),
            dtype=float,
        )

        for index in range(
            lag,
            n,
        ):
            current = design[index] * residual[index]

            previous = design[index - lag] * residual[index - lag]

            gamma += np.outer(
                current,
                previous,
            )

        meat += weight * (gamma + gamma.T)

    covariance = xtx_inverse @ meat @ xtx_inverse

    diagonal = np.diag(covariance)

    diagonal = np.maximum(
        diagonal,
        0.0,
    )

    standard_errors = np.sqrt(diagonal)

    slope_se = float(standard_errors[1])

    slope = float(beta[1])

    if slope_se > 0.0:
        t_statistic = slope / slope_se

        p_value = math.erfc(abs(t_statistic) / math.sqrt(2.0))
    else:
        t_statistic = float("nan")

        p_value = float("nan")

    total_sum_squares = float(np.sum((y_array - y_array.mean()) ** 2))

    residual_sum_squares = float(np.sum(residual**2))

    if total_sum_squares > 0.0:
        r_squared = 1.0 - residual_sum_squares / total_sum_squares
    else:
        r_squared = 0.0

    return {
        "observations": n,
        "intercept": float(beta[0]),
        "slope": slope,
        "slope_hac_se": slope_se,
        "slope_hac_t": float(t_statistic),
        "slope_normal_p_value": float(p_value),
        "r_squared": float(r_squared),
        "hac_lags": maximum_lag,
    }


def subperiod_label(
    timestamp: pd.Timestamp,
) -> str:
    if timestamp.year <= 2020:
        return "2017-2020"

    if timestamp.year <= 2023:
        return "2021-2023"

    return "2024-2026"


def build_panel() -> pd.DataFrame:
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

    if len(aligned) < 70_000:
        raise RuntimeError("Aligned sample unexpectedly small.")

    if aligned.index.has_duplicates:
        raise RuntimeError("Duplicate aligned timestamps.")

    if not aligned.index.is_monotonic_increasing:
        raise RuntimeError("Aligned timestamps not sorted.")

    panel = aligned.copy()

    panel["research_composite"] = panel.median(axis=1)

    panel["dispersion_bps"] = cross_venue_dispersion_bps(aligned)

    panel["past_24h_realized_vol"] = past_24h_realized_volatility(panel["research_composite"])

    panel["past_24h_realized_vol_pct"] = panel["past_24h_realized_vol"] * 100.0

    panel["log_past_24h_realized_vol"] = np.log(
        panel["past_24h_realized_vol"].where(panel["past_24h_realized_vol"] > 0.0)
    )

    panel["log1p_dispersion_bps"] = np.log1p(panel["dispersion_bps"])

    panel["subperiod"] = [subperiod_label(timestamp) for timestamp in panel.index]

    eligible = panel["past_24h_realized_vol"].notna() & np.isfinite(
        panel["log_past_24h_realized_vol"]
    )

    panel.loc[
        eligible,
        "volatility_quintile",
    ] = assign_quintiles(
        panel.loc[
            eligible,
            "past_24h_realized_vol",
        ]
    )

    panel["volatility_quintile"] = panel["volatility_quintile"].astype("Int64")

    return panel


def quintile_summary(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for quintile in range(
        1,
        6,
    ):
        sample = frame.loc[frame["volatility_quintile"] == quintile]

        if sample.empty:
            continue

        dispersion = sample["dispersion_bps"]

        volatility = sample["past_24h_realized_vol_pct"]

        rows.append(
            {
                "volatility_quintile": quintile,
                "observations": len(sample),
                "rv24_median_pct": float(volatility.median()),
                "rv24_p10_pct": percentile(
                    volatility,
                    0.10,
                ),
                "rv24_p90_pct": percentile(
                    volatility,
                    0.90,
                ),
                "dispersion_mean_bps": float(dispersion.mean()),
                "dispersion_median_bps": float(dispersion.median()),
                "dispersion_p90_bps": percentile(
                    dispersion,
                    0.90,
                ),
                "dispersion_p99_bps": percentile(
                    dispersion,
                    0.99,
                ),
                "share_ge_10bps": float((dispersion >= 10.0).mean()),
                "share_ge_25bps": float((dispersion >= 25.0).mean()),
                "share_ge_50bps": float((dispersion >= 50.0).mean()),
                "share_ge_100bps": float((dispersion >= 100.0).mean()),
            }
        )

    return pd.DataFrame(rows)


def subperiod_quintile_summary(
    panel: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for period in [
        "2017-2020",
        "2021-2023",
        "2024-2026",
    ]:
        sample = panel.loc[
            (panel["subperiod"] == period) & panel["past_24h_realized_vol"].notna()
        ].copy()

        if len(sample) < 100:
            continue

        sample["volatility_quintile"] = assign_quintiles(sample["past_24h_realized_vol"])

        summary = quintile_summary(sample)

        summary.insert(
            0,
            "subperiod",
            period,
        )

        rows.append(summary)

    if not rows:
        raise RuntimeError("No subperiod quintile summaries.")

    return pd.concat(
        rows,
        ignore_index=True,
    )


def sample_correlation_row(
    label: str,
    sample: pd.DataFrame,
) -> dict[str, Any]:
    eligible = sample.dropna(
        subset=[
            "dispersion_bps",
            "past_24h_realized_vol",
        ]
    )

    return {
        "sample": label,
        "observations": len(eligible),
        "spearman_dispersion_vs_past24h_rv": (
            spearman_correlation(
                eligible["dispersion_bps"],
                eligible["past_24h_realized_vol"],
            )
        ),
    }


def build_correlations(
    panel: pd.DataFrame,
) -> pd.DataFrame:
    rows = [
        sample_correlation_row(
            "full_sample",
            panel,
        )
    ]

    for period in [
        "2017-2020",
        "2021-2023",
        "2024-2026",
    ]:
        sample = panel.loc[panel["subperiod"] == period]

        rows.append(
            sample_correlation_row(
                period,
                sample,
            )
        )

    return pd.DataFrame(rows)


def regression_rows_for_sample(
    label: str,
    sample: pd.DataFrame,
) -> list[dict[str, Any]]:
    eligible = sample.dropna(
        subset=[
            "dispersion_bps",
            "log1p_dispersion_bps",
            "log_past_24h_realized_vol",
        ]
    )

    raw = newey_west_regression(
        y=eligible["dispersion_bps"],
        x=eligible["log_past_24h_realized_vol"],
        lags=HAC_LAGS,
    )

    transformed = newey_west_regression(
        y=eligible["log1p_dispersion_bps"],
        x=eligible["log_past_24h_realized_vol"],
        lags=HAC_LAGS,
    )

    return [
        {
            "sample": label,
            "specification": ("dispersion_bps_on_log_rv24"),
            **raw,
        },
        {
            "sample": label,
            "specification": ("log1p_dispersion_bps_on_log_rv24"),
            **transformed,
        },
    ]


def build_regressions(
    panel: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    rows.extend(
        regression_rows_for_sample(
            "full_sample",
            panel,
        )
    )

    for period in [
        "2017-2020",
        "2021-2023",
        "2024-2026",
    ]:
        sample = panel.loc[panel["subperiod"] == period]

        rows.extend(
            regression_rows_for_sample(
                period,
                sample,
            )
        )

    return pd.DataFrame(rows)


def monotonic_steps(
    summary: pd.DataFrame,
) -> int:
    ordered = summary.sort_values("volatility_quintile")["dispersion_median_bps"].to_numpy(
        dtype=float
    )

    if len(ordered) != 5:
        raise ValueError("Expected five quintiles.")

    return int(np.sum(np.diff(ordered) > 0.0))


def sensitivity_row(
    label: str,
    sample: pd.DataFrame,
) -> dict[str, Any]:
    eligible = sample.dropna(
        subset=[
            "dispersion_bps",
            "past_24h_realized_vol",
        ]
    ).copy()

    correlation = spearman_correlation(
        eligible["dispersion_bps"],
        eligible["past_24h_realized_vol"],
    )

    eligible["volatility_quintile"] = assign_quintiles(eligible["past_24h_realized_vol"])

    q_summary = quintile_summary(eligible)

    q1 = float(
        q_summary.loc[
            q_summary["volatility_quintile"] == 1,
            "dispersion_median_bps",
        ].iloc[0]
    )

    q5 = float(
        q_summary.loc[
            q_summary["volatility_quintile"] == 5,
            "dispersion_median_bps",
        ].iloc[0]
    )

    return {
        "sample": label,
        "observations": len(eligible),
        "spearman": correlation,
        "q1_median_dispersion_bps": q1,
        "q5_median_dispersion_bps": q5,
        "q5_to_q1_median_ratio": (q5 / q1 if q1 > 0.0 else None),
        "positive_adjacent_quintile_steps": (monotonic_steps(q_summary)),
    }


def build_sensitivity(
    panel: pd.DataFrame,
) -> pd.DataFrame:
    eligible = panel.dropna(
        subset=[
            "dispersion_bps",
            "past_24h_realized_vol",
        ]
    ).copy()

    upper_cutoff = float(eligible["dispersion_bps"].quantile(0.999))

    trimmed = eligible.loc[eligible["dispersion_bps"] <= upper_cutoff]

    post_2017 = eligible.loc[eligible.index >= pd.Timestamp("2018-01-01T00:00:00Z")]

    recent = eligible.loc[eligible.index >= pd.Timestamp("2024-01-01T00:00:00Z")]

    rows = [
        sensitivity_row(
            "full_sample",
            eligible,
        ),
        sensitivity_row(
            "exclude_top_0.1pct_dispersion",
            trimmed,
        ),
        sensitivity_row(
            "from_2018",
            post_2017,
        ),
        sensitivity_row(
            "2024-2026",
            recent,
        ),
    ]

    return pd.DataFrame(rows)


def main() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    panel = build_panel()

    eligible = panel.dropna(
        subset=[
            "dispersion_bps",
            "past_24h_realized_vol",
            "log_past_24h_realized_vol",
        ]
    ).copy()

    if len(eligible) < 70_000:
        raise RuntimeError("Eligible volatility sample unexpectedly small.")

    full_quintiles = quintile_summary(eligible)

    subperiod_quintiles = subperiod_quintile_summary(eligible)

    correlations = build_correlations(eligible)

    regressions = build_regressions(eligible)

    sensitivity = build_sensitivity(eligible)

    panel.to_csv(
        PANEL_PATH,
        compression="gzip",
        float_format="%.12g",
        date_format="%Y-%m-%dT%H:%M:%SZ",
    )

    full_quintiles.to_csv(
        QUINTILE_PATH,
        index=False,
        float_format="%.10f",
    )

    subperiod_quintiles.to_csv(
        SUBPERIOD_QUINTILE_PATH,
        index=False,
        float_format="%.10f",
    )

    correlations.to_csv(
        CORRELATION_PATH,
        index=False,
        float_format="%.10f",
    )

    regressions.to_csv(
        REGRESSION_PATH,
        index=False,
        float_format="%.10f",
    )

    sensitivity.to_csv(
        SENSITIVITY_PATH,
        index=False,
        float_format="%.10f",
    )

    full_spearman = float(
        correlations.loc[
            correlations["sample"] == "full_sample",
            "spearman_dispersion_vs_past24h_rv",
        ].iloc[0]
    )

    recent_spearman = float(
        correlations.loc[
            correlations["sample"] == "2024-2026",
            "spearman_dispersion_vs_past24h_rv",
        ].iloc[0]
    )

    q1_median = float(
        full_quintiles.loc[
            full_quintiles["volatility_quintile"] == 1,
            "dispersion_median_bps",
        ].iloc[0]
    )

    q5_median = float(
        full_quintiles.loc[
            full_quintiles["volatility_quintile"] == 5,
            "dispersion_median_bps",
        ].iloc[0]
    )

    transformed_full = regressions.loc[
        (regressions["sample"] == "full_sample")
        & (regressions["specification"] == "log1p_dispersion_bps_on_log_rv24")
    ].iloc[0]

    summary_core = {
        "study_id": ("HILMARCORP-BTC-PRICE-REFERENCE"),
        "stage": ("VOLATILITY_DISPERSION_RELATIONSHIP"),
        "volatility_definition": (
            "Square root of the sum of squared hourly log returns "
            "over the 24 strictly preceding observations of the "
            "Coinbase-Bitstamp research composite."
        ),
        "lookahead_control": (
            "The hourly return ending in the current dispersion "
            "bucket is excluded from the volatility estimate."
        ),
        "eligible_observations": len(eligible),
        "first_eligible_timestamp": (eligible.index[0].isoformat()),
        "last_eligible_timestamp": (eligible.index[-1].isoformat()),
        "full_sample_spearman": (full_spearman),
        "recent_2024_2026_spearman": (recent_spearman),
        "full_sample_quintile_medians_bps": {
            str(int(row["volatility_quintile"])): float(row["dispersion_median_bps"])
            for _, row in full_quintiles.iterrows()
        },
        "full_sample_q5_to_q1_median_ratio": (q5_median / q1_median if q1_median > 0.0 else None),
        "full_sample_positive_adjacent_quintile_steps": (monotonic_steps(full_quintiles)),
        "newey_west_log_specification": {
            "slope": float(transformed_full["slope"]),
            "hac_standard_error": float(transformed_full["slope_hac_se"]),
            "hac_t_statistic": float(transformed_full["slope_hac_t"]),
            "normal_approximation_p_value": float(transformed_full["slope_normal_p_value"]),
            "r_squared": float(transformed_full["r_squared"]),
            "hac_lags": int(transformed_full["hac_lags"]),
        },
        "interpretation_limits": [
            (
                "The analysis is descriptive and does not establish "
                "that volatility causes venue dispersion."
            ),
            (
                "Realized volatility is measured from the prior "
                "24 hours only to prevent contemporaneous leakage."
            ),
            ("Hourly venue closes are not perfectly synchronized executable prices."),
            ("The historical relationship can vary materially across subperiods."),
            ("Statistical significance must not be interpreted as economic predictability."),
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
        QUINTILE_PATH,
        SUBPERIOD_QUINTILE_PATH,
        CORRELATION_PATH,
        REGRESSION_PATH,
        SENSITIVITY_PATH,
        SUMMARY_PATH,
    ]

    manifest = {
        "study_id": ("HILMARCORP-BTC-PRICE-REFERENCE"),
        "stage": ("VOLATILITY_DISPERSION_RELATIONSHIP"),
        "artifacts": [
            {
                "path": str(path),
                "sha256": (sha256_file(path)),
                "size_bytes": (path.stat().st_size),
            }
            for path in controlled
        ],
        "local_uncommitted_artifact": {
            "path": str(PANEL_PATH),
            "sha256": (sha256_file(PANEL_PATH)),
            "size_bytes": (PANEL_PATH.stat().st_size),
        },
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

    print("VOLATILITY x VENUE DISPERSION")

    print("=" * 78)

    print(
        "Eligible observations:",
        len(eligible),
    )

    print(
        "Full-sample Spearman:",
        f"{full_spearman:.6f}",
    )

    print(
        "2024-2026 Spearman:",
        f"{recent_spearman:.6f}",
    )

    print()
    print("VOLATILITY QUINTILES")

    print(full_quintiles.to_string(index=False))

    print()
    print(
        "Q5 / Q1 median dispersion:",
        f"{q5_median / q1_median:.4f}x",
    )

    print(
        "Positive adjacent quintile steps:",
        f"{monotonic_steps(full_quintiles)}/4",
    )

    print()
    print("SPEARMAN BY SUBPERIOD")

    print(correlations.to_string(index=False))

    print()
    print("NEWEY-WEST REGRESSIONS")

    print(regressions.to_string(index=False))

    print()
    print("SENSITIVITY")

    print(sensitivity.to_string(index=False))

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
