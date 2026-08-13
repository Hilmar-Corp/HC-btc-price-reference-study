from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

OUTPUT_DIR = Path("artifacts/source_audit")
OUTPUT_PATH = OUTPUT_DIR / "source_capability_probe.json"

TIMEOUT_SECONDS = 30
MAX_ATTEMPTS = 4

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "HilmarCorp-Research/1.0",
}

PROBE_WINDOWS = {
    "historical": (
        "2017-08-17T12:00:00Z",
        "2017-08-17T12:10:00Z",
    ),
    "recent": (
        "2026-08-10T12:00:00Z",
        "2026-08-10T12:10:00Z",
    ),
}


@dataclass(frozen=True)
class ProbeResult:
    source: str
    market: str
    probe_name: str
    requested_start: str
    requested_end: str
    http_status: int | None
    raw_observation_count: int
    in_window_observation_count: int
    earliest_in_window_observation: str | None
    latest_in_window_observation: str | None
    response_sha256: str | None
    capability_passed: bool
    error: str | None


def parse_iso8601(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def unix_seconds(value: str) -> int:
    return int(parse_iso8601(value).timestamp())


def iso_from_unix(value: int | float | str) -> str:
    return datetime.fromtimestamp(float(value), tz=UTC).isoformat().replace("+00:00", "Z")


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def request_json(
    url: str,
    params: dict[str, Any],
) -> tuple[int, Any]:
    last_error: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(
                url,
                params=params,
                headers=HEADERS,
                timeout=TIMEOUT_SECONDS,
            )

            if response.status_code == 429 or 500 <= response.status_code < 600:
                if attempt == MAX_ATTEMPTS:
                    response.raise_for_status()

                time.sleep(2 ** (attempt - 1))
                continue

            response.raise_for_status()

            return response.status_code, response.json()

        except (requests.RequestException, ValueError) as exc:
            last_error = exc

            if attempt < MAX_ATTEMPTS:
                time.sleep(2 ** (attempt - 1))

    raise RuntimeError(f"Request failed after {MAX_ATTEMPTS} attempts.") from last_error


def filter_unix_window(
    timestamps: list[int],
    start: str,
    end: str,
) -> list[int]:
    start_ts = unix_seconds(start)
    end_ts = unix_seconds(end)

    return sorted(timestamp for timestamp in timestamps if start_ts <= timestamp <= end_ts)


def filter_datetime_window(
    timestamps: list[datetime],
    start: str,
    end: str,
) -> list[datetime]:
    start_dt = parse_iso8601(start)
    end_dt = parse_iso8601(end)

    return sorted(timestamp for timestamp in timestamps if start_dt <= timestamp <= end_dt)


def failed_result(
    source: str,
    market: str,
    probe_name: str,
    start: str,
    end: str,
    exc: Exception,
) -> ProbeResult:
    return ProbeResult(
        source=source,
        market=market,
        probe_name=probe_name,
        requested_start=start,
        requested_end=end,
        http_status=None,
        raw_observation_count=0,
        in_window_observation_count=0,
        earliest_in_window_observation=None,
        latest_in_window_observation=None,
        response_sha256=None,
        capability_passed=False,
        error=f"{type(exc).__name__}: {exc}",
    )


def probe_coinbase(
    probe_name: str,
    start: str,
    end: str,
) -> ProbeResult:
    source = "Coinbase"
    market = "BTC-USD"

    try:
        status, payload = request_json(
            "https://api.exchange.coinbase.com/products/BTC-USD/candles",
            {
                "granularity": 60,
                "start": start,
                "end": end,
            },
        )

        if not isinstance(payload, list):
            raise TypeError("Coinbase payload is not a list.")

        raw_timestamps = [int(row[0]) for row in payload if isinstance(row, list) and len(row) >= 5]

        filtered = filter_unix_window(raw_timestamps, start, end)

        return ProbeResult(
            source=source,
            market=market,
            probe_name=probe_name,
            requested_start=start,
            requested_end=end,
            http_status=status,
            raw_observation_count=len(raw_timestamps),
            in_window_observation_count=len(filtered),
            earliest_in_window_observation=(iso_from_unix(filtered[0]) if filtered else None),
            latest_in_window_observation=(iso_from_unix(filtered[-1]) if filtered else None),
            response_sha256=canonical_sha256(payload),
            capability_passed=len(filtered) > 0,
            error=None,
        )

    except Exception as exc:
        return failed_result(
            source,
            market,
            probe_name,
            start,
            end,
            exc,
        )


def probe_bitstamp(
    probe_name: str,
    start: str,
    end: str,
) -> ProbeResult:
    source = "Bitstamp"
    market = "BTC/USD"

    try:
        status, payload = request_json(
            "https://www.bitstamp.net/api/v2/ohlc/btcusd/",
            {
                "step": 60,
                "limit": 20,
                "start": unix_seconds(start),
                "end": unix_seconds(end),
                "exclude_current_candle": "true",
            },
        )

        rows = payload.get("data", {}).get("ohlc", [])

        if not isinstance(rows, list):
            raise TypeError("Bitstamp OHLC payload is not a list.")

        raw_timestamps = [
            int(row["timestamp"]) for row in rows if isinstance(row, dict) and "timestamp" in row
        ]

        filtered = filter_unix_window(raw_timestamps, start, end)

        return ProbeResult(
            source=source,
            market=market,
            probe_name=probe_name,
            requested_start=start,
            requested_end=end,
            http_status=status,
            raw_observation_count=len(raw_timestamps),
            in_window_observation_count=len(filtered),
            earliest_in_window_observation=(iso_from_unix(filtered[0]) if filtered else None),
            latest_in_window_observation=(iso_from_unix(filtered[-1]) if filtered else None),
            response_sha256=canonical_sha256(payload),
            capability_passed=len(filtered) > 0,
            error=None,
        )

    except Exception as exc:
        return failed_result(
            source,
            market,
            probe_name,
            start,
            end,
            exc,
        )


def probe_kraken(
    probe_name: str,
    start: str,
    end: str,
) -> ProbeResult:
    source = "Kraken"
    market = "BTC/USD"

    try:
        status, payload = request_json(
            "https://api.kraken.com/0/public/PostTrade",
            {
                "symbol": "BTC/USD",
                "from_ts": start,
                "to_ts": end,
                "count": 1000,
            },
        )

        errors = payload.get("error", [])

        if errors:
            raise RuntimeError(f"Kraken API errors: {errors}")

        rows = payload.get("result", {}).get("trades", [])

        if not isinstance(rows, list):
            raise TypeError("Kraken trades payload is not a list.")

        raw_timestamps = []

        for row in rows:
            if not isinstance(row, dict):
                continue

            timestamp = row.get("trade_ts")

            if timestamp is None:
                timestamp = row.get("publication_ts")

            if timestamp is not None:
                raw_timestamps.append(parse_iso8601(timestamp))

        filtered = filter_datetime_window(raw_timestamps, start, end)

        return ProbeResult(
            source=source,
            market=market,
            probe_name=probe_name,
            requested_start=start,
            requested_end=end,
            http_status=status,
            raw_observation_count=len(raw_timestamps),
            in_window_observation_count=len(filtered),
            earliest_in_window_observation=(
                filtered[0].isoformat().replace("+00:00", "Z") if filtered else None
            ),
            latest_in_window_observation=(
                filtered[-1].isoformat().replace("+00:00", "Z") if filtered else None
            ),
            response_sha256=canonical_sha256(payload),
            capability_passed=len(filtered) > 0,
            error=None,
        )

    except Exception as exc:
        return failed_result(
            source,
            market,
            probe_name,
            start,
            end,
            exc,
        )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results: list[ProbeResult] = []

    for probe_name, window in PROBE_WINDOWS.items():
        start, end = window

        results.extend(
            [
                probe_coinbase(probe_name, start, end),
                probe_bitstamp(probe_name, start, end),
                probe_kraken(probe_name, start, end),
            ]
        )

    rows = [asdict(result) for result in results]

    historical = [row for row in rows if row["probe_name"] == "historical"]

    recent = [row for row in rows if row["probe_name"] == "recent"]

    stable_payload = {
        "study_id": "HILMARCORP-BTC-PRICE-REFERENCE",
        "stage": "SOURCE_CAPABILITY_AUDIT",
        "probe_windows": PROBE_WINDOWS,
        "results": rows,
        "historical_all_sources_passed": all(row["capability_passed"] for row in historical),
        "recent_all_sources_passed": all(row["capability_passed"] for row in recent),
    }

    summary = {
        **stable_payload,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "artifact_sha256": canonical_sha256(stable_payload),
    }

    OUTPUT_PATH.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    print()
    print("HILMARCORP BTC PRICE REFERENCE — SOURCE CAPABILITY AUDIT")
    print("=" * 88)

    for row in rows:
        status = "PASS" if row["capability_passed"] else "FAIL"

        print(
            f"{status:4} | "
            f"{row['probe_name']:10} | "
            f"{row['source']:9} | "
            f"RAW={row['raw_observation_count']:4} | "
            f"WINDOW={row['in_window_observation_count']:4} | "
            f"{row['earliest_in_window_observation']} -> "
            f"{row['latest_in_window_observation']}"
        )

        if row["error"]:
            print(f"     ERROR: {row['error']}")

    print("=" * 88)

    print(
        "Historical all-source gate:",
        "PASS" if summary["historical_all_sources_passed"] else "FAIL",
    )

    print(
        "Recent all-source gate:",
        "PASS" if summary["recent_all_sources_passed"] else "FAIL",
    )

    print("Artifact:", OUTPUT_PATH)
    print("SHA256:", summary["artifact_sha256"])
    print()


if __name__ == "__main__":
    main()
