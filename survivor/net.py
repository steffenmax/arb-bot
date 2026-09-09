"""HTTPS downloads that work on a stock Python install.

Python installed from python.org on macOS does not read the system keychain,
so every download fails with CERTIFICATE_VERIFY_FAILED until the bundled
"Install Certificates.command" is run. Rather than require that step, each
certificate store is tried in turn and the one that works is remembered:

  1. SSL_CERT_FILE or REQUESTS_CA_BUNDLE when set (corporate proxies, CI)
  2. Python's default store (the system store on Linux, and a correctly
     configured macOS install)
  3. certifi's bundle (the fix for a stock macOS install)

Only a certificate-verification failure falls through to the next store; a
404 or a refused connection is raised as-is.
"""
from __future__ import annotations

import os
import ssl
import urllib.error
import urllib.request

USER_AGENT = "survivor-dashboard/1.0 (+https://github.com/steffenmax/arb-bot)"
TIMEOUT = 30

CERT_HELP = (
    "\nThe certificate store this Python uses is empty or incomplete, so it cannot "
    "verify any HTTPS site. Fix it with:  pip install certifi\n"
    "On macOS you can instead run the installer that ships with Python:  "
    "open \"/Applications/Python 3.x/Install Certificates.command\"  (use your version number)."
)


def _certifi_context() -> ssl.SSLContext:
    import certifi
    return ssl.create_default_context(cafile=certifi.where())


def _candidates() -> list[tuple[str, object]]:
    out: list[tuple[str, object]] = []
    for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
        path = os.environ.get(var)
        if path and os.path.exists(path):
            out.append((var, lambda p=path: ssl.create_default_context(cafile=p)))
            break
    out.append(("system", ssl.create_default_context))
    out.append(("certifi", _certifi_context))
    return out


_CANDIDATES: list[tuple[str, object]] | None = None
_BUILT: dict[int, ssl.SSLContext] = {}
_WORKING = 0          # index of the store that last succeeded


def _all() -> list[tuple[str, object]]:
    global _CANDIDATES
    if _CANDIDATES is None:
        _CANDIDATES = _candidates()
    return _CANDIDATES


def _context(i: int) -> ssl.SSLContext:
    if i not in _BUILT:
        _BUILT[i] = _all()[i][1]()          # type: ignore[operator]
    return _BUILT[i]


def cert_store() -> str:
    """Name of the certificate store currently in use (for diagnostics)."""
    return _all()[_WORKING][0]


def get(url: str, headers: dict | None = None, timeout: float = TIMEOUT) -> bytes:
    """Fetch a URL, falling back through certificate stores on a TLS failure."""
    global _WORKING
    last: Exception | None = None
    candidates = _all()
    for i in range(_WORKING, len(candidates)):
        try:
            ctx = _context(i)
        except Exception as exc:            # noqa: BLE001 - certifi may be absent
            last = exc
            continue
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                _WORKING = i
                return resp.read()
        except urllib.error.URLError as exc:
            if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
                raise
            last = exc
    raise RuntimeError(f"{last}{CERT_HELP}")
