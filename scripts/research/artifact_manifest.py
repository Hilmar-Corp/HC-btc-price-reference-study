from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

OUTPUT_PATH = Path("artifacts/source_audit/source_audit_manifest.json")

CONTROLLED_FILES = [
    Path("research_contract.json"),
    Path("source_registry.json"),
    Path("artifacts/source_audit/source_capability_probe.json"),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def main() -> None:
    missing = [str(path) for path in CONTROLLED_FILES if not path.is_file()]

    if missing:
        raise SystemExit(f"Missing controlled files: {missing}")

    inventory = []

    for path in CONTROLLED_FILES:
        inventory.append(
            {
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )

    payload = {
        "study_id": "HILMARCORP-BTC-PRICE-REFERENCE",
        "stage": "SOURCE_CAPABILITY_AUDIT",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "artifact_count": len(inventory),
        "artifacts": inventory,
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    print("MANIFEST:", OUTPUT_PATH)

    for item in inventory:
        print(
            item["sha256"],
            item["path"],
        )


if __name__ == "__main__":
    main()
