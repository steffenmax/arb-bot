"""Small HTTP fetch layer with on-disk caching and stale fallback."""
from __future__ import annotations

import datetime as dt
import json
import os
import time
import urllib.request

from .data import CACHE_DIR

USER_AGENT = "survivor-dashboard/1.0 (+https://github.com/steffenmax/arb-bot)"
TIMEOUT = 25


class FetchResult:
    def __init__(self, data, fetched_at: float, stale: bool, error: str | None):
        self.data = data
        self.fetched_at = fetched_at
        self.stale = stale
        self.error = error

    @property
    def fetched_iso(self) -> str | None:
        if not self.fetched_at:
            return None
        return dt.datetime.fromtimestamp(self.fetched_at, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cache_path(name: str) -> str:
    return os.path.join(CACHE_DIR, name)


def http_get(url: str, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def cached_fetch(url: str, name: str, ttl: float, refresh: bool = False,
                 headers: dict | None = None, parse=None) -> FetchResult:
    """Fetch `url`, caching the raw body at cache/<name> for `ttl` seconds.

    On network failure the stale cache is returned with `error` set so the
    dashboard keeps working offline and can show a warning.
    """
    path = _cache_path(name)
    os.makedirs(CACHE_DIR, exist_ok=True)
    have = os.path.exists(path)
    age = time.time() - os.path.getmtime(path) if have else None
    if have and not refresh and age is not None and age < ttl:
        with open(path, "rb") as fh:
            body = fh.read()
        return FetchResult(parse(body) if parse else body, os.path.getmtime(path), False, None)
    try:
        body = http_get(url, headers)
        tmp = path + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(body)
        os.replace(tmp, path)
        return FetchResult(parse(body) if parse else body, time.time(), False, None)
    except Exception as exc:  # noqa: BLE001
        if have:
            with open(path, "rb") as fh:
                body = fh.read()
            return FetchResult(parse(body) if parse else body, os.path.getmtime(path), True, str(exc))
        return FetchResult(None, 0.0, True, str(exc))


def parse_json(body: bytes):
    return json.loads(body.decode("utf-8"))
