#!/usr/bin/env bash
set -euo pipefail
cd /workspace/imports/alpha-transfer-20261012/prediction-market-alpha
export PYTHONPATH="$PWD/src"
export LIVE_TRADING=false
python3 - <<'PY'
import sys
from zoneinfo import ZoneInfo
assert sys.version_info >= (3, 11), "Python 3.11+ required"
ZoneInfo("America/New_York")
PY
# Imported filesystem project: preserve it; do not reset, re-extract or create a worktree.
# Back up committed SQLite snapshots before setup; each run creates a new directory.
python3 - <<'PY'
import sqlite3, uuid
from pathlib import Path
root=Path.cwd()
out=Path("/workspace/alpha-backups")/("setup-"+uuid.uuid4().hex)
out.mkdir(parents=True,exist_ok=False)
for rel in ("data/forward.sqlite","data/shadow.sqlite","reports/release_20261008/forward.sqlite"):
    source=root/rel
    if not source.exists():
        if rel=="data/shadow.sqlite":continue
        raise FileNotFoundError(source)
    destination=out/rel
    destination.parent.mkdir(parents=True,exist_ok=True)
    read=sqlite3.connect(source.resolve().as_uri()+"?mode=ro",uri=True)
    read.execute("PRAGMA query_only=ON");read.execute("BEGIN")
    original=read.execute("SELECT * FROM audit ORDER BY seq").fetchall()
    write=sqlite3.connect(destination)
    try:
        read.backup(write)
        assert write.execute("PRAGMA integrity_check").fetchone()==("ok",)
        assert write.execute("SELECT * FROM audit ORDER BY seq").fetchall()==original
    finally:write.close();read.close()
print("Consistent backups:",out)
PY
if [[ ! -x .venv/bin/python ]]; then python3 -m venv .venv; fi
.venv/bin/python -m pip install --cache-dir /workspace/shared/pip-cache -r requirements-dev.lock
.venv/bin/python scripts/check_runtime.py
.venv/bin/python -m pytest

