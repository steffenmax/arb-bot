"""Win probabilities for every remaining regular-season game.

Priority per game:
  1. Sportsbook moneyline (devigged) when nflverse has one.
  2. Point spread converted through a normal margin model.
  3. A market-implied power rating fitted to every posted spread this season,
     shrunk toward last season's closing-line ratings.

Probabilities for future weeks are then pulled toward 50% by a decay factor
because ratings drift (injuries, form) and the far future is less certain.
"""
from __future__ import annotations

from dataclasses import dataclass

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

    def home_spread(self, home: str, away: str) -> float:
        return self.rating[home] - self.rating[away] + self.hfa


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
    week: int
    home: str
    away: str
    p_home: float
    source: str


def game_probabilities(
    season_games: pd.DataFrame,
    ratings: Ratings,
) -> list[GameProb]:
    out: list[GameProb] = []
    for _, g in season_games.iterrows():
        if pd.notna(g.get("home_moneyline")) and pd.notna(g.get("away_moneyline")):
            p = devig(float(g["home_moneyline"]), float(g["away_moneyline"]))
            src = "moneyline"
        elif pd.notna(g.get("spread_line")):
            p = spread_prob(float(g["spread_line"]))
            src = "spread"
        else:
            p = spread_prob(ratings.home_spread(g["home_team"], g["away_team"]))
            src = "rating"
        out.append(GameProb(int(g["week"]), g["home_team"], g["away_team"], p, src))
    return out


@dataclass
class ProbTable:
    """Win probability of each team in each remaining week.

    prob[w, t] is the chance team t wins in week weeks[w]; NaN when the team is
    on bye or its game that week is already final.
    """
    weeks: list[int]
    teams: list[str]
    prob: np.ndarray            # shape (n_weeks, n_teams), decayed
    raw_prob: np.ndarray        # same, before decay
    opponent: np.ndarray        # object array of opponent code or ""
    source: np.ndarray          # object array of source label or ""
    is_home: np.ndarray         # bool

    def week_index(self, week: int) -> int:
        return self.weeks.index(week)

    def team_index(self, team: str) -> int:
        return self.teams.index(team)


def build_prob_table(
    season_games: pd.DataFrame,
    game_probs: list[GameProb],
    teams: list[str],
    start_week: int,
    end_week: int,
    decay: float,
) -> ProbTable:
    weeks = list(range(start_week, end_week + 1))
    nw, nt = len(weeks), len(teams)
    prob = np.full((nw, nt), np.nan)
    opp = np.full((nw, nt), "", dtype=object)
    src = np.full((nw, nt), "", dtype=object)
    home = np.zeros((nw, nt), dtype=bool)
    tix = {t: i for i, t in enumerate(teams)}
    played = {
        (int(g["week"]), g["home_team"]) for _, g in season_games.iterrows() if pd.notna(g["result"])
    }
    for gp in game_probs:
        if gp.week < start_week or gp.week > end_week:
            continue
        if (gp.week, gp.home) in played:
            continue  # game is final, cannot be picked
        w = gp.week - start_week
        prob[w, tix[gp.home]] = gp.p_home
        prob[w, tix[gp.away]] = 1.0 - gp.p_home
        opp[w, tix[gp.home]] = gp.away
        opp[w, tix[gp.away]] = gp.home
        src[w, tix[gp.home]] = gp.source
        src[w, tix[gp.away]] = gp.source
        home[w, tix[gp.home]] = True
    raw = prob.copy()
    ahead = np.arange(nw, dtype=float)[:, None]
    shrink = np.exp(-decay * ahead)
    decayed = 0.5 + (prob - 0.5) * shrink
    return ProbTable(weeks, teams, decayed, raw, opp, src, home)
