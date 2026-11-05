
import pytest

from qiskit import QuantumCircuit

from qcloudrl.circuits.feature_extractor import (
    CircuitFeatureExtractor,
    CircuitFeatureExtractionError,
)


@pytest.fixture
def extractor():
    return CircuitFeatureExtractor()


def test_basic_gate_counts(extractor):
    circuit = QuantumCircuit(2, 2)

    circuit.h(0)
    circuit.cx(0, 1)
    circuit.measure([0, 1], [0, 1])

    features = extractor.extract(circuit, "bell_test")

    assert features.num_qubits == 2
    assert features.num_clbits == 2
    assert features.circuit_width == 4

    assert features.single_qubit_gate_count == 1
    assert features.two_qubit_gate_count == 1
    assert features.multi_qubit_gate_count == 0

    assert features.total_gate_count == 2
    assert features.measurement_count == 2
    assert features.reset_count == 0


def test_gate_histogram(extractor):
    circuit = QuantumCircuit(2)

    circuit.h(0)
    circuit.h(1)
    circuit.cx(0, 1)
    circuit.x(0)

    features = extractor.extract(circuit, "histogram_test")

    assert features.gate_histogram == {
        "cx": 1,
        "h": 2,
        "x": 1,
    }

    assert features.required_gates == ["cx", "h", "x"]


def test_circuit_depth(extractor):
    circuit = QuantumCircuit(2)

    circuit.h(0)
    circuit.h(1)
    circuit.cx(0, 1)

    features = extractor.extract(circuit, "depth_test")

    assert features.circuit_depth == circuit.depth()


def test_interaction_edges(extractor):
    circuit = QuantumCircuit(3)

    circuit.cx(0, 1)
    circuit.cx(1, 2)
    circuit.cx(0, 2)

    features = extractor.extract(circuit, "connectivity_test")

    assert features.interaction_edges == [
        (0, 1),
        (0, 2),
        (1, 2),
    ]


def test_multi_qubit_gate(extractor):
    circuit = QuantumCircuit(3)

    circuit.ccx(0, 1, 2)

    features = extractor.extract(circuit, "multi_qubit_test")

    assert features.multi_qubit_gate_count == 1
    assert features.total_gate_count == 1

    assert features.interaction_edges == [
        (0, 1),
        (0, 2),
        (1, 2),
    ]


def test_measurement_and_reset_counts(extractor):
    circuit = QuantumCircuit(2, 2)

    circuit.h(0)
    circuit.reset(1)
    circuit.measure(0, 0)
    circuit.measure(1, 1)

    features = extractor.extract(circuit, "measurement_test")

    assert features.measurement_count == 2
    assert features.reset_count == 1

    # H is the only computational gate.
    assert features.total_gate_count == 1


def test_final_measurement_is_not_dynamic(extractor):
    circuit = QuantumCircuit(2, 2)

    circuit.h(0)
    circuit.cx(0, 1)
    circuit.measure([0, 1], [0, 1])

    features = extractor.extract(circuit, "static_test")

    assert features.requires_mid_circuit_measurement is False
    assert features.requires_conditional_operations is False
    assert features.requires_dynamic_circuits is False


def test_mid_circuit_measurement(extractor):
    circuit = QuantumCircuit(1, 1)

    circuit.h(0)
    circuit.measure(0, 0)
    circuit.x(0)

    features = extractor.extract(circuit, "dynamic_test")

    assert features.requires_mid_circuit_measurement is True
    assert features.requires_dynamic_circuits is True


def test_conditional_operation(extractor):
    circuit = QuantumCircuit(1, 1)

    circuit.measure(0, 0)

    with circuit.if_test((circuit.clbits[0], 1)):
        circuit.x(0)

    features = extractor.extract(circuit, "conditional_test")

    assert features.requires_conditional_operations is True
    assert features.requires_dynamic_circuits is True


def test_invalid_circuit(extractor):
    with pytest.raises(CircuitFeatureExtractionError):
        extractor.extract("not a circuit", "invalid_test")


def test_invalid_circuit_id(extractor):
    circuit = QuantumCircuit(1)

    with pytest.raises(CircuitFeatureExtractionError):
        extractor.extract(circuit, "")


def test_metadata(extractor):
    circuit = QuantumCircuit(1)
    circuit.h(0)

    features = extractor.extract(circuit, "metadata_test")

    assert features.metadata["feature_extractor"] == (
        "CircuitFeatureExtractor"
    )
    assert features.metadata["feature_version"] == 1
