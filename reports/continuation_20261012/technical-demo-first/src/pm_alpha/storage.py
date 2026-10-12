"""Append-only SQLite audit records with a hash chain and immutable raw provenance."""
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class Store:
    def __init__(self, path: str | Path) -> None:
        path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS audit (
          seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
          record_key TEXT NOT NULL UNIQUE, payload TEXT NOT NULL,
          previous_hash TEXT NOT NULL, record_hash TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit
          BEGIN SELECT RAISE(ABORT, 'append-only audit'); END;
        CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit
          BEGIN SELECT RAISE(ABORT, 'append-only audit'); END;
        CREATE INDEX IF NOT EXISTS audit_kind_seq ON audit(kind,seq);
        ''')

    def append(self, kind: str, key: str, payload: dict) -> str:
        encoded = canonical(payload)
        try:
            self.db.execute("BEGIN IMMEDIATE")
            prior = self.db.execute("SELECT record_hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
            previous = prior[0] if prior else "GENESIS"
            record_hash = digest([previous, kind, key, encoded])
            self.db.execute("INSERT INTO audit(kind,record_key,payload,previous_hash,record_hash) VALUES(?,?,?,?,?)", (kind, key, encoded, previous, record_hash))
            self.db.commit()
            return record_hash
        except Exception:
            self.db.rollback(); raise

    def records(self, kind: str | None = None) -> list[dict]:
        if kind:
            rows = self.db.execute("SELECT payload FROM audit WHERE kind=? ORDER BY seq", (kind,)).fetchall()
        else:
            rows = self.db.execute("SELECT payload FROM audit ORDER BY seq").fetchall()
        return [json.loads(r[0]) for r in rows]

    def has(self, key: str) -> bool:
        return self.db.execute("SELECT 1 FROM audit WHERE record_key=?", (key,)).fetchone() is not None

    def get(self, key: str) -> dict | None:
        row = self.db.execute("SELECT payload FROM audit WHERE record_key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def iter_records(self, kind: str):
        for row in self.db.execute("SELECT payload FROM audit WHERE kind=? ORDER BY seq", (kind,)):
            yield json.loads(row[0])

    def last(self, kind: str) -> dict | None:
        row=self.db.execute("SELECT payload FROM audit WHERE kind=? ORDER BY seq DESC LIMIT 1",(kind,)).fetchone()
        return json.loads(row[0]) if row else None

    def verify(self) -> bool:
        previous = "GENESIS"
        for kind, key, encoded, expected_previous, actual in self.db.execute("SELECT kind,record_key,payload,previous_hash,record_hash FROM audit ORDER BY seq"):
            if previous != expected_previous or digest([previous,kind,key,encoded]) != actual:
                return False
            previous = actual
        return True

    def close(self) -> None:
        self.db.close()
