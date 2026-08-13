from pathlib import Path

import pandas as pd

from scripts.research.publication_figures import (
    format_bps,
)


def test_format_bps_small() -> None:
    assert format_bps(1.234) == "1.23"


def test_format_bps_medium() -> None:
    assert format_bps(15.62) == "15.6"


def test_format_bps_large() -> None:
    assert format_bps(238.7) == "239"


def test_publication_inputs_exist() -> None:
    paths = [
        Path("artifacts/extreme_gap_validation/subperiod_summary.csv"),
        Path("artifacts/extreme_gap_validation/validation_summary.json"),
        Path("artifacts/valuation_boundary/cutoff_pairwise_summary.csv"),
        Path("artifacts/valuation_boundary/venue_effect_summary.csv"),
        Path("artifacts/valuation_boundary/largest_cutoff_effect_dates.csv"),
        Path("artifacts/final_assurance/strict_calendar_rv_validation.csv"),
        Path("artifacts/final_assurance/consolidated_decision.json"),
    ]

    assert all(path.is_file() for path in paths)


def test_top_cutoff_table_contains_three_returns() -> None:
    frame = pd.read_csv("artifacts/valuation_boundary/largest_cutoff_effect_dates.csv")

    required = {
        "composite_return__utc_0000",
        "composite_return__london_1600",
        "composite_return__new_york_1600",
    }

    assert required.issubset(frame.columns)
