
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from qiskit import QuantumCircuit, transpile

from .feature_extractor import CircuitFeatureExtractor
from .models import CircuitProfile


class CircuitProfilingError(Exception):
    """Raised when backend-specific circuit profiling fails."""


class CircuitProfiler:
    """
    Profile a logical quantum circuit for a selected Qiskit backend.

    The profiler performs classical transpilation only. It does not
    submit jobs to a quantum computer or estimate execution time.
    """

    NON_GATE_OPERATIONS = {
        "measure",
        "reset",
        "barrier",
        "delay",
    }

    def __init__(
        self,
        optimization_level: int = 1,
        seed_transpiler: int = 42,
    ):
        if optimization_level not in (0, 1, 2, 3):
            raise ValueError(
                "optimization_level must be between 0 and 3."
            )

        self.optimization_level = optimization_level
        self.seed_transpiler = seed_transpiler

        self.feature_extractor = CircuitFeatureExtractor()
        self.profile_count = 0
        self.failed_count = 0

    @staticmethod
    def _get_backend_name(backend: Any) -> str:
        """Get a readable backend name across Qiskit versions."""

        name = getattr(backend, "name", None)

        if callable(name):
            name = name()

        if name is None:
            return backend.__class__.__name__

        return str(name)

    @staticmethod
    def _get_backend_version(backend: Any) -> str | None:
        """Get the backend version when the provider exposes it."""

        version = getattr(backend, "version", None)

        if callable(version):
            version = version()

        return None if version is None else str(version)

    @staticmethod
    def _get_basis_gates(
        backend: Any,
        transpiled_circuit: QuantumCircuit,
    ) -> tuple[list[str], str]:
        """
        Obtain backend-supported operation names.

        Prefer the backend Target (BackendV2), then legacy
        backend.configuration().basis_gates (BackendV1).

        The transpiled circuit operation names are used only as
        a documented fallback.
        """

        target = getattr(backend, "target", None)

        if target is not None:
            operation_names = getattr(
                target,
                "operation_names",
                None,
            )

            if operation_names is not None:
                names = sorted(
                    name
                    for name in operation_names
                    if name not in {
                        "measure",
                        "reset",
                        "barrier",
                        "delay",
                        "if_else",
                        "while_loop",
                        "for_loop",
                        "switch_case",
                    }
                )

                return names, "backend_target"

        configuration_method = getattr(
            backend,
            "configuration",
            None,
        )

        if callable(configuration_method):
            try:
                configuration = configuration_method()
                basis_gates = getattr(
                    configuration,
                    "basis_gates",
                    None,
                )

                if basis_gates is not None:
                    return sorted(set(basis_gates)), (
                        "backend_configuration"
                    )

            except Exception:
                pass

        # Fallback: report operations actually present in the
        # transpiled circuit. These are not claimed to be the
        # complete backend basis.
        names = sorted(
            name
            for name in transpiled_circuit.count_ops()
            if name not in CircuitProfiler.NON_GATE_OPERATIONS
        )

        return names, "transpiled_circuit_operations_fallback"

    @staticmethod
    def _count_transpiled_gates(
        circuit: QuantumCircuit,
    ) -> tuple[int, dict[str, int]]:
        """Count computational operations in the transpiled circuit."""

        histogram: dict[str, int] = {}

        for operation_name, count in circuit.count_ops().items():
            name = str(operation_name)

            if name in CircuitProfiler.NON_GATE_OPERATIONS:
                continue

            histogram[name] = int(count)

        return sum(histogram.values()), dict(sorted(histogram.items()))

    @staticmethod
    def _calculate_complexity_score(
        num_qubits: int,
        depth: int,
        gate_count: int,
    ) -> float:
        """
        Calculate a simple structural complexity indicator.

        Formula:
            score = (num_qubits * depth) + gate_count

        This is a heuristic, not an execution-time or hardware-cost
        prediction.
        """

        return float((num_qubits * depth) + gate_count)

    def profile(
        self,
        circuit: QuantumCircuit,
        circuit_id: str,
        backend: Any,
        optimization_level: int | None = None,
    ) -> CircuitProfile:
        """
        Transpile and profile a circuit for a selected backend.

        Args:
            circuit: Original Qiskit QuantumCircuit.
            circuit_id: CircuitRegistry identifier.
            backend: Qiskit BackendV1 or BackendV2 instance.
            optimization_level: Optional override (0-3).

        Returns:
            CircuitProfile containing original and transpiled metrics.

        Raises:
            CircuitProfilingError: If validation or transpilation fails.
        """

        if not isinstance(circuit, QuantumCircuit):
            raise CircuitProfilingError(
                "Expected a Qiskit QuantumCircuit."
            )

        if not isinstance(circuit_id, str) or not circuit_id.strip():
            raise CircuitProfilingError(
                "circuit_id must be a non-empty string."
            )

        if backend is None:
            raise CircuitProfilingError(
                "A Qiskit backend is required for profiling."
            )

        level = (
            self.optimization_level
            if optimization_level is None
            else optimization_level
        )

        if level not in (0, 1, 2, 3):
            raise CircuitProfilingError(
                "optimization_level must be between 0 and 3."
            )

        try:
            return self._create_profile(
                circuit=circuit,
                circuit_id=circuit_id,
                backend=backend,
                optimization_level=level,
            )

        except CircuitProfilingError:
            self.failed_count += 1
            raise

        except Exception as exc:
            self.failed_count += 1

            raise CircuitProfilingError(
                f"Profiling failed for circuit '{circuit_id}': {exc}"
            ) from exc

    def _create_profile(
        self,
        circuit: QuantumCircuit,
        circuit_id: str,
        backend: Any,
        optimization_level: int,
    ) -> CircuitProfile:

        # Extract original logical circuit properties.
        original_features = self.feature_extractor.extract(
            circuit,
            circuit_id,
        )

        # Transpile for the selected backend.
        # This produces a new circuit; the original is not modified.
        transpiled_circuit = transpile(
            circuit,
            backend=backend,
            optimization_level=optimization_level,
            seed_transpiler=self.seed_transpiler,
        )

        if not isinstance(transpiled_circuit, QuantumCircuit):
            raise CircuitProfilingError(
                "Transpilation did not return a QuantumCircuit."
            )

        transpiled_depth = transpiled_circuit.depth()

        transpiled_gate_count, transpiled_histogram = (
            self._count_transpiled_gates(transpiled_circuit)
        )

        basis_gates, basis_gates_source = self._get_basis_gates(
            backend,
            transpiled_circuit,
        )

        backend_name = self._get_backend_name(backend)
        backend_version = self._get_backend_version(backend)

        complexity_score = self._calculate_complexity_score(
            num_qubits=original_features.num_qubits,
            depth=original_features.circuit_depth,
            gate_count=original_features.total_gate_count,
        )

        profile = CircuitProfile(
            circuit_id=circuit_id,
            original_depth=original_features.circuit_depth,
            original_gate_count=original_features.total_gate_count,
            complexity_score=complexity_score,
            backend_name=backend_name,
            backend_version=backend_version,
            transpiled_depth=transpiled_depth,
            transpiled_gate_count=transpiled_gate_count,
            optimization_level=optimization_level,
            basis_gates=basis_gates,
            is_compatible=True,
            compatibility_notes=[
                "Transpilation succeeded for this backend.",
                "This does not guarantee job submission or runtime execution support.",
            ],
            profiled_at=datetime.now(timezone.utc).isoformat(),
            metadata={
                "profiler": "CircuitProfiler",
                "profiler_version": 1,
                "seed_transpiler": self.seed_transpiler,
                "basis_gates_source": basis_gates_source,
                "transpiled_gate_histogram": transpiled_histogram,
                "original_num_qubits": original_features.num_qubits,
                "transpiled_num_qubits": transpiled_circuit.num_qubits,
                "complexity_score_formula": (
                    "(original_num_qubits * original_depth) "
                    "+ original_gate_count"
                ),
                "complexity_score_is_heuristic": True,
            },
        )

        self.profile_count += 1

        return profile

    def reset_statistics(self) -> None:
        """Reset profiler counters."""

        self.profile_count = 0
        self.failed_count = 0
