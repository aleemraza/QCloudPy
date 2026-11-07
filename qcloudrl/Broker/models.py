
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Assignment:
    """Records a task assignment to a quantum node."""

    task_id: str
    node_id: str
    assigned_at: float
    status: str = "assigned"


# @dataclass
# class BrokerStats:
#     """Tracks overall Broker performance."""

#     submitted: int = 0
#     assigned: int = 0
#     completed: int = 0
#     failed: int = 0
#     rejected: int = 0

#     def to_dict(self) -> dict:
#         return {
#             "submitted": self.submitted,
#             "assigned": self.assigned,
#             "completed": self.completed,
#             "failed": self.failed,
#             "rejected": self.rejected,
#         }

#     def reset(self) -> None:
#         self.submitted = 0
#         self.assigned = 0
#         self.completed = 0
#         self.failed = 0
#         self.rejected = 0

@dataclass
class BrokerStats:
    """Tracks task admission, assignment, and execution statistics."""

    submitted: int = 0
    accepted: int = 0
    rejected: int = 0

    assigned: int = 0

    completed: int = 0
    failed: int = 0

    assignment_errors: int = 0

    def to_dict(self) -> dict:
        return {
            "submitted": self.submitted,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "assigned": self.assigned,
            "completed": self.completed,
            "failed": self.failed,
            "assignment_errors": self.assignment_errors,
        }

    def reset(self) -> None:
        self.submitted = 0
        self.accepted = 0
        self.rejected = 0
        self.assigned = 0
        self.completed = 0
        self.failed = 0
        self.assignment_errors = 0


@dataclass
class ExecutionRecord:
    """Stores the execution history of one quantum task."""

    task_id: str

    node_id: Optional[str] = None

    submitted_at: Optional[float] = None
    assigned_at: Optional[float] = None

    start_time: Optional[float] = None
    finish_time: Optional[float] = None

    waiting_time: float = 0.0
    execution_time: float = 0.0

    status: str = "pending"

    result: Optional[Any] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "node_id": self.node_id,
            "submitted_at": self.submitted_at,
            "assigned_at": self.assigned_at,
            "start_time": self.start_time,
            "finish_time": self.finish_time,
            "waiting_time": self.waiting_time,
            "execution_time": self.execution_time,
            "status": self.status,
            "result": self.result,
            "error": self.error,
        }
