"""ESPN public feeds: live scores, current odds, injuries, news, teams, standings.

All endpoints are unauthenticated JSON. Team abbreviations are mapped to
nflverse codes (ESPN uses WSH and LAR where nflverse uses WAS and LA).
"""
from __future__ import annotations

import re

from .fetch import FetchResult, cached_fetch, parse_json

BASE = "https://site.api.espn.com/apis"
ESPN_TO_CODE = {"WSH": "WAS", "LAR": "LA"}
CODE_TO_ESPN = {v: k for k, v in ESPN_TO_CODE.items()}
ESPN_ID_TO_CODE = {
    "1": "ATL", "2": "BUF", "3": "CHI", "4": "CIN", "5": "CLE", "6": "DAL", "7": "DEN", "8": "DET",
    "9": "GB", "10": "TEN", "11": "IND", "12": "KC", "13": "LV", "14": "LA", "15": "MIA", "16": "MIN",
    "17": "NE", "18": "NO", "19": "NYG", "20": "NYJ", "21": "PHI", "22": "ARI", "23": "PIT", "24": "LAC",
    "25": "SF", "26": "SEA", "27": "TB", "28": "WAS", "29": "CAR", "30": "JAX", "33": "BAL", "34": "HOU",
}

INJURY_WORDS = re.compile(
    r"injur|injured reserve|\bIR\b|concussion|surgery|questionable|doubtful|ruled out|"
    r"\bout for\b|hamstring|knee|ankle|\bACL\b|achilles|protocol|expected to play|"
    r"limited|did not practice|sidelined|placed on", re.I)
TRANSACTION_WORDS = re.compile(
    r"\bsign|\bdeal\b|\btrade|\brelease|\bwaive|\bcontract|\bagree|extension|\bcut\b|"
    r"\bclaim|\bactivat|\bpromot|\bsuspend", re.I)


def to_code(abbr: str | None) -> str | None:
    if not abbr:
        return None
    return ESPN_TO_CODE.get(abbr.upper(), abbr.upper())


def espn_abbr(code: str) -> str:
    return CODE_TO_ESPN.get(code, code)


def logo_url(code: str) -> str:
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{espn_abbr(code).lower()}.png"


# ---------------------------------------------------------------------------
# Scoreboard
# ---------------------------------------------------------------------------

def _int(x):
    try:
        return int(str(x).replace("+", ""))
    except (TypeError, ValueError):
        return None


def _float(x):
    try:
        return float(str(x).lstrip("ou+"))
    except (TypeError, ValueError):
        return None


def parse_event(ev: dict) -> dict | None:
    comps = ev.get("competitions") or []
    if not comps:
        return None
    comp = comps[0]
    status = comp.get("status") or ev.get("status") or {}
    stype = status.get("type") or {}
    competitors = comp.get("competitors") or []
    home = next((c for c in competitors if c.get("homeAway") == "home"), None)
    away = next((c for c in competitors if c.get("homeAway") == "away"), None)
    if not home or not away:
        return None
    state = stype.get("state", "pre")
    completed = bool(stype.get("completed"))
    home_score = _int(home.get("score")) if state != "pre" else None
    away_score = _int(away.get("score")) if state != "pre" else None
    winner = None
    if completed:
        if home.get("winner") is True:
            winner = "home"
        elif away.get("winner") is True:
            winner = "away"
        elif home_score is not None and away_score is not None and home_score != away_score:
            winner = "home" if home_score > away_score else "away"
    odds = (comp.get("odds") or [None])[0] or {}
    spread_line = None
    if odds.get("spread") is not None:
        spread_line = -float(odds["spread"])           # nflverse sign: + = home favored
    ml = odds.get("moneyline") or {}
    home_ml = _int(((ml.get("home") or {}).get("close") or {}).get("odds"))
    away_ml = _int(((ml.get("away") or {}).get("close") or {}).get("odds"))
    headline = None
    heads = comp.get("headlines") or []
    if heads:
        headline = heads[0].get("shortLinkText") or heads[0].get("description")
    venue = comp.get("venue") or {}
    addr = venue.get("address") or {}
    name = stype.get("name", "")
    if completed or name == "STATUS_FINAL":
        gstatus = "final"
    elif "POSTPONED" in name or "CANCELED" in name:
        gstatus = "postponed"
    elif state == "in":
        gstatus = "in_progress"
    else:
        gstatus = "scheduled"
    return {
        "espnId": str(ev.get("id")),
        "week": int((ev.get("week") or {}).get("number") or 0),
        "date": ev.get("date"),
        "timeValid": comp.get("timeValid", True),
        "status": gstatus,
        "statusName": name,
        "statusDetail": stype.get("shortDetail") or stype.get("detail") or "",
        "clock": status.get("displayClock"),
        "period": status.get("period"),
        "home": to_code((home.get("team") or {}).get("abbreviation")),
        "away": to_code((away.get("team") or {}).get("abbreviation")),
        "homeScore": home_score,
        "awayScore": away_score,
        "winner": winner,
        "spreadLine": spread_line,
        "homeMoneyline": home_ml,
        "awayMoneyline": away_ml,
        "totalLine": _float(odds.get("overUnder")),
        "oddsProvider": (odds.get("provider") or {}).get("name"),
        "broadcast": comp.get("broadcast") or "",
        "headline": headline,
        "neutralSite": bool(comp.get("neutralSite")),
        "venue": venue.get("fullName"),
        "city": addr.get("city"),
        "weather": (ev.get("weather") or {}).get("displayValue"),
        "temperature": (ev.get("weather") or {}).get("temperature"),
        "homeRecord": next((r.get("summary") for r in home.get("records") or [] if r.get("type") == "total"), None),
        "awayRecord": next((r.get("summary") for r in away.get("records") or [] if r.get("type") == "total"), None),
    }


def fetch_scoreboard(season: int, refresh: bool = False, ttl: float = 300) -> FetchResult:
    """All regular-season events for a season in one call, keyed by ESPN id.

    ESPN's regular season for year Y spans early September to mid January.
    """
    url = f"{BASE}/site/v2/sports/football/nfl/scoreboard?dates={season}0901-{season + 1}0131&limit=1000"
    res = cached_fetch(url, f"espn_scoreboard_{season}.json", ttl, refresh, parse=parse_json)
    events: dict[str, dict] = {}
    calendar: list[dict] = []
    if res.data:
        for ev in res.data.get("events") or []:
            season_info = ev.get("season") or {}
            if season_info.get("type") not in (None, 2):
                continue
            if season_info.get("year") not in (None, season):
                continue
            parsed = parse_event(ev)
            if parsed:
                events[parsed["espnId"]] = parsed
        for league in res.data.get("leagues") or []:
            for section in league.get("calendar") or []:
                if str(section.get("value")) == "2":
                    for entry in section.get("entries") or []:
                        calendar.append({
                            "week": int(entry.get("value") or 0),
                            "start": entry.get("startDate"),
                            "end": entry.get("endDate"),
                            "label": entry.get("detail"),
                        })
    res.data = {"events": events, "calendar": calendar}
    return res


# ---------------------------------------------------------------------------
# Injuries
# ---------------------------------------------------------------------------

def fetch_injuries(refresh: bool = False, ttl: float = 1800) -> FetchResult:
    url = f"{BASE}/site/v2/sports/football/nfl/injuries"
    res = cached_fetch(url, "espn_injuries.json", ttl, refresh, parse=parse_json)
    by_team: dict[str, list[dict]] = {}
    if res.data:
        for group in res.data.get("injuries") or []:
            for item in group.get("injuries") or []:
                status = item.get("status") or ""
                if status.lower() == "active":
                    continue
                athlete = item.get("athlete") or {}
                team = to_code((athlete.get("team") or {}).get("abbreviation")) or ESPN_ID_TO_CODE.get(str(group.get("id")))
                if not team:
                    continue
                details = item.get("details") or {}
                headshot = ((athlete.get("headshot") or {}).get("href")) or ""
                m = re.search(r"/(\d+)\.png", headshot)
                by_team.setdefault(team, []).append({
                    "player": athlete.get("displayName") or athlete.get("shortName") or "",
                    "position": ((athlete.get("position") or {}).get("abbreviation")) or "",
                    "status": status,
                    "detail": details.get("type") or "",
                    "returnDate": details.get("returnDate"),
                    "comment": item.get("shortComment") or "",
                    "updated": item.get("date"),
                    "athleteId": m.group(1) if m else None,
                    "headshot": headshot or None,
                })
    order = {"out": 0, "injured reserve": 1, "doubtful": 2, "suspension": 3, "questionable": 4}
    for team, items in by_team.items():
        items.sort(key=lambda i: (order.get(i["status"].lower(), 9), i["player"]))
    res.data = by_team
    return res


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

def fetch_news(limit: int = 60, refresh: bool = False, ttl: float = 900) -> FetchResult:
    url = f"{BASE}/site/v2/sports/football/nfl/news?limit={limit}"
    res = cached_fetch(url, "espn_news.json", ttl, refresh, parse=parse_json)
    items: list[dict] = []
    if res.data:
        for art in res.data.get("articles") or []:
            teams, athletes = [], []
            for cat in art.get("categories") or []:
                if cat.get("type") == "team":
                    code = to_code((cat.get("team") or {}).get("abbreviation")) or ESPN_ID_TO_CODE.get(str(cat.get("teamId")))
                    if code and code not in teams:
                        teams.append(code)
                elif cat.get("type") == "athlete":
                    athletes.append(str(cat.get("athleteId") or (cat.get("athlete") or {}).get("id") or ""))
            text = f"{art.get('headline') or ''} {art.get('description') or ''}"
            if INJURY_WORDS.search(text):
                kind = "injury"
            elif TRANSACTION_WORDS.search(text):
                kind = "transaction"
            else:
                kind = "news"
            items.append({
                "id": str(art.get("id")),
                "headline": art.get("headline") or "",
                "description": art.get("description") or "",
                "published": art.get("published"),
                "url": ((art.get("links") or {}).get("web") or {}).get("href"),
                "teams": teams if len(teams) <= 4 else [],
                "leagueWide": len(teams) > 4,
                "athleteIds": [a for a in athletes if a],
                "kind": kind,
                "type": art.get("type"),
                "byline": art.get("byline"),
            })
    items.sort(key=lambda a: a.get("published") or "", reverse=True)
    res.data = items
    return res


# ---------------------------------------------------------------------------
# Teams and standings
# ---------------------------------------------------------------------------

def fetch_teams(refresh: bool = False, ttl: float = 86400) -> FetchResult:
    url = f"{BASE}/site/v2/sports/football/nfl/teams"
    res = cached_fetch(url, "espn_teams.json", ttl, refresh, parse=parse_json)
    teams: dict[str, dict] = {}
    if res.data:
        for sport in res.data.get("sports") or []:
            for league in sport.get("leagues") or []:
                for wrap in league.get("teams") or []:
                    t = wrap.get("team") or {}
                    code = to_code(t.get("abbreviation"))
                    if not code:
                        continue
                    logos = t.get("logos") or []
                    logo = next((l.get("href") for l in logos if "default" in (l.get("rel") or [])), None)
                    dark = next((l.get("href") for l in logos if "dark" in (l.get("rel") or []) and "scoreboard" not in (l.get("rel") or [])), None)
                    teams[code] = {
                        "code": code,
                        "espnId": str(t.get("id")),
                        "name": t.get("name") or t.get("shortDisplayName"),
                        "city": t.get("location"),
                        "displayName": t.get("displayName"),
                        "color": "#" + (t.get("color") or "444444"),
                        "altColor": "#" + (t.get("alternateColor") or "999999"),
                        "logo": logo or logo_url(code),
                        "logoDark": dark,
                    }
    res.data = teams
    return res


def fetch_standings(season: int, refresh: bool = False, ttl: float = 3600) -> FetchResult:
    url = f"{BASE}/v2/sports/football/nfl/standings?season={season}"
    res = cached_fetch(url, f"espn_standings_{season}.json", ttl, refresh, parse=parse_json)
    table: dict[str, dict] = {}
    if res.data:
        for conf in res.data.get("children") or []:
            entries = ((conf.get("standings") or {}).get("entries")) or []
            for e in entries:
                code = to_code((e.get("team") or {}).get("abbreviation"))
                if not code:
                    continue
                st = {s.get("name"): s for s in e.get("stats") or []}

                def val(name, default=0):
                    s = st.get(name) or {}
                    v = s.get("value")
                    return default if v is None else v

                streak_txt = (st.get("streak") or {}).get("displayValue") or ""
                table[code] = {
                    "wins": int(val("wins")),
                    "losses": int(val("losses")),
                    "ties": int(val("ties")),
                    "pointsFor": int(val("pointsFor")),
                    "pointsAgainst": int(val("pointsAgainst")),
                    "pointDiff": int(val("pointDifferential")),
                    "streak": streak_txt if re.match(r"^[WL]\d+$", streak_txt) else None,
                    "record": (st.get("overall") or {}).get("displayValue") or f"{int(val('wins'))}-{int(val('losses'))}",
                    "conference": conf.get("abbreviation"),
                    "seed": int(val("playoffSeed")) or None,
                }
    res.data = table
    return res


def fetch_calendar(refresh: bool = False, ttl: float = 86400) -> FetchResult:
    """Regular-season week date ranges from the default scoreboard call."""
    url = f"{BASE}/site/v2/sports/football/nfl/scoreboard"
    res = cached_fetch(url, "espn_calendar.json", ttl, refresh, parse=parse_json)
    weeks: list[dict] = []
    if res.data:
        for league in res.data.get("leagues") or []:
            for section in league.get("calendar") or []:
                if str(section.get("value")) == "2":
                    for entry in section.get("entries") or []:
                        weeks.append({
                            "week": int(entry.get("value") or 0),
                            "start": entry.get("startDate"),
                            "end": entry.get("endDate"),
                            "label": entry.get("detail"),
                        })
            weeks_season = (league.get("season") or {}).get("year")
            if weeks and weeks_season:
                for w in weeks:
                    w["season"] = int(weeks_season)
    res.data = weeks
    return res
