"""Command-line entry point: python3 -m survivor [options]"""
from __future__ import annotations

import argparse
import csv
import sys

import numpy as np

from . import data, probs
from .optimizer import Path, candidate_paths, contrarian_bonus, select_joint


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


def describe_path(table: probs.ProbTable, path: Path) -> str:
    parts = []
    for week, team, p in path.picks:
        w = table.week_index(week)
        j = table.team_index(team)
        where = "vs" if table.is_home[w, j] else "@"
        parts.append(f"W{week} {team} {where} {table.opponent[w, j]} {100 * p:.0f}%")
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
    ap.add_argument("--decay", type=float, default=0.03,
                    help="per-week shrink of future win probabilities toward 50%% (default 0.03)")
    ap.add_argument("--top", type=int, default=8, help="candidate current-week picks per entry (default 8)")
    ap.add_argument("--pick-pct", help="CSV with columns team,pct: share of the pool on each team this week")
    ap.add_argument("--contrarian-weight", type=float, default=1.0,
                    help="weight on the crowd-avoidance bonus when --pick-pct is given (default 1.0)")
    ap.add_argument("--objective", choices=["any", "expected"], default="any",
                    help="any: maximize P(at least one entry survives); expected: expected survivors")
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

    prior = probs.prior_from_last_season(games, season, teams)
    ratings = probs.fit_ratings(season_games, teams, prior=prior)
    game_probs = probs.game_probabilities(season_games, ratings)
    table = probs.build_prob_table(season_games, game_probs, teams, week, end_week, args.decay)

    entries = parse_used(args.used, args.entries)
    pick_pct = load_pick_pct(args.pick_pct)
    bonus = contrarian_bonus(table, pick_pct) if pick_pct else None
    weight = args.contrarian_weight if pick_pct else 0.0

    entry_candidates = []
    for name, used in entries:
        cands = candidate_paths(table, used, args.top, week0_bonus=bonus)
        if not cands:
            sys.exit(f"Entry {name}: no feasible path. Check --used and the horizon.")
        entry_candidates.append(cands)

    result = select_joint(table, entry_candidates, weight, args.objective)

    # ---- report ----------------------------------------------------------
    src_counts = {}
    for gp in game_probs:
        if week <= gp.week <= end_week:
            src_counts[gp.source] = src_counts.get(gp.source, 0) + 1
    kickoff = season_games[season_games["week"] == week]["gameday"].min().date()
    print(f"Season {season}, week {week} (first kickoff {kickoff}), horizon week {end_week}")
    print("Probability sources for remaining games: "
          + ", ".join(f"{k} {v}" for k, v in sorted(src_counts.items())))
    print(f"Future-week decay {args.decay}/week, objective '{args.objective}'")
    print()

    print(f"RECOMMENDED WEEK {week} PICKS")
    header = f"{'Entry':<6}{'Pick':<6}{'Opp':<8}{'Win%':>7}{'Crowd%':>8}{'Survive→W' + str(end_week):>13}"
    print(header)
    for (name, used), path, curve in zip(entries, result.paths, result.curve_each):
        wk, team, p = path.picks[0]
        j = table.team_index(team)
        where = ("vs " if table.is_home[0, j] else "@ ") + table.opponent[0, j]
        crowd = f"{pick_pct[team]:.0f}%" if team in pick_pct else "-"
        print(f"{name:<6}{team:<6}{where:<8}{fmt_pct(p):>7}{crowd:>8}{fmt_pct(curve[-1]):>13}")
    print()
    print(f"P(at least one entry survives through week {end_week}): {fmt_pct(result.p_any)}")
    print(f"P(all entries survive through week {end_week}):          {fmt_pct(result.p_all)}")
    print(f"Expected entries alive at week {end_week}:               {result.expected_alive:.2f}")
    print()
    print("P(at least one entry alive) after each week:")
    print("  " + "  ".join(f"W{w}:{100 * c:.0f}%" for w, c in zip(table.weeks, result.curve_any)))
    print()
    print("Projected full paths (later weeks are re-optimized each time you run this):")
    for (name, used), path in zip(entries, result.paths):
        print(f"  {name}: {describe_path(table, path)}")
    print()
    if len(result.alternatives) > 1:
        print("Next-best combinations this week (entries in order):")
        for score, picks in result.alternatives[1:]:
            print(f"  {' / '.join(picks)}")
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
        for (name, used), cands in zip(entries, entry_candidates):
            print(f"Candidate paths for entry {name} (used: {', '.join(sorted(used)) or 'none'}):")
            for path in cands:
                print(f"  survive {fmt_pct(path.survival)}  {describe_path(table, path)}")


if __name__ == "__main__":
    main()
