"""
Persistent storage layer for Cord.
Provides an atomic, SQLite-backed dictionary-like store that survives bot restarts.
"""

import json
import sqlite3
import os
from typing import Any, Dict, List, Optional, Iterator


class StoreDict(dict):
    """
    A dictionary proxy that auto-commits changes back to the root Store.
    Supports both dict indexing (d["key"]) and attribute access (d.key).
    """

    def __init__(self, data: Dict[str, Any], root_store: "Store", path: List[str]):
        super().__init__()
        self._root_store = root_store
        self._path = path
        for k, v in data.items():
            super().__setitem__(k, self._wrap(v, path + [str(k)]))

    def _wrap(self, value: Any, subpath: List[str]) -> Any:
        if isinstance(value, dict):
            return StoreDict(value, self._root_store, subpath)
        return value

    def __getitem__(self, key: Any) -> Any:
        k = str(key)
        return super().__getitem__(k)

    def __setitem__(self, key: Any, value: Any):
        k = str(key)
        wrapped = self._wrap(value, self._path + [k])
        super().__setitem__(k, wrapped)
        self._root_store.notify_update()

    def __delitem__(self, key: Any):
        k = str(key)
        super().__delitem__(k)
        self._root_store.notify_update()

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            return super().__getattribute__(name)
        if name in self:
            return self[name]
        raise AttributeError(f"'Store' has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any):
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            self[name] = value

    def get(self, key: Any, default: Any = None) -> Any:
        k = str(key)
        if k in self:
            return self[k]
        return default

    def has(self, key: Any) -> bool:
        return str(key) in self

    def unwrap(self) -> Dict[str, Any]:
        """Convert back to standard Python dictionary for serialization."""
        res = {}
        for k, v in self.items():
            if isinstance(v, StoreDict):
                res[k] = v.unwrap()
            else:
                res[k] = v
        return res


class Store:
    """
    Thread-safe SQLite-backed key-value store.
    """

    def __init__(self, db_path: str = "cord_store.db"):
        self.db_path = db_path
        self._cache: Dict[str, Any] = {}
        self._conn: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            self._conn = sqlite3.connect(":memory:")
            self._conn.row_factory = sqlite3.Row
        self._init_db()
        self._load_all()

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        # Create storage table if it does not exist
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cord_kv (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def _load_all(self):
        with self._get_connection() as conn:
            cur = conn.execute("SELECT key, value FROM cord_kv")
            for row in cur.fetchall():
                try:
                    val = json.loads(row["value"])
                except Exception:
                    val = row["value"]
                self._cache[row["key"]] = val

    def notify_update(self):
        """Save entire cached state to SQLite."""
        with self._get_connection() as conn:
            with conn:
                for k, v in self._cache.items():
                    raw_val = v.unwrap() if isinstance(v, StoreDict) else v
                    conn.execute(
                        "INSERT OR REPLACE INTO cord_kv (key, value) VALUES (?, ?)",
                        (k, json.dumps(raw_val))
                    )

    def __getitem__(self, key: Any) -> Any:
        k = str(key)
        if k not in self._cache:
            raise KeyError(f"Key '{k}' not found in store")
        val = self._cache[k]
        if isinstance(val, dict) and not isinstance(val, StoreDict):
            val = StoreDict(val, self, [k])
            self._cache[k] = val
        return val

    def __setitem__(self, key: Any, value: Any):
        k = str(key)
        if isinstance(value, dict) and not isinstance(value, StoreDict):
            value = StoreDict(value, self, [k])
        self._cache[k] = value
        self.notify_update()

    def __delitem__(self, key: Any):
        k = str(key)
        if k in self._cache:
            del self._cache[k]
            with self._get_connection() as conn:
                conn.execute("DELETE FROM cord_kv WHERE key = ?", (k,))
                conn.commit()

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            return super().__getattribute__(name)
        if name in self._cache:
            return self[name]
        return None

    def __setattr__(self, name: str, value: Any):
        if name.startswith("_") or name in ("db_path",):
            super().__setattr__(name, value)
        else:
            self[name] = value

    def get(self, key: Any, default: Any = None) -> Any:
        k = str(key)
        if k in self._cache:
            return self[k]
        return default

    def has(self, key: Any) -> bool:
        return str(key) in self._cache

    def keys(self) -> Iterator[str]:
        return iter(self._cache.keys())

    def values(self) -> Iterator[Any]:
        return iter(self._cache.values())

    def items(self) -> Iterator[tuple]:
        return iter(self._cache.items())

    def clear(self):
        self._cache.clear()
        with self._get_connection() as conn:
            conn.execute("DELETE FROM cord_kv")
            conn.commit()
