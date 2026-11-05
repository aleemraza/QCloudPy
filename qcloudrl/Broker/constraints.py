
class QubitInsufficientError(Exception):
    """Raised when a circuit requires more qubits than a node provides."""
    pass


class NodeUnavailableError(Exception):
    """Raised when a quantum node is not available."""
    pass


class TaskCompatibilityError(Exception):
    """Raised when a task cannot be validated for a quantum node."""
    pass


class ConstraintManager:
    """Validates task and quantum node compatibility."""

    NODE_UNAVAILABLE = "NODE_UNAVAILABLE"
    INSUFFICIENT_QUBITS = "INSUFFICIENT_QUBITS"
    CIRCUIT_UNAVAILABLE = "CIRCUIT_UNAVAILABLE"

    @staticmethod
    def check(task, node, check_availability=True):
        """
        Check whether a task is compatible with a quantum node.

        Returns:
            (True, None) if compatible.
            (False, error_code) otherwise.
        """

        # 1. Check node availability when required.
        if check_availability and not node.is_available:
            return False, ConstraintManager.NODE_UNAVAILABLE

        # 2. Get required circuit qubits.
        required_qubits = task.required_qubits

        # 3. Resolve unknown qubit requirements lazily.
        if required_qubits is None:
            try:
                circuit = task.get_circuit()
                required_qubits = circuit.num_qubits
            except Exception:
                return False, ConstraintManager.CIRCUIT_UNAVAILABLE

        # 4. Validate the node's capacity.
        if required_qubits > node.num_qubits:
            return False, ConstraintManager.INSUFFICIENT_QUBITS

        return True, None

    @staticmethod
    def validate(task, node, check_availability=True):
        """
        Validate compatibility.

        Raises a specific exception if the task cannot be assigned.
        """

        compatible, error_code = ConstraintManager.check(
            task=task,
            node=node,
            check_availability=check_availability,
        )

        if compatible:
            return True

        if error_code == ConstraintManager.NODE_UNAVAILABLE:
            raise NodeUnavailableError(
                f"Node {node.node_id} is unavailable."
            )

        if error_code == ConstraintManager.INSUFFICIENT_QUBITS:
            raise QubitInsufficientError(
                f"Task {task.task_id} requires more qubits "
                f"than node {node.node_id} provides. "
                f"Required: {task.required_qubits}, "
                f"Available: {node.num_qubits}."
            )

        if error_code == ConstraintManager.CIRCUIT_UNAVAILABLE:
            raise TaskCompatibilityError(
                f"Could not load or inspect the circuit "
                f"for task {task.task_id}."
            )

        raise TaskCompatibilityError(
            f"Task {task.task_id} is incompatible with "
            f"node {node.node_id}. Error: {error_code}"
        )



