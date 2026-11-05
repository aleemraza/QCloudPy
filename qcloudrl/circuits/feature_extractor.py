from __future__ import annotations
from collections import Counter
from typing import Iterable
from qiskit import QuantumCircuit
from .models import CircuitFeatures
class CircuitFeatureExtractionError(Exception):
    """Raised when circuit features cannot be extracted."""
class CircuitFeatureExtractor:
    """
    Extract structural features from an original Qiskit QuantumCircuit.

    This class does not:
    - Transpile the circuit.
    - Map logical qubits to physical backend qubits.
    - Estimate hardware execution time.
    - Estimate backend noise or fidelity.

    Measurements, resets, barriers, delays, and control-flow instructions
    are excluded from computational gate counts.
    """

    NON_GATE_OPERATIONS = {
        "measure",
        "reset",
        "barrier",
        "delay",
    }

    CONTROL_FLOW_OPERATIONS = {
        "if_else",
        "while_loop",
        "for_loop",
        "switch_case",
    }

    def extract(
        self,
        circuit: QuantumCircuit,
        circuit_id: str,
    ) -> CircuitFeatures:
        """
        Extract structural features from a quantum circuit.

        Args:
            circuit: Original Qiskit QuantumCircuit.
            circuit_id: ID assigned by CircuitRegistry.

        Returns:
            CircuitFeatures containing the extracted properties.
        """
        if not isinstance(circuit, QuantumCircuit):
            raise CircuitFeatureExtractionError(
                "Expected a Qiskit QuantumCircuit instance."
            )

        if not isinstance(circuit_id, str) or not circuit_id.strip():
            raise CircuitFeatureExtractionError(
                "circuit_id must be a non-empty string."
            )

        try:
            return self._extract_features(circuit, circuit_id)

        except CircuitFeatureExtractionError:
            raise

        except Exception as exc:
            raise CircuitFeatureExtractionError(
                f"Failed to extract features for circuit "
                f"'{circuit_id}': {exc}"
            ) from exc

    def _extract_features(
        self,
        circuit: QuantumCircuit,
        circuit_id: str,
    ) -> CircuitFeatures:

        gate_histogram: Counter[str] = Counter()
        interaction_edges: set[tuple[int, int]] = set()

        single_qubit_gate_count = 0
        two_qubit_gate_count = 0
        multi_qubit_gate_count = 0

        measurement_count = 0
        reset_count = 0

        measurement_positions: list[int] = []
        conditional_operations = False

        for position, instruction in enumerate(circuit.data):

            operation = instruction.operation
            operation_name = operation.name.lower()

            qubits = instruction.qubits
            qubit_indices = [
                circuit.find_bit(qubit).index
                for qubit in qubits
            ]

            # Count measurement operations separately.
            if operation_name == "measure":
                measurement_count += 1
                measurement_positions.append(position)
                continue

            # Count reset operations separately.
            if operation_name == "reset":
                reset_count += 1
                continue

            # These instructions are not computational gates.
            if operation_name in {"barrier", "delay"}:
                continue

            # Detect conditional and control-flow operations.
            if self._is_conditional_operation(operation):
                conditional_operations = True

            # Control-flow instructions are not ordinary gates.
            if operation_name in self.CONTROL_FLOW_OPERATIONS:
                continue

            # Ignore instructions without quantum operands.
            number_of_qubits = len(qubits)

            if number_of_qubits == 0:
                continue

            # Count computational gates.
            gate_histogram[operation_name] += 1

            if number_of_qubits == 1:
                single_qubit_gate_count += 1

            elif number_of_qubits == 2:
                two_qubit_gate_count += 1

            else:
                multi_qubit_gate_count += 1

            # Build the logical qubit interaction graph.
            # A multi-qubit gate connects every pair of participating qubits.
            if number_of_qubits >= 2:
                for i in range(number_of_qubits):
                    for j in range(i + 1, number_of_qubits):
                        edge = tuple(
                            sorted(
                                (
                                    qubit_indices[i],
                                    qubit_indices[j],
                                )
                            )
                        )
                        interaction_edges.add(edge)

        # A measurement is considered mid-circuit when a later
        # quantum operation appears after it in circuit instruction order.
        requires_mid_circuit_measurement = (
            self._has_mid_circuit_measurement(circuit, measurement_positions)
        )

        requires_conditional_operations = conditional_operations

        requires_dynamic_circuits = (
            requires_mid_circuit_measurement
            or requires_conditional_operations
        )

        total_gate_count = sum(gate_histogram.values())

        required_gates = sorted(gate_histogram.keys())

        # Qiskit native circuit depth includes the circuit's instructions.
        circuit_depth = circuit.depth()

        return CircuitFeatures(
            circuit_id=circuit_id,
            num_qubits=circuit.num_qubits,
            num_clbits=circuit.num_clbits,
            circuit_width=circuit.num_qubits + circuit.num_clbits,
            circuit_depth=circuit_depth,
            total_gate_count=total_gate_count,
            single_qubit_gate_count=single_qubit_gate_count,
            two_qubit_gate_count=two_qubit_gate_count,
            multi_qubit_gate_count=multi_qubit_gate_count,
            measurement_count=measurement_count,
            reset_count=reset_count,
            gate_histogram=dict(sorted(gate_histogram.items())),
            required_gates=required_gates,
            interaction_edges=sorted(interaction_edges),
            requires_dynamic_circuits=requires_dynamic_circuits,
            requires_mid_circuit_measurement=(
                requires_mid_circuit_measurement
            ),
            requires_conditional_operations=(
                requires_conditional_operations
            ),
            metadata={
                "feature_extractor": "CircuitFeatureExtractor",
                "feature_version": 1,
                "gate_count_excludes": [
                    "measure",
                    "reset",
                    "barrier",
                    "delay",
                    "control_flow",
                ],
            },
        )

    @staticmethod
    def _is_conditional_operation(operation) -> bool:
        """
        Detect Qiskit conditional and control-flow instructions.

        Supports both operation.condition (where available) and
        standard Qiskit control-flow operation names.
        """
        operation_name = operation.name.lower()

        if operation_name in CircuitFeatureExtractor.CONTROL_FLOW_OPERATIONS:
            return True

        condition = getattr(operation, "condition", None)

        return condition is not None

    @staticmethod
    def _has_mid_circuit_measurement(
        circuit: QuantumCircuit,
        measurement_positions: Iterable[int],
    ) -> bool:
        """
        Check whether any measurement is followed by a later
        quantum operation.

        Final measurements alone do not require dynamic circuits.
        """
        if not measurement_positions:
            return False

        for measurement_position in measurement_positions:

            for later_instruction in circuit.data[measurement_position + 1:]:

                operation = later_instruction.operation
                operation_name = operation.name.lower()

                if operation_name in {
                    "measure",
                    "barrier",
                    "delay",
                }:
                    continue

                if len(later_instruction.qubits) > 0:
                    return True

        return False
