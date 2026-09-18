"""Tests for reading contest data out of whatever JSON a pool site's front end fetches.

The shapes below are the ones pool and fantasy APIs actually use. None of this
touches the network or a browser.
"""
import unittest

from survivor.splash import (
    extract_picks, extract_pool_stats, pool_pick_pct, summarise, team_from, week_from,
)


def triples(payload):
    return sorted((p["entry"], p["week"], p["team"]) for p in extract_picks(payload))


class ValueParsingTests(unittest.TestCase):
    def test_team_from_codes_names_and_objects(self):
        self.assertEqual(team_from("PHI"), "PHI")
        self.assertEqual(team_from("Kansas City Chiefs"), "KC")
        self.assertEqual(team_from("Eagles"), "PHI")
        self.assertEqual(team_from({"abbreviation": "SF"}), "SF")
        self.assertEqual(team_from({"team": {"teamName": "Detroit Lions"}}), "DET")
        self.assertEqual(team_from("LAR"), "LA")          # other sites' abbreviation

    def test_team_from_rejects_non_teams(self):
        for junk in ("", "   ", "Pending", 7, None, {"unrelated": "value"}):
            self.assertIsNone(team_from(junk), junk)

    def test_week_from_numbers_and_text(self):
        self.assertEqual(week_from(3), 3)
        self.assertEqual(week_from("Week 12"), 12)
        self.assertEqual(week_from("W7"), 7)
        self.assertEqual(week_from("2"), 2)
        for junk in (0, 19, 2.5, True, "next week", None):
            self.assertIsNone(week_from(junk), junk)


class ShapeTests(unittest.TestCase):
    """Key names differ between sites; matching is on shape, not on one schema."""

    def test_nested_team_object(self):
        self.assertEqual(triples({"data": {"entries": [
            {"entryName": "Max 1", "picks": [{"week": 1, "team": {"abbreviation": "PHI"}}]}]}}),
            [("Max 1", 1, "PHI")])

    def test_team_as_a_bare_code_or_full_name(self):
        self.assertEqual(triples({"entries": [{"name": "E", "picks": [{"week": 2, "team": "BUF"}]}]}),
                         [("E", 2, "BUF")])
        self.assertEqual(triples({"entries": [{"name": "E", "picks": [{"week": 3, "team": "Kansas City Chiefs"}]}]}),
                         [("E", 3, "KC")])

    def test_week_written_as_text_and_a_selection_key(self):
        self.assertEqual(triples({"entries": [{"name": "E", "picks": [{"week": "Week 4", "selection": "DET"}]}]}),
                         [("E", 4, "DET")])

    def test_graphql_style_camel_case_and_nodes(self):
        self.assertEqual(triples({"data": {"contest": {"entries": {"nodes": [
            {"displayName": "Max 1", "selections": [{"roundNumber": 5, "teamAbbr": "SF"}]}]}}}}),
            [("Max 1", 5, "SF")])

    def test_flat_rows_one_per_pick(self):
        self.assertEqual(triples({"rows": [
            {"username": "Dave", "week": 1, "teamName": "Eagles"},
            {"username": "Sam", "week": 1, "teamName": "Chiefs"}]}),
            [("Dave", 1, "PHI"), ("Sam", 1, "KC")])

    def test_picks_keyed_by_week_number(self):
        self.assertEqual(triples({"entries": [{"name": "E", "picks": {"1": {"team": "PHI"}, "2": {"team": "BUF"}}}]}),
                         [("E", 1, "PHI"), ("E", 2, "BUF")])

    def test_the_same_pick_under_several_paths_is_counted_once(self):
        pick = {"week": 1, "team": "PHI"}
        payload = {"entries": [{"name": "E", "picks": [pick], "latestPick": pick}]}
        self.assertEqual(triples(payload), [("E", 1, "PHI")])

    def test_unrecognisable_payload_yields_nothing(self):
        self.assertEqual(extract_picks({"settings": {"theme": "dark", "rows": 12}}), [])


class SummaryTests(unittest.TestCase):
    PAYLOAD = {"entries": [
        {"name": "Max 1", "picks": [{"week": 1, "team": "PHI"}]},
        {"name": "Max 2", "picks": [{"week": 1, "team": "KC"}]},
        {"name": "Dave", "picks": [{"week": 1, "team": "PHI"}]},
        {"name": "Sam", "picks": [{"week": 1, "team": "PHI"}]},
    ]}

    def test_pool_wide_pick_distribution(self):
        out = summarise(extract_picks(self.PAYLOAD), me="Max")
        self.assertEqual(out["poolSize"], 4)
        self.assertEqual(out["pickPct"]["1"]["PHI"], 75.0)
        self.assertEqual(out["pickPct"]["1"]["KC"], 25.0)

    def test_my_entries_are_separated_from_the_pool(self):
        out = summarise(extract_picks(self.PAYLOAD), me="Max")
        self.assertEqual(sorted(out["mine"]), ["Max 1", "Max 2"])
        self.assertEqual(sorted(out["entries"]), ["Dave", "Max 1", "Max 2", "Sam"])

    def test_without_a_name_hint_nothing_is_claimed_as_mine(self):
        self.assertEqual(summarise(extract_picks(self.PAYLOAD))["mine"], {})



class PoolStatisticsTests(unittest.TestCase):
    """The statistics page reports the whole pool, so its numbers win."""

    def test_counts_keyed_by_week(self):
        rows = extract_pool_stats({"weeks": [{"week": 2, "teams": [
            {"abbreviation": "SF", "pickCount": 412},
            {"abbreviation": "BAL", "pickCount": 301},
            {"abbreviation": "TB", "pickCount": 118}]}]})
        self.assertEqual(sorted((r["week"], r["team"], r["count"]) for r in rows),
                         [(2, "BAL", 301), (2, "SF", 412), (2, "TB", 118)])
        self.assertEqual(pool_pick_pct(rows), {"2": {"SF": 49.6, "BAL": 36.2, "TB": 14.2}})

    def test_week_at_the_root_reaches_the_rows_under_it(self):
        rows = extract_pool_stats({"week": 3, "breakdown": [
            {"team": {"abbr": "KC"}, "percentage": 44.2},
            {"team": {"abbr": "PHI"}, "percentage": 31.0}]})
        self.assertEqual(pool_pick_pct(rows), {"3": {"KC": 44.2, "PHI": 31.0}})

    def test_published_percentages_are_believed_over_recomputing(self):
        # These do not sum to 100 because the page only lists the top teams.
        rows = extract_pool_stats({"data": {"contestStats": {"weekNumber": 4, "selections": [
            {"teamAbbreviation": "DET", "selectionCount": 88, "pickPercentage": 22.5},
            {"teamAbbreviation": "GB", "selectionCount": 52, "pickPercentage": 13.3}]}}})
        self.assertEqual(pool_pick_pct(rows), {"4": {"DET": 22.5, "GB": 13.3}})

    def test_rows_without_a_week_are_kept_but_not_turned_into_percentages(self):
        rows = extract_pool_stats({"teams": [{"team": "NYJ", "count": 5}]})
        self.assertEqual([(r["week"], r["team"]) for r in rows], [(None, "NYJ")])
        self.assertEqual(pool_pick_pct(rows), {})

    def test_nothing_team_like_yields_nothing(self):
        self.assertEqual(extract_pool_stats({"week": 2, "payouts": [{"place": 1, "count": 3}]}), [])

    def test_statistics_beat_the_entry_listing(self):
        picks = [{"entry": "Max 1", "week": 2, "team": "SF", "status": None, "path": "a"},
                 {"entry": "Max 2", "week": 2, "team": "SF", "status": None, "path": "b"}]
        stats = extract_pool_stats({"week": 2, "teams": [
            {"team": "SF", "count": 412}, {"team": "BAL", "count": 588}]})
        out = summarise(picks, me="Max", stats=stats)
        self.assertEqual(out["pctSource"], "statistics page")
        self.assertEqual(out["pickPct"]["2"], {"SF": 41.2, "BAL": 58.8})
        self.assertEqual(out["pickCounts"]["2"], {"SF": 412, "BAL": 588})
        self.assertEqual(out["poolSize"], 1000)          # the pool, not the two rows seen
        self.assertEqual(sorted(out["mine"]), ["Max 1", "Max 2"])

    def test_without_statistics_the_listing_is_used_and_labelled(self):
        picks = [{"entry": "A", "week": 2, "team": "SF", "status": None, "path": "a"},
                 {"entry": "B", "week": 2, "team": "BAL", "status": None, "path": "b"}]
        out = summarise(picks)
        self.assertEqual(out["pctSource"], "entry listing")
        self.assertEqual(out["pickPct"]["2"], {"SF": 50.0, "BAL": 50.0})
        self.assertEqual(out["poolSize"], 2)

if __name__ == "__main__":
    unittest.main()
