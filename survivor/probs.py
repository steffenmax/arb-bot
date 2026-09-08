"""Win probabilities for every regular-season game.

Priority per game:
  1. A final score (or a user what-if override): probability 1 or 0.
  2. Sportsbook moneyline (devigged) when one is posted.
  3. Point spread converted through a normal margin model.
  4. A market-implied power rating fitted to every posted spread this season,
     shrunk toward last season's closing-line ratings, optionally adjusted
     for current injuries.

Probabilities for future weeks are then pulled toward 50% by a decay factor
because ratings drift (injuries, form) and the far future is less certain.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.stats import norm

MARGIN_SD = 13.5          # std dev of NFL scoring margin around the spread
PRIOR_REGRESSION = 0.33   # how far last season's ratings regress to the mean
PRIOR_WEIGHT = 2.0        # prior counts as this many games of evidence
DEFAULT_HFA = 1.5         # home-field advantage in points when it cannot be fit


def moneyline_prob(ml: float) -> float:
    """Implied probability of an American moneyline (with vig)."""
    if ml < 0:
        return -ml / (-ml + 100.0)
    return 100.0 / (ml + 100.0)


def devig(home_ml: float, away_ml: float) -> float:
    """Home win probability after removing the bookmaker's margin."""
    h = moneyline_prob(home_ml)
    a = moneyline_prob(away_ml)
    return h / (h + a)


def spread_prob(home_spread: float) -> float:
    """Home win probability from the home team's expected margin."""
    return float(norm.cdf(home_spread / MARGIN_SD))


@dataclass
class Ratings:
    rating: dict[str, float]
    hfa: float
    # adjustment[weeks_ahead][team]: points added to the rating (injuries)
    adjustment: dict[int, dict[str, float]] = field(default_factory=dict)

    def adjusted(self, team: str, weeks_ahead: int = 0) -> float:
        table = self.adjustment.get(weeks_ahead) or self.adjustment.get(max(self.adjustment, default=0), {})
        return self.rating[team] + table.get(team, 0.0)

    def home_spread(self, home: str, away: str, weeks_ahead: int = 0) -> float:
        return self.adjusted(home, weeks_ahead) - self.adjusted(away, weeks_ahead) + self.hfa


def fit_ratings(
    games: pd.DataFrame,
    teams: list[str],
    prior: dict[str, float] | None = None,
    prior_weight: float = PRIOR_WEIGHT,
) -> Ratings:
    """Least-squares power ratings from spread lines.

    Model: spread_line = rating[home] - rating[away] + hfa. With a prior, each
    team also gets a pseudo-observation rating = prior[team] weighted by
    prior_weight, which keeps thin-data teams sensible.
    """
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    lined = games.dropna(subset=["spread_line"])
    lined = lined[lined["home_team"].isin(idx) & lined["away_team"].isin(idx)]
    rows, rhs = [], []
    for _, g in lined.iterrows():
        row = np.zeros(n + 1)
        row[idx[g["home_team"]]] = 1.0
        row[idx[g["away_team"]]] = -1.0
        row[n] = 1.0
        rows.append(row)
        rhs.append(float(g["spread_line"]))
    if prior:
        w = np.sqrt(prior_weight)
        for t in teams:
            row = np.zeros(n + 1)
            row[idx[t]] = w
            rows.append(row)
            rhs.append(w * prior.get(t, 0.0))
    else:
        # Anchor the mean rating at zero so the system is identifiable.
        row = np.zeros(n + 1)
        row[:n] = 1.0
        rows.append(row)
        rhs.append(0.0)
    if not rows:
        return Ratings({t: 0.0 for t in teams}, DEFAULT_HFA)
    A = np.vstack(rows)
    b = np.array(rhs)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    hfa = float(sol[n]) if len(lined) >= 8 else DEFAULT_HFA
    return Ratings({t: float(sol[idx[t]]) for t in teams}, hfa)


def prior_from_last_season(all_games: pd.DataFrame, season: int, teams: list[str]) -> dict[str, float]:
    """Ratings from last season's closing spreads, regressed toward zero."""
    last = all_games[(all_games["season"] == season - 1) & (all_games["game_type"] == "REG")]
    last = last[last["home_team"].isin(teams) & last["away_team"].isin(teams)]
    if last["spread_line"].notna().sum() < 32:
        return {t: 0.0 for t in teams}
    fitted = fit_ratings(last, teams, prior=None)
    return {t: r * (1.0 - PRIOR_REGRESSION) for t, r in fitted.rating.items()}


@dataclass
class GameProb:
    game_id: str
    week: int
    home: str
    away: str
    p_home: float
    source: str                 # final, override, moneyline, spread, rating
    final: bool = False         # game has a result (cannot be picked)
    p_home_market: float | None = None   # market/rating probability even when final


def _market_prob(g: pd.Series, ratings: Ratings, weeks_ahead: int = 0) -> tuple[float, str]:
    if pd.notna(g.get("home_moneyline")) and pd.notna(g.get("away_moneyline")):
        return devig(float(g["home_moneyline"]), float(g["away_moneyline"])), "moneyline"
    if pd.notna(g.get("spread_line")):
        return spread_prob(float(g["spread_line"])), "spread"
    return spread_prob(ratings.home_spread(g["home_team"], g["away_team"], weeks_ahead)), "rating"


def game_probabilities(
    season_games: pd.DataFrame,
    ratings: Ratings,
    overrides: dict[str, str] | None = None,
    live_ids: set[str] | None = None,
    current_week: int = 1,
) -> list[GameProb]:
    """One GameProb per game.

    `overrides` maps game_id to "home" or "away". `live_ids` are games in
    progress: they keep their pre-game probability but cannot be picked.
    """
    overrides = overrides or {}
    live_ids = live_ids or set()
    out: list[GameProb] = []
    for _, g in season_games.iterrows():
        gid = str(g["game_id"])
        market, src = _market_prob(g, ratings, max(0, int(g["week"]) - current_week))
        if gid in live_ids and pd.isna(g.get("result")):
            out.append(GameProb(gid, int(g["week"]), g["home_team"], g["away_team"], market, "live", True, market))
        elif pd.notna(g.get("result")):
            # nflverse result = home score - away score; a tie counts as a loss
            res = float(g["result"])
            p = 1.0 if res > 0 else 0.0
            out.append(GameProb(gid, int(g["week"]), g["home_team"], g["away_team"], p, "final", True, market))
        elif gid in overrides:
            p = 1.0 if overrides[gid] == "home" else 0.0
            out.append(GameProb(gid, int(g["week"]), g["home_team"], g["away_team"], p, "override", False, market))
        else:
            out.append(GameProb(gid, int(g["week"]), g["home_team"], g["away_team"], market, src, False, market))
    return out


@dataclass
class ProbTable:
    """Win probability of each team in each remaining week.

    prob[w, t] is the chance team t wins in week weeks[w]; NaN when the team
    cannot be picked that week (bye, or its game is already final and the
    entry had not locked it).
    """
    weeks: list[int]
    teams: list[str]
    prob: np.ndarray            # shape (n_weeks, n_teams), decayed
    raw_prob: np.ndarray        # same, before decay
    opponent: np.ndarray        # object array of opponent code or ""
    source: np.ndarray          # object array of source label or ""
    is_home: np.ndarray         # bool
    game_id: np.ndarray         # object array of game ids or ""
    picks_required: list[int]   # picks per week, aligned with weeks

    def week_index(self, week: int) -> int:
        return self.weeks.index(week)

    def team_index(self, team: str) -> int:
        return self.teams.index(team)

    def available(self, w: int) -> list[str]:
        return [t for j, t in enumerate(self.teams) if not np.isnan(self.prob[w, j])]


def build_prob_table(
    game_probs: list[GameProb],
    teams: list[str],
    start_week: int,
    end_week: int,
    decay: float,
    picks_per_week: dict[int, int] | None = None,
    pickable_finals: set[tuple[int, str]] | None = None,
) -> ProbTable:
    """Assemble the week-by-team table the optimizer works on.

    Final games are unpickable unless (week, team) is in pickable_finals
    (an entry already locked that team, so the result simply stands).
    Overrides and finals are never decayed: they are certainties.
    """
    picks_per_week = picks_per_week or {}
    pickable_finals = pickable_finals or set()
    weeks = list(range(start_week, end_week + 1))
    nw, nt = len(weeks), len(teams)
    prob = np.full((nw, nt), np.nan)
    opp = np.full((nw, nt), "", dtype=object)
    src = np.full((nw, nt), "", dtype=object)
    gid = np.full((nw, nt), "", dtype=object)
    home = np.zeros((nw, nt), dtype=bool)
    certain = np.zeros((nw, nt), dtype=bool)
    tix = {t: i for i, t in enumerate(teams)}
    for gp in game_probs:
        if gp.week < start_week or gp.week > end_week:
            continue
        if gp.home not in tix or gp.away not in tix:
            continue
        w = gp.week - start_week
        for team, p, is_home in ((gp.home, gp.p_home, True), (gp.away, 1.0 - gp.p_home, False)):
            j = tix[team]
            if gp.final and (gp.week, team) not in pickable_finals:
                continue
            prob[w, j] = p
            opp[w, j] = gp.away if is_home else gp.home
            src[w, j] = gp.source
            gid[w, j] = gp.game_id
            home[w, j] = is_home
            certain[w, j] = gp.source in ("final", "override")
    raw = prob.copy()
    ahead = np.arange(nw, dtype=float)[:, None]
    shrink = np.exp(-decay * ahead)
    decayed = np.where(certain, prob, 0.5 + (prob - 0.5) * shrink)
    required = [max(1, int(picks_per_week.get(wk, 1))) for wk in weeks]
    return ProbTable(weeks, teams, decayed, raw, opp, src, home, gid, required)
