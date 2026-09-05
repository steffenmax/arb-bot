"""Pick optimization for one or more survivor entries.

Single entry: choosing one team per week with no repeats to maximize the
chance of surviving through the horizon is an assignment problem on
-log(win probability), solved exactly with the Hungarian algorithm.

Multiple entries: all entries face the same game outcomes, so picking the
same favorite three times leaves you with no diversification. We generate
candidate paths per entry (the best path for each possible current-week
pick) and choose the combination that maximizes the exact probability that
at least one entry survives the horizon. Games are independent, so the joint
survival of any subset of entries is a product over weeks, and "at least one"
follows by inclusion-exclusion. No simulation noise.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import linear_sum_assignment

from .probs import ProbTable

INFEASIBLE = 1e6


@dataclass
class Path:
    picks: list[tuple[int, str, float]]   # (week, team, decayed win prob)
    log_survival: float                    # sum of log probs over the horizon
    bonus: float = 0.0                     # contrarian bonus for current week

    @property
    def survival(self) -> float:
        return math.exp(self.log_survival)

    @property
    def first_pick(self) -> str:
        return self.picks[0][1]

    @property
    def score(self) -> float:
        return self.log_survival + self.bonus


def best_path(
    table: ProbTable,
    used: set[str],
    forced_first: str | None = None,
    week0_bonus: dict[str, float] | None = None,
) -> Path | None:
    """Exact best no-repeat path over the table's weeks.

    week0_bonus adds a per-team log-utility term to the current week only
    (used for the contrarian adjustment). Returns None when no feasible
    assignment exists (for example, the forced team is unavailable).
    """
    nw, nt = table.prob.shape
    cost = np.where(np.isnan(table.prob), INFEASIBLE, -np.log(np.clip(table.prob, 1e-9, 1.0)))
    for t in used:
        if t in table.teams:
            cost[:, table.team_index(t)] = INFEASIBLE
    if week0_bonus:
        for t, b in week0_bonus.items():
            j = table.team_index(t)
            if cost[0, j] < INFEASIBLE:
                cost[0, j] -= b
    if forced_first is not None:
        j = table.team_index(forced_first)
        if cost[0, j] >= INFEASIBLE:
            return None
        keep = cost[0, j]
        cost[0, :] = INFEASIBLE
        cost[0, j] = keep
        cost[1:, j] = INFEASIBLE
    if nw > nt:
        return None
    rows, cols = linear_sum_assignment(cost)
    picks, log_surv, bonus = [], 0.0, 0.0
    for w, j in sorted(zip(rows, cols)):
        if cost[w, j] >= INFEASIBLE:
            return None
        p = float(table.prob[w, j])
        picks.append((table.weeks[w], table.teams[j], p))
        log_surv += math.log(max(p, 1e-9))
        if w == 0 and week0_bonus:
            bonus += week0_bonus.get(table.teams[j], 0.0)
    return Path(picks, log_surv, bonus)


def candidate_paths(
    table: ProbTable,
    used: set[str],
    top_k: int,
    week0_bonus: dict[str, float] | None = None,
) -> list[Path]:
    """Best path for each possible current-week pick, best first."""
    paths = []
    for j, team in enumerate(table.teams):
        if team in used or np.isnan(table.prob[0, j]):
            continue
        p = best_path(table, used, forced_first=team, week0_bonus=week0_bonus)
        if p is not None:
            paths.append(p)
    paths.sort(key=lambda p: p.score, reverse=True)
    return paths[:top_k]


def subset_alive_curve(table: ProbTable, paths: list[Path]) -> np.ndarray:
    """P(every entry in `paths` is still alive) after each week of the table.

    Within a week the picks are either the same team (one win needed),
    opponents (impossible for both to win), or different games (independent).
    """
    nw = len(table.weeks)
    per_week = np.ones(nw)
    picks_by_week: dict[int, list[str]] = {}
    for path in paths:
        for week, team, _ in path.picks:
            picks_by_week.setdefault(table.week_index(week), []).append(team)
    for w, teams in picks_by_week.items():
        distinct = set(teams)
        p = 1.0
        for team in distinct:
            j = table.team_index(team)
            if table.opponent[w, j] in distinct:
                p = 0.0
                break
            p *= float(table.prob[w, j])
        per_week[w] = p
    return np.cumprod(per_week)


def any_alive_curve(table: ProbTable, paths: list[Path]) -> np.ndarray:
    """P(at least one entry alive) after each week, by inclusion-exclusion."""
    total = np.zeros(len(table.weeks))
    for r in range(1, len(paths) + 1):
        sign = 1.0 if r % 2 == 1 else -1.0
        for subset in itertools.combinations(paths, r):
            total += sign * subset_alive_curve(table, list(subset))
    return np.clip(total, 0.0, 1.0)


@dataclass
class JointResult:
    paths: list[Path]
    p_any: float                     # P(at least one entry survives horizon)
    p_all: float                     # P(all entries survive horizon)
    expected_alive: float            # expected number surviving horizon
    curve_any: list[float]           # P(>=1 alive) after each week
    curve_each: list[list[float]]    # per entry, P(alive) after each week
    score: float = 0.0
    alternatives: list[tuple[float, list[str]]] = field(default_factory=list)


def select_joint(
    table: ProbTable,
    entry_candidates: list[list[Path]],
    contrarian_weight: float = 0.0,
    objective: str = "any",
    n_alternatives: int = 5,
) -> JointResult:
    """Pick one candidate path per entry to maximize the joint objective.

    objective "any": P(at least one entry survives the horizon).
    objective "expected": expected number of surviving entries (no
    diversification pressure; each entry just takes its own best path).
    """
    best, best_score, ranked = None, -np.inf, []
    for combo in itertools.product(*[range(len(c)) for c in entry_candidates]):
        paths = [entry_candidates[e][i] for e, i in enumerate(combo)]
        if objective == "expected":
            value = sum(p.survival for p in paths)
        else:
            value = float(any_alive_curve(table, paths)[-1])
        bonus = float(np.mean([p.bonus for p in paths]))
        score = math.log(max(value, 1e-300)) + contrarian_weight * bonus
        ranked.append((score, [p.first_pick for p in paths]))
        if score > best_score:
            best, best_score = combo, score
    ranked.sort(key=lambda r: r[0], reverse=True)
    # Entries with identical histories make permutations of one pick set
    # equivalent; keep only the best-scoring arrangement of each set.
    seen, deduped = set(), []
    for score, picks in ranked:
        key = tuple(sorted(picks))
        if key not in seen:
            seen.add(key)
            deduped.append((score, picks))
    ranked = deduped
    paths = [entry_candidates[e][i] for e, i in enumerate(best)]
    curve_any = any_alive_curve(table, paths)
    curve_all = subset_alive_curve(table, paths)
    curve_each = [subset_alive_curve(table, [p]) for p in paths]
    return JointResult(
        paths=paths,
        p_any=float(curve_any[-1]),
        p_all=float(curve_all[-1]),
        expected_alive=float(sum(c[-1] for c in curve_each)),
        curve_any=curve_any.tolist(),
        curve_each=[c.tolist() for c in curve_each],
        score=best_score,
        alternatives=ranked[:n_alternatives],
    )


def contrarian_bonus(
    table: ProbTable,
    pick_pct: dict[str, float],
) -> dict[str, float]:
    """log(1 / expected surviving share of the pool) given you pick each team.

    If you pick team t and it wins, everyone else on t also survives, and the
    rest of the pool survives at their own teams' rates. A smaller surviving
    share means a bigger slice of the pot, so the bonus rewards picks the
    crowd is avoiding. Teams missing from pick_pct are treated as 0%.
    """
    probs = {t: table.prob[0, j] for j, t in enumerate(table.teams) if not np.isnan(table.prob[0, j])}
    total = sum(pick_pct.values())
    share = {t: pick_pct.get(t, 0.0) / total for t in probs} if total > 0 else {t: 0.0 for t in probs}
    others = sum(share[t] * probs[t] for t in probs)
    bonus = {}
    for t, p in probs.items():
        surviving = share[t] + (others - share[t] * p)
        bonus[t] = -math.log(max(surviving, 1e-6))
    return bonus
