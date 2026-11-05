
import time

from qiskit import transpile
from qiskit_aer import AerSimulator


class QNodeExecutor:
    """
    Executes quantum circuits using AerSimulator
    configured with IBM Fake Backend properties.
    """

    def __init__(self, fake_backend):
        self.fake_backend = fake_backend

        # Construct a local simulator using the Fake Backend
        # configuration and noise model where supported.
        self.simulator = AerSimulator.from_backend(
            fake_backend
        )

    def execute(self, circuit, shots: int = 1024):
        """
        Transpile and execute a quantum circuit.

        Returns counts and execution metadata.
        """

        if shots <= 0:
            raise ValueError("shots must be greater than zero")

        # Check backend capacity.
        if circuit.num_qubits > self.fake_backend.num_qubits:
            raise ValueError(
                f"Circuit requires {circuit.num_qubits} qubits, "
                f"but backend supports only "
                f"{self.fake_backend.num_qubits}"
            )

        start_time = time.perf_counter()

        # Compile circuit for the selected Fake Backend.
        transpiled_circuit = transpile(
            circuit,
            backend=self.fake_backend,
            optimization_level=1,
        )

        # Execute on the local Aer simulator.
        job = self.simulator.run(
            transpiled_circuit,
            shots=shots,
        )

        result = job.result()
        counts = result.get_counts()

        elapsed_time = time.perf_counter() - start_time

        return {
            "success": result.success,
            "counts": counts,
            "shots": shots,
            "backend_name": str(self.fake_backend.name),
            "elapsed_seconds": elapsed_time,
            "circuit_qubits": circuit.num_qubits,
            "transpiled_depth": transpiled_circuit.depth(),
            "transpiled_size": transpiled_circuit.size(),
            "transpiled_circuit": transpiled_circuit,
        }
