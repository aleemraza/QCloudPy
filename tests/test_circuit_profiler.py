import pytest
from qiskit import QuantumCircuit
from qcloudrl.circuits.profiler import (
    CircuitProfiler,
    CircuitProfilingError,
)


@pytest.fixture
def backend():
    """
    Create a small local Qiskit backend.

    This does not connect to IBM Quantum or consume QPU resources.
    """
    try:
        from qiskit.providers.fake_provider import GenericBackendV2
    except ImportError:
        pytest.skip("GenericBackendV2 is unavailable in this Qiskit version.")

    return GenericBackendV2(
        num_qubits=3,
        basis_gates=[
            "id",
            "rz",
            "sx",
            "x",
            "cx",
            "reset",
        ],
        coupling_map=[
            [0, 1],
            [1, 2],
        ],
    )


@pytest.fixture
def bell_circuit():
    circuit = QuantumCircuit(2, 2)

    circuit.h(0)
    circuit.cx(0, 1)
    circuit.measure([0, 1], [0, 1])

    return circuit


@pytest.fixture
def profiler():
    return CircuitProfiler(
        optimization_level=1,
        seed_transpiler=42,
    )


def test_profile_bell_circuit(profiler, bell_circuit, backend):
    profile = profiler.profile(
        circuit=bell_circuit,
        circuit_id="bell_test",
        backend=backend,
    )

    assert profile.circuit_id == "bell_test"
    assert profile.original_depth == bell_circuit.depth()
    assert profile.original_gate_count == 2

    assert profile.transpiled_depth >= 0
    assert profile.transpiled_gate_count >= 0

    assert profile.backend_name
    assert isinstance(profile.basis_gates, list)
    assert profile.is_compatible is True
    assert any(
        "Transpilation succeeded" in note
        for note in profile.compatibility_notes
    )


def test_backend_information(profiler, bell_circuit, backend):
    profile = profiler.profile(
        bell_circuit,
        "backend_test",
        backend,
    )

    assert profile.backend_name == str(backend.name)
    assert profile.optimization_level == 1
    assert isinstance(profile.basis_gates, list)


def test_optimization_level_override(
    profiler,
    bell_circuit,
    backend,
):
    profile = profiler.profile(
        bell_circuit,
        "optimization_test",
        backend,
        optimization_level=2,
    )

    assert profile.optimization_level == 2


def test_original_circuit_is_not_modified(
    profiler,
    bell_circuit,
    backend,
):
    original = bell_circuit.copy()

    profiler.profile(
        bell_circuit,
        "immutability_test",
        backend,
    )

    assert bell_circuit == original


def test_complexity_score(
    profiler,
    bell_circuit,
    backend,
):
    profile = profiler.profile(
        bell_circuit,
        "complexity_test",
        backend,
    )

    expected = (
        bell_circuit.num_qubits * bell_circuit.depth()
        + 2
    )

    assert profile.complexity_score == float(expected)


def test_profile_metadata(
    profiler,
    bell_circuit,
    backend,
):
    profile = profiler.profile(
        bell_circuit,
        "metadata_test",
        backend,
    )

    assert profile.metadata["profiler"] == "CircuitProfiler"
    assert profile.metadata["profiler_version"] == 1
    assert profile.metadata["seed_transpiler"] == 42

    assert "transpiled_gate_histogram" in profile.metadata
    assert profile.profiled_at is not None


def test_invalid_circuit(profiler, backend):
    with pytest.raises(CircuitProfilingError):
        profiler.profile(
            "not a circuit",
            "invalid_test",
            backend,
        )


def test_invalid_circuit_id(profiler, bell_circuit, backend):
    with pytest.raises(CircuitProfilingError):
        profiler.profile(
            bell_circuit,
            "",
            backend,
        )


def test_missing_backend(profiler, bell_circuit):
    with pytest.raises(CircuitProfilingError):
        profiler.profile(
            bell_circuit,
            "missing_backend_test",
            None,
        )


def test_invalid_optimization_level(
    profiler,
    bell_circuit,
    backend,
):
    with pytest.raises(CircuitProfilingError):
        profiler.profile(
            bell_circuit,
            "invalid_optimization_test",
            backend,
            optimization_level=5,
        )


def test_profiler_statistics(
    profiler,
    bell_circuit,
    backend,
):
    profiler.profile(
        bell_circuit,
        "statistics_test",
        backend,
    )

    assert profiler.profile_count == 1
    assert profiler.failed_count == 0


def test_reset_statistics(
    profiler,
    bell_circuit,
    backend,
):
    profiler.profile(
        bell_circuit,
        "reset_statistics_test",
        backend,
    )

    profiler.reset_statistics()

    assert profiler.profile_count == 0
    assert profiler.failed_count == 0
