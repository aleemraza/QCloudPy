from __future__ import annotations
from pathlib import Path
from qiskit import QuantumCircuit
from .circuit_cache import LRUCache
from .circuit_loader import CircuitLoader
from .circuit_profiler import CircuitProfiler
from .circuit_registry import CircuitRegistry
from .models import CircuitArtifact, CircuitProfile, CircuitRecord


class CircuitService:
    """Facade for indexing, lazy loading, profiling, and cloud preparation."""

    def __init__(
        self,
        dataset_root: str | Path,
        manifest_path: str | Path | None = None,
        cache_size: int = 32,
    ):
        self.dataset_root = Path(dataset_root).expanduser().resolve()
        self.manifest_path = Path(manifest_path) if manifest_path else None
        self.registry = CircuitRegistry(self.dataset_root)
        self.loader = CircuitLoader()
        self.profiler = CircuitProfiler()
        self.cache: LRUCache[QuantumCircuit] = LRUCache(cache_size)
        self.records: dict[str, CircuitRecord] = {}

    def index(
        self,
        limit: int | None = None,
        seed: int = 42,
        include_hash: bool = False,
        save_manifest: bool = True,
    ) -> list[CircuitRecord]:
        discovered = self.registry.discover(include_hash=include_hash)
        selected = self.registry.select(discovered, limit=limit, seed=seed)
        self.records = {record.circuit_id: record for record in selected}
        if save_manifest and self.manifest_path:
            self.registry.save_manifest(selected, self.manifest_path)
        return selected

    def load_manifest(self) -> list[CircuitRecord]:
        if not self.manifest_path:
            raise ValueError("manifest_path was not configured")
        records = self.registry.load_manifest(self.manifest_path)
        self.records = {record.circuit_id: record for record in records}
        return records

    def get_record(self, circuit_id: str) -> CircuitRecord:
        try:
            return self.records[circuit_id]
        except KeyError as exc:
            raise KeyError(
                f"Unknown circuit_id {circuit_id!r}. Run index() or load_manifest() first."
            ) from exc

    def load(self, circuit_id: str) -> QuantumCircuit:
        cached = self.cache.get(circuit_id)
        if cached is not None:
            return cached
        record = self.get_record(circuit_id)
        circuit = self.loader.load(record, self.dataset_root)
        self.cache.put(circuit_id, circuit)
        return circuit

    def profile(self, circuit_id: str) -> CircuitProfile:
        circuit = self.load(circuit_id)
        return self.profiler.profile(circuit, circuit_id=circuit_id)

    def prepare_for_cloud(self, circuit_id: str) -> CircuitArtifact:
        """Return the loaded circuit and profile for a future QNode adapter.

        No cloud execution time, fidelity, queue delay, or cost is fabricated here.
        """
        record = self.get_record(circuit_id)
        circuit = self.load(circuit_id)
        profile = self.profiler.profile(circuit, circuit_id=circuit_id)
        return CircuitArtifact(
            circuit_id=circuit_id,
            path=str(record.resolve(self.dataset_root)),
            circuit=circuit,
            profile=profile,
        )

    def cache_stats(self) -> dict[str, int]:
        return self.cache.stats()
