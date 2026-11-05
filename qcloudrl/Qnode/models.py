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

    # Optional backend resource information
    basis_gates: Optional[list] = None
    coupling_map: Optional[list] = None

    def __post_init__(self):
        if not isinstance(self.node_id, str) or not self.node_id.strip():
            raise ValueError("node_id cannot be empty.")

        if not isinstance(self.backend_name, str) or not self.backend_name.strip():
            raise ValueError("backend_name cannot be empty.")

        if (
            not isinstance(self.num_qubits, int)
            or isinstance(self.num_qubits, bool)
            or self.num_qubits <= 0
        ):
            raise ValueError("num_qubits must be a positive integer.")

        self.node_id = self.node_id.strip()
        self.backend_name = self.backend_name.strip()