
"""
QCloudRL Circuit Module
File: loader.py

Purpose:
    Load OpenQASM 2 and OpenQASM 3 files into
    Qiskit QuantumCircuit objects.

Features:
    - OpenQASM 2 loading
    - OpenQASM 3 loading
    - CircuitRecord support
    - Automatic format detection
    - Circuit validation
    - Batch loading
    - Clear parsing error reporting

Python: 3.10+
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from qiskit import QuantumCircuit
from qiskit import qasm2, qasm3

from .models import CircuitFormat, CircuitRecord
from .registry import detect_qasm_format


# ============================================================
# 1. CUSTOM EXCEPTIONS
# ============================================================

class CircuitLoadError(Exception):
    """Raised when a quantum circuit cannot be loaded."""


class UnsupportedCircuitFormatError(CircuitLoadError):
    """Raised when a circuit format is unsupported."""


class CircuitValidationError(CircuitLoadError):
    """Raised when a loaded circuit fails validation."""


# ============================================================
# 2. CIRCUIT LOADER
# ============================================================

class CircuitLoader:
    """
    Load QASM circuit files into Qiskit QuantumCircuit objects.

    The loader does not maintain a cache or registry.
    Those responsibilities belong to separate components.
    """

    def __init__(
        self,
        strict_format: bool = True,
    ):
        """
        Args:
            strict_format:
                If True, reject files whose QASM format
                cannot be identified.
        """

        self.strict_format = strict_format

        self._loaded_count = 0
        self._failed_count = 0

    # ========================================================
    # 3. FORMAT DETECTION
    # ========================================================

    def get_format(
        self,
        file_path: Union[str, Path],
        circuit_format: Optional[CircuitFormat] = None,
    ) -> CircuitFormat:
        """
        Determine the circuit format.

        An explicitly supplied format takes priority.
        Otherwise, inspect the file header.
        """

        if circuit_format is not None:

            if isinstance(circuit_format, str):
                try:
                    circuit_format = CircuitFormat(circuit_format)
                except ValueError as exc:
                    raise UnsupportedCircuitFormatError(
                        f"Unsupported circuit format: {circuit_format}"
                    ) from exc

            if circuit_format != CircuitFormat.UNKNOWN:
                return circuit_format

        detected = detect_qasm_format(file_path)

        if detected == CircuitFormat.UNKNOWN:

            if self.strict_format:
                raise UnsupportedCircuitFormatError(
                    f"Unable to identify QASM format: {file_path}"
                )

        return detected

    # ========================================================
    # 4. LOAD QASM 2
    # ========================================================

    @staticmethod
    def _load_qasm2(file_path: Path) -> QuantumCircuit:
        """
        Load an OpenQASM 2 circuit.

        Uses the Qiskit QASM 2 importer.
        """

        try:
            circuit = qasm2.load(str(file_path))

        except Exception as exc:
            raise CircuitLoadError(
                f"Failed to parse OpenQASM 2 file "
                f"'{file_path}': {exc}"
            ) from exc

        return circuit

    # ========================================================
    # 5. LOAD QASM 3
    # ========================================================

    @staticmethod
    def _load_qasm3(file_path: Path) -> QuantumCircuit:
        """
        Load an OpenQASM 3 circuit.

        Uses the Qiskit QASM 3 importer.
        """

        try:
            circuit = qasm3.load(str(file_path))

        except Exception as exc:
            raise CircuitLoadError(
                f"Failed to parse OpenQASM 3 file "
                f"'{file_path}': {exc}"
            ) from exc

        return circuit

    # ========================================================
    # 6. CIRCUIT VALIDATION
    # ========================================================

    @staticmethod
    def validate(
        circuit: QuantumCircuit,
    ) -> bool:
        """
        Perform basic structural validation.

        This checks the returned object and its basic
        circuit properties. It does not prove that the
        circuit is physically executable on a backend.
        """

        if not isinstance(circuit, QuantumCircuit):
            raise CircuitValidationError(
                "Loaded object is not a Qiskit QuantumCircuit."
            )

        if circuit.num_qubits < 0:
            raise CircuitValidationError(
                "Invalid number of qubits."
            )

        if circuit.num_clbits < 0:
            raise CircuitValidationError(
                "Invalid number of classical bits."
            )

        if circuit.depth() is None:
            raise CircuitValidationError(
                "Circuit depth could not be calculated."
            )

        return True

    # ========================================================
    # 7. LOAD SINGLE CIRCUIT
    # ========================================================

    def load(
        self,
        file_path: Union[str, Path],
        circuit_format: Optional[CircuitFormat] = None,
        validate: bool = True,
    ) -> QuantumCircuit:
        """
        Load a circuit from a QASM file.

        Args:
            file_path:
                Path to the QASM file.

            circuit_format:
                Optional explicit QASM format.

            validate:
                Perform basic validation after loading.

        Returns:
            Qiskit QuantumCircuit.
        """

        path = Path(file_path).expanduser().resolve()

        if not path.exists():
            self._failed_count += 1

            raise FileNotFoundError(
                f"Circuit file does not exist: {path}"
            )

        if not path.is_file():
            self._failed_count += 1

            raise CircuitLoadError(
                f"Expected a file, received: {path}"
            )

        try:
            detected_format = self.get_format(
                path,
                circuit_format,
            )

            if detected_format == CircuitFormat.QASM2:

                circuit = self._load_qasm2(path)

            elif detected_format == CircuitFormat.QASM3:

                circuit = self._load_qasm3(path)

            else:

                raise UnsupportedCircuitFormatError(
                    f"Unsupported or unknown QASM format: {path}"
                )

            if validate:
                self.validate(circuit)

            self._loaded_count += 1

            return circuit

        except Exception:
            self._failed_count += 1
            raise

    # ========================================================
    # 8. LOAD FROM CIRCUIT RECORD
    # ========================================================

    def load_record(
        self,
        record: CircuitRecord,
        validate: bool = True,
    ) -> QuantumCircuit:
        """
        Load a circuit using its CircuitRecord.

        This connects the Registry and Loader modules.
        """

        if not isinstance(record, CircuitRecord):
            raise TypeError(
                "Expected a CircuitRecord object."
            )

        return self.load(
            file_path=record.file_path,
            circuit_format=record.circuit_format,
            validate=validate,
        )

    # ========================================================
    # 9. LOAD MULTIPLE CIRCUITS
    # ========================================================

    def load_many(
        self,
        records: list[CircuitRecord],
        skip_errors: bool = False,
    ) -> dict[str, QuantumCircuit]:
        """
        Load multiple circuit records.

        Args:
            records:
                List of CircuitRecord objects.

            skip_errors:
                If True, continue when an individual
                circuit cannot be loaded.

        Returns:
            Dictionary:
                circuit_id -> QuantumCircuit

        Note:
            This method loads all requested circuits into
            memory. For large datasets, use lazy loading
            through CircuitService instead.
        """

        loaded_circuits = {}

        for record in records:

            try:
                circuit = self.load_record(record)

                loaded_circuits[record.circuit_id] = circuit

            except Exception:
                if not skip_errors:
                    raise

        return loaded_circuits

    # ========================================================
    # 10. LOADER STATISTICS
    # ========================================================

    @property
    def loaded_count(self) -> int:
        """Number of successfully loaded circuits."""

        return self._loaded_count

    @property
    def failed_count(self) -> int:
        """Number of failed loading attempts."""

        return self._failed_count

    def reset_statistics(self) -> None:
        """Reset loader counters."""

        self._loaded_count = 0
        self._failed_count = 0
