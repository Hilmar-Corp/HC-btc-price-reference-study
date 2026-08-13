from datetime import UTC

from scripts.research.source_capability_probe import (
    ProbeResult,
    canonical_sha256,
    failed_result,
    filter_datetime_window,
    filter_unix_window,
    iso_from_unix,
    parse_iso8601,
    unix_seconds,
)


def test_iso_round_trip() -> None:
    value = "2017-08-17T12:00:00Z"

    assert iso_from_unix(unix_seconds(value)) == value


def test_parse_iso_is_utc() -> None:
    parsed = parse_iso8601("2026-08-10T12:00:00Z")

    assert parsed.tzinfo == UTC


def test_canonical_sha256_is_stable() -> None:
    first = {
        "a": 1,
        "b": 2,
    }

    second = {
        "b": 2,
        "a": 1,
    }

    assert canonical_sha256(first) == canonical_sha256(second)


def test_filter_unix_window() -> None:
    start = "2026-08-10T12:00:00Z"
    end = "2026-08-10T12:02:00Z"

    timestamps = [
        unix_seconds("2026-08-10T11:59:00Z"),
        unix_seconds("2026-08-10T12:00:00Z"),
        unix_seconds("2026-08-10T12:01:00Z"),
        unix_seconds("2026-08-10T12:03:00Z"),
    ]

    filtered = filter_unix_window(
        timestamps,
        start,
        end,
    )

    assert len(filtered) == 2


def test_filter_datetime_window() -> None:
    start = "2026-08-10T12:00:00Z"
    end = "2026-08-10T12:02:00Z"

    timestamps = [
        parse_iso8601("2026-08-10T11:59:00Z"),
        parse_iso8601("2026-08-10T12:01:00Z"),
    ]

    filtered = filter_datetime_window(
        timestamps,
        start,
        end,
    )

    assert len(filtered) == 1


def test_failed_result() -> None:
    result = failed_result(
        "Test",
        "BTC/USD",
        "historical",
        "2026-08-10T12:00:00Z",
        "2026-08-10T12:10:00Z",
        RuntimeError("failure"),
    )

    assert isinstance(
        result,
        ProbeResult,
    )

    assert result.capability_passed is False
    assert result.in_window_observation_count == 0
    assert "RuntimeError" in result.error
