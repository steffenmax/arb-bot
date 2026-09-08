"""Parser, config and injury-model tests (no network)."""
import unittest

from survivor import espn
from survivor.dashboard import config
from survivor.injuries import Injury, team_impact


def event(state="pre", completed=False, home_score="0", away_score="0", winner=None, odds=True):
    home = {"homeAway": "home", "team": {"abbreviation": "WSH"}, "score": home_score,
            "records": [{"type": "total", "summary": "0-0"}]}
    away = {"homeAway": "away", "team": {"abbreviation": "LAR"}, "score": away_score, "records": []}
    if winner == "home":
        home["winner"], away["winner"] = True, False
    elif winner == "away":
        home["winner"], away["winner"] = False, True
    comp = {
        "competitors": [away, home],
        "status": {"type": {"state": state, "completed": completed, "name": "STATUS_FINAL" if completed else "STATUS_SCHEDULED",
                            "shortDetail": "Final" if completed else "9/13 - 1:00 PM EDT"},
                   "displayClock": "0:00", "period": 4 if completed else 0},
        "broadcast": "FOX", "venue": {"fullName": "Northwest Stadium", "address": {"city": "Landover"}},
        "neutralSite": False, "timeValid": True,
    }
    if odds:
        comp["odds"] = [{"provider": {"name": "DraftKings"}, "spread": -2.5, "overUnder": 47.5,
                         "moneyline": {"home": {"close": {"odds": "-142"}}, "away": {"close": {"odds": "+120"}}}}]
    if completed:
        comp["headlines"] = [{"shortLinkText": "Commanders hold on"}]
    return {"id": "401", "date": "2026-09-13T17:00Z", "week": {"number": 1}, "competitions": [comp]}


class EspnParseTests(unittest.TestCase):
    def test_pregame_event(self):
        g = espn.parse_event(event())
        self.assertEqual((g["home"], g["away"]), ("WAS", "LA"))
        self.assertEqual(g["status"], "scheduled")
        self.assertEqual(g["spreadLine"], 2.5)            # nflverse sign: home favored positive
        self.assertEqual((g["homeMoneyline"], g["awayMoneyline"]), (-142, 120))
        self.assertEqual(g["totalLine"], 47.5)
        self.assertIsNone(g["homeScore"])
        self.assertIsNone(g["winner"])

    def test_final_event(self):
        g = espn.parse_event(event("post", True, "24", "20", "home", odds=False))
        self.assertEqual(g["status"], "final")
        self.assertEqual((g["homeScore"], g["awayScore"]), (24, 20))
        self.assertEqual(g["winner"], "home")
        self.assertIsNone(g["spreadLine"])
        self.assertEqual(g["headline"], "Commanders hold on")

    def test_final_without_winner_flag_uses_scores(self):
        g = espn.parse_event(event("post", True, "17", "20", None, odds=False))
        self.assertEqual(g["winner"], "away")
        tie = espn.parse_event(event("post", True, "17", "17", None, odds=False))
        self.assertIsNone(tie["winner"])

    def test_code_mapping(self):
        self.assertEqual(espn.to_code("WSH"), "WAS")
        self.assertEqual(espn.to_code("LAR"), "LA")
        self.assertEqual(espn.to_code("KC"), "KC")
        self.assertEqual(espn.logo_url("LA"), "https://a.espncdn.com/i/teamlogos/nfl/500/lar.png")


class ConfigTests(unittest.TestCase):
    def test_defaults_and_normalization(self):
        cfg = config.normalize({"entries": [{"name": "A", "used": ["lar", "Chiefs"], "locks": {"3": ["det"]}}],
                                "picksPerWeek": {"12": 2, "5": 1}, "horizon": 10})
        self.assertEqual(cfg["entries"][0]["used"], ["LA", "KC"])
        self.assertEqual(cfg["entries"][0]["locks"], {"3": ["DET"]})
        self.assertEqual(cfg["picksPerWeek"], {"12": 2})
        self.assertEqual(cfg["horizon"], 10)
        self.assertEqual(cfg["objective"], "any")
        self.assertTrue(cfg["injuryAdjust"])

    def test_rejects_bad_input(self):
        for bad in [{"horizon": 99}, {"objective": "max"}, {"entries": []}, {"entries": [{"name": "A"}, {"name": "A"}]},
                    {"overrides": {"g": "tie"}}, {"entries": [{"name": "A", "used": ["XYZ"]}]}, {"decay": 2}]:
            with self.assertRaises(config.ConfigError, msg=str(bad)):
                config.normalize(bad)


class InjuryModelTests(unittest.TestCase):
    def test_qb_dominates_and_fades(self):
        inj = [Injury("QB1", "QB", "Out"), Injury("WR1", "WR", "Questionable"), Injury("LT", "LT", "Injured Reserve")]
        now = team_impact(inj)
        later = team_impact(inj, 6)
        self.assertLess(now, -5.0)
        self.assertGreater(later, now)                        # short-term absences heal
        self.assertLessEqual(later, -0.9)                     # IR persists
        self.assertGreaterEqual(team_impact([Injury(f"p{i}", "QB", "Out") for i in range(5)]), -9.0)  # cap

    def test_backup_qb_is_minor(self):
        self.assertGreater(team_impact([Injury("QB2", "QB2", "Out")]), -0.5)


if __name__ == "__main__":
    unittest.main()
