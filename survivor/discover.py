"""Learn how a pool site works by watching your own browser use it.

The site sits behind a login and publishes no documentation, so rather than
guess at its API this records what its own front end does while you drive it.
You click; it watches. Afterwards it writes two files:

    survivor/cache/splash/capture-<stamp>.json   everything it saw
    survivor/cache/splash/report-<stamp>.md      a short, readable summary

The report is the one to send me. It holds endpoint URLs, GraphQL operation
names and the *shape* of each response — key names, value types, a few sample
values — which is all that is needed to write an exact parser. It deliberately
does not hold request headers, cookies or anything that looks like a token,
and the same redaction runs over the full capture.

    python3 -m survivor.discover --url https://contests.app.splashsports.com/...

A window opens in the profile you signed into with `survivor.splash --login`.
It walks you through three phases, pressing Enter between them:

    1. entries    your entries and their names
    2. pick       making or changing a pick, so the write is recorded too
    3. stats      the league-wide pick breakdown

Skip any phase by pressing Enter without doing anything.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys

from .data import CACHE_DIR, TEAM_NAMES
from .splash import CAPTURE_DIR, PROFILE_DIR, SplashError, _playwright, load_settings, save_settings

# ---------------------------------------------------------------- redaction
# Anything matching these is replaced before a byte is written to disk. The
# capture is meant to be shareable; a session token in it would not be.
SECRET_KEY = re.compile(
    r"(token|auth|session|cookie|password|passwd|secret|jwt|apikey|api_key|bearer|"
    r"credential|signature|csrf|refresh|access)", re.I)
JWT = re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.?[A-Za-z0-9_\-]*")
LONG_OPAQUE = re.compile(r"\b[A-Za-z0-9_\-]{40,}\b")
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
REDACTED = "<redacted>"


def scrub_text(text: str) -> str:
    if not isinstance(text, str):
        return text
    text = JWT.sub(REDACTED, text)
    text = EMAIL.sub("<email>", text)
    return LONG_OPAQUE.sub(REDACTED, text)


def scrub(node):
    """Redact secrets anywhere in a nested structure, by key name and by shape."""
    if isinstance(node, dict):
        return {k: (REDACTED if SECRET_KEY.search(str(k)) else scrub(v)) for k, v in node.items()}
    if isinstance(node, list):
        return [scrub(v) for v in node]
    return scrub_text(node)


# ---------------------------------------------------------------- shape digest
TEAM_WORDS = {c.lower() for c in TEAM_NAMES} | {n.lower() for n in TEAM_NAMES.values()}


def _sample(value) -> str:
    if isinstance(value, str):
        s = value if len(value) <= 48 else value[:45] + "..."
        return json.dumps(s)
    if isinstance(value, bool) or value is None:
        return json.dumps(value)
    if isinstance(value, (int, float)):
        return json.dumps(value)
    return type(value).__name__


def digest(node, indent: int = 0, max_depth: int = 7, max_keys: int = 30,
           max_items: int = 2, out: list[str] | None = None) -> list[str]:
    """A readable skeleton of a JSON value: keys, types and a sample or two.

    Long lists collapse to their length plus the shape of the first entries,
    which keeps a 5 MB response to a page that can be read in one sitting.
    """
    out = [] if out is None else out
    pad = "  " * indent
    if indent >= max_depth:
        out.append(pad + "...")
        return out
    if isinstance(node, dict):
        keys = list(node)
        for k in keys[:max_keys]:
            v = node[k]
            if isinstance(v, dict):
                out.append(f"{pad}{k}: {{{len(v)} keys}}")
                digest(v, indent + 1, max_depth, max_keys, max_items, out)
            elif isinstance(v, list):
                out.append(f"{pad}{k}: [{len(v)}]")
                for item in v[:max_items]:
                    if isinstance(item, (dict, list)):
                        digest(item, indent + 1, max_depth, max_keys, max_items, out)
                    else:
                        out.append(f"{pad}  - {_sample(item)}")
            else:
                out.append(f"{pad}{k} = {_sample(v)}")
        if len(keys) > max_keys:
            out.append(f"{pad}... {len(keys) - max_keys} more keys")
    elif isinstance(node, list):
        out.append(f"{pad}[{len(node)}]")
        for item in node[:max_items]:
            digest(item, indent + 1, max_depth, max_keys, max_items, out)
    else:
        out.append(pad + _sample(node))
    return out


def interesting(body) -> list[str]:
    """Why a response looks worth parsing, in the words of what it contains."""
    blob = json.dumps(body)[:400000].lower()
    notes = []
    hits = sum(1 for w in TEAM_WORDS if f'"{w}"' in blob)
    if hits >= 3:
        notes.append(f"{hits} team codes/names")
    for word, label in (("entryname", "entry names"), ("pick", "picks"), ("week", "weeks"),
                        ("eliminat", "elimination"), ("percent", "percentages"),
                        ("count", "counts"), ("survivor", "survivor"), ("standing", "standings")):
        if word in blob:
            notes.append(label)
    return notes


# ---------------------------------------------------------------- recording
def _op_name(post_data: str | None) -> str | None:
    """The GraphQL operation a request body carries, if it is GraphQL at all."""
    if not post_data:
        return None
    try:
        body = json.loads(post_data)
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(body, list) and body:
        body = body[0]
    if not isinstance(body, dict):
        return None
    if body.get("operationName"):
        return str(body["operationName"])
    query = body.get("query")
    if isinstance(query, str):
        m = re.search(r"\b(query|mutation)\s+(\w+)", query)
        if m:
            return f"{m.group(1)} {m.group(2)}"
    return None


def _body_of(post_data: str | None):
    if not post_data:
        return None
    try:
        return json.loads(post_data)
    except (json.JSONDecodeError, TypeError):
        return post_data[:2000]


class Recorder:
    """Collects request/response pairs into whichever phase is open."""

    def __init__(self):
        self.phase = "setup"
        self.calls: list[dict] = []

    def on_response(self, resp) -> None:
        try:
            req = resp.request
            if req.resource_type in ("image", "font", "stylesheet", "media"):
                return
            ctype = (resp.headers or {}).get("content-type", "")
            if "json" not in ctype.lower():
                return
            try:
                body = resp.json()
            except Exception:
                return
            self.calls.append({
                "phase": self.phase,
                "method": req.method,
                "url": resp.url.split("?")[0],
                "query": resp.url.split("?", 1)[1][:500] if "?" in resp.url else None,
                "status": resp.status,
                "operation": _op_name(req.post_data),
                "requestBody": _body_of(req.post_data),
                "body": body,
            })
        except Exception:
            pass                       # a response we cannot read is not a failure


PHASES = [
    ("entries", "Open the page that lists YOUR entries, with their names.",
     "Let it finish loading. Scroll so every entry has rendered."),
    ("pick", "Now make or change a pick on one entry.",
     "Go all the way through — if it asks you to confirm, confirm. This is the\n"
     "  only way to learn how a pick is submitted. You can change it back after."),
    ("stats", "Now open the general statistics / league picks page.",
     "The one showing how many people picked each team. If it has a week\n"
     "  selector, click through a couple of weeks."),
]


def explore(url: str, headless: bool = False) -> dict:
    sync_playwright = _playwright()
    os.makedirs(PROFILE_DIR, exist_ok=True)
    os.makedirs(CAPTURE_DIR, exist_ok=True)
    rec = Recorder()
    pages: dict[str, str] = {}

    launch = {"headless": headless, "viewport": {"width": 1500, "height": 1000}}
    if os.environ.get("SURVIVOR_CHROME"):
        launch["executable_path"] = os.environ["SURVIVOR_CHROME"]
    if os.environ.get("SURVIVOR_NO_SANDBOX"):
        launch["args"] = ["--no-sandbox"]

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(PROFILE_DIR, **launch)
        ctx.on("response", rec.on_response)          # context-level: catches new tabs too
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        print("\nA browser window is open. I am recording everything its pages fetch.")
        print("Nothing is sent anywhere — it all lands in survivor/cache/splash/.\n")
        for key, ask, detail in PHASES:
            rec.phase = key
            before = len(rec.calls)
            print(f"[{key}] {ask}")
            print(f"  {detail}")
            try:
                input(f"  press Enter when done (or Enter now to skip) ... ")
            except EOFError:
                page.wait_for_timeout(20000)
            try:
                pages[key] = page.inner_text("body")[:20000]
                pages[key + "Url"] = page.url
            except Exception:
                pass
            print(f"  recorded {len(rec.calls) - before} JSON call(s)\n")
        rec.phase = "done"
        ctx.close()

    return {"url": url, "calls": rec.calls, "pages": pages}


# ---------------------------------------------------------------- report
def report(session: dict) -> str:
    calls = session["calls"]
    lines = [
        "# Splash site capture",
        "",
        f"Start URL: {session['url']}",
        f"Captured: {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"JSON calls recorded: {len(calls)}",
        "",
        "Secrets are redacted: request headers are never recorded, and any key named",
        "like a token plus any JWT, long opaque string or email address is replaced.",
        "",
    ]
    for key, _, _ in PHASES + [("done", "", "")]:
        phase_calls = [c for c in calls if c["phase"] == key]
        if not phase_calls:
            continue
        lines += [f"## Phase: {key}", ""]
        url = session.get("pages", {}).get(key + "Url")
        if url:
            lines += [f"Page URL: `{url}`", ""]
        # Several identical calls are common; show each endpoint once, the richest.
        seen: dict[tuple, dict] = {}
        for c in phase_calls:
            k = (c["method"], c["url"], c["operation"])
            if k not in seen or len(json.dumps(c["body"])) > len(json.dumps(seen[k]["body"])):
                seen[k] = c
        for (method, endpoint, op), c in seen.items():
            head = f"### {method} {endpoint}"
            if op:
                head += f"  —  `{op}`"
            lines += [head, ""]
            notes = interesting(c["body"])
            if notes:
                lines += [f"Contains: {', '.join(notes)}", ""]
            if c["requestBody"] is not None:
                lines += ["Request body:", "```", *digest(c["requestBody"], max_depth=6)[:60], "```", ""]
            lines += ["Response shape:", "```", *digest(c["body"])[:160], "```", ""]
    text = session.get("pages", {}).get("stats")
    if text:
        lines += ["## Stats page, as rendered text", "```", text[:4000], "```", ""]
    return "\n".join(lines)


def save(session: dict) -> tuple[str, str]:
    os.makedirs(CAPTURE_DIR, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    clean = scrub(session)
    raw = os.path.join(CAPTURE_DIR, f"capture-{stamp}.json")
    with open(raw, "w") as fh:
        json.dump(clean, fh, indent=2)
    md = os.path.join(CAPTURE_DIR, f"report-{stamp}.md")
    with open(md, "w") as fh:
        fh.write(report(clean))
    return raw, md


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m survivor.discover", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", help="the contest page to start from (remembered from splash)")
    args = ap.parse_args(argv)

    settings = load_settings()
    url = args.url or settings.get("url")
    if not url:
        ap.error("no contest URL yet — pass --url https://...")
    settings["url"] = url
    save_settings(settings)

    try:
        session = explore(url)
    except SplashError as exc:
        print(f"survivor: {exc}", file=sys.stderr)
        return 1
    raw, md = save(session)
    size = os.path.getsize(md) / 1024
    print(f"survivor: recorded {len(session['calls'])} JSON call(s).")
    print(f"   report      {md}  ({size:.0f} KB)  <- send me this one")
    print(f"   full capture {raw}")
    if not session["calls"]:
        print("   nothing was recorded — the pages may render server-side. Send the")
        print("   report anyway; it still carries the page text.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
