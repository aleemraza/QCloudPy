
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class NodeStatus(str, Enum):
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"


@dataclass
class QNodeConfig:
    """Configuration and resource information for a QNode."""

    node_id: str
    backend_name: str
    num_qubits: int
    simulator: bool = True
    available: bool = True

    # Optional resource information
    basis_gates: Optional[list] = None
    coupling_map: Optional[list] = None

    def __post_init__(self):
        if not self.node_id:
            raise ValueError("node_id cannot be empty")

        if not self.backend_name:
            raise ValueError("backend_name cannot be empty")

        if self.num_qubits <= 0:
            raise ValueError("num_qubits must be positive")
