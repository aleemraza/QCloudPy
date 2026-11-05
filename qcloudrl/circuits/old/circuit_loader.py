from __future__ import annotations
from pathlib import Path
from qiskit import QuantumCircuit, qasm2, qasm3
from .models import CircuitRecord


class CircuitLoader:
    """Loads OpenQASM 2.0 and 3.0 files into Qiskit QuantumCircuit objects."""

    def load(self, record: CircuitRecord, dataset_root: str | Path) -> QuantumCircuit:
        path = record.resolve(dataset_root)
        if not path.exists():
            raise FileNotFoundError(f"Circuit file not found: {path}")

        if record.format == "qasm2":
            return qasm2.load(str(path))
        if record.format == "qasm3":
            return qasm3.load(str(path))

        raise ValueError(f"Unsupported circuit format: {record.format}")
