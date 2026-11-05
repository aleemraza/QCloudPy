
from __future__ import annotations

from collections import OrderedDict
from threading import RLock
from typing import Optional

from qiskit import QuantumCircuit


class CircuitCacheError(Exception):
    """Raised when a circuit cache operation fails."""


class CircuitCache:
    """
    Thread-safe, bounded LRU cache for Qiskit QuantumCircuit objects.

    The cache stores circuits using their circuit IDs.

    When the cache reaches its capacity, the least recently used
    circuit is evicted before a new circuit is inserted.

    Notes:
        - The default capacity is 32 circuits.
        - get() returns the stored circuit object itself.
        - Returned circuits should be treated as read-only by callers.
        - This cache stores logical circuits, not transpiled circuits.
    """

    DEFAULT_CAPACITY = 32

    def __init__(self, capacity: int = DEFAULT_CAPACITY):
        if not isinstance(capacity, int) or isinstance(capacity, bool):
            raise ValueError("Cache capacity must be an integer.")

        if capacity < 1:
            raise ValueError("Cache capacity must be at least 1.")

        self.capacity = capacity

        # Oldest entry is at the beginning.
        # Most recently used entry is at the end.
        self._cache: OrderedDict[str, QuantumCircuit] = OrderedDict()

        self._lock = RLock()

        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def put(
        self,
        circuit_id: str,
        circuit: QuantumCircuit,
    ) -> Optional[str]:
        """
        Insert or update a circuit.

        Args:
            circuit_id: Unique circuit identifier.
            circuit: Parsed Qiskit QuantumCircuit.

        Returns:
            The evicted circuit ID, or None if no eviction occurred.
        """

        self._validate_circuit_id(circuit_id)

        if not isinstance(circuit, QuantumCircuit):
            raise CircuitCacheError(
                "Expected a Qiskit QuantumCircuit instance."
            )

        with self._lock:

            # Updating an existing entry makes it the most recently used.
            if circuit_id in self._cache:
                self._cache.pop(circuit_id)

            evicted_id = None

            # Make room if this is a new circuit and the cache is full.
            if len(self._cache) >= self.capacity:
                evicted_id, _ = self._cache.popitem(last=False)
                self._evictions += 1

            self._cache[circuit_id] = circuit

            return evicted_id

    def get(self, circuit_id: str) -> Optional[QuantumCircuit]:
        """
        Retrieve a circuit and mark it as recently used.

        Returns:
            QuantumCircuit if found, otherwise None.
        """

        self._validate_circuit_id(circuit_id)

        with self._lock:

            circuit = self._cache.get(circuit_id)

            if circuit is None:
                self._misses += 1
                return None

            # Move the accessed circuit to the newest position.
            self._cache.move_to_end(circuit_id)

            self._hits += 1

            return circuit

    def peek(self, circuit_id: str) -> Optional[QuantumCircuit]:
        """
        Retrieve a circuit without changing its LRU position
        or hit/miss statistics.
        """

        self._validate_circuit_id(circuit_id)

        with self._lock:
            return self._cache.get(circuit_id)

    def remove(self, circuit_id: str) -> bool:
        """
        Remove a circuit from the cache.

        Returns:
            True if removed, otherwise False.
        """

        self._validate_circuit_id(circuit_id)

        with self._lock:
            if circuit_id not in self._cache:
                return False

            del self._cache[circuit_id]
            return True

    def contains(self, circuit_id: str) -> bool:
        """Check whether a circuit is cached."""

        self._validate_circuit_id(circuit_id)

        with self._lock:
            return circuit_id in self._cache

    def clear(self, reset_statistics: bool = False) -> None:
        """
        Remove all cached circuits.

        Statistics are preserved by default.
        Set reset_statistics=True to reset them as well.
        """

        with self._lock:
            self._cache.clear()

            if reset_statistics:
                self._hits = 0
                self._misses = 0
                self._evictions = 0

    def set_capacity(self, capacity: int) -> list[str]:
        """
        Change the cache capacity.

        If the new capacity is smaller than the current cache size,
        least recently used circuits are evicted first.

        Returns:
            List of evicted circuit IDs in eviction order.
        """

        if not isinstance(capacity, int) or isinstance(capacity, bool):
            raise ValueError("Cache capacity must be an integer.")

        if capacity < 1:
            raise ValueError("Cache capacity must be at least 1.")

        evicted_ids = []

        with self._lock:
            self.capacity = capacity

            while len(self._cache) > self.capacity:
                circuit_id, _ = self._cache.popitem(last=False)

                evicted_ids.append(circuit_id)
                self._evictions += 1

        return evicted_ids

    @staticmethod
    def _validate_circuit_id(circuit_id: str) -> None:
        if not isinstance(circuit_id, str) or not circuit_id.strip():
            raise CircuitCacheError(
                "circuit_id must be a non-empty string."
            )

    @property
    def size(self) -> int:
        """Number of circuits currently stored."""

        with self._lock:
            return len(self._cache)

    @property
    def is_empty(self) -> bool:
        with self._lock:
            return len(self._cache) == 0

    @property
    def is_full(self) -> bool:
        with self._lock:
            return len(self._cache) >= self.capacity

    @property
    def hits(self) -> int:
        with self._lock:
            return self._hits

    @property
    def misses(self) -> int:
        with self._lock:
            return self._misses

    @property
    def evictions(self) -> int:
        with self._lock:
            return self._evictions

    @property
    def hit_rate(self) -> float:
        """Cache hit rate as a value between 0.0 and 1.0."""

        with self._lock:
            total = self._hits + self._misses

            if total == 0:
                return 0.0

            return self._hits / total

    @property
    def keys(self) -> list[str]:
        """Return circuit IDs from oldest to newest."""

        with self._lock:
            return list(self._cache.keys())

    def get_statistics(self) -> dict:
        """Return a snapshot of cache statistics."""

        with self._lock:
            total_requests = self._hits + self._misses

            return {
                "capacity": self.capacity,
                "size": len(self._cache),
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "total_requests": total_requests,
                "hit_rate": (
                    self._hits / total_requests
                    if total_requests > 0
                    else 0.0
                ),
            }

    def __len__(self) -> int:
        return self.size

    def __contains__(self, circuit_id: str) -> bool:
        return self.contains(circuit_id)
