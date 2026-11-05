from __future__ import annotations
from time import perf_counter
from qiskit import QuantumCircuit
from .models import AerExecutionResult


class AerExecutor:
    """Optional local execution adapter backed by qiskit-aer."""

    def __init__(self, backend_name: str = "aer_simulator"):
        try:
            from qiskit_aer import AerSimulator
        except ImportError as exc:
            raise ImportError(
                "Qiskit Aer is required. Install it with: pip install qiskit-aer"
            ) from exc
        self.backend = AerSimulator()
        self.backend_name = backend_name

    @staticmethod
    def _prepare_measurements(
        circuit: QuantumCircuit,
        auto_measure: bool,
    ) -> QuantumCircuit:
        executable = circuit.copy()
        has_measurements = any(item.operation.name == "measure" for item in executable.data)

        if not has_measurements:
            if not auto_measure:
                raise ValueError(
                    "Circuit has no measurements. Set auto_measure=True "
                    "or provide a measured circuit."
                )
            # Only add all-qubit measurements when there are no existing classical
            # registers/measurement operations. This avoids silently changing a
            # circuit with a deliberate partial measurement layout.
            if executable.num_clbits != 0:
                raise ValueError(
                    "Circuit has classical bits but no measurement operations. "
                    "Add measurements explicitly or revise the circuit."
                )
            executable.measure_all()

        return executable

    def run(
        self,
        circuit: QuantumCircuit,
        shots: int = 1024,
        auto_measure: bool = True,
    ) -> AerExecutionResult:
        if shots <= 0:
            raise ValueError("shots must be a positive integer")

        executable = self._prepare_measurements(circuit, auto_measure)
        started = perf_counter()
        job = self.backend.run(executable, shots=shots)
        result = job.result()
        elapsed = perf_counter() - started
        counts = result.get_counts()
        if isinstance(counts, list):
            # Current Aer commonly returns one dictionary for one circuit.
            counts = counts[0]

        return AerExecutionResult(
            counts={str(key): int(value) for key, value in counts.items()},
            shots=shots,
            elapsed_seconds=elapsed,
            backend_name=self.backend_name,
            success=bool(result.success),
        )
