"""Schedule, results and betting-line data from nflverse.

Source: https://github.com/nflverse/nfldata (data/games.csv). One row per game
from 1999 to the current season. Betting lines (moneylines, spreads) are
populated for upcoming games as sportsbooks post them, and closing lines are
kept for completed games.
"""
from __future__ import annotations

import datetime as dt
import os
import time
import urllib.request

import pandas as pd

GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "games.csv")
CACHE_MAX_AGE_SECONDS = 6 * 3600

TEAM_NAMES = {
    "ARI": "Cardinals", "ATL": "Falcons", "BAL": "Ravens", "BUF": "Bills",
    "CAR": "Panthers", "CHI": "Bears", "CIN": "Bengals", "CLE": "Browns",
    "DAL": "Cowboys", "DEN": "Broncos", "DET": "Lions", "GB": "Packers",
    "HOU": "Texans", "IND": "Colts", "JAX": "Jaguars", "KC": "Chiefs",
    "LA": "Rams", "LAC": "Chargers", "LV": "Raiders", "MIA": "Dolphins",
    "MIN": "Vikings", "NE": "Patriots", "NO": "Saints", "NYG": "Giants",
    "NYJ": "Jets", "PHI": "Eagles", "PIT": "Steelers", "SEA": "Seahawks",
    "SF": "49ers", "TB": "Buccaneers", "TEN": "Titans", "WAS": "Commanders",
}

# Aliases people commonly type -> nflverse abbreviation.
TEAM_ALIASES = {
    "LAR": "LA", "RAMS": "LA", "STL": "LA",
    "OAK": "LV", "SD": "LAC", "WSH": "WAS", "JAC": "JAX",
    "GNB": "GB", "KAN": "KC", "NWE": "NE", "NOR": "NO", "SFO": "SF",
    "TAM": "TB", "LVR": "LV",
}
for _abbr, _name in TEAM_NAMES.items():
    TEAM_ALIASES[_name.upper()] = _abbr


def normalize_team(text: str) -> str:
    """Map a user-typed team (abbreviation or nickname) to the nflverse code."""
    key = text.strip().upper()
    if key in TEAM_NAMES:
        return key
    if key in TEAM_ALIASES:
        return TEAM_ALIASES[key]
    raise ValueError(f"Unknown team '{text}'. Use one of: {', '.join(sorted(TEAM_NAMES))}")


def load_games(refresh: bool = False, cache_file: str = CACHE_FILE) -> pd.DataFrame:
    """Load the nflverse games table, downloading when the cache is stale."""
    stale = True
    if os.path.exists(cache_file) and not refresh:
        age = time.time() - os.path.getmtime(cache_file)
        stale = age > CACHE_MAX_AGE_SECONDS
    if stale or refresh:
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        try:
            urllib.request.urlretrieve(GAMES_URL, cache_file + ".tmp")
            os.replace(cache_file + ".tmp", cache_file)
        except Exception as exc:  # noqa: BLE001 - fall back to a stale cache
            if not os.path.exists(cache_file):
                raise RuntimeError(f"Could not download {GAMES_URL}: {exc}") from exc
            print(f"warning: download failed ({exc}); using cached data")
    games = pd.read_csv(cache_file, low_memory=False)
    games["gameday"] = pd.to_datetime(games["gameday"])
    return games


def regular_season(games: pd.DataFrame, season: int) -> pd.DataFrame:
    """Regular-season games for one season, sorted by week and kickoff."""
    out = games[(games["season"] == season) & (games["game_type"] == "REG")].copy()
    return out.sort_values(["week", "gameday", "gametime"]).reset_index(drop=True)


def latest_season(games: pd.DataFrame) -> int:
    return int(games["season"].max())


def current_week(season_games: pd.DataFrame, today: dt.date | None = None) -> int:
    """First week that still has an unplayed game.

    A game counts as played once nflverse has recorded a result. Before the
    season starts this is week 1; after week 18 is complete it stays at 18.
    """
    pending = season_games[season_games["result"].isna()]
    if pending.empty:
        return int(season_games["week"].max())
    return int(pending["week"].min())


def team_list(season_games: pd.DataFrame) -> list[str]:
    teams = set(season_games["home_team"]).union(season_games["away_team"])
    return sorted(teams)
