
import pytest

from qiskit import QuantumCircuit

from qcloudrl.circuits.cache import (
    CircuitCache,
    CircuitCacheError,
)


@pytest.fixture
def cache():
    return CircuitCache(capacity=3)


def make_circuit(num_qubits=2):
    circuit = QuantumCircuit(num_qubits)
    circuit.h(0)

    if num_qubits >= 2:
        circuit.cx(0, 1)

    return circuit


def test_cache_initialization():
    cache = CircuitCache()

    assert cache.capacity == 32
    assert cache.size == 0
    assert cache.is_empty is True
    assert cache.is_full is False


def test_custom_capacity():
    cache = CircuitCache(capacity=5)

    assert cache.capacity == 5


def test_invalid_capacity():
    with pytest.raises(ValueError):
        CircuitCache(capacity=0)

    with pytest.raises(ValueError):
        CircuitCache(capacity=-1)

    with pytest.raises(ValueError):
        CircuitCache(capacity=1.5)


def test_put_and_get(cache):
    circuit = make_circuit()

    evicted = cache.put("circuit_1", circuit)
    result = cache.get("circuit_1")

    assert evicted is None
    assert result is circuit
    assert cache.size == 1


def test_cache_miss(cache):
    result = cache.get("missing_circuit")

    assert result is None
    assert cache.misses == 1


def test_cache_hit_statistics(cache):
    circuit = make_circuit()

    cache.put("circuit_1", circuit)

    cache.get("circuit_1")
    cache.get("circuit_1")

    assert cache.hits == 2
    assert cache.misses == 0
    assert cache.hit_rate == 1.0


def test_lru_eviction(cache):
    cache.put("A", make_circuit())
    cache.put("B", make_circuit())
    cache.put("C", make_circuit())

    # A becomes most recently used.
    cache.get("A")

    # B should now be the least recently used.
    evicted = cache.put("D", make_circuit())

    assert evicted == "B"

    assert cache.contains("A")
    assert cache.contains("C")
    assert cache.contains("D")

    assert not cache.contains("B")
    assert cache.size == 3
    assert cache.evictions == 1


def test_update_existing_circuit(cache):
    original = make_circuit(2)
    updated = make_circuit(3)

    cache.put("A", original)
    evicted = cache.put("A", updated)

    assert evicted is None
    assert cache.get("A") is updated
    assert cache.size == 1
    assert cache.evictions == 0


def test_peek_does_not_change_lru_order(cache):
    cache.put("A", make_circuit())
    cache.put("B", make_circuit())
    cache.put("C", make_circuit())

    original_order = cache.keys

    cache.peek("A")

    assert cache.keys == original_order
    assert cache.hits == 0
    assert cache.misses == 0


def test_remove(cache):
    cache.put("A", make_circuit())

    assert cache.remove("A") is True
    assert cache.remove("A") is False
    assert cache.size == 0


def test_clear(cache):
    cache.put("A", make_circuit())
    cache.put("B", make_circuit())

    cache.clear()

    assert cache.size == 0
    assert cache.is_empty is True


def test_clear_and_reset_statistics(cache):
    cache.put("A", make_circuit())
    cache.get("A")
    cache.get("missing")

    cache.clear(reset_statistics=True)

    assert cache.size == 0
    assert cache.hits == 0
    assert cache.misses == 0
    assert cache.evictions == 0


def test_set_capacity(cache):
    cache.put("A", make_circuit())
    cache.put("B", make_circuit())
    cache.put("C", make_circuit())

    evicted = cache.set_capacity(2)

    assert evicted == ["A"]
    assert cache.capacity == 2
    assert cache.size == 2
    assert not cache.contains("A")


def test_statistics(cache):
    cache.put("A", make_circuit())

    cache.get("A")
    cache.get("missing")

    statistics = cache.get_statistics()

    assert statistics["capacity"] == 3
    assert statistics["size"] == 1
    assert statistics["hits"] == 1
    assert statistics["misses"] == 1
    assert statistics["total_requests"] == 2
    assert statistics["hit_rate"] == 0.5


def test_invalid_circuit(cache):
    with pytest.raises(CircuitCacheError):
        cache.put("A", "not a quantum circuit")


def test_invalid_circuit_id(cache):
    with pytest.raises(CircuitCacheError):
        cache.put("", make_circuit())

    with pytest.raises(CircuitCacheError):
        cache.get("")


def test_contains_operator(cache):
    cache.put("A", make_circuit())

    assert "A" in cache
    assert "B" not in cache


def test_capacity_one():
    cache = CircuitCache(capacity=1)

    cache.put("A", make_circuit())
    evicted = cache.put("B", make_circuit())

    assert evicted == "A"
    assert cache.size == 1
    assert "B" in cache
