import time

from qiskit import transpile
from qiskit_aer import AerSimulator


class QNodeExecutor:
    """
    Executes quantum circuits using AerSimulator
    configured from an IBM Fake Backend.

    Execution flow:
        QuantumCircuit
            -> Transpilation
            -> AerSimulator
            -> Measurement Counts
    """

    def __init__(self, fake_backend):
        if fake_backend is None:
            raise ValueError("Fake Backend cannot be None.")

        self.fake_backend = fake_backend

        # Build local simulator using backend configuration
        # and noise properties supported by Aer.
        self.simulator = AerSimulator.from_backend(fake_backend)

    @staticmethod
    def _get_backend_name(backend):
        """Handle backend names exposed as properties or methods."""

        name = getattr(backend, "name", None)

        if callable(name):
            name = name()

        if name is None:
            return backend.__class__.__name__

        return str(name)

    def execute(
        self,
        circuit,
        shots: int = 1024,
        optimization_level: int = 1,
    ):
        """
        Transpile and execute a QuantumCircuit.

        Returns:
            Dictionary containing execution results and metrics.
        """

        if circuit is None:
            raise ValueError("Circuit cannot be None.")

        if not isinstance(shots, int) or isinstance(shots, bool) or shots <= 0:
            raise ValueError("shots must be a positive integer.")

        if optimization_level not in (0, 1, 2, 3):
            raise ValueError(
                "optimization_level must be between 0 and 3."
            )

        backend_qubits = self.fake_backend.num_qubits

        if circuit.num_qubits > backend_qubits:
            raise ValueError(
                f"Circuit requires {circuit.num_qubits} qubits, "
                f"but backend supports only {backend_qubits}."
            )

        start_time = time.perf_counter()

        # Compile for the selected Fake Backend.
        transpiled_circuit = transpile(
            circuit,
            backend=self.fake_backend,
            optimization_level=optimization_level,
        )

        transpilation_time = time.perf_counter() - start_time

        execution_start = time.perf_counter()

        # Execute locally using AerSimulator.
        job = self.simulator.run(
            transpiled_circuit,
            shots=shots,
        )

        result = job.result()

        execution_time = time.perf_counter() - execution_start
        elapsed_time = time.perf_counter() - start_time

        if not result.success:
            raise RuntimeError("AerSimulator execution was unsuccessful.")

        counts = result.get_counts()

        return {
            "success": result.success,
            "counts": counts,
            "shots": shots,
            "backend_name": self._get_backend_name(self.fake_backend),
            "elapsed_seconds": elapsed_time,
            "transpilation_seconds": transpilation_time,
            "execution_seconds": execution_time,
            "circuit_qubits": circuit.num_qubits,
            "circuit_depth": circuit.depth(),
            "transpiled_depth": transpiled_circuit.depth(),
            "transpiled_size": transpiled_circuit.size(),
            "transpiled_circuit": transpiled_circuit,
        }