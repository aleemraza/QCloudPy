"""
File: update_circuit_manifest.py

Purpose:
    Create or incrementally update circuit_manifest.json for a QASM dataset.

Placement:
    Save this file in the SAME directory as registry.py and models.py.

What it does:
    1. Loads the existing manifest when one is present.
    2. Discovers .qasm and .qasm3 files.
    3. Adds new circuits.
    4. Updates records when circuit files have changed.
    5. Keeps existing records for missing files by default.
    6. Saves the updated manifest atomically through CircuitRegistry.

This indexes circuit metadata only. It does not parse circuits into
Qiskit QuantumCircuit objects.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_circuit_registry():
    from qcloudrl.circuits.registry import CircuitRegistry
    return CircuitRegistry

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create or incrementally update a QASM circuit manifest."
    )

    parser.add_argument(
        "--dataset-dir",
        required=True,
        help="Dataset folder containing .qasm/.qasm3 files.",
    )

    parser.add_argument(
        "--manifest",
        default=None,
        help=(
            "Manifest JSON path. Default: "
            "<dataset-dir>/circuit_manifest.json"
        ),
    )

    parser.add_argument(
        "--dataset-name",
        default=None,
        help="Logical dataset name. Default: dataset folder name.",
    )

    parser.add_argument(
        "--non-recursive",
        action="store_true",
        help="Search only the top-level dataset folder.",
    )

    parser.add_argument(
        "--prune-missing",
        action="store_true",
        help=(
            "Remove manifest records whose QASM files are no longer present. "
            "Without this option, missing-file records are retained."
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    dataset_dir = Path(args.dataset_dir).expanduser().resolve()

    if not dataset_dir.is_dir():
        print(f"ERROR: Dataset directory does not exist: {dataset_dir}")
        return 1

    manifest_path = (
        Path(args.manifest).expanduser().resolve()
        if args.manifest
        else dataset_dir / "circuit_manifest.json"
    )

    dataset_name = args.dataset_name or dataset_dir.name

    CircuitRegistry = load_circuit_registry()

    registry = CircuitRegistry(
        dataset_dir=dataset_dir,
        manifest_path=manifest_path,
        dataset_name=dataset_name,
    )

    print("=" * 68)
    print("QASM CIRCUIT MANIFEST BUILDER")
    print("=" * 68)
    print(f"Dataset directory : {dataset_dir}")
    print(f"Dataset name      : {dataset_name}")
    print(f"Manifest path     : {manifest_path}")

    # Load previous index when available. A missing manifest is normal
    # on the first run.
    if manifest_path.is_file():
        loaded_count = registry.load_manifest(manifest_path)
        print(f"Existing records  : {loaded_count}")
        action = "updated"
    else:
        print("Existing records  : 0 (new manifest)")
        action = "created"

    # CircuitRegistry.index_dataset() performs incremental indexing:
    # new files are added, modified files are refreshed, and unchanged
    # files keep their existing records.
    indexed_records = registry.index_dataset(
        dataset_dir=dataset_dir,
        dataset_name=dataset_name,
        recursive=not args.non_recursive,
        prune_missing=args.prune_missing,
    )

    # Save the refreshed registry to JSON.
    saved_path = registry.save_manifest(manifest_path)

    discovered_count = len(indexed_records)
    total_count = len(registry.get_all())

    print("-" * 68)
    print(f"Indexing result   : {discovered_count} discovered/indexed")
    print(f"Total manifest    : {total_count} records")
    print(f"Manifest status   : {action}")
    print(f"Saved successfully: {saved_path}")
    print("=" * 68)
    print("Done. QASM circuits remain on disk and are loaded lazily later.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
