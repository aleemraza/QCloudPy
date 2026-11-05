
import pytest

from qcloudrl.circuits.models import (
    CircuitFormat,
    CircuitRecord,
    CircuitFeatures,
    CircuitProfile,
)


def test_circuit_format():
    assert CircuitFormat.QASM2.value == "qasm2"
    assert CircuitFormat.QASM3.value == "qasm3"


def test_circuit_record():
    record = CircuitRecord(
        circuit_id="test_001",
        name="test_circuit",
        file_path="dataset/test",
        circuit_format=CircuitFormat.QASM2,
    )

    assert record.circuit_id == "test_001"
    assert record.circuit_format == CircuitFormat.QASM2


def test_circuit_features():
    features = CircuitFeatures(
        circuit_id="test_001",
        num_qubits=4,
        circuit_depth=10,
        total_gate_count=20,
    )

    assert features.num_qubits == 4
    assert features.circuit_depth == 10


def test_circuit_profile():
    profile = CircuitProfile(
        circuit_id="test_001",
        original_depth=10,
        original_gate_count=20,
        backend_name="fake_backend",
        transpiled_depth=15,
        transpiled_gate_count=25,
    )

    assert profile.original_depth == 10
    assert profile.transpiled_depth == 15


def test_negative_qubit_count():
    with pytest.raises(ValueError):
        CircuitFeatures(
            circuit_id="test_001",
            num_qubits=-1,
        )


def test_negative_transpiled_depth():
    with pytest.raises(ValueError):
        CircuitProfile(
            circuit_id="test_001",
            transpiled_depth=-1,
        )
