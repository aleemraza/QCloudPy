from qcloudrl.circuits import CircuitRegistry


def test_discovers_qasm2_and_qasm3(qasm_dataset):
    records = CircuitRegistry(qasm_dataset).discover()
    assert len(records) == 2
    assert {record.format for record in records} == {"qasm2", "qasm3"}


def test_deterministic_selection(qasm_dataset):
    registry = CircuitRegistry(qasm_dataset)
    records = registry.discover()
    first = registry.select(records, limit=1, seed=42)
    second = registry.select(records, limit=1, seed=42)
    assert [x.circuit_id for x in first] == [x.circuit_id for x in second]


def test_manifest_round_trip(qasm_dataset, tmp_path):
    registry = CircuitRegistry(qasm_dataset)
    records = registry.discover()
    manifest = tmp_path / "manifest.json"
    registry.save_manifest(records, manifest)
    loaded = registry.load_manifest(manifest)
    assert loaded == records
