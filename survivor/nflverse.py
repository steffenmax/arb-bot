"""nflverse release assets: team statistics and depth charts."""
from __future__ import annotations

import io

import pandas as pd

from .fetch import FetchResult, cached_fetch

RELEASES = "https://github.com/nflverse/nflverse-data/releases/download"


def _csv(body: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(body), low_memory=False)


def fetch_team_stats(season: int, refresh: bool = False, ttl: float = 6 * 3600) -> tuple[FetchResult, int]:
    """Season team stats; falls back to the previous season until this one
    is published (nflverse posts the first file after week 1)."""
    for yr in (season, season - 1):
        res = cached_fetch(f"{RELEASES}/stats_team/stats_team_reg_{yr}.csv", f"stats_team_reg_{yr}.csv",
                           ttl, refresh, parse=_csv)
        if res.data is not None and len(res.data):
            return res, yr
    return FetchResult(None, 0.0, True, "team stats unavailable"), season


def fetch_team_week_stats(season: int, refresh: bool = False, ttl: float = 6 * 3600) -> tuple[FetchResult, int]:
    for yr in (season, season - 1):
        res = cached_fetch(f"{RELEASES}/stats_team/stats_team_week_{yr}.csv", f"stats_team_week_{yr}.csv",
                           ttl, refresh, parse=_csv)
        if res.data is not None and len(res.data):
            return res, yr
    return FetchResult(None, 0.0, True, "team week stats unavailable"), season


def team_strength_table(reg: pd.DataFrame | None, week: pd.DataFrame | None) -> dict[str, dict]:
    """Per-team efficiency summary from the nflverse stat files."""
    out: dict[str, dict] = {}
    if reg is None or reg.empty:
        return out
    reg = reg[reg.get("season_type", "REG") == "REG"] if "season_type" in reg else reg
    def_epa: dict[str, float] = {}
    def_plays: dict[str, float] = {}
    if week is not None and not week.empty and {"game_id", "team", "opponent_team"} <= set(week.columns):
        wk = week[week.get("season_type", "REG") == "REG"] if "season_type" in week else week
        for _, r in wk.iterrows():
            opp = r["opponent_team"]
            epa = float(r.get("passing_epa", 0) or 0) + float(r.get("rushing_epa", 0) or 0)
            plays = float(r.get("attempts", 0) or 0) + float(r.get("carries", 0) or 0) + float(r.get("sacks_suffered", 0) or 0)
            def_epa[opp] = def_epa.get(opp, 0.0) + epa
            def_plays[opp] = def_plays.get(opp, 0.0) + plays
    for _, r in reg.iterrows():
        team = r["team"]
        games = int(r.get("games", 0) or 0) or None
        plays = float(r.get("attempts", 0) or 0) + float(r.get("carries", 0) or 0) + float(r.get("sacks_suffered", 0) or 0)
        off_epa = float(r.get("passing_epa", 0) or 0) + float(r.get("rushing_epa", 0) or 0)
        takeaways = float(r.get("def_interceptions", 0) or 0) + float(r.get("fumble_recovery_opp", 0) or 0)
        giveaways = float(r.get("passing_interceptions", 0) or 0) + float(r.get("fumbles_lost_total", 0) or 0)
        out[team] = {
            "games": games,
            "offEpaPerPlay": round(off_epa / plays, 4) if plays else None,
            "defEpaPerPlay": round(def_epa[team] / def_plays[team], 4) if def_plays.get(team) else None,
            "passEpaPerDropback": round(float(r.get("passing_epa", 0) or 0) / (float(r.get("attempts", 0) or 0) + float(r.get("sacks_suffered", 0) or 0)), 4)
            if (float(r.get("attempts", 0) or 0) + float(r.get("sacks_suffered", 0) or 0)) else None,
            "rushEpaPerCarry": round(float(r.get("rushing_epa", 0) or 0) / float(r.get("carries", 0) or 0), 4) if float(r.get("carries", 0) or 0) else None,
            "cpoe": round(float(r.get("passing_cpoe", 0) or 0), 2) if r.get("passing_cpoe") is not None else None,
            "turnoverMargin": int(takeaways - giveaways),
            "sacksTaken": int(r.get("sacks_suffered", 0) or 0),
            "sacksMade": int(r.get("def_sacks", 0) or 0),
            "passYards": int(r.get("passing_yards", 0) or 0),
            "rushYards": int(r.get("rushing_yards", 0) or 0),
        }
    return out


def fetch_depth_chart_qb1(season: int, refresh: bool = False, ttl: float = 86400) -> FetchResult:
    """Starting quarterback per team from the newest depth-chart snapshot.

    The full file is about 48 MB of daily snapshots, newest first, so only
    the first 1.5 MB is requested with an HTTP Range header.
    """
    url = f"{RELEASES}/depth_charts/depth_charts_{season}.csv"
    res = cached_fetch(url, f"depth_charts_{season}_head.csv", ttl, refresh,
                       headers={"Range": "bytes=0-1500000"})
    qb1: dict[str, dict] = {}
    if res.data:
        try:
            df = pd.read_csv(io.BytesIO(res.data), on_bad_lines="skip", low_memory=False)
            if {"dt", "team", "pos_abb", "pos_rank"} <= set(df.columns):
                latest = df.groupby("team")["dt"].transform("max")
                qb = df[(df["dt"] == latest) & (df["pos_abb"] == "QB") & (df["pos_rank"] == 1)]
                for _, r in qb.iterrows():
                    qb1[r["team"]] = {
                        "name": r.get("player_name"),
                        "espnId": str(int(r["espn_id"])) if pd.notna(r.get("espn_id")) else None,
                        "gsisId": r.get("gsis_id") if pd.notna(r.get("gsis_id")) else None,
                        "asOf": r.get("dt"),
                    }
        except Exception as exc:  # noqa: BLE001
            res.error = f"depth chart parse failed: {exc}"
    res.data = qb1
    return res
