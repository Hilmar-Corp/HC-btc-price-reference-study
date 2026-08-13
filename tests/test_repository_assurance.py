import json
from pathlib import Path

import pytest

from scripts.research.ci_core_coverage_gate import (
    calculate_coverage,
)
from scripts.research.verify_repository import (
    sha256_file,
)


def test_calculate_coverage() -> None:
    payload = {
        "totals": {
            "num_statements": 100,
            "covered_lines": 91,
            "num_branches": 20,
            "covered_branches": 16,
        }
    }

    line_pct, branch_pct = calculate_coverage(payload)

    assert line_pct == pytest.approx(91.0)

    assert branch_pct == pytest.approx(80.0)


def test_sha256_is_deterministic(
    tmp_path: Path,
) -> None:
    path = tmp_path / "sample.txt"

    path.write_text(
        "HilmarCorp\n",
        encoding="utf-8",
    )

    first = sha256_file(path)

    second = sha256_file(path)

    assert first == second
    assert len(first) == 64


def test_final_assurance_is_pass() -> None:
    path = Path("artifacts/final_assurance/consolidated_decision.json")

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["decision"] == "PASS"

    assert payload["passed_checks"] == 16

    assert payload["failed_checks"] == 0
