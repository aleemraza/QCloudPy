
import json

import pytest

from qcloudrl.circuits.models import CircuitFormat
from qcloudrl.circuits.registry import (
    CircuitRegistry,
    detect_qasm_format,
)


@pytest.fixture
def dataset(tmp_path):
    root = tmp_path / "mqt_bench"
    root.mkdir()

    (root / "ghz.qasm").write_text(
        'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\n',
        encoding="utf-8",
    )

    (root / "qft.qasm3").write_text(
        'OPENQASM 3.0;\nqubit[3] q;\n',
        encoding="utf-8",
    )

    nested = root / "nested"
    nested.mkdir()

    (nested / "grover.qasm").write_text(
        'OPENQASM 2.0;\nqreg q[3];\n',
        encoding="utf-8",
    )

    return root


def test_detect_qasm2(dataset):
    assert detect_qasm_format(
        dataset / "ghz.qasm"
    ) == CircuitFormat.QASM2


def test_detect_qasm3(dataset):
    assert detect_qasm_format(
        dataset / "qft.qasm3"
    ) == CircuitFormat.QASM3


def test_discover_circuits(dataset):
    registry = CircuitRegistry(dataset_dir=dataset)

    files = registry.discover_circuits()

    assert len(files) == 3


def test_non_recursive_discovery(dataset):
    registry = CircuitRegistry(dataset_dir=dataset)

    files = registry.discover_circuits(
        recursive=False
    )

    assert len(files) == 2


def test_index_dataset(dataset):
    registry = CircuitRegistry(dataset_dir=dataset)

    records = registry.index_dataset()

    assert len(records) == 3
    assert len(registry) == 3

    assert all(record.circuit_hash for record in records)
    assert all(record.circuit_id for record in records)


def test_unique_circuit_ids(dataset):
    registry = CircuitRegistry(dataset_dir=dataset)

    records = registry.index_dataset()

    ids = [record.circuit_id for record in records]

    assert len(ids) == len(set(ids))


def test_filter_by_format(dataset):
    registry = CircuitRegistry(dataset_dir=dataset)

    registry.index_dataset()

    qasm2 = registry.get_by_format(
        CircuitFormat.QASM2
    )

    qasm3 = registry.get_by_format(
        CircuitFormat.QASM3
    )

    assert len(qasm2) == 2
    assert len(qasm3) == 1


def test_get_by_name(dataset):
    registry = CircuitRegistry(dataset_dir=dataset)

    registry.index_dataset()

    records = registry.get_by_name("ghz")

    assert len(records) == 1
    assert records[0].name == "ghz"


def test_manifest_save_and_load(dataset, tmp_path):
    registry = CircuitRegistry(dataset_dir=dataset)

    registry.index_dataset()

    manifest = tmp_path / "manifest.json"

    registry.save_manifest(manifest)

    assert manifest.exists()

    new_registry = CircuitRegistry()

    count = new_registry.load_manifest(manifest)

    assert count == 3
    assert len(new_registry) == 3


def test_incremental_indexing(dataset):
    registry = CircuitRegistry(dataset_dir=dataset)

    first_records = registry.index_dataset()

    original_ids = {
        record.circuit_id for record in first_records
    }

    second_records = registry.index_dataset()

    second_ids = {
        record.circuit_id for record in second_records
    }

    assert original_ids == second_ids
    assert len(registry) == 3


def test_new_file_detection(dataset):
    registry = CircuitRegistry(dataset_dir=dataset)

    registry.index_dataset()

    new_file = dataset / "new_circuit.qasm"

    new_file.write_text(
        'OPENQASM 2.0;\nqreg q[4];\n',
        encoding="utf-8",
    )

    records = registry.index_dataset()

    assert len(records) == 4
    assert len(registry) == 4


def test_modified_file_detection(dataset):
    registry = CircuitRegistry(dataset_dir=dataset)

    first_records = registry.index_dataset()

    original = next(
        r for r in first_records if r.name == "ghz"
    )

    ghz_file = dataset / "ghz.qasm"

    ghz_file.write_text(
        'OPENQASM 2.0;\nqreg q[4];\n',
        encoding="utf-8",
    )

    registry.index_dataset()

    updated = registry.get(original.circuit_id)

    assert updated.circuit_hash != original.circuit_hash


def test_missing_dataset():
    registry = CircuitRegistry()

    with pytest.raises(FileNotFoundError):
        registry.index_dataset("missing_dataset")


def test_negative_limit(dataset):
    registry = CircuitRegistry(dataset_dir=dataset)

    with pytest.raises(ValueError):
        registry.index_dataset(limit=-1)
