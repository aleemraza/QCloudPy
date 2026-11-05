from qcloudrl.QTask.QTask import TaskStatus
from qcloudrl.Qnode.models import QNodeConfig, NodeStatus
from qcloudrl.Qnode.backend_factory import BackendFactory
from qcloudrl.Qnode.executor import QNodeExecutor


class QNode:
    """
    Represents one quantum computing resource in QCloudRL.

    Each QNode is associated with one IBM Fake Backend
    and executes circuits through a local AerSimulator.
    """

    def __init__(
        self,
        node_id: str,
        backend_name: str,
        circuit_service,
        backend=None,
    ):
        if circuit_service is None:
            raise ValueError("CircuitService cannot be None.")

        self.circuit_service = circuit_service

        # Create backend or use the supplied backend.
        if backend is None:
            backend = BackendFactory.create(backend_name)

        self.backend = backend

        # Read actual backend properties.
        num_qubits = backend.num_qubits

        actual_backend_name = self._get_backend_name(backend)

        # Read supported operations.
        basis_gates = getattr(backend, "operation_names", None)

        if basis_gates is None:
            try:
                basis_gates = backend.configuration().basis_gates
            except (AttributeError, Exception):
                basis_gates = None

        # Read connectivity information.
        coupling_map = getattr(backend, "coupling_map", None)

        if coupling_map is not None:
            try:
                coupling_map = coupling_map.get_edges()
            except AttributeError:
                pass

        self.config = QNodeConfig(
            node_id=node_id,
            backend_name=actual_backend_name,
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

        # Initialize execution engine.
        self.executor = QNodeExecutor(self.backend)

        # Execution statistics.
        self.total_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0

        self.total_execution_time = 0.0

    @staticmethod
    def _get_backend_name(backend):
        """Handle backend names exposed as methods or properties."""

        name = getattr(backend, "name", None)

        if callable(name):
            name = name()

        if name is None:
            return backend.__class__.__name__

        return str(name)

    @property
    def node_id(self):
        return self.config.node_id

    @property
    def backend_name(self):
        return self.config.backend_name

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
        Check whether this node has enough resources
        to execute the given QTask.

        If required_qubits is unknown, the circuit is
        loaded lazily through QTask and CircuitService.
        """

        if not self.is_available:
            return False

        if task.status in {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.RUNNING,
        }:
            return False

        required_qubits = task.required_qubits

        if required_qubits is None:
            circuit = task.get_circuit()
            required_qubits = circuit.num_qubits

        return required_qubits <= self.num_qubits

    def execute_task(self, task, simulation_time=None):
        """
        Execute a scheduled QTask on this QNode.

        Args:
            task: QTask instance in SCHEDULED state.
            simulation_time: Optional simulation start time.

        Returns:
            Execution result dictionary.
        """

        if task.status != TaskStatus.SCHEDULED:
            raise ValueError(
                f"Task {task.task_id} must be SCHEDULED "
                f"before execution. Current status: "
                f"{task.status.value}"
            )

        if not self.is_available:
            raise RuntimeError(
                f"QNode {self.node_id} is not available."
            )

        # Ensure the task uses this node's CircuitService.
        # This verifies the circuit record without parsing it.
        task.bind_circuit_service(self.circuit_service)

        self.status = NodeStatus.BUSY
        self.total_tasks += 1

        try:
            # Use simulation time consistently.
            if simulation_time is None:
                start_time = task.arrival_time
            else:
                start_time = float(simulation_time)

            if start_time < task.arrival_time:
                raise ValueError(
                    "simulation_time cannot be earlier "
                    "than the task arrival time."
                )

            # Move task to RUNNING.
            task.mark_running(start_time=start_time)

            # Get the circuit through CircuitService.
            # CircuitService handles loading and LRU caching.
            circuit = task.get_circuit()

            # Check actual circuit capacity.
            if circuit.num_qubits > self.num_qubits:
                raise ValueError(
                    f"Task requires {circuit.num_qubits} qubits, "
                    f"but {self.node_id} supports "
                    f"{self.num_qubits}."
                )

            # Execute quantum circuit.
            execution_result = self.executor.execute(
                circuit=circuit,
                shots=task.shots,
            )

            if not execution_result["success"]:
                raise RuntimeError(
                    "Quantum circuit execution failed."
                )

            # Use elapsed execution time to advance simulation time.
            elapsed = execution_result["elapsed_seconds"]
            completion_time = start_time + elapsed

            # Update task lifecycle.
            task.mark_completed(
                result=execution_result,
                completion_time=completion_time,
            )

            self.completed_tasks += 1
            self.total_execution_time += elapsed

            return execution_result

        except Exception as error:

            self.failed_tasks += 1

            # Mark the task failed if its current lifecycle
            # state allows the transition.
            if task.status in {
                TaskStatus.SCHEDULED,
                TaskStatus.RUNNING,
            }:
                task.mark_failed(str(error))

            raise

        finally:
            # Always release the node after execution.
            self.status = NodeStatus.IDLE

    def set_offline(self):
        """Make this node unavailable."""

        if self.status == NodeStatus.BUSY:
            raise RuntimeError(
                "Cannot take a busy node offline."
            )

        self.config.available = False
        self.status = NodeStatus.OFFLINE

    def set_online(self):
        """Make this node available again."""

        if self.status == NodeStatus.BUSY:
            raise RuntimeError(
                "Cannot change availability while node is busy."
            )

        self.config.available = True
        self.status = NodeStatus.IDLE

    def get_resource_info(self):
        """Return the node's current resource information."""

        return {
            "node_id": self.node_id,
            "backend_name": self.backend_name,
            "num_qubits": self.num_qubits,
            "status": self.status.value,
            "available": self.is_available,
            "simulator": self.config.simulator,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "total_execution_time": self.total_execution_time,
            "basis_gates": self.config.basis_gates,
            "coupling_map": self.config.coupling_map,
        }