from __future__ import annotations

import argparse
import json
from pathlib import Path

MIN_LINE_COVERAGE = 0.85
MIN_BRANCH_COVERAGE = 0.75


def ratio(covered: int, total: int) -> float:
    if total == 0:
        return 1.0

    return covered / total


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coverage-json", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    input_path = Path(args.coverage_json)
    output_path = Path(args.output)

    payload = json.loads(input_path.read_text(encoding="utf-8"))

    totals = payload["totals"]

    line_coverage = ratio(
        totals["covered_lines"],
        totals["num_statements"],
    )

    branch_coverage = ratio(
        totals.get("covered_branches", 0),
        totals.get("num_branches", 0),
    )

    line_passed = line_coverage >= MIN_LINE_COVERAGE
    branch_passed = branch_coverage >= MIN_BRANCH_COVERAGE
    validation_passed = line_passed and branch_passed

    result = {
        "line_coverage": line_coverage,
        "branch_coverage": branch_coverage,
        "minimum_line_coverage": MIN_LINE_COVERAGE,
        "minimum_branch_coverage": MIN_BRANCH_COVERAGE,
        "line_gate_passed": line_passed,
        "branch_gate_passed": branch_passed,
        "validation_passed": validation_passed,
    }

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    print(
        "Core line coverage:",
        f"{line_coverage:.2%}",
    )

    print(
        "Core branch coverage:",
        f"{branch_coverage:.2%}",
    )

    if not validation_passed:
        raise SystemExit("Analytical coverage gate failed.")

    print("ANALYTICAL COVERAGE GATE: PASS")


if __name__ == "__main__":
    main()
