
"""
QCloudRL Circuit Module
File: registry.py

Purpose:
    Discover, identify, index, and manage quantum circuit datasets.

Features:
    - Recursive QASM 2 / QASM 3 discovery
    - Circuit format detection
    - SHA-256 content hashing
    - Stable circuit identifiers
    - CircuitRecord generation
    - JSON manifest persistence
    - Incremental indexing
    - Circuit lookup and filtering

Python: 3.10+
"""

from __future__ import annotations

import hashlib
import json
import random

from pathlib import Path
from typing import Optional, Iterable

from .models import CircuitFormat, CircuitRecord


# ============================================================
# 1. QASM FORMAT DETECTION
# ============================================================

def detect_qasm_format(file_path: str | Path) -> CircuitFormat:
    """
    Detect whether a circuit file uses OpenQASM 2 or OpenQASM 3.

    Detection is based on the OpenQASM header.
    The file extension is used as a secondary indication.

    Returns:
        CircuitFormat.QASM2
        CircuitFormat.QASM3
        CircuitFormat.UNKNOWN
    """

    path = Path(file_path)

    if not path.is_file():
        return CircuitFormat.UNKNOWN

    try:
        with path.open("r", encoding="utf-8-sig") as file:
            # Only inspect the beginning of the file.
            header = file.read(8192)

    except (OSError, UnicodeDecodeError):
        return CircuitFormat.UNKNOWN

    for line in header.splitlines():

        line = line.strip()

        if not line or line.startswith("//"):
            continue

        normalized = line.lower().replace(" ", "")

        if normalized.startswith("openqasm3") or normalized.startswith(
            "openqasm3.0"
        ):
            return CircuitFormat.QASM3

        if normalized.startswith("openqasm2") or normalized.startswith(
            "openqasm2.0"
        ):
            return CircuitFormat.QASM2

        # OpenQASM headers normally appear before circuit instructions.
        if normalized.startswith("openqasm"):
            if "3" in normalized:
                return CircuitFormat.QASM3

            if "2" in normalized:
                return CircuitFormat.QASM2

    # Secondary extension-based detection.
    suffix = path.suffix.lower()

    if suffix == ".qasm3":
        return CircuitFormat.QASM3

    return CircuitFormat.UNKNOWN


# ============================================================
# 2. CIRCUIT REGISTRY
# ============================================================

class CircuitRegistry:
    """
    Manage quantum circuit dataset indexing and metadata.

    The registry stores CircuitRecord objects, not loaded
    Qiskit QuantumCircuit objects.

    This supports lazy circuit loading and bounded memory usage.
    """

    MANIFEST_VERSION = 1

    SUPPORTED_EXTENSIONS = {
        ".qasm",
        ".qasm3",
    }

    def __init__(
        self,
        dataset_dir: Optional[str | Path] = None,
        manifest_path: Optional[str | Path] = None,
        dataset_name: Optional[str] = None,
    ):
        self.dataset_dir = (
            Path(dataset_dir).expanduser().resolve()
            if dataset_dir is not None
            else None
        )

        self.manifest_path = (
            Path(manifest_path).expanduser().resolve()
            if manifest_path is not None
            else None
        )

        self.dataset_name = dataset_name

        # circuit_id -> CircuitRecord
        self.records: dict[str, CircuitRecord] = {}

        # Relative file path -> circuit_id
        self._path_index: dict[str, str] = {}

    # ========================================================
    # 3. FILE DISCOVERY
    # ========================================================

    def discover_circuits(
        self,
        dataset_dir: Optional[str | Path] = None,
        recursive: bool = True,
    ) -> list[Path]:
        """
        Discover supported QASM circuit files.

        Does not load or parse circuit contents.
        """

        root = (
            Path(dataset_dir).expanduser().resolve()
            if dataset_dir is not None
            else self.dataset_dir
        )

        if root is None:
            raise ValueError("Dataset directory was not provided.")

        if not root.exists():
            raise FileNotFoundError(f"Dataset directory not found: {root}")

        if not root.is_dir():
            raise NotADirectoryError(str(root))

        iterator = root.rglob("*") if recursive else root.iterdir()

        files = [
            path.resolve()
            for path in iterator
            if path.is_file()
            and path.suffix.lower() in self.SUPPORTED_EXTENSIONS
        ]

        return sorted(files, key=lambda p: p.as_posix().lower())

    # ========================================================
    # 4. FILE HASHING
    # ========================================================

    @staticmethod
    def calculate_hash(
        file_path: str | Path,
        algorithm: str = "sha256",
    ) -> str:
        """
        Calculate a file's content hash incrementally.

        Reading in chunks avoids loading large files entirely
        into memory.
        """

        path = Path(file_path)

        if algorithm.lower() != "sha256":
            raise ValueError("Only SHA-256 hashing is supported.")

        hasher = hashlib.sha256()

        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                hasher.update(chunk)

        return hasher.hexdigest()

    # ========================================================
    # 5. CIRCUIT IDENTIFICATION
    # ========================================================

    @staticmethod
    def generate_circuit_id(
        relative_path: str,
        dataset_name: Optional[str] = None,
    ) -> str:
        """
        Generate a deterministic circuit identifier.

        The identifier is based on the dataset name and
        relative file path, not file contents.

        Therefore, modifying a circuit does not change its ID.
        """

        identity = (
            f"{dataset_name or 'dataset'}:"
            f"{Path(relative_path).as_posix()}"
        )

        digest = hashlib.sha256(
            identity.encode("utf-8")
        ).hexdigest()[:16]

        return f"qc_{digest}"

    # ========================================================
    # 6. RECORD GENERATION
    # ========================================================

    def _create_record(
        self,
        file_path: Path,
        root: Path,
        dataset_name: Optional[str],
    ) -> CircuitRecord:

        relative_path = file_path.relative_to(root).as_posix()

        circuit_id = self.generate_circuit_id(
            relative_path,
            dataset_name,
        )

        file_size = file_path.stat().st_size

        circuit_hash = self.calculate_hash(file_path)

        circuit_format = detect_qasm_format(file_path)

        return CircuitRecord(
            circuit_id=circuit_id,
            name=file_path.stem,
            file_path=str(file_path.resolve()),
            circuit_format=circuit_format,
            dataset_name=dataset_name,
            file_size_bytes=file_size,
            circuit_hash=circuit_hash,
            metadata={
                "relative_path": relative_path,
                "extension": file_path.suffix.lower(),
            },
        )

    # ========================================================
    # 7. DATASET INDEXING
    # ========================================================

    def index_dataset(
        self,
        dataset_dir: Optional[str | Path] = None,
        dataset_name: Optional[str] = None,
        recursive: bool = True,
        limit: Optional[int] = None,
        seed: Optional[int] = None,
        prune_missing: bool = False,
    ) -> list[CircuitRecord]:
        """
        Index circuit files in a dataset.

        Incremental behavior:
            - New files are added.
            - Modified files are updated.
            - Unchanged files retain their existing records.
            - Missing files are retained unless prune_missing=True.

        Args:
            dataset_dir: Dataset root directory.
            dataset_name: Dataset identifier.
            recursive: Search nested directories.
            limit: Optional maximum number of files to index.
            seed: Optional random seed for limited sampling.
            prune_missing: Remove records for missing files.

        Returns:
            List of indexed CircuitRecord objects.
        """

        root = (
            Path(dataset_dir).expanduser().resolve()
            if dataset_dir is not None
            else self.dataset_dir
        )

        if root is None:
            raise ValueError("Dataset directory was not provided.")

        if not root.is_dir():
            raise FileNotFoundError(
                f"Dataset directory not found: {root}"
            )

        name = dataset_name or self.dataset_name or root.name

        self.dataset_dir = root
        self.dataset_name = name

        files = self.discover_circuits(
            root,
            recursive=recursive,
        )

        if limit is not None:
            if limit < 0:
                raise ValueError("limit cannot be negative.")

            if limit < len(files):
                if seed is not None:
                    rng = random.Random(seed)
                    files = sorted(
                        rng.sample(files, limit),
                        key=lambda p: p.as_posix().lower(),
                    )
                else:
                    files = files[:limit]

        indexed_records = []
        discovered_ids = set()

        for file_path in files:

            relative_path = file_path.relative_to(root).as_posix()

            circuit_id = self.generate_circuit_id(
                relative_path,
                name,
            )

            discovered_ids.add(circuit_id)

            existing = self.records.get(circuit_id)

            # Check whether the file is unchanged.
            if existing is not None:
                current_size = file_path.stat().st_size

                if (
                    existing.file_size_bytes == current_size
                    and existing.circuit_hash
                    == self.calculate_hash(file_path)
                ):
                    indexed_records.append(existing)
                    continue

            record = self._create_record(
                file_path,
                root,
                name,
            )

            self.records[record.circuit_id] = record

            self._path_index[relative_path] = record.circuit_id

            indexed_records.append(record)

        if prune_missing:
            for circuit_id, record in list(self.records.items()):

                if record.dataset_name != name:
                    continue

                if circuit_id not in discovered_ids:
                    self.records.pop(circuit_id)

                    relative_path = record.metadata.get(
                        "relative_path"
                    )

                    if relative_path:
                        self._path_index.pop(relative_path, None)

        return indexed_records

    # ========================================================
    # 8. CIRCUIT LOOKUP
    # ========================================================

    def get(self, circuit_id: str) -> Optional[CircuitRecord]:
        """Retrieve a circuit record by ID."""

        return self.records.get(circuit_id)

    def get_by_name(
        self,
        name: str,
    ) -> list[CircuitRecord]:
        """Retrieve all records matching a circuit name."""

        return [
            record
            for record in self.records.values()
            if record.name == name
        ]

    def get_by_format(
        self,
        circuit_format: CircuitFormat,
    ) -> list[CircuitRecord]:
        """Retrieve circuits by QASM format."""

        return [
            record
            for record in self.records.values()
            if record.circuit_format == circuit_format
        ]

    def get_all(self) -> list[CircuitRecord]:
        """Return all registered circuit records."""

        return list(self.records.values())

    def __len__(self) -> int:
        return len(self.records)

    # ========================================================
    # 9. MANIFEST SERIALIZATION
    # ========================================================

    @staticmethod
    def _record_to_dict(
        record: CircuitRecord,
    ) -> dict:

        return {
            "circuit_id": record.circuit_id,
            "name": record.name,
            "file_path": record.file_path,
            "circuit_format": record.circuit_format.value,
            "dataset_name": record.dataset_name,
            "file_size_bytes": record.file_size_bytes,
            "circuit_hash": record.circuit_hash,
            "indexed_at": record.indexed_at,
            "metadata": record.metadata,
        }

    @staticmethod
    def _record_from_dict(data: dict) -> CircuitRecord:

        return CircuitRecord(
            circuit_id=data["circuit_id"],
            name=data["name"],
            file_path=data["file_path"],
            circuit_format=CircuitFormat(
                data.get("circuit_format", "unknown")
            ),
            dataset_name=data.get("dataset_name"),
            file_size_bytes=data.get("file_size_bytes", 0),
            circuit_hash=data.get("circuit_hash"),
            indexed_at=data.get("indexed_at"),
            metadata=data.get("metadata", {}),
        )

    # ========================================================
    # 10. SAVE MANIFEST
    # ========================================================

    def save_manifest(
        self,
        manifest_path: Optional[str | Path] = None,
    ) -> Path:
        """
        Save the current circuit index to JSON.

        The manifest is written atomically to avoid leaving
        a partially written index if saving fails.
        """

        target = (
            Path(manifest_path).expanduser().resolve()
            if manifest_path is not None
            else self.manifest_path
        )

        if target is None:
            if self.dataset_dir is None:
                raise ValueError("Manifest path was not provided.")

            target = self.dataset_dir / "circuit_manifest.json"

        target.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "manifest_version": self.MANIFEST_VERSION,
            "dataset_name": self.dataset_name,
            "dataset_dir": (
                str(self.dataset_dir)
                if self.dataset_dir is not None
                else None
            ),
            "total_circuits": len(self.records),
            "records": [
                self._record_to_dict(record)
                for record in self.records.values()
            ],
        }

        temporary_path = target.with_name(
            target.name + ".tmp"
        )

        try:
            with temporary_path.open(
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    data,
                    file,
                    indent=2,
                    ensure_ascii=False,
                )

            temporary_path.replace(target)

        finally:
            if temporary_path.exists():
                temporary_path.unlink()

        self.manifest_path = target

        return target

    # ========================================================
    # 11. LOAD MANIFEST
    # ========================================================

    def load_manifest(
        self,
        manifest_path: Optional[str | Path] = None,
    ) -> int:
        """
        Load previously indexed records from JSON.

        Returns:
            Number of records loaded.
        """

        target = (
            Path(manifest_path).expanduser().resolve()
            if manifest_path is not None
            else self.manifest_path
        )

        if target is None:
            raise ValueError("Manifest path was not provided.")

        if not target.is_file():
            raise FileNotFoundError(
                f"Manifest not found: {target}"
            )

        with target.open("r", encoding="utf-8") as file:
            data = json.load(file)

        version = data.get("manifest_version")

        if version != self.MANIFEST_VERSION:
            raise ValueError(
                f"Unsupported manifest version: {version}"
            )

        records = {}

        for item in data.get("records", []):
            record = self._record_from_dict(item)
            records[record.circuit_id] = record

        self.records.update(records)

        self.dataset_name = data.get("dataset_name")

        if data.get("dataset_dir"):
            self.dataset_dir = Path(
                data["dataset_dir"]
            ).resolve()

        self.manifest_path = target

        self._path_index = {
            record.metadata["relative_path"]: record.circuit_id
            for record in records.values()
            if "relative_path" in record.metadata
        }

        return len(records)

    # ========================================================
    # 12. CLEAR REGISTRY
    # ========================================================

    def clear(self) -> None:
        """Remove all registered records from memory."""

        self.records.clear()
        self._path_index.clear()





