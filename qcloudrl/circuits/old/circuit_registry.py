from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Iterable

from .models import CircuitRecord

SUPPORTED_SUFFIXES = {".qasm", ".qasm2", ".qasm3"}


def detect_qasm_format(path: Path) -> str:
    """Detect QASM version from extension/header; do not infer from dataset name."""
    suffix = path.suffix.lower()
    if suffix == ".qasm2":
        return "qasm2"
    if suffix == ".qasm3":
        return "qasm3"

    # Generic .qasm: inspect header. OpenQASM 3 starts with OPENQASM 3.
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            if line.startswith("OPENQASM 3"):
                return "qasm3"
            if line.startswith("OPENQASM 2"):
                return "qasm2"
            break
    raise ValueError(
        f"Cannot determine QASM version for {path}. "
        "Use .qasm2/.qasm3 or a valid OPENQASM header."
    )


class CircuitRegistry:
    """Discovers circuit files and persists a lightweight JSON manifest."""

    def __init__(self, dataset_root: str | Path):
        self.dataset_root = Path(dataset_root).expanduser().resolve()

    @staticmethod
    def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(chunk_size):
                digest.update(chunk)
        return digest.hexdigest()

    def discover(self, include_hash: bool = False) -> list[CircuitRecord]:
        if not self.dataset_root.exists():
            raise FileNotFoundError(f"Dataset directory does not exist: {self.dataset_root}")
        if not self.dataset_root.is_dir():
            raise NotADirectoryError(self.dataset_root)

        paths = sorted(
            p for p in self.dataset_root.rglob("*")
            if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
        )

        records: list[CircuitRecord] = []
        for path in paths:
            fmt = detect_qasm_format(path)
            try:
                relative = path.relative_to(self.dataset_root).as_posix()
            except ValueError:
                relative = str(path)
            records.append(
                CircuitRecord(
                    circuit_id=path.relative_to(self.dataset_root).with_suffix("").as_posix().replace("/", "__"),
                    path=relative,
                    format=fmt,
                    size_bytes=path.stat().st_size,
                    sha256=self._sha256(path) if include_hash else None,
                )
            )
        return records

    @staticmethod
    def select(
        records: Iterable[CircuitRecord],
        limit: int | None = None,
        seed: int = 42,
    ) -> list[CircuitRecord]:
        items = list(records)
        if limit is None:
            return items
        if limit < 0:
            raise ValueError("limit must be >= 0")
        if len(items) <= limit:
            return items
        rng = random.Random(seed)
        selected = rng.sample(items, limit)
        # Stable order after deterministic selection.
        return sorted(selected, key=lambda item: item.circuit_id)

    @staticmethod
    def save_manifest(records: Iterable[CircuitRecord], manifest_path: str | Path) -> Path:
        destination = Path(manifest_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "record_count": len(items := list(records)),
            "circuits": [record.to_dict() for record in items],
        }
        destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return destination

    @staticmethod
    def load_manifest(manifest_path: str | Path) -> list[CircuitRecord]:
        source = Path(manifest_path)
        payload = json.loads(source.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 1:
            raise ValueError("Unsupported circuit manifest schema_version")
        return [CircuitRecord.from_dict(item) for item in payload["circuits"]]
