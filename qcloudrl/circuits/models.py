
"""
QCloudRL Circuit Module
File: models.py

Purpose:
    Define the core data models used by the Circuit Module.

Models:
    - CircuitFormat
    - CircuitRecord
    - CircuitFeatures
    - CircuitProfile

Python: 3.10+
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional


# ============================================================
# 1. CIRCUIT FORMAT
# ============================================================

class CircuitFormat(str, Enum):
    """Supported quantum circuit file formats."""

    QASM2 = "qasm2"
    QASM3 = "qasm3"
    UNKNOWN = "unknown"


# ============================================================
# 2. CIRCUIT RECORD
# ============================================================

@dataclass
class CircuitRecord:
    """
    Represents an indexed circuit in a dataset.

    This model stores circuit identity and file metadata.
    It does not contain the loaded QuantumCircuit object.
    """

    circuit_id: str
    name: str
    file_path: str

    circuit_format: CircuitFormat = CircuitFormat.UNKNOWN

    dataset_name: Optional[str] = None
    file_size_bytes: int = 0
    circuit_hash: Optional[str] = None

    indexed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.circuit_id:
            raise ValueError("circuit_id cannot be empty")

        if not self.name:
            raise ValueError("Circuit name cannot be empty")

        if self.file_size_bytes < 0:
            raise ValueError("file_size_bytes cannot be negative")

        self.file_path = str(Path(self.file_path))

        if isinstance(self.circuit_format, str):
            self.circuit_format = CircuitFormat(self.circuit_format)

    @property
    def exists(self) -> bool:
        """Check whether the circuit file exists."""

        return Path(self.file_path).is_file()


# ============================================================
# 3. CIRCUIT FEATURES
# ============================================================

@dataclass
class CircuitFeatures:
    """
    Stores hardware-independent circuit characteristics.

    These features describe the original circuit before
    backend-specific transpilation.
    """

    circuit_id: str

    # Basic properties
    num_qubits: int = 0
    num_clbits: int = 0
    circuit_width: int = 0

    # Circuit complexity
    circuit_depth: int = 0
    total_gate_count: int = 0

    single_qubit_gate_count: int = 0
    two_qubit_gate_count: int = 0
    multi_qubit_gate_count: int = 0

    # Special operations
    measurement_count: int = 0
    reset_count: int = 0

    # Gate information
    gate_histogram: dict[str, int] = field(default_factory=dict)
    required_gates: list[str] = field(default_factory=list)

    # Connectivity information
    interaction_edges: list[tuple[int, int]] = field(
        default_factory=list
    )

    # Circuit requirements
    requires_dynamic_circuits: bool = False
    requires_mid_circuit_measurement: bool = False
    requires_conditional_operations: bool = False

    # Additional information
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.circuit_id:
            raise ValueError("circuit_id cannot be empty")

        count_fields = [
            self.num_qubits,
            self.num_clbits,
            self.circuit_width,
            self.circuit_depth,
            self.total_gate_count,
            self.single_qubit_gate_count,
            self.two_qubit_gate_count,
            self.multi_qubit_gate_count,
            self.measurement_count,
            self.reset_count,
        ]

        if any(value < 0 for value in count_fields):
            raise ValueError("Circuit feature counts cannot be negative")


# ============================================================
# 4. CIRCUIT PROFILE
# ============================================================

@dataclass
class CircuitProfile:
    """
    Stores circuit complexity and profiling results.

    Original circuit characteristics are kept separate from
    backend-specific transpilation information.
    """

    circuit_id: str

    # Original circuit information
    original_depth: int = 0
    original_gate_count: int = 0

    # Complexity estimates
    complexity_score: Optional[float] = None

    # Backend identification
    backend_name: Optional[str] = None
    backend_version: Optional[str] = None

    # Transpiled circuit information
    transpiled_depth: Optional[int] = None
    transpiled_gate_count: Optional[int] = None

    # Transpilation configuration
    optimization_level: Optional[int] = None
    basis_gates: list[str] = field(default_factory=list)

    # Hardware compatibility
    is_compatible: Optional[bool] = None
    compatibility_notes: list[str] = field(default_factory=list)

    # Profile metadata
    profiled_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.circuit_id:
            raise ValueError("circuit_id cannot be empty")

        if self.original_depth < 0 or self.original_gate_count < 0:
            raise ValueError("Original circuit metrics cannot be negative")

        if self.transpiled_depth is not None and self.transpiled_depth < 0:
            raise ValueError("Transpiled depth cannot be negative")

        if (
            self.transpiled_gate_count is not None
            and self.transpiled_gate_count < 0
        ):
            raise ValueError("Transpiled gate count cannot be negative")

        if self.complexity_score is not None and self.complexity_score < 0:
            raise ValueError("Complexity score cannot be negative")
    
    

