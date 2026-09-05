"""Unit tests: python3 -m unittest discover survivor/tests"""
import itertools
import math
import unittest

import numpy as np

from survivor.optimizer import (
    any_alive_curve, best_path, candidate_paths, contrarian_bonus,
    select_joint, subset_alive_curve,
)
from survivor.probs import ProbTable, devig, spread_prob


def make_table(weeks, teams, games):
    """games: {week: [(home, away, p_home), ...]}; teams absent are on bye."""
    nw, nt = len(weeks), len(teams)
    prob = np.full((nw, nt), np.nan)
    opp = np.full((nw, nt), "", dtype=object)
    src = np.full((nw, nt), "", dtype=object)
    home = np.zeros((nw, nt), dtype=bool)
    for w, wk in enumerate(weeks):
        for h, a, p in games.get(wk, []):
            i, j = teams.index(h), teams.index(a)
            prob[w, i], prob[w, j] = p, 1 - p
            opp[w, i], opp[w, j] = a, h
            src[w, i] = src[w, j] = "test"
            home[w, i] = True
    return ProbTable(list(weeks), list(teams), prob, prob.copy(), opp, src, home)


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
        teams = [t for _, t, _ in path.picks]
        self.assertEqual(len(set(teams)), len(teams))
        # A is 0.9 in week 1 and 0.8 in week 2; best is A wk1 + B wk2 (0.63)
        self.assertEqual(teams, ["A", "B"])
        self.assertAlmostEqual(path.survival, 0.9 * 0.7)

    def test_used_and_forced(self):
        path = best_path(self.table, used={"A"})
        self.assertNotIn("A", [t for _, t, _ in path.picks])
        forced = best_path(self.table, used=set(), forced_first="C")
        self.assertEqual(forced.picks[0][1], "C")
        self.assertEqual(forced.picks[1][1], "A")
        self.assertIsNone(best_path(self.table, used={"C"}, forced_first="C"))

    def test_bye_is_unpickable(self):
        table = make_table([1, 2], self.teams, {
            1: [("A", "B", 0.9)],           # C and D on bye
            2: [("C", "D", 0.95)],
        })
        path = best_path(table, used=set())
        self.assertEqual([t for _, t, _ in path.picks], ["A", "C"])


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
            alive = [all(winners[(wk, t)] for wk, t, _ in path.picks if wk <= week_count) for path in paths]
            p_any += prob * any(alive)
            p_all += prob * all(alive)
        return p_any, p_all

    def test_inclusion_exclusion_matches_brute_force(self):
        p1 = best_path(self.table, set(), forced_first="A")
        p2 = best_path(self.table, set(), forced_first="C")
        p3 = best_path(self.table, set(), forced_first="B")
        for paths in [[p1], [p1, p2], [p1, p2, p3], [p1, p1]]:
            any_curve = any_alive_curve(self.table, paths)
            all_curve = subset_alive_curve(self.table, paths)
            for k in (1, 2):
                exp_any, exp_all = self.brute_force(paths, k)
                self.assertAlmostEqual(any_curve[k - 1], exp_any, places=9)
                self.assertAlmostEqual(all_curve[k - 1], exp_all, places=9)

    def test_opponents_cannot_both_survive(self):
        pa = best_path(self.table, set(), forced_first="A")
        pb = best_path(self.table, set(), forced_first="B")
        self.assertEqual(subset_alive_curve(self.table, [pa, pb])[0], 0.0)

    def test_any_objective_diversifies(self):
        # Two entries, same history: the joint pick should not double up on A.
        cands = candidate_paths(self.table, set(), top_k=4)
        result = select_joint(self.table, [cands, cands], objective="any")
        picks = [p.first_pick for p in result.paths]
        self.assertEqual(len(set(picks)), 2)
        self.assertGreater(result.p_any, max(p.survival for p in cands))
        # The "expected" objective just stacks the single best path.
        result_e = select_joint(self.table, [cands, cands], objective="expected")
        self.assertEqual(len({p.first_pick for p in result_e.paths}), 1)

    def test_contrarian_bonus_prefers_unpopular(self):
        bonus = contrarian_bonus(self.table, {"A": 70, "C": 30})
        # Same win probability neighbourhood, but nobody is on B or D.
        self.assertGreater(bonus["D"], bonus["C"])
        self.assertGreater(bonus["C"], bonus["A"])
        self.assertTrue(all(math.isfinite(v) for v in bonus.values()))


if __name__ == "__main__":
    unittest.main()
