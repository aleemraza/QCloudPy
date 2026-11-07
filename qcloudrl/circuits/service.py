
"""
Circuit Service
===============

Central interface for circuit discovery, loading, feature extraction,
backend profiling, and caching.

The service coordinates the circuit module components. It does not
implement QASM parsing, feature extraction, or transpilation itself.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from qiskit import QuantumCircuit

from .cache import CircuitCache
from .feature_extractor import CircuitFeatureExtractor
from .loader import CircuitLoader
from .profiler import CircuitProfiler
from .registry import CircuitRegistry


class CircuitServiceError(Exception):
    """Base exception for CircuitService errors."""


class CircuitNotFoundError(CircuitServiceError):
    """Raised when a circuit ID is not present in the registry."""


class CircuitService:
    """
    Common interface for accessing quantum circuits.

    Parameters
    ----------
    dataset_dir:
        Root directory containing circuit files.

    dataset_name:
        Logical name of the dataset, such as 'mqt_bench'.

    manifest_path:
        Optional path for the JSON circuit manifest.

    cache_capacity:
        Maximum number of parsed circuits held in memory.

    Notes
    -----
    The registry indexes metadata only. Circuit files are parsed
    when get_circuit() is called.
    """

    def __init__(
        self,
        dataset_dir: str,
        dataset_name: str = "mqt_bench",
        manifest_path: Optional[str] = None,
        cache_capacity: int = 32,
    ) -> None:

        self.dataset_dir = Path(dataset_dir)
        self.dataset_name = dataset_name

        if not self.dataset_dir.exists():
            raise FileNotFoundError(
                f"Dataset directory does not exist: {self.dataset_dir}"
            )

        if not self.dataset_dir.is_dir():
            raise NotADirectoryError(
                f"Dataset path is not a directory: {self.dataset_dir}"
            )

        self.manifest_path = (
            Path(manifest_path)
            if manifest_path is not None
            else self.dataset_dir / "circuit_manifest.json"
        )

        # Component initialization
        self.registry = CircuitRegistry(
            dataset_dir=str(self.dataset_dir)
        )

        self.loader = CircuitLoader()
        self.feature_extractor = CircuitFeatureExtractor()
        self.profiler = CircuitProfiler()
        self.cache = CircuitCache(capacity=cache_capacity)

    # ---------------------------------------------------------
    # Registry operations
    # ---------------------------------------------------------

    # def index_dataset(
    #     self,
    #     limit: Optional[int] = None,
    #     sample: Optional[int] = None,
    #     save_manifest: bool = True,
    # ) -> List[Any]:
    #     """
    #     Index circuit files in the dataset.

    #     Only metadata is indexed. QASM files are not parsed here.
    #     """

    #     records = self.registry.index_dataset(
    #         limit=limit,
    #         sample=sample,
    #     )

    #     if save_manifest:
    #         self.save_manifest()

    #     return records
    
    def index_dataset(
        self,
        limit: Optional[int] = None,
        seed: Optional[int] = None,
        save_manifest: bool = True,
    ) -> List[Any]:
        """
        Index circuit files and optionally save the JSON manifest.

        Circuit files are indexed as metadata only.
        They are not parsed into QuantumCircuit objects here.
        """

        records = self.registry.index_dataset(
            limit=limit,
            seed=seed,
        )

        if save_manifest:
            self.save_manifest()

        return records

    def save_manifest(self) -> None:
        """Save the current registry index to JSON."""

        self.manifest_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.registry.save_manifest(
            str(self.manifest_path)
        )

    def load_manifest(self) -> None:
        """Load an existing JSON manifest into the registry."""

        if not self.manifest_path.exists():
            raise FileNotFoundError(
                f"Circuit manifest not found: {self.manifest_path}"
            )

        self.registry.load_manifest(
            str(self.manifest_path)
        )

    # ---------------------------------------------------------
    # Record lookup
    # ---------------------------------------------------------

    def get_record(self, circuit_id: str) -> Any:
        """
        Return metadata for a circuit.

        This method does not parse or load the circuit.
        """

        record = self._lookup_record(circuit_id)

        if record is None:
            raise CircuitNotFoundError(
                f"Circuit ID not found: {circuit_id}. "
                "Index the dataset or load its manifest first."
            )

        return record

    def list_circuits(
        self,
        circuit_format: Optional[Any] = None,
    ) -> List[Any]:
        """
        Return indexed circuit records.

        If circuit_format is provided, return only records
        matching that format.
        """

        records = self._list_records()

        if circuit_format is None:
            return records

        return [
            record
            for record in records
            if record.circuit_format == circuit_format
        ]

    # ---------------------------------------------------------
    # Circuit loading and caching
    # ---------------------------------------------------------

    def get_circuit(self, circuit_id: str) -> QuantumCircuit:
        """
        Get a parsed QuantumCircuit.

        Execution flow:
        1. Check cache.
        2. Find the circuit record.
        3. Load and parse the original QASM file.
        4. Store the parsed circuit in cache.
        5. Return the circuit.
        """

        # Step 1: Check cache
        cached_circuit = self.cache.get(circuit_id)

        if cached_circuit is not None:
            return cached_circuit

        # Step 2: Find metadata
        record = self.get_record(circuit_id)

        # Step 3: Check original file
        if not record.exists:
            raise CircuitServiceError(
                f"Circuit file is missing: {record.file_path}"
            )

        # Step 4: Parse QASM
        try:
            circuit = self.loader.load(record.file_path)
        except Exception as exc:
            raise CircuitServiceError(
                f"Could not load circuit '{circuit_id}': {exc}"
            ) from exc

        if not isinstance(circuit, QuantumCircuit):
            raise CircuitServiceError(
                "CircuitLoader did not return a QuantumCircuit."
            )

        # Step 5: Cache parsed circuit
        self.cache.put(circuit_id, circuit)

        return circuit

    # ---------------------------------------------------------
    # Logical feature extraction
    # ---------------------------------------------------------

    def get_features(self, circuit_id: str) -> Any:
        """
        Extract logical features from the original circuit.

        This method does not transpile the circuit.
        """

        record = self.get_record(circuit_id)
        circuit = self.get_circuit(circuit_id)

        try:
            return self.feature_extractor.extract(
                circuit=circuit,
                circuit_id=record.circuit_id,
            )
        except Exception as exc:
            raise CircuitServiceError(
                f"Feature extraction failed for "
                f"'{circuit_id}': {exc}"
            ) from exc

    # ---------------------------------------------------------
    # Backend-specific profiling
    # ---------------------------------------------------------

    def profile_circuit(
        self,
        circuit_id: str,
        backend: Any,
        optimization_level: Optional[int] = None,
    ) -> Any:
        """
        Transpile and profile a circuit for a target backend.

        This does not submit a job to a QPU.
        """

        record = self.get_record(circuit_id)
        circuit = self.get_circuit(circuit_id)

        try:
            return self.profiler.profile(
                circuit=circuit,
                circuit_id=record.circuit_id,
                backend=backend,
                optimization_level=optimization_level,
            )
        except Exception as exc:
            raise CircuitServiceError(
                f"Backend profiling failed for "
                f"'{circuit_id}': {exc}"
            ) from exc

    # ---------------------------------------------------------
    # Cache management
    # ---------------------------------------------------------

    def clear_cache(
        self,
        reset_statistics: bool = False,
    ) -> None:
        """Clear parsed circuits from memory."""

        self.cache.clear(
            reset_statistics=reset_statistics
        )

    # ---------------------------------------------------------
    # Statistics
    # ---------------------------------------------------------

    def get_statistics(self) -> Dict[str, Any]:
        """Return statistics from the service components."""

        records = self._list_records()

        return {
            "dataset": {
                "name": self.dataset_name,
                "directory": str(self.dataset_dir),
                "manifest": str(self.manifest_path),
                "indexed_circuits": len(records),
            },
            "cache": self.cache.get_statistics(),
            "loader": self._safe_statistics(self.loader),
            "profiler": self._safe_statistics(self.profiler),
        }

    # ---------------------------------------------------------
    # Internal compatibility helpers
    # ---------------------------------------------------------

    def _lookup_record(self, circuit_id: str) -> Optional[Any]:
        """
        Find a record using the registry's available lookup method.
        """

        for method_name in ("get_by_id", "get_record", "get"):
            method = getattr(self.registry, method_name, None)

            if callable(method):
                return method(circuit_id)

        raise CircuitServiceError(
            "CircuitRegistry does not expose a supported "
            "record lookup method."
        )

    def _list_records(self) -> List[Any]:
        """Retrieve all records from the registry."""

        for method_name in ("list_records", "get_all", "list_circuits"):
            method = getattr(self.registry, method_name, None)

            if callable(method):
                return list(method())

        records = getattr(self.registry, "records", None)

        if isinstance(records, dict):
            return list(records.values())

        if isinstance(records, (list, tuple)):
            return list(records)

        raise CircuitServiceError(
            "CircuitRegistry does not expose a supported "
            "record listing method."
        )

    @staticmethod
    def _safe_statistics(component: Any) -> Dict[str, Any]:
        """Return component statistics when available."""

        method = getattr(component, "get_statistics", None)

        if callable(method):
            return method()

        return {}



