from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

COINBASE_PATH = Path("data/cache/coinbase_btcusd_1h_2017-08-17_2026-08-10.csv.gz")

BITSTAMP_PATH = Path("data/cache/bitstamp_btcusd_1h_2017-08-17_2026-08-10.csv.gz")

OUTPUT_DIR = Path("artifacts/extreme_gap_validation")

EXTREMES_PATH = OUTPUT_DIR / "extreme_hourly_events.csv"
VALIDATION_PATH = OUTPUT_DIR / "minute_validation.csv.gz"
SUBPERIOD_PATH = OUTPUT_DIR / "subperiod_summary.csv"
MISSING_PATH = OUTPUT_DIR / "missing_coinbase_hours.csv"
SUMMARY_PATH = OUTPUT_DIR / "validation_summary.json"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "HilmarCorp-Research/1.0",
}

TIMEOUT = 30
MAX_ATTEMPTS = 5
BPS = 10_000.0


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def request_json(
    url: str,
    params: dict[str, Any],
) -> Any:
    last_error: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(
                url,
                params=params,
                headers=HEADERS,
                timeout=TIMEOUT,
            )

            if response.status_code == 429 or 500 <= response.status_code < 600:
                if attempt == MAX_ATTEMPTS:
                    response.raise_for_status()

                time.sleep(
                    min(
                        30.0,
                        2.0 ** (attempt - 1),
                    )
                )
                continue

            response.raise_for_status()

            return response.json()

        except (requests.RequestException, ValueError) as exc:
            last_error = exc

            if attempt < MAX_ATTEMPTS:
                time.sleep(
                    min(
                        30.0,
                        2.0 ** (attempt - 1),
                    )
                )

    raise RuntimeError(f"Request failed after {MAX_ATTEMPTS} attempts.") from last_error


def load_close(
    path: Path,
    name: str,
) -> pd.Series:
    frame = pd.read_csv(
        path,
        parse_dates=["timestamp"],
    )

    if "timestamp" not in frame.columns or "close" not in frame.columns:
        raise ValueError(f"{name}: timestamp/close missing")

    frame["timestamp"] = pd.to_datetime(
        frame["timestamp"],
        utc=True,
    )

    if frame["timestamp"].duplicated().any():
        raise ValueError(f"{name}: duplicated timestamps")

    frame = frame.sort_values("timestamp")

    close = frame.set_index("timestamp")["close"].astype(float)

    values = close.to_numpy()

    if not np.isfinite(values).all():
        raise ValueError(f"{name}: non-finite close")

    if (values <= 0).any():
        raise ValueError(f"{name}: non-positive close")

    close.name = name

    return close


def dispersion_bps(
    prices: list[float],
) -> float:
    values = np.asarray(
        prices,
        dtype=float,
    )

    if len(values) < 2:
        raise ValueError("At least two prices required.")

    if not np.isfinite(values).all():
        raise ValueError("Prices must be finite.")

    if (values <= 0).any():
        raise ValueError("Prices must be positive.")

    median = float(np.median(values))

    return float((values.max() - values.min()) / median * BPS)


def absolute_pairwise_bps(
    first: float,
    second: float,
) -> float:
    if not np.isfinite(first) or not np.isfinite(second) or first <= 0 or second <= 0:
        raise ValueError("Pairwise prices invalid.")

    return abs(first / second - 1.0) * BPS


def subperiod_label(
    timestamp: pd.Timestamp,
) -> str:
    year = timestamp.year

    if year <= 2020:
        return "2017-2020"

    if year <= 2023:
        return "2021-2023"

    return "2024-2026"


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


def fetch_coinbase_minute(
    minute_start: pd.Timestamp,
) -> dict[str, Any]:
    endpoint = "https://api.exchange.coinbase.com/products/BTC-USD/candles"

    minute_end = minute_start + pd.Timedelta(minutes=1)

    payload = request_json(
        endpoint,
        {
            "granularity": 60,
            "start": minute_start.isoformat(),
            "end": minute_end.isoformat(),
        },
    )

    if not isinstance(payload, list):
        raise TypeError("Coinbase minute payload not a list.")

    target = int(minute_start.timestamp())

    matches = [
        row
        for row in payload
        if (isinstance(row, list) and len(row) >= 6 and int(row[0]) == target)
    ]

    if len(matches) != 1:
        return {
            "close": None,
            "observation_count": len(matches),
            "response_sha256": canonical_sha256(payload),
            "error": (
                f"Expected exactly one exact Coinbase minute candle, received {len(matches)}."
            ),
        }

    close = float(matches[0][4])

    if not np.isfinite(close) or close <= 0:
        raise ValueError("Invalid Coinbase minute close.")

    return {
        "close": close,
        "observation_count": 1,
        "response_sha256": canonical_sha256(payload),
        "error": None,
    }


def fetch_bitstamp_minute(
    minute_start: pd.Timestamp,
) -> dict[str, Any]:
    endpoint = "https://www.bitstamp.net/api/v2/ohlc/btcusd/"

    minute_end = minute_start + pd.Timedelta(minutes=1)

    payload = request_json(
        endpoint,
        {
            "step": 60,
            "limit": 10,
            "start": int(minute_start.timestamp()),
            "end": int(minute_end.timestamp()) - 1,
            "exclude_current_candle": "true",
        },
    )

    rows = payload.get(
        "data",
        {},
    ).get(
        "ohlc",
        [],
    )

    if not isinstance(rows, list):
        raise TypeError("Bitstamp minute payload not a list.")

    target = int(minute_start.timestamp())

    matches = [row for row in rows if (isinstance(row, dict) and int(row["timestamp"]) == target)]

    if len(matches) != 1:
        return {
            "close": None,
            "observation_count": len(matches),
            "response_sha256": canonical_sha256(payload),
            "error": (
                f"Expected exactly one exact Bitstamp minute candle, received {len(matches)}."
            ),
        }

    close = float(matches[0]["close"])

    if not np.isfinite(close) or close <= 0:
        raise ValueError("Invalid Bitstamp minute close.")

    return {
        "close": close,
        "observation_count": 1,
        "response_sha256": canonical_sha256(payload),
        "error": None,
    }


def fetch_kraken_last_trade(
    minute_start: pd.Timestamp,
) -> dict[str, Any]:
    endpoint = "https://api.kraken.com/0/public/PostTrade"

    minute_end = minute_start + pd.Timedelta(minutes=1)

    from_time = minute_start - pd.Timedelta(microseconds=1)

    to_time = minute_end - pd.Timedelta(microseconds=1)

    cursor = from_time.isoformat().replace(
        "+00:00",
        "Z",
    )

    to_iso = to_time.isoformat().replace(
        "+00:00",
        "Z",
    )

    trades_by_id: dict[
        str,
        dict[str, Any],
    ] = {}

    page_hashes: list[str] = []

    for _ in range(30):
        payload = request_json(
            endpoint,
            {
                "symbol": "BTC/USD",
                "from_ts": cursor,
                "to_ts": to_iso,
                "count": 1000,
            },
        )

        page_hashes.append(canonical_sha256(payload))

        errors = payload.get(
            "error",
            [],
        )

        if errors:
            raise RuntimeError(f"Kraken errors: {errors}")

        result = payload.get(
            "result",
            {},
        )

        rows = result.get(
            "trades",
            [],
        )

        if not isinstance(
            rows,
            list,
        ):
            raise TypeError("Kraken trades not a list.")

        for trade in rows:
            if not isinstance(
                trade,
                dict,
            ):
                continue

            trade_id = trade.get("trade_id")

            if trade_id is None:
                continue

            trades_by_id[str(trade_id)] = trade

        if len(rows) < 1000:
            break

        last_ts = result.get("last_ts")

        if not last_ts:
            raise RuntimeError("Kraken pagination missing last_ts.")

        if last_ts == cursor:
            raise RuntimeError("Kraken pagination did not advance.")

        if pd.Timestamp(last_ts) >= to_time:
            break

        cursor = last_ts

    else:
        raise RuntimeError("Kraken pagination safety limit exceeded.")

    parsed: list[
        tuple[
            pd.Timestamp,
            float,
        ]
    ] = []

    for trade in trades_by_id.values():
        timestamp_raw = trade.get("trade_ts")

        price_raw = trade.get("price")

        if timestamp_raw is None or price_raw is None:
            continue

        timestamp = pd.Timestamp(timestamp_raw)

        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize("UTC")
        else:
            timestamp = timestamp.tz_convert("UTC")

        if not (minute_start <= timestamp < minute_end):
            continue

        price = float(price_raw)

        if not np.isfinite(price) or price <= 0:
            raise ValueError("Invalid Kraken trade price.")

        parsed.append(
            (
                timestamp,
                price,
            )
        )

    parsed.sort(key=lambda item: item[0])

    if not parsed:
        return {
            "last_trade": None,
            "trade_count": 0,
            "last_trade_timestamp": None,
            "response_sha256": canonical_sha256(page_hashes),
            "error": ("No Kraken BTC/USD trade inside exact validation minute."),
        }

    last_timestamp, last_price = parsed[-1]

    return {
        "last_trade": last_price,
        "trade_count": len(parsed),
        "last_trade_timestamp": (last_timestamp.isoformat()),
        "response_sha256": canonical_sha256(page_hashes),
        "error": None,
    }


def build_hourly_frame() -> tuple[
    pd.DataFrame,
    pd.DatetimeIndex,
]:
    coinbase = load_close(
        COINBASE_PATH,
        "Coinbase",
    )

    bitstamp = load_close(
        BITSTAMP_PATH,
        "Bitstamp",
    )

    missing_coinbase = bitstamp.index.difference(coinbase.index)

    aligned = pd.concat(
        [
            coinbase,
            bitstamp,
        ],
        axis=1,
        join="inner",
    ).dropna()

    if aligned.empty:
        raise RuntimeError("No common hourly observations.")

    aligned["absolute_pairwise_gap_bps"] = aligned.apply(
        lambda row: absolute_pairwise_bps(
            float(row["Coinbase"]),
            float(row["Bitstamp"]),
        ),
        axis=1,
    )

    aligned["dispersion_bps"] = aligned.apply(
        lambda row: dispersion_bps(
            [
                float(row["Coinbase"]),
                float(row["Bitstamp"]),
            ]
        ),
        axis=1,
    )

    aligned["subperiod"] = [subperiod_label(timestamp) for timestamp in aligned.index]

    return (
        aligned,
        missing_coinbase,
    )


def build_subperiod_summary(
    aligned: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for period in [
        "2017-2020",
        "2021-2023",
        "2024-2026",
    ]:
        sample = aligned.loc[
            aligned["subperiod"] == period,
            "dispersion_bps",
        ]

        if sample.empty:
            continue

        rows.append(
            {
                "subperiod": period,
                "hours": len(sample),
                "mean_bps": float(sample.mean()),
                "median_bps": float(sample.median()),
                "p90_bps": percentile(
                    sample,
                    0.90,
                ),
                "p95_bps": percentile(
                    sample,
                    0.95,
                ),
                "p99_bps": percentile(
                    sample,
                    0.99,
                ),
                "p999_bps": percentile(
                    sample,
                    0.999,
                ),
                "max_bps": float(sample.max()),
                "share_ge_10bps": float((sample >= 10.0).mean()),
                "share_ge_25bps": float((sample >= 25.0).mean()),
                "share_ge_50bps": float((sample >= 50.0).mean()),
                "share_ge_100bps": float((sample >= 100.0).mean()),
                "share_ge_250bps": float((sample >= 250.0).mean()),
                "share_ge_500bps": float((sample >= 500.0).mean()),
            }
        )

    return pd.DataFrame(rows)


def validate_extreme_event(
    timestamp: pd.Timestamp,
    hourly_row: pd.Series,
) -> dict[str, Any]:
    minute_start = timestamp + pd.Timedelta(minutes=59)

    record: dict[
        str,
        Any,
    ] = {
        "hour_start_utc": (timestamp.isoformat()),
        "validation_minute_start_utc": (minute_start.isoformat()),
        "hourly_coinbase_close": float(hourly_row["Coinbase"]),
        "hourly_bitstamp_close": float(hourly_row["Bitstamp"]),
        "hourly_absolute_pairwise_gap_bps": float(hourly_row["absolute_pairwise_gap_bps"]),
        "hourly_dispersion_bps": float(hourly_row["dispersion_bps"]),
        "subperiod": hourly_row["subperiod"],
    }

    try:
        coinbase = fetch_coinbase_minute(minute_start)
    except Exception as exc:
        coinbase = {
            "close": None,
            "observation_count": 0,
            "response_sha256": None,
            "error": (f"{type(exc).__name__}: {exc}"),
        }

    try:
        bitstamp = fetch_bitstamp_minute(minute_start)
    except Exception as exc:
        bitstamp = {
            "close": None,
            "observation_count": 0,
            "response_sha256": None,
            "error": (f"{type(exc).__name__}: {exc}"),
        }

    try:
        kraken = fetch_kraken_last_trade(minute_start)
    except Exception as exc:
        kraken = {
            "last_trade": None,
            "trade_count": 0,
            "last_trade_timestamp": None,
            "response_sha256": None,
            "error": (f"{type(exc).__name__}: {exc}"),
        }

    record.update(
        {
            "coinbase_1m_close": (coinbase["close"]),
            "coinbase_1m_count": (coinbase["observation_count"]),
            "coinbase_response_sha256": (coinbase["response_sha256"]),
            "coinbase_error": (coinbase["error"]),
            "bitstamp_1m_close": (bitstamp["close"]),
            "bitstamp_1m_count": (bitstamp["observation_count"]),
            "bitstamp_response_sha256": (bitstamp["response_sha256"]),
            "bitstamp_error": (bitstamp["error"]),
            "kraken_last_trade": (kraken["last_trade"]),
            "kraken_trade_count": (kraken["trade_count"]),
            "kraken_last_trade_timestamp": (kraken["last_trade_timestamp"]),
            "kraken_response_sha256": (kraken["response_sha256"]),
            "kraken_error": (kraken["error"]),
        }
    )

    cb = record["coinbase_1m_close"]
    bs = record["bitstamp_1m_close"]
    kr = record["kraken_last_trade"]

    record["minute_two_source_gap_bps"] = None

    record["minute_two_source_dispersion_bps"] = None

    record["minute_three_source_dispersion_bps"] = None

    record["minute_source_count"] = sum(
        price is not None
        for price in [
            cb,
            bs,
            kr,
        ]
    )

    if cb is not None and bs is not None:
        record["minute_two_source_gap_bps"] = absolute_pairwise_bps(
            float(cb),
            float(bs),
        )

        record["minute_two_source_dispersion_bps"] = dispersion_bps(
            [
                float(cb),
                float(bs),
            ]
        )

    if cb is not None and bs is not None and kr is not None:
        record["minute_three_source_dispersion_bps"] = dispersion_bps(
            [
                float(cb),
                float(bs),
                float(kr),
            ]
        )

    if record["minute_two_source_dispersion_bps"] is not None:
        record["two_source_revalidation_ratio"] = (
            record["minute_two_source_dispersion_bps"] / record["hourly_dispersion_bps"]
        )
    else:
        record["two_source_revalidation_ratio"] = None

    return record


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--top",
        type=int,
        default=40,
    )

    args = parser.parse_args()

    if args.top <= 0:
        raise ValueError("--top must be positive.")

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    aligned, missing_coinbase = build_hourly_frame()

    missing_frame = pd.DataFrame({"timestamp_utc": (missing_coinbase)})

    missing_frame.to_csv(
        MISSING_PATH,
        index=False,
        date_format=("%Y-%m-%dT%H:%M:%SZ"),
    )

    subperiod = build_subperiod_summary(aligned)

    subperiod.to_csv(
        SUBPERIOD_PATH,
        index=False,
        float_format="%.10f",
    )

    extremes = (
        aligned.sort_values(
            "dispersion_bps",
            ascending=False,
        )
        .head(args.top)
        .copy()
    )

    extreme_export = extremes.reset_index().rename(columns={"timestamp": ("hour_start_utc")})

    if "hour_start_utc" not in extreme_export.columns:
        extreme_export = extreme_export.rename(
            columns={extreme_export.columns[0]: ("hour_start_utc")}
        )

    extreme_export.to_csv(
        EXTREMES_PATH,
        index=False,
        float_format="%.10f",
        date_format=("%Y-%m-%dT%H:%M:%SZ"),
    )

    validation_rows: list[dict[str, Any]] = []

    for position, (
        timestamp,
        row,
    ) in enumerate(
        extremes.iterrows(),
        start=1,
    ):
        print(
            f"VALIDATING {position}/{len(extremes)} "
            f"{timestamp.isoformat()} "
            f"hourly_dispersion="
            f"{row['dispersion_bps']:.4f}bps"
        )

        validation_rows.append(
            validate_extreme_event(
                timestamp,
                row,
            )
        )

        time.sleep(0.10)

    validation = pd.DataFrame(validation_rows)

    validation.to_csv(
        VALIDATION_PATH,
        index=False,
        compression="gzip",
        float_format="%.12g",
    )

    all_three = validation.loc[validation["minute_three_source_dispersion_bps"].notna()]

    two_source = validation.loc[validation["minute_two_source_dispersion_bps"].notna()]

    ratios = validation.loc[
        validation["two_source_revalidation_ratio"].notna(),
        "two_source_revalidation_ratio",
    ]

    summary_core = {
        "study_id": ("HILMARCORP-BTC-PRICE-REFERENCE"),
        "stage": ("EXTREME_GAP_MINUTE_REVALIDATION"),
        "hourly_observations": len(aligned),
        "missing_coinbase_hours": len(missing_coinbase),
        "selected_extreme_events": len(extremes),
        "events_with_coinbase_bitstamp_minute_validation": len(two_source),
        "events_with_full_three_source_minute_validation": len(all_three),
        "selected_hourly_dispersion_bps": {
            "minimum": float(extremes["dispersion_bps"].min()),
            "median": float(extremes["dispersion_bps"].median()),
            "maximum": float(extremes["dispersion_bps"].max()),
        },
        "minute_two_source_dispersion_bps": (
            {
                "median": float(two_source["minute_two_source_dispersion_bps"].median()),
                "maximum": float(two_source["minute_two_source_dispersion_bps"].max()),
            }
            if not two_source.empty
            else None
        ),
        "minute_three_source_dispersion_bps": (
            {
                "median": float(all_three["minute_three_source_dispersion_bps"].median()),
                "p90": float(
                    np.quantile(
                        all_three["minute_three_source_dispersion_bps"],
                        0.90,
                    )
                ),
                "maximum": float(all_three["minute_three_source_dispersion_bps"].max()),
            }
            if not all_three.empty
            else None
        ),
        "two_source_revalidation_ratio": (
            {
                "median": float(ratios.median()),
                "p90": float(
                    np.quantile(
                        ratios,
                        0.90,
                    )
                ),
            }
            if not ratios.empty
            else None
        ),
        "interpretation": (
            "Extreme hourly candle-close dispersion is being "
            "revalidated using the final one-minute bucket on "
            "Coinbase and Bitstamp and exact Kraken BTC/USD trades "
            "inside the same minute. No result from this gate is "
            "treated as evidence of a persistent venue premium."
        ),
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
        EXTREMES_PATH,
        SUBPERIOD_PATH,
        MISSING_PATH,
        SUMMARY_PATH,
    ]

    manifest = {
        "study_id": ("HILMARCORP-BTC-PRICE-REFERENCE"),
        "stage": ("EXTREME_GAP_MINUTE_REVALIDATION"),
        "artifacts": [
            {
                "path": str(path),
                "sha256": (sha256_file(path)),
                "size_bytes": (path.stat().st_size),
            }
            for path in controlled
        ],
        "local_uncommitted_validation_artifact": {
            "path": str(VALIDATION_PATH),
            "sha256": (sha256_file(VALIDATION_PATH)),
            "size_bytes": (VALIDATION_PATH.stat().st_size),
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
    print("EXTREME GAP MINUTE REVALIDATION")
    print("=" * 76)

    print(
        "Hourly observations:",
        len(aligned),
    )

    print(
        "Missing Coinbase hours:",
        len(missing_coinbase),
    )

    print(
        "Extreme events tested:",
        len(extremes),
    )

    print(
        "2-source minute validations:",
        len(two_source),
    )

    print(
        "3-source minute validations:",
        len(all_three),
    )

    if not two_source.empty:
        print(
            "Median selected hourly dispersion:",
            f"{extremes['dispersion_bps'].median():.4f} bps",
        )

        print(
            "Median 1m Coinbase/Bitstamp dispersion:",
            f"{two_source['minute_two_source_dispersion_bps'].median():.4f} bps",
        )

    if not all_three.empty:
        print(
            "Median 1m three-source dispersion:",
            f"{all_three['minute_three_source_dispersion_bps'].median():.4f} bps",
        )

        print(
            "Maximum 1m three-source dispersion:",
            f"{all_three['minute_three_source_dispersion_bps'].max():.4f} bps",
        )

    if not ratios.empty:
        print(
            "Median 1m/hourly revalidation ratio:",
            f"{ratios.median():.6f}",
        )

    print()
    print("SUBPERIOD SUMMARY")

    print(subperiod.to_string(index=False))

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
