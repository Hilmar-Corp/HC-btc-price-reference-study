from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

START = pd.Timestamp("2017-08-17T00:00:00Z")
END = pd.Timestamp("2026-08-11T00:00:00Z")
STEP_SECONDS = 3600

COINBASE_OUTPUT = Path("data/cache/coinbase_btcusd_1h_2017-08-17_2026-08-10.csv.gz")

BITSTAMP_OUTPUT = Path("data/cache/bitstamp_btcusd_1h_2017-08-17_2026-08-10.csv.gz")

SUMMARY_OUTPUT = Path("artifacts/full_history_hourly/acquisition_summary.json")

MANIFEST_OUTPUT = Path("artifacts/full_history_hourly/data_manifest.json")

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "HilmarCorp-Research/1.0",
}

TIMEOUT = 30
MAX_ATTEMPTS = 5


@dataclass(frozen=True)
class SourceStats:
    source: str
    rows: int
    first_timestamp: str
    last_timestamp: str
    expected_hours: int
    missing_hours: int
    coverage_ratio: float
    duplicate_timestamps: int
    finite_values: bool
    positive_prices: bool
    valid_ohlc_relations: bool
    sha256: str


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

                time.sleep(min(30.0, 2.0 ** (attempt - 1)))
                continue

            response.raise_for_status()

            return response.json()

        except (requests.RequestException, ValueError) as exc:
            last_error = exc

            if attempt < MAX_ATTEMPTS:
                time.sleep(min(30.0, 2.0 ** (attempt - 1)))

    raise RuntimeError(f"Request failed after {MAX_ATTEMPTS} attempts.") from last_error


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def canonical_json_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def validate_ohlc(frame: pd.DataFrame) -> None:
    required = {
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    missing = required.difference(frame.columns)

    if missing:
        raise ValueError(f"Missing OHLC fields: {sorted(missing)}")

    if frame.empty:
        raise ValueError("OHLC frame is empty.")

    if frame["timestamp"].duplicated().any():
        duplicates = frame.loc[
            frame["timestamp"].duplicated(keep=False),
            "timestamp",
        ]

        raise ValueError(f"Duplicate timestamps detected: {duplicates.head(10).tolist()}")

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    values = frame[numeric_columns].to_numpy(dtype=float)

    if not np.isfinite(values).all():
        raise ValueError("Non-finite OHLC values detected.")

    prices = frame[
        [
            "open",
            "high",
            "low",
            "close",
        ]
    ].to_numpy(dtype=float)

    if (prices <= 0.0).any():
        raise ValueError("Non-positive price detected.")

    invalid = (
        (frame["low"] > frame["high"])
        | (frame["open"] < frame["low"])
        | (frame["open"] > frame["high"])
        | (frame["close"] < frame["low"])
        | (frame["close"] > frame["high"])
    )

    if invalid.any():
        raise ValueError("Invalid OHLC relationship detected.")

    if not frame["timestamp"].is_monotonic_increasing:
        raise ValueError("Timestamps are not chronologically sorted.")


def normalize_timestamp_column(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    result = frame.copy()

    result["timestamp"] = pd.to_datetime(
        result["timestamp"],
        utc=True,
    )

    result = result.sort_values(
        "timestamp",
        kind="stable",
    ).reset_index(drop=True)

    return result


def deduplicate_identical(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    if frame.empty:
        return frame

    columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    conflicts: list[pd.Timestamp] = []

    for timestamp, group in frame.groupby(
        "timestamp",
        sort=False,
    ):
        if len(group) <= 1:
            continue

        reference = group.iloc[0][columns].to_numpy(dtype=float)

        for _, row in group.iloc[1:].iterrows():
            candidate = row[columns].to_numpy(dtype=float)

            if not np.allclose(
                reference,
                candidate,
                rtol=0.0,
                atol=1e-12,
                equal_nan=False,
            ):
                conflicts.append(timestamp)
                break

    if conflicts:
        raise ValueError(f"Conflicting duplicated observations detected: {conflicts[:10]}")

    return (
        frame.drop_duplicates(
            subset=["timestamp"],
            keep="first",
        )
        .sort_values("timestamp")
        .reset_index(drop=True)
    )


def download_coinbase(
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    endpoint = "https://api.exchange.coinbase.com/products/BTC-USD/candles"

    frames: list[pd.DataFrame] = []

    cursor = start
    request_count = 0

    while cursor < end:
        chunk_end = min(
            cursor + pd.Timedelta(hours=240),
            end,
        )

        request_end = chunk_end - pd.Timedelta(seconds=1)

        payload = request_json(
            endpoint,
            {
                "granularity": STEP_SECONDS,
                "start": cursor.isoformat(),
                "end": request_end.isoformat(),
            },
        )

        request_count += 1

        if not isinstance(payload, list):
            raise TypeError("Coinbase response is not a list.")

        rows = []

        for item in payload:
            if not isinstance(item, list):
                continue

            if len(item) < 6:
                continue

            rows.append(
                {
                    "timestamp": pd.to_datetime(
                        int(item[0]),
                        unit="s",
                        utc=True,
                    ),
                    "low": float(item[1]),
                    "high": float(item[2]),
                    "open": float(item[3]),
                    "close": float(item[4]),
                    "volume": float(item[5]),
                }
            )

        if rows:
            chunk = pd.DataFrame(rows)

            chunk = chunk.loc[(chunk["timestamp"] >= cursor) & (chunk["timestamp"] < chunk_end)]

            frames.append(chunk)

        print(
            "COINBASE",
            request_count,
            cursor.isoformat(),
            "->",
            chunk_end.isoformat(),
            "rows=",
            len(rows),
        )

        cursor = chunk_end
        time.sleep(0.12)

    if not frames:
        raise RuntimeError("Coinbase acquisition returned no data.")

    result = pd.concat(
        frames,
        ignore_index=True,
    )

    result = normalize_timestamp_column(result)
    result = deduplicate_identical(result)

    result = result.loc[(result["timestamp"] >= start) & (result["timestamp"] < end)].reset_index(
        drop=True
    )

    validate_ohlc(result)

    return result


def download_bitstamp(
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    endpoint = "https://www.bitstamp.net/api/v2/ohlc/btcusd/"

    frames: list[pd.DataFrame] = []

    cursor = start
    request_count = 0

    while cursor < end:
        chunk_end = min(
            cursor + pd.Timedelta(hours=900),
            end,
        )

        expected = int((chunk_end - cursor) / pd.Timedelta(hours=1))

        limit = min(
            1000,
            expected + 4,
        )

        payload = request_json(
            endpoint,
            {
                "step": STEP_SECONDS,
                "limit": limit,
                "start": int(cursor.timestamp()),
                "end": int((chunk_end - pd.Timedelta(seconds=1)).timestamp()),
                "exclude_current_candle": "true",
            },
        )

        request_count += 1

        rows = payload.get("data", {}).get("ohlc", [])

        if not isinstance(rows, list):
            raise TypeError("Bitstamp OHLC response is not a list.")

        parsed = []

        for item in rows:
            if not isinstance(item, dict):
                continue

            parsed.append(
                {
                    "timestamp": pd.to_datetime(
                        int(item["timestamp"]),
                        unit="s",
                        utc=True,
                    ),
                    "open": float(item["open"]),
                    "high": float(item["high"]),
                    "low": float(item["low"]),
                    "close": float(item["close"]),
                    "volume": float(item["volume"]),
                }
            )

        if parsed:
            chunk = pd.DataFrame(parsed)

            chunk = chunk.loc[(chunk["timestamp"] >= cursor) & (chunk["timestamp"] < chunk_end)]

            frames.append(chunk)

        print(
            "BITSTAMP",
            request_count,
            cursor.isoformat(),
            "->",
            chunk_end.isoformat(),
            "raw=",
            len(rows),
            "kept=",
            len(parsed),
        )

        cursor = chunk_end
        time.sleep(0.12)

    if not frames:
        raise RuntimeError("Bitstamp acquisition returned no data.")

    result = pd.concat(
        frames,
        ignore_index=True,
    )

    result = normalize_timestamp_column(result)
    result = deduplicate_identical(result)

    result = result.loc[(result["timestamp"] >= start) & (result["timestamp"] < end)].reset_index(
        drop=True
    )

    validate_ohlc(result)

    return result


def source_stats(
    source: str,
    frame: pd.DataFrame,
    path: Path,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> SourceStats:
    expected_index = pd.date_range(
        start=start,
        end=end,
        freq="h",
        inclusive="left",
    )

    observed = pd.DatetimeIndex(frame["timestamp"])

    missing = expected_index.difference(observed)

    numeric = frame[
        [
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
    ].to_numpy(dtype=float)

    prices = frame[
        [
            "open",
            "high",
            "low",
            "close",
        ]
    ].to_numpy(dtype=float)

    relations = (
        (frame["low"] <= frame["high"])
        & (frame["open"] >= frame["low"])
        & (frame["open"] <= frame["high"])
        & (frame["close"] >= frame["low"])
        & (frame["close"] <= frame["high"])
    )

    return SourceStats(
        source=source,
        rows=len(frame),
        first_timestamp=(frame["timestamp"].iloc[0].isoformat()),
        last_timestamp=(frame["timestamp"].iloc[-1].isoformat()),
        expected_hours=len(expected_index),
        missing_hours=len(missing),
        coverage_ratio=(len(frame) / len(expected_index)),
        duplicate_timestamps=int(frame["timestamp"].duplicated().sum()),
        finite_values=bool(np.isfinite(numeric).all()),
        positive_prices=bool((prices > 0.0).all()),
        valid_ohlc_relations=bool(relations.all()),
        sha256=sha256_file(path),
    )


def write_frame(
    frame: pd.DataFrame,
    path: Path,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    frame.to_csv(
        path,
        index=False,
        compression="gzip",
        float_format="%.12g",
        date_format="%Y-%m-%dT%H:%M:%SZ",
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--refresh",
        action="store_true",
    )

    args = parser.parse_args()

    COINBASE_OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    SUMMARY_OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if COINBASE_OUTPUT.exists() and not args.refresh:
        print(
            "Using cached Coinbase:",
            COINBASE_OUTPUT,
        )

        coinbase = pd.read_csv(
            COINBASE_OUTPUT,
            parse_dates=["timestamp"],
        )

        coinbase = normalize_timestamp_column(coinbase)

        validate_ohlc(coinbase)

    else:
        coinbase = download_coinbase(
            START,
            END,
        )

        write_frame(
            coinbase,
            COINBASE_OUTPUT,
        )

    if BITSTAMP_OUTPUT.exists() and not args.refresh:
        print(
            "Using cached Bitstamp:",
            BITSTAMP_OUTPUT,
        )

        bitstamp = pd.read_csv(
            BITSTAMP_OUTPUT,
            parse_dates=["timestamp"],
        )

        bitstamp = normalize_timestamp_column(bitstamp)

        validate_ohlc(bitstamp)

    else:
        bitstamp = download_bitstamp(
            START,
            END,
        )

        write_frame(
            bitstamp,
            BITSTAMP_OUTPUT,
        )

    coinbase_stats = source_stats(
        "Coinbase BTC-USD",
        coinbase,
        COINBASE_OUTPUT,
        START,
        END,
    )

    bitstamp_stats = source_stats(
        "Bitstamp BTC/USD",
        bitstamp,
        BITSTAMP_OUTPUT,
        START,
        END,
    )

    expected_hours = len(
        pd.date_range(
            START,
            END,
            freq="h",
            inclusive="left",
        )
    )

    summary_core = {
        "study_id": ("HILMARCORP-BTC-PRICE-REFERENCE"),
        "stage": ("FULL_HISTORY_HOURLY_GATE"),
        "start_utc": START.isoformat(),
        "end_utc_exclusive": END.isoformat(),
        "expected_hours": expected_hours,
        "sources": [
            coinbase_stats.__dict__,
            bitstamp_stats.__dict__,
        ],
    }

    summary = {
        **summary_core,
        "generated_at_utc": (datetime.now(UTC).isoformat()),
        "summary_sha256": (canonical_json_sha256(summary_core)),
    }

    SUMMARY_OUTPUT.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    manifest = {
        "study_id": ("HILMARCORP-BTC-PRICE-REFERENCE"),
        "artifacts": [
            {
                "path": str(COINBASE_OUTPUT),
                "sha256": sha256_file(COINBASE_OUTPUT),
                "size_bytes": (COINBASE_OUTPUT.stat().st_size),
            },
            {
                "path": str(BITSTAMP_OUTPUT),
                "sha256": sha256_file(BITSTAMP_OUTPUT),
                "size_bytes": (BITSTAMP_OUTPUT.stat().st_size),
            },
            {
                "path": str(SUMMARY_OUTPUT),
                "sha256": sha256_file(SUMMARY_OUTPUT),
                "size_bytes": (SUMMARY_OUTPUT.stat().st_size),
            },
        ],
    }

    MANIFEST_OUTPUT.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    print()
    print("FULL HISTORY HOURLY ACQUISITION")
    print("=" * 72)

    for stats in [
        coinbase_stats,
        bitstamp_stats,
    ]:
        print(
            stats.source,
            "rows=",
            stats.rows,
            "missing=",
            stats.missing_hours,
            "coverage=",
            f"{stats.coverage_ratio:.8%}",
        )

    print(
        "Summary:",
        SUMMARY_OUTPUT,
    )

    print(
        "Manifest:",
        MANIFEST_OUTPUT,
    )


if __name__ == "__main__":
    main()
