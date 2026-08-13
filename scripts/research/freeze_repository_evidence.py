from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

OUTPUT = Path("evidence/repository_evidence.json")

ROOT_FILES = [
    ".gitattributes",
    ".gitignore",
    "README.md",
    "DATA_NOTICE.md",
    "REPRODUCIBILITY.md",
    "RESEARCH_ASSURANCE.md",
    "NOTICE",
    "CITATION.cff",
    "LICENSE",
    "Makefile",
    "pyproject.toml",
    "requirements-ci.txt",
    "research_contract.json",
    "source_registry.json",
    "acquisition_protocol.json",
]

PATTERNS = [
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
    "scripts/**/*.py",
    "tests/**/*.py",
    "artifacts/**/*.json",
    "artifacts/**/*.csv",
    "artifacts/publication_figures/*.png",
    "artifacts/publication_figures/*.svg",
]


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


def collect_files() -> list[Path]:
    files: set[Path] = set()

    for name in ROOT_FILES:
        path = Path(name)

        if not path.is_file():
            raise FileNotFoundError(path)

        files.add(path)

    for pattern in PATTERNS:
        for path in Path(".").glob(pattern):
            if not path.is_file():
                continue

            if path.as_posix().startswith("artifacts/ci_assurance/"):
                continue

            files.add(path)

    return sorted(
        files,
        key=lambda item: item.as_posix(),
    )


def main() -> None:
    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    final_decision_path = Path("artifacts/final_assurance/consolidated_decision.json")

    final_decision = json.loads(final_decision_path.read_text(encoding="utf-8"))

    if final_decision.get("decision") != "PASS":
        raise RuntimeError("Final research assurance is not PASS.")

    files = collect_files()

    payload = {
        "study_id": ("HILMARCORP-BTC-PRICE-REFERENCE"),
        "repository": ("Hilmar-Corp/HC-btc-price-reference-study"),
        "release": "1.0.0",
        "state": "FROZEN",
        "generated_at_utc": (datetime.now(UTC).isoformat()),
        "raw_market_data_included": False,
        "expected_final_assurance_checks": 16,
        "final_assurance_decision": "PASS",
        "controlled_file_count": len(files),
        "files": [
            {
                "path": path.as_posix(),
                "sha256": (sha256_file(path)),
                "size_bytes": (path.stat().st_size),
            }
            for path in files
        ],
    }

    OUTPUT.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    print("FROZEN REPOSITORY EVIDENCE CREATED")

    print(
        "Controlled files:",
        len(files),
    )


if __name__ == "__main__":
    main()
