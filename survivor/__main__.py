"""Command-line entry point: python3 -m survivor [options]"""
from __future__ import annotations

import argparse
import csv
import sys

import numpy as np

from . import data, probs
from .optimizer import EntrySpec, Path, contrarian_bonus, plan_entries


def parse_used(values: list[str], n_entries: int) -> list[tuple[str, set[str]]]:
    """--used A=KC,BUF --used B= ... or positional lists for entries 1..n."""
    names = [chr(ord("A") + i) for i in range(n_entries)]
    used: dict[str, set[str]] = {n: set() for n in names}
    for i, raw in enumerate(values):
        if "=" in raw:
            name, teams = raw.split("=", 1)
            name = name.strip().upper()
        else:
            name, teams = names[i] if i < n_entries else "", raw
        if name not in used:
            sys.exit(f"Entry '{name}' not in {names}. Use --entries to add more.")
        used[name] = {data.normalize_team(t) for t in teams.split(",") if t.strip()}
    return [(n, used[n]) for n in names]


def parse_locks(values: list[str]) -> dict[str, dict[int, list[str]]]:
    """--lock A=3:DET --lock B=12:KC+BUF"""
    out: dict[str, dict[int, list[str]]] = {}
    for raw in values:
        name, rest = raw.split("=", 1)
        week, teams = rest.split(":", 1)
        out.setdefault(name.strip().upper(), {})[int(week)] = [
            data.normalize_team(t) for t in teams.replace("+", ",").split(",") if t.strip()
        ]
    return out


def load_pick_pct(path: str | None) -> dict[str, float]:
    if not path:
        return {}
    out: dict[str, float] = {}
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            team = data.normalize_team(row["team"])
            out[team] = float(str(row["pct"]).strip().rstrip("%"))
    return out


def fmt_pct(x: float) -> str:
    return f"{100 * x:5.1f}%"


def describe_pick(table: probs.ProbTable, week: int, team: str) -> str:
    w = table.week_index(week)
    j = table.team_index(team)
    where = "vs" if table.is_home[w, j] else "@"
    return f"{team} {where} {table.opponent[w, j]} {100 * table.prob[w, j]:.0f}%"


def describe_path(table: probs.ProbTable, path: Path, start: int = 0) -> str:
    parts = []
    for wp in path.picks[start:]:
        parts.append(f"W{wp.week} " + " + ".join(describe_pick(table, wp.week, t) for t in wp.teams))
    return "  ".join(parts)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        prog="python3 -m survivor",
        description="Recommend NFL survivor pool picks for one or more entries.",
    )
    ap.add_argument("--season", type=int, help="season year (default: latest in data)")
    ap.add_argument("--week", type=int, help="current week (default: first week with an unplayed game)")
    ap.add_argument("--end-week", type=int, default=18, help="last week of the pool horizon (default 18)")
    ap.add_argument("--entries", type=int, default=3, help="number of entries you control (default 3)")
    ap.add_argument("--used", action="append", default=[],
                    help="teams an entry has already used, e.g. --used A=KC,BUF (repeatable)")
    ap.add_argument("--lock", action="append", default=[],
                    help="pin a pick, e.g. --lock A=3:DET or --lock B=12:KC+BUF (repeatable)")
    ap.add_argument("--two-pick-weeks", default="",
                    help="comma-separated weeks that require two picks, e.g. 12,18")
    ap.add_argument("--decay", type=float, default=0.03,
                    help="per-week shrink of future win probabilities toward 50%% (default 0.03)")
    ap.add_argument("--top", type=int, default=8, help="candidate current-week picks per entry (default 8)")
    ap.add_argument("--hedge", type=float, default=0.1,
                    help="penalty for sharing a team with another entry in later weeks (default 0.1)")
    ap.add_argument("--pick-pct", help="CSV with columns team,pct: share of the pool on each team this week")
    ap.add_argument("--contrarian-weight", type=float, default=1.0,
                    help="weight on the crowd-avoidance bonus when --pick-pct is given (default 1.0)")
    ap.add_argument("--objective", choices=["any", "final", "expected"], default="any",
                    help="any: expected weeks with a live entry; final: P(any alive at horizon); "
                         "expected: expected survivors at horizon")
    ap.add_argument("--refresh", action="store_true", help="re-download the nflverse games file")
    ap.add_argument("--show-paths", action="store_true", help="print every candidate path per entry")
    args = ap.parse_args(argv)

    games = data.load_games(refresh=args.refresh)
    season = args.season or data.latest_season(games)
    season_games = data.regular_season(games, season)
    if season_games.empty:
        sys.exit(f"No regular-season games found for {season}.")
    teams = data.team_list(season_games)
    week = args.week or data.current_week(season_games)
    end_week = min(args.end_week, int(season_games["week"].max()))
    if week > end_week:
        sys.exit(f"Current week {week} is past the horizon {end_week}.")
    two_pick = {int(w) for w in args.two_pick_weeks.split(",") if w.strip()}

    prior = probs.prior_from_last_season(games, season, teams)
    ratings = probs.fit_ratings(season_games, teams, prior=prior)
    game_probs = probs.game_probabilities(season_games, ratings)
    locks = parse_locks(args.lock)
    pickable = {(wk, t) for lk in locks.values() for wk, ts in lk.items() for t in ts}
    table = probs.build_prob_table(game_probs, teams, week, end_week, args.decay,
                                   {w: 2 for w in two_pick}, pickable)

    entries = parse_used(args.used, args.entries)
    specs = [EntrySpec(name, used, locks.get(name, {})) for name, used in entries]
    pick_pct = load_pick_pct(args.pick_pct)
    bonus = contrarian_bonus(table, pick_pct) if pick_pct else None
    weight = args.contrarian_weight if pick_pct else 0.0
    result = plan_entries(table, specs, args.top, bonus, weight, args.objective, args.hedge)
    joint = result.joint

    # ---- report ----------------------------------------------------------
    src_counts: dict[str, int] = {}
    for gp in game_probs:
        if week <= gp.week <= end_week:
            src_counts[gp.source] = src_counts.get(gp.source, 0) + 1
    kickoff = season_games[season_games["week"] == week]["gameday"].min().date()
    print(f"Season {season}, week {week} (first kickoff {kickoff}), horizon week {end_week}")
    print("Probability sources for remaining games: "
          + ", ".join(f"{k} {v}" for k, v in sorted(src_counts.items())))
    extra = f", two picks in weeks {sorted(two_pick)}" if two_pick else ""
    print(f"Future-week decay {args.decay}/week, objective '{args.objective}'{extra}")
    for er in result.entries:
        for w in er.warnings:
            print(f"warning: entry {er.spec.name}: {w}")
    print()

    print(f"RECOMMENDED WEEK {week} PICKS")
    print(f"{'Entry':<6}{'Pick':<28}{'Win%':>7}{'Crowd%':>8}{'Survive→W' + str(end_week):>13}")
    for er in result.entries:
        if er.plan is None:
            print(f"{er.spec.name:<6}{'(no plan)':<28}")
            continue
        wp = er.plan.picks[0]
        desc = " + ".join(describe_pick(table, wp.week, t) for t in wp.teams)
        crowd = "/".join(f"{pick_pct[t]:.0f}%" for t in wp.teams if t in pick_pct) or "-"
        print(f"{er.spec.name:<6}{desc:<28}{fmt_pct(wp.p):>7}{crowd:>8}{fmt_pct(er.curve[-1]):>13}")
    print()
    print(f"P(at least one entry survives through week {end_week}): {fmt_pct(joint.p_any)}")
    print(f"P(all entries survive through week {end_week}):          {fmt_pct(joint.p_all)}")
    print(f"Expected entries alive at week {end_week}:               {joint.expected_alive:.2f}")
    print(f"Expected weeks with at least one live entry:      {joint.expected_weeks_any:.2f} of {len(table.weeks)}")
    print()
    print("P(at least one entry alive) after each week:")
    print("  " + "  ".join(f"W{w}:{100 * c:.0f}%" for w, c in zip(table.weeks, joint.curve_any)))
    print()
    print("Projected full paths (later weeks are re-optimized each time you run this):")
    for er in result.entries:
        if er.plan is not None:
            print(f"  {er.spec.name}: {describe_path(table, er.plan)}")
    print()
    if len(joint.alternatives) > 1:
        print("Next-best combinations this week (entries in order):")
        for _, value, picks in joint.alternatives[1:]:
            print(f"  {' / '.join('+'.join(p) for p in picks)}   value {value:.3f}")
        print()

    print(f"WEEK {week} BOARD (all available teams)")
    rows = []
    for j, team in enumerate(table.teams):
        if np.isnan(table.prob[0, j]):
            continue
        rows.append((table.raw_prob[0, j], team, j))
    rows.sort(reverse=True)
    print(f"{'Team':<6}{'Opp':<8}{'Win%':>7}{'Src':>11}{'Crowd%':>8}{'Used by':>10}")
    for p, team, j in rows:
        where = ("vs " if table.is_home[0, j] else "@ ") + table.opponent[0, j]
        crowd = f"{pick_pct[team]:.0f}%" if team in pick_pct else "-"
        used_by = ",".join(n for n, u in entries if team in u) or "-"
        print(f"{team:<6}{where:<8}{fmt_pct(p):>7}{table.source[0, j]:>11}{crowd:>8}{used_by:>10}")

    if args.show_paths:
        print()
        for er in result.entries:
            if er.plan is None:
                continue
            print(f"Candidate paths for entry {er.spec.name} (used: {', '.join(sorted(er.spec.used)) or 'none'}):")
            for b in er.branches.get(week, []):
                flag = "*" if b.recommended else " "
                print(f" {flag} survive {fmt_pct(b.survival_from)}  {describe_path(table, b.path)}")


if __name__ == "__main__":
    main()
