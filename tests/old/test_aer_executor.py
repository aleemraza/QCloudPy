import pytest

from qcloudrl.circuits import AerExecutor, CircuitService


def test_aer_executes_measured_qasm2(qasm_dataset, tmp_path):
    pytest.importorskip("qiskit_aer")
    service = CircuitService(qasm_dataset)
    records = service.index()
    record = next(item for item in records if item.format == "qasm2")
    circuit = service.load(record.circuit_id)

    result = AerExecutor().run(circuit, shots=128)
    assert result.success
    assert sum(result.counts.values()) == 128
    assert result.shots == 128


def test_aer_auto_measure_unmeasured_circuit():
    pytest.importorskip("qiskit_aer")
    from qiskit import QuantumCircuit

    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.cx(0, 1)

    result = AerExecutor().run(circuit, shots=64, auto_measure=True)
    assert sum(result.counts.values()) == 64
