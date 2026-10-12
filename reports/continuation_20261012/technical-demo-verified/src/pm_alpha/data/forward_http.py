"""Prospective public GET recorder. Receipt times are conservative availability."""
import gzip
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from ..schema import DataInvalid
from ..storage import Store
from .http import AccessBlocked


class RateLimiter:
    """One process, no bursts; all attempts consume the same global budget."""
    def __init__(self, interval=1.0, clock=time.monotonic, sleep=time.sleep):
        if interval < 1:
            raise ValueError("Forward GET budget cannot exceed 1 request/second")
        self.interval, self.clock, self.sleep = interval, clock, sleep
        self.next_global = 0.0
        self.next_host = {}

    def acquire(self, host, host_interval=0.0):
        now = self.clock()
        delay = max(0, self.next_global-now, self.next_host.get(host, 0)-now)
        if delay:
            self.sleep(delay)
        now = self.clock()
        self.next_global = now+self.interval
        self.next_host[host] = now+host_interval


@dataclass(frozen=True)
class Response:
    data: dict | list
    sha256: str
    received_at: datetime
    started_at: datetime
    elapsed_ms: float
    endpoint: str
    headers: dict

    def provenance(self):
        return {"sha256": self.sha256, "endpoint": self.endpoint,
                "available_time": self.received_at.isoformat(),
                "request_start": self.started_at.isoformat(), "elapsed_ms": self.elapsed_ms,
                "http_date": self.headers.get("Date"), "cache_age": self.headers.get("Age")}


class ForwardHTTP:
    def __init__(self, raw_dir: Path, store: Store, timeout=15, limiter=None):
        self.raw_dir, self.store, self.timeout = raw_dir, store, timeout
        self.limiter = limiter or RateLimiter()
        self.blocked_hosts = set()
        raw_dir.mkdir(parents=True, exist_ok=True)

    def get(self, base, path, params=None):
        parsed = urllib.parse.urlsplit(base)
        if parsed.scheme != "https" or parsed.username or parsed.password:
            raise ValueError("Public HTTPS only")
        host = parsed.hostname
        if host in self.blocked_hosts:
            raise AccessBlocked(f"Host {host} stopped after access denial; no automatic fallback")
        query = urllib.parse.urlencode({k:v for k,v in (params or {}).items() if v is not None}, doseq=True)
        url = base.rstrip("/")+"/"+path.lstrip("/")+("?"+query if query else "")
        for attempt in range(3):
            self.limiter.acquire(host, 10 if host == "api.weather.gov" else 0)
            started = datetime.now(timezone.utc); tick = time.monotonic()
            req = urllib.request.Request(url, headers={"User-Agent":"pm-alpha-forward/0.2 (public research; no trading)",
                                                       "Accept":"application/json"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    body = r.read(); status = r.status; headers = dict(r.headers.items())
                received = datetime.now(timezone.utc)
                sha = hashlib.sha256(body).hexdigest()
                target = self.raw_dir/f"{sha}.json.gz"
                try:
                    with target.open("xb") as f:
                        f.write(gzip.compress(body, mtime=0))
                except FileExistsError:
                    if hashlib.sha256(gzip.decompress(target.read_bytes())).hexdigest() != sha:
                        raise DataInvalid("Raw hash collision/corruption")
                record = {"url":url,"retrieved_at":received.isoformat(),"request_start":started.isoformat(),
                          "elapsed_ms":round((time.monotonic()-tick)*1000,3),"status":status,
                          "sha256":sha,"raw_file":target.name,"raw_bytes":len(body),"stored_bytes":target.stat().st_size,
                          "headers":{k:v for k,v in headers.items() if k.lower() in ("date","age","etag","last-modified","content-type","cache-control")}}
                self.store.append("forward_retrieval", f"get:{time.time_ns()}:{sha}", record)
                try:
                    data = json.loads(body)
                except (ValueError, UnicodeError) as e:
                    self.blocked_hosts.add(host)
                    self.store.append('forward_schema_failure',f'schema-failure:{time.time_ns()}',
                                      {'url':url,'status':status,'timestamp':received.isoformat(),'sha256':sha,'reason':'NON_JSON_RESPONSE_HOST_PAUSED'})
                    raise DataInvalid("Unexpected non-JSON public response; raw retained") from e
                if not isinstance(data, (dict,list)):
                    raise DataInvalid("Unexpected scalar API schema")
                return Response(data,sha,received,started,record["elapsed_ms"],url,headers)
            except urllib.error.HTTPError as e:
                received = datetime.now(timezone.utc)
                self.store.append("forward_api_failure", f"failure:{time.time_ns()}",
                                  {"url":url,"status":e.code,"attempt":attempt,"timestamp":received.isoformat(),
                                   "reason":str(e),"retry_after":e.headers.get("Retry-After")})
                if e.code in (401,403,451):
                    self.blocked_hosts.add(host)
                    raise AccessBlocked(f"HTTP {e.code}: {host} stopped; no bypass") from e
                if e.code not in (429,500,502,503,504) or attempt == 2:
                    raise
                retry = e.headers.get("Retry-After")
                try:
                    delay = max(2**(attempt+1), float(retry)) if retry else 2**(attempt+1)
                except ValueError:
                    from email.utils import parsedate_to_datetime
                    delay = max(2**(attempt+1),(parsedate_to_datetime(retry)-received).total_seconds())
                # Respect long server waits; fail this run visibly rather than shorten them.
                if delay > 60:
                    self.blocked_hosts.add(host)
                    raise DataInvalid(f"Server requests {delay:.0f}s cooldown; host paused") from e
                time.sleep(delay)
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                self.store.append("forward_api_failure",f"failure:{time.time_ns()}",
                                  {"url":url,"status":None,"attempt":attempt,"timestamp":datetime.now(timezone.utc).isoformat(),"reason":str(e)})
                # HTTPS proxy CONNECT denials arrive as URLError, not HTTPError.
                # A denied host must not be retried each series/cycle as a timeout.
                denial=str(e).lower()
                if 'tunnel connection failed' in denial and any(str(code) in denial for code in (401,403,451)):
                    self.blocked_hosts.add(host)
                    raise AccessBlocked(f'Proxy access denied: {host} stopped; no bypass') from e
                raise
