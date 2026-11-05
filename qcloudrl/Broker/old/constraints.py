class QubitInsufficientError(Exception):
    pass


class NodeUnavailableError(Exception):
    pass


class TaskCompatibilityError(Exception):
    pass


class ConstraintManager:

    @staticmethod
    def check(task, node, check_availability=True):

        if check_availability and not node.is_available:
            return False, "NODE_UNAVAILABLE"

        required_qubits = task.required_qubits

        if required_qubits is not None:
            if required_qubits > node.num_qubits:
                return False, "INSUFFICIENT_QUBITS"

        return True, None

    @staticmethod
    def validate(task, node, check_availability=True):

        compatible, error_code = ConstraintManager.check(
            task,
            node,
            check_availability=check_availability,
        )

        if not compatible:

            if error_code == "NODE_UNAVAILABLE":
                raise NodeUnavailableError(
                    f"QNode {node.node_id} is unavailable."
                )

            if error_code == "INSUFFICIENT_QUBITS":
                raise QubitInsufficientError(
                    f"Task {task.task_id} requires "
                    f"{task.required_qubits} qubits, but "
                    f"QNode {node.node_id} has {node.num_qubits}."
                )

        return True