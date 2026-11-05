from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class Assignment:
    task_id: str
    node_id: str
    assigned_at: float
    status: str = "assigned"


@dataclass
class BrokerStats:
    submitted: int = 0
    assigned: int = 0
    completed: int = 0
    failed: int = 0
    rejected: int = 0

    def to_dict(self):
        return {
            "submitted": self.submitted,
            "assigned": self.assigned,
            "completed": self.completed,
            "failed": self.failed,
            "rejected": self.rejected,
        }


@dataclass
class ExecutionRecord:
    task_id: str
    node_id: Optional[str] = None
    start_time: Optional[float] = None
    finish_time: Optional[float] = None
    status: str = "pending"
    result: Optional[Any] = None
    error: Optional[str] = None