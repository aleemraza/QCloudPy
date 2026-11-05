from qcloudrl.circuits import CircuitService


def test_index_does_not_parse_circuits(qasm_dataset, tmp_path):
    service = CircuitService(qasm_dataset, tmp_path / "manifest.json")
    records = service.index()
    assert len(records) == 2
    assert service.cache_stats()["size"] == 0


def test_lazy_load_and_profile_qasm2_qasm3(qasm_dataset, tmp_path):
    service = CircuitService(qasm_dataset, tmp_path / "manifest.json")
    records = service.index()

    for record in records:
        artifact = service.prepare_for_cloud(record.circuit_id)
        assert artifact.circuit.num_qubits in {2, 3}
        assert artifact.profile.depth > 0

    assert service.cache_stats()["size"] == 2


def test_cache_reuses_loaded_circuit(qasm_dataset, tmp_path):
    service = CircuitService(qasm_dataset, cache_size=1)
    records = service.index()
    circuit_id = records[0].circuit_id

    first = service.load(circuit_id)
    second = service.load(circuit_id)

    assert first is second
    assert service.cache_stats()["hits"] == 1


def test_cache_evicts_old_entries(qasm_dataset, tmp_path):
    service = CircuitService(qasm_dataset, cache_size=1)
    records = service.index()

    service.load(records[0].circuit_id)
    service.load(records[1].circuit_id)

    assert service.cache_stats()["size"] == 1
    assert service.cache_stats()["evictions"] == 1
