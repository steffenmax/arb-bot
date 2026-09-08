"""Unit tests: python3 -m unittest discover -s survivor/tests -t ."""
import itertools
import math
import unittest

import numpy as np

from survivor.optimizer import (
    EntrySpec, any_alive_curve, best_path, branch_tree, branches_for_week,
    contrarian_bonus, plan_entries, select_joint, subset_alive_curve,
)
from survivor.probs import ProbTable, devig, spread_prob


def make_table(weeks, teams, games, picks_required=None):
    """games: {week: [(home, away, p_home), ...]}; teams absent are on bye."""
    nw, nt = len(weeks), len(teams)
    prob = np.full((nw, nt), np.nan)
    opp = np.full((nw, nt), "", dtype=object)
    src = np.full((nw, nt), "", dtype=object)
    gid = np.full((nw, nt), "", dtype=object)
    home = np.zeros((nw, nt), dtype=bool)
    for w, wk in enumerate(weeks):
        for h, a, p in games.get(wk, []):
            i, j = teams.index(h), teams.index(a)
            prob[w, i], prob[w, j] = p, 1 - p
            opp[w, i], opp[w, j] = a, h
            src[w, i] = src[w, j] = "test"
            gid[w, i] = gid[w, j] = f"{wk}_{a}_{h}"
            home[w, i] = True
    req = picks_required or [1] * nw
    return ProbTable(list(weeks), list(teams), prob, prob.copy(), opp, src, home, gid, req)


def teams_of(path):
    return [list(wp.teams) for wp in path.picks]


class ProbabilityTests(unittest.TestCase):
    def test_devig_symmetric(self):
        self.assertAlmostEqual(devig(-110, -110), 0.5)
        self.assertGreater(devig(-200, 170), 0.6)
        self.assertAlmostEqual(devig(-200, 170) + devig(170, -200), 1.0)

    def test_spread_prob(self):
        self.assertAlmostEqual(spread_prob(0.0), 0.5)
        self.assertGreater(spread_prob(7.0), 0.65)
        self.assertLess(spread_prob(-7.0), 0.35)


class BestPathTests(unittest.TestCase):
    def setUp(self):
        self.teams = ["A", "B", "C", "D"]
        self.table = make_table([1, 2], self.teams, {
            1: [("A", "B", 0.9), ("C", "D", 0.6)],
            2: [("A", "C", 0.8), ("B", "D", 0.7)],
        })

    def test_no_repeat(self):
        path = best_path(self.table, used=set())
        flat = [t for ts in teams_of(path) for t in ts]
        self.assertEqual(len(set(flat)), len(flat))
        # A is 0.9 in week 1 and 0.8 in week 2; best is A wk1 + B wk2 (0.63)
        self.assertEqual(teams_of(path), [["A"], ["B"]])
        self.assertAlmostEqual(path.survival, 0.9 * 0.7)

    def test_used_and_locks(self):
        path = best_path(self.table, used={"A"})
        self.assertNotIn("A", [t for ts in teams_of(path) for t in ts])
        forced = best_path(self.table, used=set(), locks={0: ["C"]})
        self.assertEqual(teams_of(forced), [["C"], ["A"]])
        self.assertIsNone(best_path(self.table, used={"C"}, locks={0: ["C"]}))
        later = best_path(self.table, used=set(), locks={1: ["D"]})
        self.assertEqual(teams_of(later), [["A"], ["D"]])

    def test_bye_is_unpickable(self):
        table = make_table([1, 2], self.teams, {
            1: [("A", "B", 0.9)],           # C and D on bye
            2: [("C", "D", 0.95)],
        })
        path = best_path(table, used=set())
        self.assertEqual(teams_of(path), [["A"], ["C"]])

    def test_two_pick_week(self):
        table = make_table([1, 2], self.teams, {
            1: [("A", "B", 0.9), ("C", "D", 0.6)],
            2: [("A", "C", 0.8), ("B", "D", 0.7)],
        }, picks_required=[2, 1])
        path = best_path(table, used=set())
        self.assertEqual(len(path.picks[0].teams), 2)
        self.assertEqual(len(path.picks[1].teams), 1)
        # Week 1 picks must not be opponents; best is A + C (0.54) then B (0.7)
        self.assertEqual(sorted(path.picks[0].teams), ["A", "C"])
        self.assertEqual(path.picks[1].teams, ["B"])
        self.assertAlmostEqual(path.picks[0].p, 0.9 * 0.6)
        self.assertAlmostEqual(path.survival, 0.9 * 0.6 * 0.7)

    def test_two_pick_week_never_picks_opponents(self):
        # Only one game in a two-pick week: the two slots cannot both be filled
        # from the same game, so no path exists.
        table = make_table([1], ["A", "B"], {1: [("A", "B", 0.5)]}, picks_required=[2])
        self.assertIsNone(best_path(table, used=set()))

    def test_partial_lock_in_two_pick_week(self):
        table = make_table([1, 2], self.teams, {
            1: [("A", "B", 0.9), ("C", "D", 0.6)],
            2: [("A", "C", 0.8), ("B", "D", 0.7)],
        }, picks_required=[2, 1])
        path = best_path(table, used=set(), locks={0: ["D"]})
        self.assertIn("D", path.picks[0].teams)
        self.assertEqual(sorted(path.picks[0].teams), ["A", "D"])


class BranchTests(unittest.TestCase):
    def setUp(self):
        self.teams = ["A", "B", "C", "D", "E", "F"]
        self.table = make_table([1, 2, 3], self.teams, {
            1: [("A", "B", 0.8), ("C", "D", 0.7), ("E", "F", 0.6)],
            2: [("A", "C", 0.6), ("B", "E", 0.55), ("D", "F", 0.65)],
            3: [("A", "E", 0.7), ("C", "F", 0.6), ("B", "D", 0.5)],
        })

    def test_branches_cover_every_available_pick(self):
        branches = branches_for_week(self.table, set(), {}, {}, 0, top_k=99)
        self.assertEqual(sorted(b.teams[0] for b in branches), sorted(self.teams))
        for b in branches:
            self.assertEqual(b.path.picks[0].teams, b.teams)
        scores = [b.score for b in branches]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_tree_prefixes_follow_plan(self):
        plan = best_path(self.table, set())
        tree = branch_tree(self.table, set(), {}, plan, top_k=99)
        for w, branches in tree.items():
            wi = self.table.week_index(w)
            self.assertEqual(sum(b.recommended for b in branches), 1)
            for b in branches:
                self.assertEqual(teams_of(b.path)[:wi], teams_of(plan)[:wi])
                if b.recommended:
                    self.assertEqual(teams_of(b.path), teams_of(plan))

    def test_locked_week_has_single_branch(self):
        plan = best_path(self.table, set(), locks={1: ["D"]})
        tree = branch_tree(self.table, set(), {1: ["D"]}, plan, top_k=99)
        self.assertEqual(len(tree[2]), 1)
        self.assertEqual(tree[2][0].teams, ["D"])


class JointTests(unittest.TestCase):
    def setUp(self):
        self.teams = ["A", "B", "C", "D"]
        self.games = {
            1: [("A", "B", 0.8), ("C", "D", 0.75)],
            2: [("A", "C", 0.6), ("B", "D", 0.55)],
        }
        self.table = make_table([1, 2], self.teams, self.games)

    def brute_force(self, paths, week_count):
        """Enumerate every outcome to get P(>=1 alive) and P(all alive)."""
        game_list = [(wk, h, a, p) for wk in [1, 2][:week_count] for h, a, p in self.games[wk]]
        p_any = p_all = 0.0
        for outcome in itertools.product([True, False], repeat=len(game_list)):
            prob = 1.0
            winners = {}
            for (wk, h, a, p), home_wins in zip(game_list, outcome):
                prob *= p if home_wins else 1 - p
                winners[(wk, h)] = home_wins
                winners[(wk, a)] = not home_wins
            alive = []
            for path in paths:
                ok = all(winners[(wp.week, t)] for wp in path.picks if wp.week <= week_count for t in wp.teams)
                alive.append(ok)
            p_any += prob * any(alive)
            p_all += prob * all(alive)
        return p_any, p_all

    def test_inclusion_exclusion_matches_brute_force(self):
        p1 = best_path(self.table, set(), locks={0: ["A"]})
        p2 = best_path(self.table, set(), locks={0: ["C"]})
        p3 = best_path(self.table, set(), locks={0: ["B"]})
        for paths in [[p1], [p1, p2], [p1, p2, p3], [p1, p1]]:
            any_curve = any_alive_curve(self.table, paths)
            all_curve = subset_alive_curve(self.table, paths)
            for k in (1, 2):
                exp_any, exp_all = self.brute_force(paths, k)
                self.assertAlmostEqual(any_curve[k - 1], exp_any, places=9)
                self.assertAlmostEqual(all_curve[k - 1], exp_all, places=9)

    def test_two_pick_joint_matches_brute_force(self):
        table = make_table([1, 2], self.teams, self.games, picks_required=[2, 1])
        p1 = best_path(table, set(), locks={0: ["A", "C"]})
        p2 = best_path(table, set(), locks={0: ["A", "D"]})
        any_curve = any_alive_curve(table, [p1, p2])
        all_curve = subset_alive_curve(table, [p1, p2])
        for k in (1, 2):
            exp_any, exp_all = self.brute_force([p1, p2], k)
            self.assertAlmostEqual(any_curve[k - 1], exp_any, places=9)
            self.assertAlmostEqual(all_curve[k - 1], exp_all, places=9)

    def test_opponents_cannot_both_survive(self):
        pa = best_path(self.table, set(), locks={0: ["A"]})
        pb = best_path(self.table, set(), locks={0: ["B"]})
        self.assertEqual(subset_alive_curve(self.table, [pa, pb])[0], 0.0)

    def test_any_objective_diversifies(self):
        cands = [b.path for b in branches_for_week(self.table, set(), {}, {}, 0, top_k=4)]
        result = select_joint(self.table, [cands, cands], objective="any")
        picks = [p.first_teams[0] for p in result.paths]
        self.assertEqual(len(set(picks)), 2)
        self.assertGreater(result.p_any, max(p.survival for p in cands))
        result_e = select_joint(self.table, [cands, cands], objective="expected")
        self.assertEqual(len({p.first_teams[0] for p in result_e.paths}), 1)
        result_f = select_joint(self.table, [cands, cands], objective="final")
        self.assertGreaterEqual(result_f.p_any, result.p_any - 1e-12)

    def test_contrarian_bonus_prefers_unpopular(self):
        bonus = contrarian_bonus(self.table, {"A": 70, "C": 30})
        self.assertGreater(bonus["D"], bonus["C"])
        self.assertGreater(bonus["C"], bonus["A"])
        self.assertTrue(all(math.isfinite(v) for v in bonus.values()))


class PlanEntriesTests(unittest.TestCase):
    def setUp(self):
        self.teams = ["A", "B", "C", "D", "E", "F"]
        self.table = make_table([1, 2, 3], self.teams, {
            1: [("A", "B", 0.8), ("C", "D", 0.7), ("E", "F", 0.6)],
            2: [("A", "C", 0.6), ("B", "E", 0.55), ("D", "F", 0.65)],
            3: [("A", "E", 0.7), ("C", "F", 0.6), ("B", "D", 0.5)],
        })

    def test_three_entries_diversify_first_week(self):
        specs = [EntrySpec(n, set(), {}) for n in "ABC"]
        result = plan_entries(self.table, specs, top_k=6)
        firsts = [er.plan.first_teams[0] for er in result.entries]
        self.assertEqual(len(set(firsts)), 3)
        self.assertEqual(len(result.joint.curve_any), 3)
        for er in result.entries:
            self.assertEqual(set(er.branches), {1, 2, 3})
            self.assertEqual(len(er.curve), 3)
            self.assertAlmostEqual(er.curve[-1], er.plan.survival)

    def test_dead_entry_and_locks_and_infeasible_lock_warning(self):
        specs = [
            EntrySpec("A", set(), {2: ["D"]}),
            EntrySpec("B", set(), {}, alive=False),
            EntrySpec("C", {"B", "C"}, {3: ["B"]}),  # B already used: infeasible lock
        ]
        result = plan_entries(self.table, specs, top_k=6)
        a, b, c = result.entries
        self.assertEqual(a.plan.picks[1].teams, ["D"])
        self.assertNotIn("D", a.plan.picks[0].teams)      # later lock reserves the team
        self.assertIsNone(b.plan)
        self.assertTrue(any("infeasible" in w for w in c.warnings))
        self.assertIsNotNone(c.plan)
        self.assertEqual(len(result.joint.paths), 2)

    def test_later_lock_reserves_team_from_first_week(self):
        specs = [EntrySpec("A", set(), {3: ["A"]})]
        result = plan_entries(self.table, specs, top_k=9)
        plan = result.entries[0].plan
        self.assertEqual(plan.picks[2].teams, ["A"])
        self.assertNotIn("A", plan.picks[0].teams + plan.picks[1].teams)
        for b in result.entries[0].branches[1]:
            self.assertNotIn("A", b.teams)


if __name__ == "__main__":
    unittest.main()
