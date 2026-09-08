"""Assemble the dashboard payload: data feeds -> probabilities -> plan -> JSON."""
from __future__ import annotations

import datetime as dt
import math
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .. import data, espn, nflverse, probs
from ..injuries import Injury, team_impact
from ..optimizer import (
    Branch, EntrySpec, Path, PlanResult, WeekPick, contrarian_bonus, plan_entries,
)

EASTERN = ZoneInfo("America/New_York")
VERSION = "1.0.0"


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean(x):
    """Make numpy / pandas / NaN / infinite values JSON-safe."""
    if x is None:
        return None
    if isinstance(x, (np.floating, float)):
        f = float(x)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    if isinstance(x, pd.Timestamp):
        return None if pd.isna(x) else x.isoformat()
    if x is pd.NaT or x is pd.NA:
        return None
    if isinstance(x, str) and x.lower() == "nan":
        return None
    return x


def sanitize(obj):
    """Recursively convert numpy scalars and NaN so json.dumps emits valid JSON."""
    if isinstance(obj, dict):
        return {str(k): sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize(v) for v in obj]
    return _clean(obj)


def _kickoff_iso(row: pd.Series, ev: dict | None) -> str | None:
    if ev and ev.get("date"):
        raw = ev["date"]
        try:
            d = dt.datetime.strptime(raw, "%Y-%m-%dT%H:%MZ").replace(tzinfo=dt.timezone.utc)
            return d.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            return raw
    try:
        day = pd.Timestamp(row["gameday"]).to_pydatetime()
        hh, mm = str(row.get("gametime") or "13:00").split(":")[:2]
        local = day.replace(hour=int(hh), minute=int(mm), tzinfo=EASTERN)
        return local.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Data assembly
# ---------------------------------------------------------------------------

class Bundle:
    """Everything loaded for one dashboard build."""

    def __init__(self, cfg: dict, refresh: bool = False):
        self.warnings: list[str] = []
        self.ages: dict[str, str | None] = {}
        games = data.load_games(refresh=refresh)
        if data.LAST_WARNING:
            self.warnings.append(data.LAST_WARNING)
        self.ages["games"] = dt.datetime.fromtimestamp(
            __import__("os").path.getmtime(data.CACHE_FILE), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.all_games = games
        self.season = int(cfg["season"] or data.latest_season(games))
        sg = data.regular_season(games, self.season)
        if sg.empty:
            raise ValueError(f"No regular-season games for {self.season}")
        self.teams = data.team_list(sg)

        sb = espn.fetch_scoreboard(self.season, refresh)
        self._note("espn", sb)
        self.events = (sb.data or {}).get("events", {})
        cal = espn.fetch_calendar(refresh)
        self.calendar = [w for w in (cal.data or []) if w.get("season") in (None, self.season)]
        inj = espn.fetch_injuries(refresh)
        self._note("injuries", inj)
        self.injuries = inj.data or {}
        news = espn.fetch_news(refresh=refresh)
        self._note("news", news)
        self.news = news.data or []
        tm = espn.fetch_teams(refresh)
        self._note("teams", tm)
        self.team_meta = tm.data or {}
        st = espn.fetch_standings(self.season, refresh)
        self._note("standings", st)
        self.standings = st.data or {}
        st_prev = espn.fetch_standings(self.season - 1, refresh)
        self.standings_prev = st_prev.data or {}
        reg, yr = nflverse.fetch_team_stats(self.season, refresh)
        wk, _ = nflverse.fetch_team_week_stats(self.season, refresh)
        self._note("stats", reg)
        self.stats_season = yr
        self.strength = nflverse.team_strength_table(reg.data, wk.data)
        qb = nflverse.fetch_depth_chart_qb1(self.season, refresh)
        self._note("depthChart", qb)
        self.qb1 = qb.data or {}

        self.season_games = self._merge(sg)
        self.current_week = data.current_week(self.season_games)

    def _note(self, key: str, res) -> None:
        self.ages[key] = res.fetched_iso
        if res.error:
            has_data = res.data is not None and res.fetched_at > 0
            self.warnings.append(f"{key}: {res.error}" + (" (using cached copy)" if has_data else " (no data)"))

    def _merge(self, sg: pd.DataFrame) -> pd.DataFrame:
        """Overlay ESPN live status, scores and fresh odds on the nflverse table."""
        sg = sg.copy()
        status, detail, kickoff, home_s, away_s, headline, broadcast = [], [], [], [], [], [], []
        venue, weather, line_src, clock, period, prov, time_valid = [], [], [], [], [], [], []
        for _, row in sg.iterrows():
            eid = str(int(row["espn"])) if pd.notna(row.get("espn")) else None
            ev = self.events.get(eid) if eid else None
            has_result = pd.notna(row.get("result"))
            st = "final" if has_result else "scheduled"
            det = "Final" if has_result else ""
            hs = _clean(row.get("home_score"))
            as_ = _clean(row.get("away_score"))
            src = "nflverse" if pd.notna(row.get("home_moneyline")) or pd.notna(row.get("spread_line")) else None
            if ev:
                if not has_result:
                    st = ev["status"]
                    det = ev.get("statusDetail") or ""
                if ev["status"] == "final":
                    if ev.get("homeScore") is not None:
                        hs, as_ = ev["homeScore"], ev["awayScore"]
                    if pd.isna(row.get("result")) and hs is not None and as_ is not None:
                        sg.loc[row.name, "home_score"] = hs
                        sg.loc[row.name, "away_score"] = as_
                        sg.loc[row.name, "result"] = hs - as_
                elif ev["status"] == "in_progress":
                    hs, as_ = ev.get("homeScore"), ev.get("awayScore")
                if pd.isna(row.get("home_moneyline")) and ev.get("homeMoneyline") is not None and ev.get("awayMoneyline") is not None:
                    sg.loc[row.name, "home_moneyline"] = ev["homeMoneyline"]
                    sg.loc[row.name, "away_moneyline"] = ev["awayMoneyline"]
                    src = "espn"
                if pd.isna(row.get("spread_line")) and ev.get("spreadLine") is not None:
                    sg.loc[row.name, "spread_line"] = ev["spreadLine"]
                    src = src or "espn"
                if pd.isna(row.get("total_line")) and ev.get("totalLine") is not None:
                    sg.loc[row.name, "total_line"] = ev["totalLine"]
            status.append(st)
            detail.append(det)
            kickoff.append(_kickoff_iso(row, ev))
            home_s.append(hs)
            away_s.append(as_)
            headline.append((ev or {}).get("headline"))
            broadcast.append((ev or {}).get("broadcast") or "")
            venue.append((ev or {}).get("venue") or _clean(row.get("stadium")))
            weather.append((ev or {}).get("weather"))
            line_src.append(src)
            clock.append((ev or {}).get("clock"))
            period.append((ev or {}).get("period"))
            prov.append((ev or {}).get("oddsProvider"))
            time_valid.append(bool((ev or {}).get("timeValid", True)))
        sg["status"] = status
        sg["time_valid"] = time_valid
        sg["status_detail"] = detail
        sg["kickoff"] = kickoff
        sg["home_score_live"] = home_s
        sg["away_score_live"] = away_s
        sg["headline"] = headline
        sg["broadcast"] = broadcast
        sg["venue"] = venue
        sg["weather"] = weather
        sg["line_source"] = line_src
        sg["clock"] = clock
        sg["period"] = period
        sg["odds_provider"] = prov
        return sg

    # ---- injuries -> rating adjustments --------------------------------
    def starter_qb(self, team: str) -> dict:
        """Starting quarterback: depth chart first, then nflverse's projected
        starter for the team's next game (by name)."""
        info = dict(self.qb1.get(team) or {})
        if not info.get("name"):
            sg = getattr(self, "season_games", None)
            rows = self.all_games[(self.all_games["season"] == self.season) & (self.all_games["game_type"] == "REG")] if sg is None else sg
            rows = rows[(rows["home_team"] == team) | (rows["away_team"] == team)].sort_values("week")
            for _, r in rows.iterrows():
                name = r.get("home_qb_name") if r["home_team"] == team else r.get("away_qb_name")
                if isinstance(name, str) and name:
                    info["name"] = name
                    break
        return info

    def is_starter_qb(self, team: str, injury: dict) -> bool:
        qb = self.starter_qb(team)
        if qb.get("espnId") and injury.get("athleteId"):
            return injury["athleteId"] == qb["espnId"]
        name = (qb.get("name") or "").strip().lower()
        return bool(name) and name == (injury.get("player") or "").strip().lower()

    def injury_objects(self, team: str) -> list[Injury]:
        out = []
        for i in self.injuries.get(team, []):
            pos = i["position"]
            if pos == "QB":
                pos = "QB" if self.is_starter_qb(team, i) else "QB2"
            out.append(Injury(i["player"], pos, i["status"], i.get("detail", ""), i.get("updated") or ""))
        return out

    def injury_adjustments(self, weeks: int) -> dict[int, dict[str, float]]:
        table: dict[int, dict[str, float]] = {}
        objs = {t: self.injury_objects(t) for t in self.teams}
        for ahead in range(weeks + 1):
            table[ahead] = {t: team_impact(objs[t], ahead) for t in self.teams}
        return table


# ---------------------------------------------------------------------------
# Payload builders
# ---------------------------------------------------------------------------

def _week_pick(table: probs.ProbTable, wp: WeekPick, locks: dict[str, list[str]]) -> dict:
    w = table.week_index(wp.week)
    opp, home, srcs, gids, raw = [], [], [], [], 1.0
    for t in wp.teams:
        j = table.team_index(t)
        opp.append(table.opponent[w, j])
        home.append(bool(table.is_home[w, j]))
        srcs.append(table.source[w, j])
        gids.append(table.game_id[w, j])
        raw *= float(table.raw_prob[w, j])
    return {
        "week": wp.week, "teams": list(wp.teams), "opponents": opp, "home": home,
        "p": _clean(wp.p), "pRaw": _clean(raw), "sources": srcs,
        "locked": str(wp.week) in locks and sorted(locks[str(wp.week)]) == sorted(wp.teams),
        "required": table.picks_required[w], "gameIds": gids,
    }


def _path_payload(table: probs.ProbTable, path: Path, locks: dict, start: int = 0) -> list[dict]:
    return [_week_pick(table, wp, locks) for wp in path.picks[start:]]


def _branch_payload(table: probs.ProbTable, b: Branch, locks: dict, crowd: dict[str, float], bonus: dict | None) -> dict:
    out = {
        "teams": list(b.teams),
        "p": _clean(b.p_week),
        "pHorizon": _clean(b.survival_from),
        "recommended": bool(b.recommended),
        "path": _path_payload(table, b.path, locks, b.week_index),
    }
    if b.week_index == 0:
        out["crowdPct"] = _clean(sum(crowd.get(t, 0.0) for t in b.teams)) if crowd else None
        out["crowdBonus"] = _clean(sum((bonus or {}).get(t, 0.0) for t in b.teams)) if bonus else None
    return out


def build_dashboard(cfg: dict, refresh: bool = False) -> dict:
    bundle = Bundle(cfg, refresh)
    sg = bundle.season_games
    teams = bundle.teams
    season = bundle.season
    current_week = bundle.current_week
    max_week = int(sg["week"].max())
    horizon = min(int(cfg["horizon"]), max_week)
    warnings = list(bundle.warnings)
    if horizon < current_week:
        warnings.append(f"Horizon week {horizon} is before the current week; using week {current_week}.")
        horizon = current_week

    # ---- probabilities ------------------------------------------------
    prior = probs.prior_from_last_season(bundle.all_games, season, teams)
    ratings = probs.fit_ratings(sg, teams, prior=prior)
    if cfg["injuryAdjust"]:
        ratings.adjustment = bundle.injury_adjustments(max_week - current_week)
    live_ids = set(sg.loc[sg["status"] == "in_progress", "game_id"].astype(str))
    decided = set(sg.loc[sg["result"].notna() | (sg["status"] == "in_progress"), "game_id"].astype(str))
    overrides = {}
    for gid, side in cfg["overrides"].items():
        if gid in decided:
            warnings.append(f"What-if on {gid} ignored: the game is already decided.")
        else:
            overrides[gid] = side
    game_probs = probs.game_probabilities(sg, ratings, overrides, live_ids, current_week)
    picks_per_week = {int(k): v for k, v in cfg["picksPerWeek"].items()}
    table = probs.build_prob_table(game_probs, teams, current_week, horizon, cfg["decay"], picks_per_week)

    # ---- plan -----------------------------------------------------------
    specs = []
    for e in cfg["entries"]:
        used = set(e["used"])
        locks = {}
        for wk, ts in e["locks"].items():
            if int(wk) < current_week:
                # A lock in a played week is history: those teams are burned.
                used.update(ts)
                warnings.append(f"Entry {e['name']}: week {wk} lock {'/'.join(ts)} counted as used (week is over).")
            else:
                locks[int(wk)] = list(ts)
        specs.append(EntrySpec(e["name"], used, locks, e["alive"]))
    crowd = cfg["pickPct"].get(str(current_week), {})
    bonus = contrarian_bonus(table, crowd) if crowd else None
    weight = cfg["contrarianWeight"] if crowd else 0.0
    result: PlanResult = plan_entries(table, specs, cfg["topBranches"], bonus, weight, cfg["objective"], cfg["hedge"])
    for er in result.entries:
        for w in er.warnings:
            warnings.append(f"Entry {er.spec.name}: {w}")

    # ---- games ------------------------------------------------------------
    gp_by_id = {gp.game_id: gp for gp in game_probs}
    picks_by_game: dict[str, list[dict]] = {}
    for er in result.entries:
        if er.plan is None:
            continue
        for wp in er.plan.picks:
            w = table.week_index(wp.week)
            for t in wp.teams:
                gid = table.game_id[w, table.team_index(t)]
                picks_by_game.setdefault(gid, []).append({"entry": er.spec.name, "team": t})
    games_out = []
    sources: dict[str, int] = {}
    for _, row in sg.iterrows():
        gid = str(row["game_id"])
        gp = gp_by_id[gid]
        week = int(row["week"])
        ahead = max(0, week - current_week)
        certain = gp.source in ("final", "override")
        p_dec = gp.p_home if certain else 0.5 + (gp.p_home - 0.5) * math.exp(-cfg["decay"] * ahead)
        if week >= current_week:
            sources[gp.source] = sources.get(gp.source, 0) + 1
        games_out.append({
            "id": gid, "week": week, "kickoff": row["kickoff"], "timeValid": bool(row.get("time_valid", True)),
            "home": row["home_team"], "away": row["away_team"],
            "neutral": str(row.get("location")) == "Neutral",
            "spread": _clean(row.get("spread_line")),
            "homeMoneyline": _clean(row.get("home_moneyline")),
            "awayMoneyline": _clean(row.get("away_moneyline")),
            "total": _clean(row.get("total_line")),
            "lineSource": row.get("line_source"),
            "oddsProvider": row.get("odds_provider"),
            "pHome": _clean(p_dec), "pHomeRaw": _clean(gp.p_home_market if gp.p_home_market is not None else gp.p_home),
            "source": gp.source,
            "status": row["status"], "statusDetail": row["status_detail"],
            "clock": row.get("clock"), "period": _clean(row.get("period")),
            "homeScore": _clean(row["home_score_live"]), "awayScore": _clean(row["away_score_live"]),
            "override": cfg["overrides"].get(gid),
            "headline": row.get("headline"), "broadcast": row.get("broadcast"),
            "venue": row.get("venue"), "weather": row.get("weather"),
            "homeQb": _clean(row.get("home_qb_name")), "awayQb": _clean(row.get("away_qb_name")),
            "picks": picks_by_game.get(gid, []),
        })

    # ---- weeks ------------------------------------------------------------
    cal = {w["week"]: w for w in bundle.calendar}
    weeks_out = []
    for week in range(1, max_week + 1):
        rows = sg[sg["week"] == week]
        statuses = set(rows["status"])
        if statuses <= {"final", "postponed"}:
            wstatus = "final"
        elif "in_progress" in statuses or "final" in statuses:
            wstatus = "live"
        else:
            wstatus = "upcoming"
        c = cal.get(week, {})
        weeks_out.append({
            "week": week,
            "picksRequired": picks_per_week.get(week, 1),
            "start": (c.get("start") or str(rows["gameday"].min().date()))[:10],
            "end": (c.get("end") or str(rows["gameday"].max().date()))[:10],
            "label": c.get("label"),
            "status": wstatus,
            "gameIds": [str(g) for g in rows["game_id"]],
            "byes": sorted(set(teams) - set(rows["home_team"]) - set(rows["away_team"])),
        })

    # ---- teams --------------------------------------------------------------
    now_adj = ratings.adjustment.get(0, {})
    by_week_team: dict[tuple[int, str], pd.Series] = {}
    for _, row in sg.iterrows():
        by_week_team[(int(row["week"]), row["home_team"])] = row
        by_week_team[(int(row["week"]), row["away_team"])] = row
    injury_objs = {t: bundle.injury_objects(t) for t in teams}
    teams_out = {}
    for t in teams:
        meta = bundle.team_meta.get(t, {})
        rec = bundle.standings.get(t, {})
        prev = bundle.standings_prev.get(t, {})
        sched = []
        for week in range(1, max_week + 1):
            row = by_week_team.get((week, t))
            if row is None:
                sched.append({"week": week, "bye": True})
                continue
            gid = str(row["game_id"])
            gp = gp_by_id[gid]
            home = row["home_team"] == t
            p = gp.p_home if home else 1.0 - gp.p_home
            ahead = max(0, week - current_week)
            certain = gp.source in ("final", "override")
            p_dec = p if certain else 0.5 + (p - 0.5) * math.exp(-cfg["decay"] * ahead)
            won = None
            if gp.final and gp.source == "final":
                won = bool(p > 0.5)
            sched.append({
                "week": week, "bye": False, "opponent": row["away_team"] if home else row["home_team"],
                "home": bool(home), "p": _clean(p_dec), "pRaw": _clean(gp.p_home_market if home else (1 - gp.p_home_market) if gp.p_home_market is not None else p),
                "source": gp.source, "gameId": gid, "status": row["status"], "won": won,
            })
        inj = [{
            "player": i["player"], "position": i["position"], "status": i["status"], "detail": i.get("detail"),
            "returnDate": i.get("returnDate"), "comment": i.get("comment"), "updated": i.get("updated"),
            "impact": _clean(next((o.points for o in injury_objs[t] if o.player == i["player"]), 0.0)),
            "isStarterQb": bool(i["position"] == "QB" and bundle.is_starter_qb(t, i)),
        } for i in bundle.injuries.get(t, [])]
        teams_out[t] = {
            "code": t, "name": meta.get("name") or data.TEAM_NAMES.get(t, t), "city": meta.get("city"),
            "displayName": meta.get("displayName"), "color": meta.get("color", "#444444"),
            "altColor": meta.get("altColor", "#999999"), "logo": meta.get("logo") or espn.logo_url(t),
            "record": {"wins": rec.get("wins", 0), "losses": rec.get("losses", 0), "ties": rec.get("ties", 0),
                       "summary": rec.get("record", "0-0"), "streak": rec.get("streak")},
            "rating": _clean(round(ratings.rating[t], 2)),
            "injuryImpact": _clean(round(now_adj.get(t, 0.0), 2)),
            "ratingAdjusted": _clean(round(ratings.rating[t] + now_adj.get(t, 0.0), 2)),
            "qb1": bundle.starter_qb(t).get("name"),
            "stats": {
                "pointsFor": rec.get("pointsFor", 0), "pointsAgainst": rec.get("pointsAgainst", 0),
                "pointDiff": rec.get("pointDiff", 0),
                "lastSeason": {"wins": prev.get("wins"), "losses": prev.get("losses"), "ties": prev.get("ties"),
                               "pointDiff": prev.get("pointDiff"), "record": prev.get("record")},
                "efficiency": bundle.strength.get(t, {}),
                "efficiencySeason": bundle.stats_season,
            },
            "injuries": inj,
            "schedule": sched,
        }

    # ---- entries and joint ------------------------------------------------
    entries_out = []
    for er in result.entries:
        e_cfg = next(e for e in cfg["entries"] if e["name"] == er.spec.name)
        item = {
            "name": er.spec.name, "alive": er.spec.alive, "used": sorted(er.spec.used), "locks": e_cfg["locks"],
            "warnings": er.warnings,
        }
        if er.plan is None:
            item.update({"pHorizon": 0.0, "survivalCurve": [], "plan": [], "branches": {}})
        else:
            item.update({
                "pHorizon": _clean(er.curve[-1]),
                "survivalCurve": [_clean(c) for c in er.curve],
                "plan": _path_payload(table, er.plan, e_cfg["locks"]),
                "branches": {str(wk): [_branch_payload(table, b, e_cfg["locks"], crowd, bonus) for b in bs]
                             for wk, bs in er.branches.items()},
            })
        entries_out.append(item)
    live_names = [er.spec.name for er in result.entries if er.plan is not None]
    joint = result.joint
    alternatives = []
    for k, (score, value, picks) in enumerate(joint.alternatives):
        alternatives.append({"picks": {n: p for n, p in zip(live_names, picks)}, "value": _clean(value),
                             "score": _clean(score), "recommended": k == 0})
    joint_out = {
        "pAny": _clean(joint.p_any), "pAll": _clean(joint.p_all), "expectedAlive": _clean(joint.expected_alive),
        "expectedWeeksAny": _clean(joint.expected_weeks_any),
        "curveAny": [_clean(c) for c in joint.curve_any], "curveAll": [_clean(c) for c in joint.curve_all],
        "weeks": list(table.weeks), "alternatives": alternatives,
    }

    cfg_echo = dict(cfg)
    cfg_echo["season"] = season
    cfg_echo["horizon"] = horizon
    return sanitize({
        "meta": {
            "season": season, "currentWeek": current_week, "generatedAt": _now_iso(), "horizon": horizon,
            "decay": cfg["decay"], "weeksInSeason": max_week, "sources": sources, "dataAge": bundle.ages,
            "warnings": warnings, "version": VERSION, "hfa": _clean(round(ratings.hfa, 2)),
            "ratingsFrom": f"{int(sg['spread_line'].notna().sum())} posted spreads, prior from {season - 1} closing lines",
        },
        "config": cfg_echo,
        "teams": teams_out,
        "weeks": weeks_out,
        "games": games_out,
        "entries": entries_out,
        "joint": joint_out,
        "news": bundle.news,
    })


def refresh_all() -> dict:
    """Force re-download of every feed; returns fetch times."""
    cfgmod = __import__("survivor.dashboard.config", fromlist=["load"])
    bundle = Bundle(cfgmod.load(), refresh=True)
    return bundle.ages
