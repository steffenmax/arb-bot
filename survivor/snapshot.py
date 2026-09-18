"""Build a standalone, browsable copy of the dashboard.

The result is one HTML file with the stylesheet, both scripts and the current
dashboard payload inlined. It opens straight from disk with no server, which
makes it the thing to send someone who should see the plan but will not run
the app: every view and every game is there to read. Anything that writes -
locking a pick, moving the horizon, refreshing a feed - needs the real app,
and the page says so in a banner.

    python3 -m survivor.snapshot                 # -> survivor-snapshot.html
    python3 -m survivor.snapshot -o plan.html --refresh
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .dashboard import config as cfgmod
from .dashboard import service

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard", "static")


def _read(name: str) -> str:
    with open(os.path.join(STATIC_DIR, name), encoding="utf-8") as fh:
        return fh.read()


def _inline_safe(text: str) -> str:
    """Keep a nested </script> or <!-- from ending the script element early."""
    return text.replace("</script", "<\\/script").replace("<!--", "<\\!--")


def build(payload: dict) -> str:
    """Return the full HTML document for a dashboard payload."""
    head = _read("index.html")
    body = head.split("<body>", 1)[1].rsplit("</body>", 1)[0]
    body = body.replace('<script src="app.js"></script>', "").replace(
        '<script src="views.js"></script>', ""
    )
    fonts = [
        line for line in head.splitlines() if "fonts.googleapis.com" in line or "fonts.gstatic.com" in line
    ]
    week = payload.get("meta", {}).get("currentWeek")
    title = f"Survivor Pool Desk — Week {week}" if week else "Survivor Pool Desk"
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{title}</title>",
            *fonts,
            "<style>",
            _read("styles.css"),
            "</style>",
            "</head>",
            "<body>",
            body,
            "<script>window.SURVIVOR_SNAPSHOT = "
            + _inline_safe(json.dumps(payload, separators=(",", ":")))
            + ";</script>",
            "<script>" + _inline_safe(_read("app.js")) + "</script>",
            "<script>" + _inline_safe(_read("views.js")) + "</script>",
            "</body>",
            "</html>",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m survivor.snapshot", description=__doc__)
    ap.add_argument("-o", "--out", default="survivor-snapshot.html", help="file to write")
    ap.add_argument("--refresh", action="store_true", help="re-download every feed first")
    args = ap.parse_args(argv)

    payload = service.build_dashboard(cfgmod.load(), refresh=args.refresh)
    html = build(payload)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(html)
    meta = payload.get("meta", {})
    print(
        f"wrote {args.out} ({len(html) / 1e6:.2f} MB) — "
        f"week {meta.get('currentWeek')}, {len(payload.get('games', []))} games"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
