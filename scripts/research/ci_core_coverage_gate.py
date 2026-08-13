from __future__ import annotations

import json
import sys
from pathlib import Path

MIN_LINE = 85.0
MIN_BRANCH = 75.0


def calculate_coverage(
    payload: dict,
) -> tuple[float, float]:
    totals = payload["totals"]

    statements = int(totals["num_statements"])

    covered_lines = int(totals["covered_lines"])

    branches = int(totals["num_branches"])

    covered_branches = int(totals["covered_branches"])

    if statements <= 0:
        raise ValueError("No analytical statements measured.")

    if branches <= 0:
        raise ValueError("No analytical branches measured.")

    line_pct = 100.0 * covered_lines / statements

    branch_pct = 100.0 * covered_branches / branches

    return (
        line_pct,
        branch_pct,
    )


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m scripts.research.ci_core_coverage_gate <coverage.json>")

    path = Path(sys.argv[1])

    payload = json.loads(path.read_text(encoding="utf-8"))

    line_pct, branch_pct = calculate_coverage(payload)

    print(f"Analytical core line coverage: {line_pct:.2f}%")

    print(f"Analytical core branch coverage: {branch_pct:.2f}%")

    failures = []

    if line_pct < MIN_LINE:
        failures.append(f"line {line_pct:.2f}% < {MIN_LINE:.2f}%")

    if branch_pct < MIN_BRANCH:
        failures.append(f"branch {branch_pct:.2f}% < {MIN_BRANCH:.2f}%")

    if failures:
        print("CORE COVERAGE GATE: FAIL")

        for failure in failures:
            print(failure)

        raise SystemExit(1)

    print("CORE COVERAGE GATE: PASS")


if __name__ == "__main__":
    main()
