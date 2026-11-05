from __future__ import annotations

from collections import OrderedDict
from typing import Generic, TypeVar

T = TypeVar("T")


class LRUCache(Generic[T]):
    """Small bounded LRU cache. Capacity is measured in number of entries."""

    def __init__(self, max_items: int = 32):
        if max_items < 0:
            raise ValueError("max_items must be >= 0")
        self.max_items = max_items
        self._items: OrderedDict[str, T] = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def get(self, key: str) -> T | None:
        if key not in self._items:
            self.misses += 1
            return None
        self.hits += 1
        self._items.move_to_end(key)
        return self._items[key]

    def put(self, key: str, value: T) -> None:
        if self.max_items == 0:
            return
        if key in self._items:
            self._items.move_to_end(key)
            self._items[key] = value
            return
        self._items[key] = value
        if len(self._items) > self.max_items:
            self._items.popitem(last=False)
            self.evictions += 1

    def clear(self) -> None:
        self._items.clear()

    def stats(self) -> dict[str, int]:
        return {
            "size": len(self._items),
            "capacity": self.max_items,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
        }
