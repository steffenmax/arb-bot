"""Parse survivor picks pasted from a pool site.

Pool sites vary, and none of them offer a public export, so this reads what
you get from selecting the entries page and copying it. It looks for week
markers and team names in reading order and pairs them up, which covers the
common shapes:

    Entry 1
    Week 1   Philadelphia Eagles   WIN
    Week 2   Buffalo Bills         LOSS

    My Entry: W1 PHI, W2 BUF

    Week 1
    Eagles
    Week 2
    Bills

Nothing is applied automatically: the caller shows the result for review
first, because a misread pick would corrupt the record of what you have
burned.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

TEAMS = {
    "ARI": ("Arizona", "Cardinals"), "ATL": ("Atlanta", "Falcons"),
    "BAL": ("Baltimore", "Ravens"), "BUF": ("Buffalo", "Bills"),
    "CAR": ("Carolina", "Panthers"), "CHI": ("Chicago", "Bears"),
    "CIN": ("Cincinnati", "Bengals"), "CLE": ("Cleveland", "Browns"),
    "DAL": ("Dallas", "Cowboys"), "DEN": ("Denver", "Broncos"),
    "DET": ("Detroit", "Lions"), "GB": ("Green Bay", "Packers"),
    "HOU": ("Houston", "Texans"), "IND": ("Indianapolis", "Colts"),
    "JAX": ("Jacksonville", "Jaguars"), "KC": ("Kansas City", "Chiefs"),
    "LA": ("Los Angeles", "Rams"), "LAC": ("Los Angeles", "Chargers"),
    "LV": ("Las Vegas", "Raiders"), "MIA": ("Miami", "Dolphins"),
    "MIN": ("Minnesota", "Vikings"), "NE": ("New England", "Patriots"),
    "NO": ("New Orleans", "Saints"), "NYG": ("New York", "Giants"),
    "NYJ": ("New York", "Jets"), "PHI": ("Philadelphia", "Eagles"),
    "PIT": ("Pittsburgh", "Steelers"), "SEA": ("Seattle", "Seahawks"),
    "SF": ("San Francisco", "49ers"), "TB": ("Tampa Bay", "Buccaneers"),
    "TEN": ("Tennessee", "Titans"), "WAS": ("Washington", "Commanders"),
}
# Abbreviations other sites use for the same teams.
ALIASES = {
    "LAR": "LA", "STL": "LA", "RAMS": "LA", "WSH": "WAS", "WFT": "WAS",
    "JAC": "JAX", "OAK": "LV", "LVR": "LV", "SD": "LAC", "SDG": "LAC",
    "GNB": "GB", "KAN": "KC", "NWE": "NE", "NOR": "NO", "SFO": "SF",
    "TAM": "TB", "NINERS": "SF", "49ERS": "SF",
}


# Codes collide with ordinary words — NO, WAS, CAR, DEN, MIN, TEN, SEA, PIT,
# LA, IN — so a bare code only counts when it is capitalised, the way every
# pool site writes it. Nicknames and city names match in any case.
NICKNAME_ALIASES = {"RAMS", "NINERS", "49ERS"}      # names, not codes
CODE_PHRASES = (set(TEAMS) | set(ALIASES)) - NICKNAME_ALIASES


def _lookup() -> list[tuple[str, str]]:
    """(searchable phrase, team code), longest first so 'New York Jets' wins
    over 'Jets' and neither is confused with 'New York'."""
    out: list[tuple[str, str]] = []
    cities: dict[str, list[str]] = {}
    for code, (city, nick) in TEAMS.items():
        cities.setdefault(city.upper(), []).append(code)
    for code, (city, nick) in TEAMS.items():
        out.append((f"{city} {nick}".upper(), code))
        out.append((nick.upper(), code))
        if len(cities[city.upper()]) == 1:      # "Los Angeles" alone is ambiguous
            out.append((city.upper(), code))
        out.append((code, code))
    out.extend((alias, code) for alias, code in ALIASES.items())
    out.sort(key=lambda kv: -len(kv[0]))
    return out


LOOKUP = _lookup()
WEEK_RE = re.compile(r"\b(?:WEEK|WK|W)\s*[:#]?\s*(\d{1,2})\b", re.I)
RESULT_RE = re.compile(r"\b(WIN|WON|LOSS|LOST|ELIMINATED|OUT|ALIVE|SURVIVED|PENDING)\b", re.I)
ENTRY_RE = re.compile(r"^\s*(?:ENTRY|TEAM|LINEUP)\s*[:#]?\s*([A-Za-z0-9 '._-]{1,24})\s*$", re.I)
LABEL_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 '._-]{0,23}?)\s*:\s*(.*)$")


def find_teams(text: str) -> list[tuple[int, str, str]]:
    """(position, matched phrase, team code) for every team named in `text`."""
    upper = text.upper()
    claimed: list[tuple[int, int]] = []
    found: list[tuple[int, str, str]] = []
    for phrase, code in LOOKUP:
        for m in re.finditer(rf"(?<![A-Z0-9]){re.escape(phrase)}(?![A-Z0-9])", upper):
            a, b = m.span()
            if any(a < y and x < b for x, y in claimed):
                continue                      # already part of a longer name
            if phrase in CODE_PHRASES and not text[a:b].isupper():
                continue                      # 'no', 'was', 'car' are words
            claimed.append((a, b))
            found.append((a, text[a:b], code))
    found.sort()
    return found


@dataclass
class ImportedPick:
    week: int
    team: str
    matched: str
    result: str | None = None


@dataclass
class ImportResult:
    entries: dict[str, list[ImportedPick]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "entries": {
                name: [{"week": p.week, "team": p.team, "matched": p.matched, "result": p.result}
                       for p in sorted(picks, key=lambda p: p.week)]
                for name, picks in self.entries.items()
            },
            "notes": self.notes,
        }


def parse_picks(text: str, default_entry: str = "A", known_entries: list[str] | None = None) -> ImportResult:
    """Pull (entry, week, team) triples out of pasted text."""
    out = ImportResult()
    known = {e.upper(): e for e in (known_entries or [])}
    entry = default_entry
    week: int | None = None
    seen: set[tuple[str, int]] = set()

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        # "Entry 2" or "Max's Entry" on its own line switches entry
        m = ENTRY_RE.match(line)
        if m:
            label = m.group(1).strip()
            entry = known.get(label.upper(), label)
            week = None
            continue
        # "B: W1 PHI, W2 BUF" names the entry and carries picks on one line
        rest = line
        m = LABEL_RE.match(line)
        if m and not WEEK_RE.match(line) and not find_teams(m.group(1)):
            label = m.group(1).strip()
            if label.upper() in known or len(label) <= 12:
                entry = known.get(label.upper(), label)
                rest = m.group(2)
                week = None

        weeks = [int(w) for w in WEEK_RE.findall(rest)]
        teams = find_teams(rest)
        result = RESULT_RE.search(rest)
        verdict = result.group(1).upper() if result else None

        if weeks and not teams:
            week = weeks[-1]                 # a bare "Week 3" header
            continue
        if not teams:
            continue

        picks = out.entries.setdefault(entry, [])
        if len(weeks) == len(teams) and weeks:
            pairs = list(zip(weeks, teams))
        elif len(weeks) == 1:
            pairs = [(weeks[0], teams[0])]
            if len(teams) > 1:
                out.notes.append(
                    f"Line {raw.strip()[:60]!r} names {len(teams)} teams for week {weeks[0]}; "
                    f"kept {teams[0][2]}.")
        elif week is not None:
            pairs = [(week, teams[0])]
        else:
            out.notes.append(f"No week number for {teams[0][2]} in {raw.strip()[:60]!r}; skipped.")
            continue

        for wk, (_, matched, code) in pairs:
            if not 1 <= wk <= 18:
                out.notes.append(f"Week {wk} is out of range; skipped {code}.")
                continue
            if (entry, wk) in seen:
                out.notes.append(f"Entry {entry} already has a week {wk} pick; ignored the later {code}.")
                continue
            seen.add((entry, wk))
            picks.append(ImportedPick(wk, code, matched, verdict))
        week = None

    out.entries = {name: picks for name, picks in out.entries.items() if picks}
    for name, picks in out.entries.items():
        out.notes.append(f"Entry {name}: {len(picks)} pick(s) read — "
                         + ", ".join(f"W{p.week} {p.team}" for p in sorted(picks, key=lambda p: p.week)))
    if not out.entries:
        out.notes.append("No picks recognised. Include a week number and a team name on each line, "
                         "for example: Week 1  Philadelphia Eagles")
    return out
