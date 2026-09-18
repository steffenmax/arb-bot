"""Read your own contest data out of a pool site using your own browser.

Pool sites sit behind a login and publish no API, so this drives a browser on
your machine that you have signed into. Your credentials never leave the
machine and are never handled here: you log in once, by hand, in a normal
browser window, and the session is kept in a dedicated Chrome profile under
survivor/cache/browser/. Later runs reuse that profile headlessly.

    python3 -m survivor.splash --login    # once: a window opens, you sign in
    python3 -m survivor.splash            # after that: pulls the latest data
    python3 -m survivor.splash --watch 30 # or keep pulling every 30 minutes

Rather than scrape the rendered page, this records the JSON the site's own
front end fetches, which is stable in a way that HTML layout is not. Every
capture is written to survivor/cache/splash/ so a parser can be checked
against exactly what came back.

Nothing about your account is stored beyond the browser profile, and that
profile is yours to delete at any time.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict

from .data import CACHE_DIR, normalize_team
from .importer import find_teams

PROFILE_DIR = os.path.join(CACHE_DIR, "browser")
CAPTURE_DIR = os.path.join(CACHE_DIR, "splash")
SETTINGS = os.path.join(CACHE_DIR, "splash.json")
API_HINT = re.compile(r"(api|graphql)\.|/api/|/graphql", re.I)

def _norm(key: str) -> str:
    """Compare key names ignoring case and separators, so weekNumber,
    week_number and WEEK-NUMBER are all the same key."""
    return re.sub(r"[^a-z]", "", str(key).lower())


def _keys(*names: str) -> frozenset[str]:
    return frozenset(_norm(n) for n in names)


WEEK_KEYS = _keys("week", "weekNumber", "week_number", "round", "roundNumber", "round_number",
                  "period", "gameWeek", "slate")
TEAM_KEYS = _keys("team", "teamAbbreviation", "team_abbr", "teamAbbr", "abbreviation", "abbr",
                  "pick", "selection", "selectedTeam", "teamName", "team_name", "shortName",
                  "short_name", "code", "teamCode", "tricode", "triCode")
ENTRY_KEYS = _keys("entryName", "entry_name", "name", "nickname", "username", "userName",
                   "displayName", "display_name", "alias", "teamName", "entry", "label")
STATUS_KEYS = _keys("status", "state", "result", "outcome", "isEliminated", "eliminated",
                    "alive", "isAlive")
COUNT_KEYS = _keys("count", "picks", "pickCount", "pick_count", "numPicks", "num_picks",
                   "entries", "entryCount", "entry_count", "total", "totalPicks", "n",
                   "selections", "selectionCount")
PCT_KEYS = _keys("percent", "percentage", "pct", "pickPercent", "pick_percent",
                 "pickPercentage", "pickPct", "share", "rate", "ownership")


class SplashError(RuntimeError):
    pass


def _playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SplashError(
            "This needs Playwright, which drives your browser:\n"
            "    pip install playwright && python3 -m playwright install chromium\n"
            "If the dashboard is running from survivor/.venv, use that Python:\n"
            "    survivor/.venv/bin/python -m pip install playwright\n"
            "    survivor/.venv/bin/python -m playwright install chromium"
        ) from exc
    return sync_playwright


def load_settings() -> dict:
    try:
        with open(SETTINGS) as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_settings(data: dict) -> None:
    os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
    with open(SETTINGS, "w") as fh:
        json.dump(data, fh, indent=2)


# ---------------------------------------------------------------- extraction
def walk(node, path: str = ""):
    """Every dict in a nested JSON structure, with the path that reached it."""
    if isinstance(node, dict):
        yield path, node
        for k, v in node.items():
            yield from walk(v, f"{path}.{k}" if path else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{path}[{i}]")


def team_from(value) -> str | None:
    """A team code from a code, a name, or a nested object describing one."""
    if isinstance(value, dict):
        for k, v in value.items():
            if _norm(k) in TEAM_KEYS or _norm(k) in ("id", "key"):
                got = team_from(v)
                if got:
                    return got
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        return normalize_team(text)
    except ValueError:
        pass
    found = find_teams(text if text.isupper() or " " in text else text.title())
    return found[0][2] if len(found) == 1 else None


def week_from(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and 1 <= int(value) <= 18 and float(value) == int(value):
        return int(value)
    if isinstance(value, str):
        m = re.fullmatch(r"\s*(?:week|wk|w)?\s*[:#]?\s*(\d{1,2})\s*", value, re.I)
        if m and 1 <= int(m.group(1)) <= 18:
            return int(m.group(1))
    return None


def extract_picks(payload) -> list[dict]:
    """Every (entry, week, team) the captured JSON describes.

    Written against shape rather than a specific site: any object carrying
    something week-like and something team-like is a pick, and the nearest
    enclosing object with a name is the entry it belongs to.
    """
    picks: list[dict] = []
    names: dict[str, str] = {}          # path prefix -> entry name

    for path, obj in walk(payload):
        for k, v in obj.items():
            if _norm(k) in ENTRY_KEYS and isinstance(v, str) and v.strip() and not team_from(v):
                names[path] = v.strip()
                break

    def enclosing_name(path: str) -> str | None:
        best = None
        for prefix, name in names.items():
            if path == prefix or path.startswith(prefix + ".") or path.startswith(prefix + "["):
                if best is None or len(prefix) > len(best[0]):
                    best = (prefix, name)
        return best[1] if best else None

    for path, obj in walk(payload):
        week = team = status = None
        for k, v in obj.items():
            n = _norm(k)
            if week is None and n in WEEK_KEYS:
                week = week_from(v)
            if team is None and n in TEAM_KEYS:
                team = team_from(v)
            if status is None and n in STATUS_KEYS and isinstance(v, (str, bool)):
                status = v
        if week is not None and team is not None:
            picks.append({"entry": enclosing_name(path), "week": week, "team": team,
                          "status": status, "path": path})
            continue
        # some sites key the picks by week: {"1": {"team": "PHI"}, "2": ...}
        for k, v in obj.items():
            wk = week_from(k)
            if wk is None:
                continue
            got = team_from(v)
            if got:
                picks.append({"entry": enclosing_name(path), "week": wk, "team": got,
                              "status": None, "path": f"{path}.{k}" if path else str(k)})
    # the same pick often appears under several paths
    seen, unique = set(), []
    for p in sorted(picks, key=lambda p: (p["entry"] or "", p["week"], p["team"])):
        key = (p["entry"], p["week"], p["team"])
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def extract_pool_stats(payload) -> list[dict]:
    """Whole-pool pick counts from a stats page.

    The statistics page reports the pool directly - how many entries took each
    team - which is a truer number than counting the entries a listing happens
    to show. Matched on shape: any object naming a team alongside a count or a
    percentage, taking its week from the nearest enclosing object that has one.
    """
    weeks: dict[str, int] = {}
    for path, obj in walk(payload):
        for k, v in obj.items():
            if _norm(k) in WEEK_KEYS:
                wk = week_from(v)
                if wk is not None:
                    weeks[path] = wk
                    break

    def enclosing_week(path: str) -> int | None:
        best = None
        for prefix, wk in weeks.items():
            # "" is the root object, which encloses everything.
            if prefix and not (path == prefix or path.startswith(prefix + ".")
                               or path.startswith(prefix + "[")):
                continue
            if best is None or len(prefix) > len(best[0]):
                best = (prefix, wk)
        return best[1] if best else None

    rows: list[dict] = []
    for path, obj in walk(payload):
        team = count = pct = None
        for k, v in obj.items():
            n = _norm(k)
            if team is None and n in TEAM_KEYS:
                team = team_from(v)
            if count is None and n in COUNT_KEYS and isinstance(v, (int, float)) \
                    and not isinstance(v, bool) and float(v) == int(v) and v >= 0:
                count = int(v)
            if pct is None and n in PCT_KEYS and isinstance(v, (int, float)) \
                    and not isinstance(v, bool) and 0 <= float(v) <= 100:
                pct = float(v)
        if team and (count is not None or pct is not None):
            rows.append({"week": enclosing_week(path), "team": team,
                         "count": count, "pct": pct, "path": path})

    seen, unique = set(), []
    for r in rows:
        key = (r["week"], r["team"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    return unique


def pool_pick_pct(rows: list[dict]) -> dict[str, dict[str, float]]:
    """Week -> team -> percent of the pool, from stats rows.

    A site that already publishes percentages is believed. Otherwise the counts
    are turned into percentages of that week's total.
    """
    by_week: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        if r["week"] is not None:
            by_week[r["week"]].append(r)
    out: dict[str, dict[str, float]] = {}
    for wk, items in by_week.items():
        if all(i["pct"] is not None for i in items):
            out[str(wk)] = {i["team"]: round(i["pct"], 1) for i in items}
            continue
        total = sum(i["count"] or 0 for i in items)
        if not total:
            continue
        out[str(wk)] = {i["team"]: round(100.0 * (i["count"] or 0) / total, 1) for i in items}
    return out


def summarise(picks: list[dict], me: str | None = None,
              stats: list[dict] | None = None) -> dict:
    """Split the pool into your entries and the league-wide pick distribution.

    Percentages come from the statistics page when it was captured, since that
    covers the whole pool; counting the entries a listing rendered is the
    fallback and is only as complete as that listing.
    """
    by_entry: dict[str, dict[int, list[str]]] = defaultdict(dict)
    for p in picks:
        by_entry[p["entry"] or "(unnamed)"][p["week"]] = [p["team"]]
    crowd: dict[int, Counter] = defaultdict(Counter)
    for entry, weeks in by_entry.items():
        for wk, teams in weeks.items():
            for t in teams:
                crowd[wk][t] += 1
    pick_pct = {
        str(wk): {t: round(100.0 * n / sum(c.values()), 1) for t, n in c.items()}
        for wk, c in crowd.items() if sum(c.values())
    }
    pct_source = "entry listing" if pick_pct else "none"
    counts: dict[str, dict[str, int]] = {}
    if stats:
        from_stats = pool_pick_pct(stats)
        if from_stats:
            pick_pct = {**pick_pct, **from_stats}
            pct_source = "statistics page"
        for r in stats:
            if r["week"] is not None and r["count"] is not None:
                counts.setdefault(str(r["week"]), {})[r["team"]] = r["count"]
    mine = {k: v for k, v in by_entry.items() if me and me.lower() in k.lower()}
    pool_size = len(by_entry)
    for wk_counts in counts.values():
        pool_size = max(pool_size, sum(wk_counts.values()))
    return {
        "entries": {k: {str(w): t for w, t in sorted(v.items())} for k, v in by_entry.items()},
        "mine": {k: {str(w): t for w, t in sorted(v.items())} for k, v in mine.items()},
        "pickPct": pick_pct,
        "pickCounts": counts,
        "pctSource": pct_source,
        "poolSize": pool_size,
    }


# ---------------------------------------------------------------- browser
def _capture(url: str, headless: bool, wait: float, on_ready=None,
             also: list[str] | None = None) -> tuple[list[dict], str]:
    """Open `url` in the saved profile and record the JSON its page fetches.

    `also` names further pages to visit in the same session, so the entries
    page and the statistics page are read under one sign-in.
    """
    sync_playwright = _playwright()
    os.makedirs(PROFILE_DIR, exist_ok=True)
    os.makedirs(CAPTURE_DIR, exist_ok=True)
    payloads: list[dict] = []
    page_text = ""

    def note(resp):
        try:
            if not API_HINT.search(resp.url) or resp.status >= 400:
                return
            ctype = (resp.headers or {}).get("content-type", "")
            if "json" not in ctype.lower():
                return
            payloads.append({"url": resp.url, "status": resp.status, "body": resp.json()})
        except Exception:                      # a body that cannot be read is not fatal
            pass

    launch = {"headless": headless, "viewport": {"width": 1400, "height": 1000}}
    # SURVIVOR_CHROME points at a specific browser binary; without it Playwright
    # uses the Chromium it installed.
    if os.environ.get("SURVIVOR_CHROME"):
        launch["executable_path"] = os.environ["SURVIVOR_CHROME"]
    if os.environ.get("SURVIVOR_NO_SANDBOX"):
        launch["args"] = ["--no-sandbox"]
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(PROFILE_DIR, **launch)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.on("response", note)
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        if on_ready:
            on_ready(page)
        else:
            page.wait_for_timeout(int(wait * 1000))
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        page_text = page.inner_text("body")
        for extra in (also or []):
            try:
                page.goto(extra, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(int(wait * 1000))
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                page_text += "\n\n" + page.inner_text("body")
            except Exception as exc:
                print(f"survivor: could not read {extra}: {exc}", file=sys.stderr)
        ctx.close()
    return payloads, page_text


def login(url: str) -> None:
    """Open a real window so you can sign in; the session is then remembered."""
    print("A browser window is opening. Sign in to your pool, get to the page that")
    print("shows the entries, then come back here and press Enter.")

    def wait_for_person(page):
        try:
            input("\n  press Enter once you can see your entries... ")
        except EOFError:
            page.wait_for_timeout(120000)

    _capture(url, headless=False, wait=0, on_ready=wait_for_person)
    s = load_settings()
    s["url"] = url
    s["loggedInAt"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    save_settings(s)
    print("\nSession saved. From now on: python3 -m survivor.splash")


def sync(url: str, me: str | None = None, wait: float = 8.0, keep_raw: bool = True,
         stats_url: str | None = None) -> dict:
    """Pull the contest pages and pull picks out of what their front end fetched.

    `stats_url` is the league-wide statistics page. When given it is read in the
    same session, and its numbers - which cover the whole pool - are what the
    pick percentages are built from.
    """
    payloads, text = _capture(url, headless=True, wait=wait,
                              also=[stats_url] if stats_url else None)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = None
    if keep_raw:
        os.makedirs(CAPTURE_DIR, exist_ok=True)
        raw_path = os.path.join(CAPTURE_DIR, f"capture-{stamp}.json")
        with open(raw_path, "w") as fh:
            json.dump({"url": url, "captured": stamp, "responses": payloads,
                       "pageText": text[:20000]}, fh, indent=2)

    picks: list[dict] = []
    stats: list[dict] = []
    for item in payloads:
        picks.extend(extract_picks(item["body"]))
        stats.extend(extract_pool_stats(item["body"]))
    source = "api"
    if not picks:
        from .importer import parse_picks           # fall back to the visible text
        parsed = parse_picks(text)
        for entry, plist in parsed.as_dict()["entries"].items():
            picks.extend({"entry": entry, "week": p["week"], "team": p["team"],
                          "status": p["result"], "path": "pageText"} for p in plist)
        source = "page text"

    out = summarise(picks, me, stats)
    out.update({
        "source": source, "responses": len(payloads), "rawCapture": raw_path,
        "statsRows": len(stats),
        "signedIn": "sign in" not in text.lower() and "log in" not in text.lower(),
        "capturedAt": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python3 -m survivor.splash",
                                 description="Pull your contest entries using your own signed-in browser.")
    ap.add_argument("--url", help="the contest entries page (remembered after the first run)")
    ap.add_argument("--stats-url", help="the league statistics page, for whole-pool pick percentages")
    ap.add_argument("--login", action="store_true", help="open a window to sign in, once")
    ap.add_argument("--me", help="text that appears in your own entry names, to tell them from the pool's")
    ap.add_argument("--watch", type=float, metavar="MINUTES", help="keep pulling on this interval")
    ap.add_argument("--wait", type=float, default=8.0, help="seconds to let the page load (default 8)")
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    args = ap.parse_args(argv)

    settings = load_settings()
    url = args.url or settings.get("url")
    if not url:
        ap.error("no contest URL yet — pass --url https://... the first time")
    if args.me:
        settings["me"] = args.me
    if args.stats_url:
        settings["statsUrl"] = args.stats_url
    settings["url"] = url
    save_settings(settings)
    me = args.me or settings.get("me")
    stats_url = args.stats_url or settings.get("statsUrl")

    if args.login:
        login(url)
        return

    def once():
        try:
            res = sync(url, me, wait=args.wait, stats_url=stats_url)
        except SplashError as exc:
            print(f"survivor: {exc}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(res, indent=2))
            return 0
        if not res["signedIn"]:
            print("survivor: that page still looks signed out. Run with --login first.", file=sys.stderr)
        print(f"captured {res['responses']} API response(s) via {res['source']}; "
              f"{res['poolSize']} entr{'y' if res['poolSize'] == 1 else 'ies'} seen")
        for name, weeks in list(res["entries"].items())[:12]:
            print(f"   {name}: " + ", ".join(f"W{w} {'+'.join(t)}" for w, t in sorted(weeks.items(), key=lambda kv: int(kv[0]))))
        for wk, dist in sorted(res["pickPct"].items(), key=lambda kv: int(kv[0])):
            top = sorted(dist.items(), key=lambda kv: -kv[1])[:6]
            counts = res.get("pickCounts", {}).get(wk, {})
            parts = [f"{t} {p}%" + (f" ({counts[t]})" if t in counts else "") for t, p in top]
            print(f"   week {wk} crowd: " + ", ".join(parts))
        if res["pickPct"]:
            print(f"   percentages from the {res['pctSource']}")
        if res["rawCapture"]:
            print(f"   raw capture: {res['rawCapture']}")
        if not res["entries"]:
            print("   nothing recognised — send me the raw capture above and I will match the site's shape.")
        return 0

    if args.watch:
        print(f"survivor: pulling every {args.watch:g} minutes; Ctrl+C to stop.")
        while True:
            once()
            try:
                time.sleep(args.watch * 60)
            except KeyboardInterrupt:
                print("\nstopped")
                return
    sys.exit(once())


if __name__ == "__main__":
    main()
