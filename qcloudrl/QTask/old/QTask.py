
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class TaskStatus(str, Enum):
    """Lifecycle states of a quantum job."""

    CREATED = "created"
    QUEUED = "queued"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Define which status transitions are allowed.
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
    Represents one quantum computing job.

    A QTask stores job information and a reference to a circuit.
    It does not load the actual circuit during construction.
    """

    # Job identity
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

    # Circuit information obtained from the registry
    circuit_metadata: dict = field(default_factory=dict)

    # Job lifecycle
    status: TaskStatus = TaskStatus.CREATED

    # Scheduling and execution information
    assigned_node_id: Optional[str] = None
    submitted_at: Optional[float] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    # Execution result
    failure_reason: Optional[str] = None
    result: Any = None

    # Internal references; not included in task serialization
    _circuit_service: Any = field(
        default=None,
        repr=False,
        compare=False,
    )
    _loaded_circuit: Any = field(
        default=None,
        repr=False,
        compare=False,
    )

    def __post_init__(self):
        """Validate the task when it is created."""

        if not self.task_id:
            raise ValueError("task_id cannot be empty")

        if not self.circuit_id:
            raise ValueError("circuit_id cannot be empty")

        if not self.circuit_ref:
            raise ValueError("circuit_ref cannot be empty")

        if self.circuit_format.lower() not in {"qasm2", "qasm3"}:
            raise ValueError("circuit_format must be qasm2 or qasm3")

        if self.shots <= 0:
            raise ValueError("shots must be greater than zero")

        if self.priority < 0:
            raise ValueError("priority cannot be negative")

        if self.arrival_time < 0:
            raise ValueError("arrival_time cannot be negative")

        if self.deadline is not None:
            if self.deadline < self.arrival_time:
                raise ValueError(
                    "deadline cannot be earlier than arrival_time"
                )

        if self.required_qubits is not None:
            if self.required_qubits <= 0:
                raise ValueError(
                    "required_qubits must be greater than zero"
                )

        # Normalize format.
        self.circuit_format = self.circuit_format.lower()

    @property
    def circuit_loaded(self) -> bool:
        """Check whether the actual circuit is loaded in memory."""
        return self._loaded_circuit is not None

    def bind_circuit_service(self, circuit_service):
        """
        Connect this task to CircuitService.

        This only validates the circuit reference.
        It does not load the circuit.
        """

        record = circuit_service.get_record(self.circuit_id)

        if record is None:
            raise ValueError(
                f"Circuit {self.circuit_id} is not registered"
            )

        self._circuit_service = circuit_service

    def get_circuit(self):
        """
        Load the actual QuantumCircuit only when requested.

        The loaded circuit is cached inside this task.
        """

        if self._loaded_circuit is not None:
            return self._loaded_circuit

        if self._circuit_service is None:
            raise RuntimeError(
                "No CircuitService is connected to this task"
            )

        self._loaded_circuit = self._circuit_service.load(
            self.circuit_id
        )

        return self._loaded_circuit

    def transition(self, new_status: TaskStatus):
        """Change the task status after validating the transition."""

        if not isinstance(new_status, TaskStatus):
            new_status = TaskStatus(new_status)

        allowed = ALLOWED_TRANSITIONS[self.status]

        if new_status not in allowed:
            raise ValueError(
                f"Invalid task transition: "
                f"{self.status.value} -> {new_status.value}"
            )

        self.status = new_status

    def mark_queued(self):
        self.transition(TaskStatus.QUEUED)

    def mark_scheduled(self, node_id: str):
        if not node_id:
            raise ValueError("node_id cannot be empty")

        self.assigned_node_id = node_id
        self.transition(TaskStatus.SCHEDULED)

    def mark_running(self, start_time: Optional[float] = None):
        self.transition(TaskStatus.RUNNING)
        self.started_at = start_time

    def mark_completed(
        self,
        result: Any = None,
        completion_time: Optional[float] = None,
    ):
        self.transition(TaskStatus.COMPLETED)
        self.result = result
        self.completed_at = completion_time

    def mark_failed(self, reason: str):
        self.transition(TaskStatus.FAILED)
        self.failure_reason = reason

    def cancel(self):
        self.transition(TaskStatus.CANCELLED)

    def to_dict(self) -> dict:
        """
        Return serializable task information.

        The actual QuantumCircuit and CircuitService are excluded.
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
            "circuit_metadata": self.circuit_metadata,
            "status": self.status.value,
            "assigned_node_id": self.assigned_node_id,
            "submitted_at": self.submitted_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "failure_reason": self.failure_reason,
        }
