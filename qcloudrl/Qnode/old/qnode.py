
import time

from qcloudrl.QTask.QTask import TaskStatus
from qcloudrl.Qnode.models import QNodeConfig, NodeStatus
from qcloudrl.Qnode.backend_factory import BackendFactory
from qcloudrl.Qnode.executor import QNodeExecutor


class QNode:
    """
    Represents one quantum resource in QCloudRL.

    Each QNode is associated with one IBM Fake Backend.
    """

    def __init__(
        self,
        node_id: str,
        backend_name: str,
        circuit_service,
        backend=None,
    ):

        self.circuit_service = circuit_service

        # Create or accept the backend.
        if backend is None:
            backend = BackendFactory.create(backend_name)

        self.backend = backend

        # Read backend resource properties.
        num_qubits = backend.num_qubits

        backend_name_value = backend.name
        if callable(backend_name_value):
            backend_name_value = backend_name_value()

        # Read basis gates where available.
        basis_gates = getattr(backend, "operation_names", None)

        if basis_gates is None:
            try:
                basis_gates = backend.configuration().basis_gates
            except (AttributeError, Exception):
                basis_gates = None

        # Read connectivity where available.
        coupling_map = getattr(backend, "coupling_map", None)

        if coupling_map is not None:
            try:
                coupling_map = coupling_map.get_edges()
            except AttributeError:
                pass

        self.config = QNodeConfig(
            node_id=node_id,
            backend_name=str(backend_name_value),
            num_qubits=num_qubits,
            simulator=True,
            available=True,
            basis_gates=(
                list(basis_gates)
                if basis_gates is not None
                else None
            ),
            coupling_map=(
                list(coupling_map)
                if coupling_map is not None
                else None
            ),
        )

        self.status = NodeStatus.IDLE

        # Execution engine.
        self.executor = QNodeExecutor(self.backend)

        self.total_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0

    @property
    def node_id(self):
        return self.config.node_id

    @property
    def num_qubits(self):
        return self.config.num_qubits

    @property
    def is_available(self):
        return (
            self.config.available
            and self.status == NodeStatus.IDLE
        )

    def can_execute(self, task):
        """
        Check whether this QNode can execute a QTask.
        """

        if not self.is_available:
            return False

        # Use task metadata if available.
        required_qubits = task.required_qubits

        # If metadata does not contain qubit count,
        # load the circuit only when checking execution.
        if required_qubits is None:
            circuit = task.get_circuit()
            required_qubits = circuit.num_qubits

        return required_qubits <= self.num_qubits

    def execute_task(self, task):
        """
        Execute a scheduled QTask on this QNode.

        The task must already be in SCHEDULED state.
        """

        if task.status != TaskStatus.SCHEDULED:
            raise ValueError(
                f"Task {task.task_id} must be SCHEDULED "
                f"before execution. Current status: "
                f"{task.status.value}"
            )

        if not self.is_available:
            raise RuntimeError(
                f"QNode {self.node_id} is not available"
            )

        self.status = NodeStatus.BUSY
        self.total_tasks += 1

        try:
            # Start the task.
            start_time = time.time()
            task.mark_running(start_time=start_time)

            # Get the actual circuit from CircuitService.
            circuit = task.get_circuit()

            # Validate resource capacity.
            if circuit.num_qubits > self.num_qubits:
                raise ValueError(
                    f"Task requires {circuit.num_qubits} qubits, "
                    f"but {self.node_id} supports "
                    f"{self.num_qubits}"
                )

            # Execute circuit.
            execution_result = self.executor.execute(
                circuit=circuit,
                shots=task.shots,
            )

            if not execution_result["success"]:
                raise RuntimeError(
                    "Quantum circuit execution failed"
                )

            # Store result in QTask.
            completion_time = time.time()

            task.mark_completed(
                result=execution_result,
                completion_time=completion_time,
            )

            self.completed_tasks += 1

            return execution_result

        except Exception as error:

            self.failed_tasks += 1

            if task.status == TaskStatus.RUNNING:
                task.mark_failed(str(error))

            raise

        finally:
            # Release the resource.
            self.status = NodeStatus.IDLE

    def get_resource_info(self):
        """Return information about this quantum resource."""

        return {
            "node_id": self.node_id,
            "backend_name": self.config.backend_name,
            "num_qubits": self.num_qubits,
            "status": self.status.value,
            "available": self.is_available,
            "simulator": self.config.simulator,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "basis_gates": self.config.basis_gates,
            "coupling_map": self.config.coupling_map,
        }
