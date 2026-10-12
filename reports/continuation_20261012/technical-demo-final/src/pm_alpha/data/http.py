"""Public GET only, rate limited and content addressed. No anti-bot bypass."""
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from ..storage import Store


class AccessBlocked(RuntimeError):
    pass


class PublicHTTP:
    def __init__(self, raw_dir: Path, store: Store, timeout: float = 15, requests_per_second: float = 1) -> None:
        self.raw_dir, self.store, self.timeout = raw_dir, store, timeout
        if requests_per_second <= 0 or requests_per_second > 2:
            raise ValueError("Validation collector rate must be in (0,2]")
        self.interval = 1/requests_per_second
        self.last_request = 0.0
        raw_dir.mkdir(parents=True, exist_ok=True)

    def get(self, base: str, path: str, params: dict | None = None) -> tuple[dict | list, str, datetime]:
        if not base.startswith("https://"):
            raise ValueError("HTTPS public data required")
        query = urllib.parse.urlencode({k:v for k,v in (params or {}).items() if v is not None}, doseq=True)
        url = base.rstrip("/") + "/" + path.lstrip("/") + ("?" + query if query else "")
        for attempt in range(3):
            delay = max(0, self.interval - (time.monotonic()-self.last_request))
            if delay: time.sleep(delay)
            self.last_request = time.monotonic()
            request = urllib.request.Request(url, headers={"User-Agent": "pm-alpha-research/0.1 (public-data; paper-only)", "Accept": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as r:
                    body = r.read(); status = r.status
                ingested = datetime.now(timezone.utc)
                sha = hashlib.sha256(body).hexdigest()
                file = self.raw_dir / f"{sha}.json"
                if not file.exists(): file.write_bytes(body)
                self.store.append("retrieval", f"retrieval:{ingested.isoformat()}:{sha}", {"url":url,"retrieved_at":ingested.isoformat(),"status":status,"sha256":sha,"raw_file":file.name})
                return json.loads(body), sha, ingested
            except urllib.error.HTTPError as e:
                body = e.read(400).decode(errors="replace")
                if e.code in (401,403):
                    self.store.append("blocker", f"blocker:{time.time_ns()}", {"url":url,"status":e.code,"body":body,"retrieved_at":datetime.now(timezone.utc).isoformat()})
                    raise AccessBlocked(f"HTTP {e.code} at {url}: {body}. No bypass attempted.") from e
                if e.code not in (429,500,502,503,504) or attempt == 2: raise
                retry = e.headers.get("Retry-After", "1")
                try: delay = min(10.0, max(1.0,float(retry)))
                except ValueError: delay = 2.0
                time.sleep(delay)
        raise RuntimeError("Unreachable retry state")
