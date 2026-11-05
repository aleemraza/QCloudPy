from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CircuitRecord:
    """Lightweight registry entry. It never contains a parsed circuit."""

    circuit_id: str
    path: str
    format: str
    size_bytes: int
    sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CircuitRecord":
        return cls(**data)

    def resolve(self, dataset_root: str | Path) -> Path:
        path = Path(self.path)
        return path if path.is_absolute() else Path(dataset_root) / path


@dataclass(frozen=True)
class CircuitProfile:
    circuit_id: str | None
    num_qubits: int
    num_clbits: int
    depth: int
    size: int
    operation_counts: dict[str, int]
    num_single_qubit_gates: int
    num_multi_qubit_gates: int
    multi_qubit_gate_ratio: float
    num_measurements: int
    num_parameters: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CircuitArtifact:
    """A loaded circuit plus its provenance and profile, ready for a QNode."""

    circuit_id: str
    path: str
    circuit: Any
    profile: CircuitProfile

    @property
    def metadata(self) -> dict[str, Any]:
        return self.profile.to_dict()


@dataclass
class AerExecutionResult:
    counts: dict[str, int]
    shots: int
    elapsed_seconds: float
    backend_name: str
    success: bool = True


@dataclass
class CircuitRunOutput:
    cloud_artifact: CircuitArtifact | None = None
    aer_result: AerExecutionResult | None = None
