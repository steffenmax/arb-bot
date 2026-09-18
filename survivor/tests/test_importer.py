"""Tests for parsing picks pasted from a pool site."""
import unittest

from survivor.importer import find_teams, parse_picks


def picks(result, entry):
    return [(p["week"], p["team"]) for p in result.as_dict()["entries"][entry]]


class TeamMatchingTests(unittest.TestCase):
    def test_longest_name_wins(self):
        self.assertEqual([c for _, _, c in find_teams("New York Jets")], ["NYJ"])
        self.assertEqual([c for _, _, c in find_teams("New York Giants")], ["NYG"])
        self.assertEqual([c for _, _, c in find_teams("Los Angeles Chargers")], ["LAC"])

    def test_bare_ambiguous_city_is_not_guessed(self):
        self.assertEqual(find_teams("Los Angeles"), [])
        self.assertEqual(find_teams("New York"), [])

    def test_unambiguous_city_nickname_and_code(self):
        for text, code in [("Jacksonville", "JAX"), ("Jaguars", "JAX"), ("JAX", "JAX"),
                           ("Chiefs", "KC"), ("49ers", "SF"), ("Commanders", "WAS")]:
            self.assertEqual([c for _, _, c in find_teams(text)], [code], text)

    def test_other_sites_abbreviations(self):
        for text, code in [("LAR", "LA"), ("WSH", "WAS"), ("JAC", "JAX"), ("OAK", "LV"), ("SD", "LAC")]:
            self.assertEqual([c for _, _, c in find_teams(text)], [code], text)

    def test_a_code_inside_a_word_is_not_a_team(self):
        self.assertEqual(find_teams("SFO2"), [])

    def test_lowercase_words_that_look_like_codes_are_ignored(self):
        # NO, was, car, den, min, ten, sea, pit are all real team codes
        for text in ["no picks here", "it was a car", "den of ten", "by the sea", "the pit"]:
            self.assertEqual(find_teams(text), [], text)
        # but the capitalised code still counts
        self.assertEqual([c for _, _, c in find_teams("Week 1 NO")], ["NO"])


class ParsePicksTests(unittest.TestCase):
    def test_one_row_per_week_with_results(self):
        r = parse_picks("""Entry 1
Week 1   Philadelphia Eagles   WIN
Week 2   Buffalo Bills   LOSS""")
        self.assertEqual(picks(r, "1"), [(1, "PHI"), (2, "BUF")])
        self.assertEqual([p["result"] for p in r.as_dict()["entries"]["1"]], ["WIN", "LOSS"])

    def test_compact_one_line_per_entry(self):
        r = parse_picks("A: W1 PHI, W2 BUF\nB: W1 KC, W2 DET", known_entries=["A", "B"])
        self.assertEqual(picks(r, "A"), [(1, "PHI"), (2, "BUF")])
        self.assertEqual(picks(r, "B"), [(1, "KC"), (2, "DET")])

    def test_week_header_then_team_on_its_own_line(self):
        r = parse_picks("Week 1\nEagles\nWeek 2\nBills")
        self.assertEqual(picks(r, "A"), [(1, "PHI"), (2, "BUF")])

    def test_a_team_with_no_week_is_reported_not_guessed(self):
        r = parse_picks("Eagles").as_dict()
        self.assertEqual(r["entries"], {})
        self.assertTrue(any("No week number" in n for n in r["notes"]))

    def test_duplicate_week_keeps_the_first(self):
        r = parse_picks("Week 1 Eagles\nWeek 1 Bills")
        self.assertEqual(picks(r, "A"), [(1, "PHI")])
        self.assertTrue(any("already has a week 1" in n for n in r.as_dict()["notes"]))

    def test_out_of_range_week_is_skipped(self):
        r = parse_picks("Week 23 Eagles").as_dict()
        self.assertEqual(r["entries"], {})
        self.assertTrue(any("out of range" in n for n in r["notes"]))

    def test_nothing_recognised_explains_the_format(self):
        notes = parse_picks("no picks here").as_dict()["notes"]
        self.assertTrue(any("No picks recognised" in n for n in notes))

    def test_matchup_line_keeps_the_picked_team_and_says_so(self):
        r = parse_picks("Week 1  Philadelphia Eagles vs Dallas Cowboys")
        self.assertEqual(picks(r, "A"), [(1, "PHI")])
        self.assertTrue(any("names 2 teams" in n for n in r.as_dict()["notes"]))


if __name__ == "__main__":
    unittest.main()
