from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class TaskStatus(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Allowed task lifecycle transitions
ALLOWED_TRANSITIONS = {
    TaskStatus.CREATED: {
        TaskStatus.QUEUED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.QUEUED: {
        TaskStatus.SCHEDULED,
        TaskStatus.CANCELLED,
        TaskStatus.FAILED,
    },
    TaskStatus.SCHEDULED: {
        TaskStatus.RUNNING,
        TaskStatus.QUEUED,
        TaskStatus.CANCELLED,
        TaskStatus.FAILED,
    },
    TaskStatus.RUNNING: {
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
    },
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.CANCELLED: set(),
}


@dataclass
class QTask:
    """
    Represents a quantum computing task in QCloudRL.

    QTask stores task information and a reference to a circuit.
    Circuit loading, parsing, and caching are delegated to CircuitService.

    The actual QuantumCircuit is loaded lazily when get_circuit()
    is called.
    """

    # Task identification
    task_id: str
    circuit_id: str
    circuit_ref: str
    circuit_format: str

    # Execution requirements
    shots: int = 1024
    priority: int = 0
    arrival_time: float = 0.0
    deadline: Optional[float] = None
    required_qubits: Optional[int] = None

    # Circuit metadata obtained from CircuitRecord
    circuit_metadata: dict = field(default_factory=dict)

    # Task lifecycle
    status: TaskStatus = TaskStatus.CREATED
    assigned_node_id: Optional[str] = None

    # Execution timestamps
    submitted_at: Optional[float] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    # Execution output
    failure_reason: Optional[str] = None
    result: Any = None

    # Internal CircuitService reference
    _circuit_service: Any = field(
        default=None,
        repr=False,
        compare=False,
    )

    # Internally held circuit reference after lazy loading
    _loaded_circuit: Any = field(
        default=None,
        repr=False,
        compare=False,
    )

    def __post_init__(self):
        """Validate and normalize task information."""

        # Validate identifiers
        for field_name in ("task_id", "circuit_id", "circuit_ref"):
            value = getattr(self, field_name)

            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"{field_name} must be a non-empty string."
                )

            setattr(self, field_name, value.strip())

        # Support both string and Enum circuit formats
        circuit_format = getattr(
            self.circuit_format,
            "value",
            self.circuit_format,
        )

        self.circuit_format = str(circuit_format).lower()

        if self.circuit_format not in {"qasm2", "qasm3"}:
            raise ValueError(
                "circuit_format must be 'qasm2' or 'qasm3'."
            )

        # Validate execution requirements
        if not isinstance(self.shots, int) or isinstance(self.shots, bool):
            raise ValueError("shots must be an integer.")

        if self.shots <= 0:
            raise ValueError("shots must be greater than zero.")

        if not isinstance(self.priority, int) or isinstance(self.priority, bool):
            raise ValueError("priority must be an integer.")

        if self.priority < 0:
            raise ValueError("priority cannot be negative.")

        if self.arrival_time < 0:
            raise ValueError("arrival_time cannot be negative.")

        if self.deadline is not None:
            if self.deadline < self.arrival_time:
                raise ValueError(
                    "deadline cannot be earlier than arrival_time."
                )

        if self.required_qubits is not None:
            if (
                not isinstance(self.required_qubits, int)
                or isinstance(self.required_qubits, bool)
                or self.required_qubits <= 0
            ):
                raise ValueError(
                    "required_qubits must be a positive integer."
                )

        # Normalize metadata
        if self.circuit_metadata is None:
            self.circuit_metadata = {}

        if not isinstance(self.circuit_metadata, dict):
            raise ValueError("circuit_metadata must be a dictionary.")

        # Normalize status
        if not isinstance(self.status, TaskStatus):
            self.status = TaskStatus(self.status)

    @property
    def circuit_loaded(self) -> bool:
        """Return whether this task currently holds a loaded circuit."""

        return self._loaded_circuit is not None

    def bind_circuit_service(self, circuit_service):
        """
        Connect this task to the existing CircuitService.

        This verifies that the circuit exists in the registry.
        It does not load or parse the circuit.
        """

        if circuit_service is None:
            raise ValueError("CircuitService cannot be None.")

        # CircuitService.get_record raises CircuitNotFoundError
        # if the requested circuit does not exist.
        circuit_service.get_record(self.circuit_id)

        self._circuit_service = circuit_service

    def get_circuit(self):
        """
        Lazily retrieve the QuantumCircuit through CircuitService.

        CircuitService handles parsing and its bounded LRU cache.
        """

        # Reuse the circuit already held by this task.
        if self._loaded_circuit is not None:
            return self._loaded_circuit

        if self._circuit_service is None:
            raise RuntimeError(
                "No CircuitService is bound to this task. "
                "Call bind_circuit_service() first."
            )

        # Use the actual CircuitService method.
        self._loaded_circuit = self._circuit_service.get_circuit(
            self.circuit_id
        )

        return self._loaded_circuit

    def transition(self, new_status: TaskStatus):
        """Validate and perform a task status transition."""

        if not isinstance(new_status, TaskStatus):
            new_status = TaskStatus(new_status)

        allowed = ALLOWED_TRANSITIONS[self.status]

        if new_status not in allowed:
            raise ValueError(
                f"Invalid task transition: "
                f"{self.status.value} -> {new_status.value}"
            )

        self.status = new_status

    def mark_queued(self, submitted_at: Optional[float] = None):
        """Move the task into the queue."""

        self.transition(TaskStatus.QUEUED)

        if submitted_at is not None:
            self.submitted_at = submitted_at

    def mark_scheduled(self, node_id: str):
        """Assign the task to a quantum computing node."""

        if not isinstance(node_id, str) or not node_id.strip():
            raise ValueError("node_id must be a non-empty string.")

        self.transition(TaskStatus.SCHEDULED)
        self.assigned_node_id = node_id.strip()

    def mark_running(self, start_time: float):
        """Mark the task as running."""

        if start_time < self.arrival_time:
            raise ValueError(
                "start_time cannot be earlier than arrival_time."
            )

        self.transition(TaskStatus.RUNNING)
        self.started_at = start_time

    def mark_completed(self, result: Any, completion_time: float):
        """Mark the task as successfully completed."""

        if self.started_at is None:
            raise ValueError(
                "Task must have a start time before completion."
            )

        if completion_time < self.started_at:
            raise ValueError(
                "completion_time cannot be earlier than started_at."
            )

        self.transition(TaskStatus.COMPLETED)

        self.result = result
        self.completed_at = completion_time

    def mark_failed(self, reason: str):
        """Mark the task as failed."""

        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Failure reason must be provided.")

        self.transition(TaskStatus.FAILED)
        self.failure_reason = reason.strip()

    def cancel(self):
        """Cancel the task if its current state allows cancellation."""

        self.transition(TaskStatus.CANCELLED)

    def to_dict(self) -> dict:
        """
        Convert task information into a serializable dictionary.

        The actual QuantumCircuit, CircuitService, and execution result
        are intentionally excluded.
        """

        return {
            "task_id": self.task_id,
            "circuit_id": self.circuit_id,
            "circuit_ref": self.circuit_ref,
            "circuit_format": self.circuit_format,
            "shots": self.shots,
            "priority": self.priority,
            "arrival_time": self.arrival_time,
            "deadline": self.deadline,
            "required_qubits": self.required_qubits,
            "circuit_metadata": self.circuit_metadata.copy(),
            "status": self.status.value,
            "assigned_node_id": self.assigned_node_id,
            "submitted_at": self.submitted_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "failure_reason": self.failure_reason,
            "circuit_loaded": self.circuit_loaded,
        }

    def __repr__(self):
        return (
            f"QTask("
            f"task_id={self.task_id!r}, "
            f"circuit_id={self.circuit_id!r}, "
            f"status={self.status.value!r}, "
            f"shots={self.shots}, "
            f"priority={self.priority}"
            f")"
        )