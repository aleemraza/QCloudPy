from __future__ import annotations
from qiskit import QuantumCircuit
from .models import CircuitProfile
NON_GATE_OPERATIONS = {
    "barrier", "measure", "reset", "delay",
}


class CircuitProfiler:
    """Extracts structural circuit features; it does not estimate QPU fidelity/time."""

    def profile(self, circuit: QuantumCircuit, circuit_id: str | None = None) -> CircuitProfile:
        operation_counts: dict[str, int] = {}
        single_qubit = 0
        multi_qubit = 0
        measurements = 0

        for instruction in circuit.data:
            operation = instruction.operation
            name = operation.name
            operation_counts[name] = operation_counts.get(name, 0) + 1

            if name == "measure":
                measurements += 1

            if name not in NON_GATE_OPERATIONS:
                num_qargs = len(instruction.qubits)
                if num_qargs == 1:
                    single_qubit += 1
                elif num_qargs > 1:
                    multi_qubit += 1

        total_gates = single_qubit + multi_qubit
        ratio = multi_qubit / total_gates if total_gates else 0.0

        return CircuitProfile(
            circuit_id=circuit_id,
            num_qubits=circuit.num_qubits,
            num_clbits=circuit.num_clbits,
            depth=circuit.depth() or 0,
            size=circuit.size(),
            operation_counts=operation_counts,
            num_single_qubit_gates=single_qubit,
            num_multi_qubit_gates=multi_qubit,
            multi_qubit_gate_ratio=ratio,
            num_measurements=measurements,
            num_parameters=len(circuit.parameters),
        )
