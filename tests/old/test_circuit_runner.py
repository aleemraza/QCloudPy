import pytest

from qcloudrl.circuits import AerExecutor, CircuitRunner, CircuitService


def test_cloud_mode_does_not_require_aer(qasm_dataset):
    service = CircuitService(qasm_dataset)
    records = service.index()
    runner = CircuitRunner(service)
    output = runner.run(records[0].circuit_id, mode="cloud")
    assert output.cloud_artifact is not None
    assert output.aer_result is None


def test_both_mode(qasm_dataset):
    pytest.importorskip("qiskit_aer")
    service = CircuitService(qasm_dataset)
    records = service.index()
    runner = CircuitRunner(service, AerExecutor())
    output = runner.run(records[0].circuit_id, mode="both", shots=32)
    assert output.cloud_artifact is not None
    assert output.aer_result is not None
    assert sum(output.aer_result.counts.values()) == 32
