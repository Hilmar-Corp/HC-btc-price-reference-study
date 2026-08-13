from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

EVIDENCE_PATH = Path("evidence/repository_evidence.json")

FINAL_DECISION_PATH = Path("artifacts/final_assurance/consolidated_decision.json")

ASSURANCE_CHECKS_PATH = Path("artifacts/final_assurance/assurance_checks.csv")

PUBLICATION_SUMMARY_PATH = Path("artifacts/publication_figures/publication_figure_summary.json")

LICENSE_PATH = Path("LICENSE")


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


def read_json(
    path: Path,
) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(
        payload,
        dict,
    ):
        raise TypeError(f"{path} must contain a JSON object.")

    return payload


def tracked_files() -> list[str]:
    result = subprocess.run(
        [
            "git",
            "ls-files",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> None:
    evidence = read_json(EVIDENCE_PATH)

    failures: list[str] = []

    if evidence.get("state") != "FROZEN":
        failures.append("Repository evidence is not FROZEN.")

    if evidence.get("raw_market_data_included") is not False:
        failures.append("Raw-market-data declaration invalid.")

    files = evidence.get("files")

    if not isinstance(
        files,
        list,
    ):
        raise TypeError("Controlled evidence inventory missing.")

    for item in files:
        path = Path(item["path"])

        expected = str(item["sha256"])

        if not path.is_file():
            failures.append(f"Missing controlled file: {path}")
            continue

        observed = sha256_file(path)

        if observed != expected:
            failures.append(f"SHA mismatch: {path}")

    final_decision = read_json(FINAL_DECISION_PATH)

    if final_decision.get("decision") != "PASS":
        failures.append("Final research assurance is not PASS.")

    if (
        int(
            final_decision.get(
                "total_checks",
                -1,
            )
        )
        != 16
    ):
        failures.append("Final assurance total_checks != 16.")

    if (
        int(
            final_decision.get(
                "passed_checks",
                -1,
            )
        )
        != 16
    ):
        failures.append("Final assurance passed_checks != 16.")

    if (
        int(
            final_decision.get(
                "failed_checks",
                -1,
            )
        )
        != 0
    ):
        failures.append("Final assurance contains failures.")

    with ASSURANCE_CHECKS_PATH.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        rows = list(csv.DictReader(handle))

    if len(rows) != 16:
        failures.append(f"Expected 16 assurance rows; found {len(rows)}.")

    for row in rows:
        if str(row.get("passed", "")).lower() != "true":
            failures.append("Non-passing assurance check: " + str(row.get("check_id")))

    publication = read_json(PUBLICATION_SUMMARY_PATH)

    publication_status = publication.get("final_assurance") or publication.get(
        "final_assurance_decision"
    )

    if publication_status != "PASS":
        failures.append("Publication evidence is not linked to PASS assurance.")

    licence = LICENSE_PATH.read_text(encoding="utf-8")

    if "Apache License" not in licence or "Version 2.0" not in licence:
        failures.append("Apache License 2.0 not detected.")

    tracked = tracked_files()

    forbidden = [
        path
        for path in tracked
        if path.startswith(
            (
                "data/cache/",
                "data/raw/",
            )
        )
    ]

    if forbidden:
        failures.append("Raw market data tracked: " + ", ".join(forbidden))

    sensitive_names = {
        ".env",
        ".env.local",
        "id_rsa",
        "id_ed25519",
    }

    sensitive = [path for path in tracked if Path(path).name in sensitive_names]

    if sensitive:
        failures.append("Potential sensitive files tracked: " + ", ".join(sensitive))

    print("HILMARCORP BTC PRICE REFERENCE")

    print("REPOSITORY ASSURANCE")

    print("=" * 72)

    print(
        "Controlled files:",
        len(files),
    )

    print("Final research checks: 16/16 PASS")

    print(
        "Raw market data tracked:",
        len(forbidden),
    )

    if failures:
        print()

        print("REPOSITORY ASSURANCE: FAIL")

        for failure in failures:
            print(
                "-",
                failure,
            )

        raise SystemExit(1)

    print()

    print("REPOSITORY ASSURANCE: PASS")


if __name__ == "__main__":
    main()
