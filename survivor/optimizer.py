"""Pick optimization for one or more survivor entries.

Single entry: choosing teams week by week with no repeats to maximize the
chance of surviving through the horizon is an assignment problem on
-log(win probability). Weeks that require two picks contribute two rows.
Locked weeks pin their teams. It is solved exactly with the Hungarian
algorithm.

Multiple entries: all entries face the same game outcomes, so stacking the
same favorite on every entry leaves no diversification. We generate
candidate paths per entry for the current week (the best path for each
possible pick) and choose the combination that maximizes the exact
probability that at least one entry survives the horizon. Games are
independent, so the joint survival of any subset of entries is a product
over weeks, and "at least one" follows by inclusion-exclusion. Later weeks
are hedged with a soft penalty for sharing a team with another entry.

Branches: for every week of an entry's plan, every alternative pick that
week is expanded into its own fully re-optimized downstream path, so the
user can see what each choice commits them to.
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
class WeekPick:
    week: int
    teams: list[str]
    p: float                    # product of decayed win probs this week


@dataclass
class Path:
    picks: list[WeekPick]
    log_survival: float         # sum of log p over the horizon
    bonus: float = 0.0          # contrarian bonus for the first week

    @property
    def survival(self) -> float:
        return math.exp(self.log_survival)

    @property
    def first_teams(self) -> list[str]:
        return list(self.picks[0].teams)

    @property
    def score(self) -> float:
        return self.log_survival + self.bonus

    def teams_before(self, week_index: int) -> dict[int, list[str]]:
        return {i: list(wp.teams) for i, wp in enumerate(self.picks) if i < week_index}


def _base_cost(table: ProbTable, used: set[str], penalty: np.ndarray | None) -> np.ndarray:
    cost = np.where(np.isnan(table.prob), INFEASIBLE, -np.log(np.clip(table.prob, 1e-9, 1.0)))
    if penalty is not None:
        cost = np.where(cost < INFEASIBLE, cost + penalty, cost)
    for t in used:
        if t in table.teams:
            cost[:, table.team_index(t)] = INFEASIBLE
    return cost


def best_path(
    table: ProbTable,
    used: set[str],
    locks: dict[int, list[str]] | None = None,
    week0_bonus: dict[str, float] | None = None,
    penalty: np.ndarray | None = None,
) -> Path | None:
    """Exact best no-repeat path over the table's weeks.

    locks: week index -> teams pinned in that week (a partial lock pins some
    of a multi-pick week's slots). week0_bonus adds a per-team log-utility
    term to the first week only. penalty is a (weeks, teams) array of extra
    cost, used to hedge against other entries. Returns None when no
    feasible assignment exists.
    """
    locks = {w: list(ts) for w, ts in (locks or {}).items() if ts}
    nw, nt = table.prob.shape
    base = _base_cost(table, used, penalty)
    if week0_bonus:
        for t, b in week0_bonus.items():
            j = table.team_index(t)
            if base[0, j] < INFEASIBLE:
                base[0, j] -= b
    row_week = [w for w in range(nw) for _ in range(table.picks_required[w])]
    if len(row_week) > nt:
        return None
    cost = base[row_week, :].copy()
    for w, teams in locks.items():
        if w < 0 or w >= nw:
            continue
        jids = [table.team_index(t) for t in teams if t in table.teams]
        if len(jids) != len(teams):
            return None
        week_rows = [r for r, ww in enumerate(row_week) if ww == w]
        other_rows = [r for r, ww in enumerate(row_week) if ww != w]
        if len(jids) > len(week_rows):
            return None
        for j in jids:
            cost[other_rows, j] = INFEASIBLE
        mask = np.ones(nt, dtype=bool)
        mask[jids] = False
        for r in week_rows[:len(jids)]:
            cost[r, mask] = INFEASIBLE
        for r in week_rows[len(jids):]:
            cost[r, jids] = INFEASIBLE
    for _ in range(8):
        rows, cols = linear_sum_assignment(cost)
        chosen: dict[int, list[int]] = {}
        for r, j in zip(rows, cols):
            if cost[r, j] >= INFEASIBLE:
                return None
            chosen.setdefault(row_week[r], []).append(int(j))
        conflict = None
        for w, js in chosen.items():
            names = {table.teams[j] for j in js}
            for j in js:
                if table.opponent[w, j] in names:
                    # two picks in one week from the same game: forbid the weaker
                    k = table.team_index(table.opponent[w, j])
                    weaker = j if table.prob[w, j] <= table.prob[w, k] else k
                    conflict = (w, weaker)
                    break
            if conflict:
                break
        if conflict is None:
            break
        w, j = conflict
        for r, ww in enumerate(row_week):
            if ww == w:
                cost[r, j] = INFEASIBLE
    else:
        return None
    picks, log_surv, bonus = [], 0.0, 0.0
    for w in range(nw):
        js = sorted(chosen.get(w, []), key=lambda j: -table.prob[w, j])
        p = float(np.prod([table.prob[w, j] for j in js])) if js else 1.0
        picks.append(WeekPick(table.weeks[w], [table.teams[j] for j in js], p))
        log_surv += math.log(max(p, 1e-9))
        if w == 0 and week0_bonus:
            bonus += sum(week0_bonus.get(table.teams[j], 0.0) for j in js)
    return Path(picks, log_surv, bonus)


@dataclass
class Branch:
    week: int
    teams: list[str]            # the pick(s) this branch commits to that week
    path: Path                  # full path (from the table's first week)
    week_index: int
    recommended: bool = False

    @property
    def p_week(self) -> float:
        return self.path.picks[self.week_index].p

    @property
    def log_survival_from(self) -> float:
        return sum(math.log(max(wp.p, 1e-9)) for wp in self.path.picks[self.week_index:])

    @property
    def survival_from(self) -> float:
        return math.exp(self.log_survival_from)

    @property
    def score(self) -> float:
        return self.log_survival_from + (self.path.bonus if self.week_index == 0 else 0.0)


def branches_for_week(
    table: ProbTable,
    used: set[str],
    locks: dict[int, list[str]],
    prior_picks: dict[int, list[str]],
    w: int,
    top_k: int,
    week0_bonus: dict[str, float] | None = None,
    penalty: np.ndarray | None = None,
    pairs_from_top: int = 6,
) -> list[Branch]:
    """Every candidate pick for week index w, given picks pinned before it.

    Each branch pins one team in week w (plus any existing partial lock) and
    re-optimizes everything after it. A fully locked week yields one branch.
    """
    pinned = {**locks, **prior_picks}
    week_lock = list(locks.get(w, []))
    need = table.picks_required[w]
    out: list[Branch] = []
    if len(week_lock) >= need:
        pinned[w] = week_lock[:need]
        path = best_path(table, used, pinned, week0_bonus, penalty)
        if path:
            out.append(Branch(table.weeks[w], list(path.picks[w].teams), path, w))
        return out
    taken = {t for ts in prior_picks.values() for t in ts} | used | set(week_lock)
    free = [t for t in table.available(w) if t not in taken]
    seen: set[tuple[str, ...]] = set()

    def add(pin: list[str]) -> None:
        pinned[w] = week_lock + pin
        path = best_path(table, used, pinned, week0_bonus, penalty)
        if path is None:
            return
        key = tuple(sorted(path.picks[w].teams))
        if key in seen:
            return
        seen.add(key)
        out.append(Branch(table.weeks[w], list(path.picks[w].teams), path, w))

    for team in free:
        add([team])
    if need - len(week_lock) >= 2:
        # Multi-pick week: the anchor-plus-best-partner branches above all
        # share the same partner, so also enumerate explicit pairs among the
        # strongest teams to give the joint selection real alternatives.
        strongest = sorted(free, key=lambda t: -table.prob[w, table.team_index(t)])[:pairs_from_top]
        for a, b in itertools.combinations(strongest, 2):
            if table.opponent[w, table.team_index(a)] != b:
                add([a, b])
    out.sort(key=lambda b: b.score, reverse=True)
    return out[:top_k]


def branch_tree(
    table: ProbTable,
    used: set[str],
    locks: dict[int, list[str]],
    plan: Path,
    top_k: int,
    week0_bonus: dict[str, float] | None = None,
    penalty: np.ndarray | None = None,
) -> dict[int, list[Branch]]:
    """Branches for every week along the plan, marking the plan's own pick."""
    tree: dict[int, list[Branch]] = {}
    for w in range(len(table.weeks)):
        prior = plan.teams_before(w)
        branches = branches_for_week(table, used, locks, prior, w, top_k, week0_bonus, penalty)
        plan_teams = set(plan.picks[w].teams)
        if not any(set(b.teams) == plan_teams for b in branches):
            branches.append(Branch(table.weeks[w], list(plan.picks[w].teams), plan, w))
            branches.sort(key=lambda b: b.score, reverse=True)
        for b in branches:
            b.recommended = set(b.teams) == plan_teams
        tree[table.weeks[w]] = branches
    return tree


def subset_alive_curve(table: ProbTable, paths: list[Path]) -> np.ndarray:
    """P(every entry in `paths` is still alive) after each week of the table.

    Within a week the picks are either the same team (one win needed),
    opponents (impossible for both to win), or different games (independent).
    """
    nw = len(table.weeks)
    per_week = np.ones(nw)
    for w in range(nw):
        distinct: set[str] = set()
        for path in paths:
            distinct.update(path.picks[w].teams)
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
    p_any: float
    p_all: float
    expected_alive: float
    curve_any: list[float]
    curve_all: list[float]
    curve_each: list[list[float]]
    expected_weeks_any: float = 0.0
    score: float = 0.0
    alternatives: list[tuple[float, float, list[list[str]]]] = field(default_factory=list)


OBJECTIVES = ("any", "final", "expected")


def joint_value(table: ProbTable, paths: list[Path], objective: str) -> float:
    """Value of a set of entry paths under the chosen objective.

    "any":      expected number of weeks (through the horizon) with at least
                one entry alive. Pools can end any week, so this rewards
                staying represented every week, not just at the horizon.
    "final":    P(at least one entry alive at the horizon).
    "expected": expected number of entries alive at the horizon.
    """
    if not paths:
        return 0.0
    if objective == "expected":
        return float(sum(p.survival for p in paths))
    curve = any_alive_curve(table, paths)
    if objective == "final":
        return float(curve[-1])
    return float(np.sum(curve))


def select_joint(
    table: ProbTable,
    entry_candidates: list[list[Path]],
    contrarian_weight: float = 0.0,
    objective: str = "any",
    n_alternatives: int = 6,
) -> JointResult:
    """Pick one candidate path per entry to maximize the joint objective."""
    best, best_score, ranked = None, -np.inf, []
    for combo in itertools.product(*[range(len(c)) for c in entry_candidates]):
        paths = [entry_candidates[e][i] for e, i in enumerate(combo)]
        value = joint_value(table, paths, objective)
        bonus = float(np.mean([p.bonus for p in paths]))
        score = math.log(max(value, 1e-300)) + contrarian_weight * bonus
        ranked.append((score, value, [p.first_teams for p in paths]))
        if score > best_score:
            best, best_score = combo, score
    ranked.sort(key=lambda r: r[0], reverse=True)
    seen, deduped = set(), []
    for score, value, picks in ranked:
        key = tuple(sorted(tuple(sorted(p)) for p in picks))
        if key not in seen:
            seen.add(key)
            deduped.append((score, value, picks))
    paths = [entry_candidates[e][i] for e, i in enumerate(best)]
    return summarize_joint(table, paths, best_score, deduped[:n_alternatives])


def summarize_joint(
    table: ProbTable,
    paths: list[Path],
    score: float = 0.0,
    alternatives: list | None = None,
) -> JointResult:
    curve_any = any_alive_curve(table, paths) if paths else np.zeros(len(table.weeks))
    curve_all = subset_alive_curve(table, paths) if paths else np.zeros(len(table.weeks))
    curve_each = [subset_alive_curve(table, [p]) for p in paths]
    return JointResult(
        paths=paths,
        p_any=float(curve_any[-1]) if paths else 0.0,
        p_all=float(curve_all[-1]) if paths else 0.0,
        expected_alive=float(sum(c[-1] for c in curve_each)),
        curve_any=curve_any.tolist(),
        curve_all=curve_all.tolist(),
        curve_each=[c.tolist() for c in curve_each],
        expected_weeks_any=float(np.sum(curve_any)) if paths else 0.0,
        score=score,
        alternatives=alternatives or [],
    )


def hedge_penalty(table: ProbTable, other_paths: list[Path], strength: float) -> np.ndarray:
    """Extra cost for using a team in a week where another entry already does.

    Applies from the second week on; the first week is decided jointly and
    exactly, so it needs no heuristic.
    """
    nw, nt = table.prob.shape
    pen = np.zeros((nw, nt))
    for path in other_paths:
        for w in range(1, nw):
            for t in path.picks[w].teams:
                pen[w, table.team_index(t)] += strength
    return pen


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


@dataclass
class EntrySpec:
    name: str
    used: set[str]
    locks: dict[int, list[str]]        # week number -> teams
    alive: bool = True


@dataclass
class EntryResult:
    spec: EntrySpec
    plan: Path | None
    branches: dict[int, list[Branch]]
    curve: list[float]
    warnings: list[str]


@dataclass
class PlanResult:
    entries: list[EntryResult]
    joint: JointResult


def plan_entries(
    table: ProbTable,
    specs: list[EntrySpec],
    top_k: int = 10,
    week0_bonus: dict[str, float] | None = None,
    contrarian_weight: float = 0.0,
    objective: str = "any",
    hedge: float = 0.1,
    refine_rounds: int = 2,
) -> PlanResult:
    """Full multi-entry plan: joint first-week picks, hedged later weeks,
    and a branch tree for every entry and week.

    The joint objective is exact for whatever paths it compares, but a path
    is only a forecast: later weeks get re-planned as results arrive, and a
    re-planner would steer entries apart when that is cheap. So candidate
    tails are built with a hedge penalty against the other entries' current
    plans, and the joint selection is repeated for a couple of rounds until
    the first-week picks settle. Without this, two entries whose forecasts
    coincide from week two on look far more correlated than they really are,
    and the optimizer starts sacrificing this week's win probability to
    escape a correlation that weekly re-planning would remove anyway.
    """
    week_locks: dict[str, dict[int, list[str]]] = {}
    warnings: dict[str, list[str]] = {s.name: [] for s in specs}
    for s in specs:
        wl = {}
        for wk, teams in s.locks.items():
            if wk in table.weeks:
                wl[table.week_index(wk)] = list(teams)
        week_locks[s.name] = wl

    def feasible_locks(s: EntrySpec) -> dict[int, list[str]]:
        locks = dict(week_locks[s.name])
        while locks and best_path(table, s.used, locks) is None:
            w = max(locks)
            warnings[s.name].append(
                f"Lock {'/'.join(locks[w])} in week {table.weeks[w]} is infeasible and was ignored.")
            del locks[w]
        week_locks[s.name] = locks
        return locks

    hedging = objective != "expected" and hedge > 0

    def penalty_for(name: str, plans: dict[str, Path]) -> np.ndarray | None:
        others = [p for n, p in plans.items() if n != name]
        return hedge_penalty(table, others, hedge) if hedging and others else None

    def candidates_for(s: EntrySpec, plans: dict[str, Path]) -> list[Path]:
        branches = branches_for_week(table, s.used, week_locks[s.name], {}, 0, top_k,
                                     week0_bonus, penalty_for(s.name, plans))
        return [b.path for b in branches]

    def hedged_plans(live: list[EntrySpec], joint: JointResult) -> dict[str, Path]:
        order = sorted(range(len(live)), key=lambda i: -joint.paths[i].survival)
        plans: dict[str, Path] = {}
        for i in order:
            s = live[i]
            pinned = {**week_locks[s.name], 0: joint.paths[i].first_teams}
            path = best_path(table, s.used, pinned, week0_bonus, penalty_for(s.name, plans))
            plans[s.name] = path if path is not None else joint.paths[i]
        return plans

    alive = [s for s in specs if s.alive]
    for s in alive:
        feasible_locks(s)
        if best_path(table, s.used, week_locks[s.name]) is None:
            warnings[s.name].append("No feasible path: too few teams left for the horizon.")
    live = [s for s in alive if best_path(table, s.used, week_locks[s.name]) is not None]

    plans: dict[str, Path] = {}
    joint = summarize_joint(table, [])
    if live:
        rounds = 1 + (refine_rounds if hedging and len(live) > 1 else 0)
        for _ in range(rounds):
            cands = [candidates_for(s, plans) for s in live]
            joint = select_joint(table, cands, contrarian_weight, objective)
            new_plans = hedged_plans(live, joint)
            settled = plans and all(new_plans[s.name].first_teams == plans[s.name].first_teams for s in live)
            plans = new_plans
            if settled:
                break
        joint = summarize_joint(table, [plans[s.name] for s in live], joint.score, joint.alternatives)

    results = []
    for s in specs:
        if s.name not in plans:
            results.append(EntryResult(s, None, {}, [], warnings[s.name]))
            continue
        path = plans[s.name]
        tree = branch_tree(table, s.used, week_locks[s.name], path, top_k, week0_bonus, penalty_for(s.name, plans))
        curve = subset_alive_curve(table, [path]).tolist()
        results.append(EntryResult(s, path, tree, curve, warnings[s.name]))
    return PlanResult(results, joint)
