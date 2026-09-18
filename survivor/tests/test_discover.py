"""Tests for the site recorder.

The capture it writes describes a signed-in session, so the redaction below is
the part that has to be right: a token that survived into a file meant for
sharing would be the whole problem. Nothing here touches a browser.
"""
import json
import unittest

from survivor.discover import digest, interesting, report, scrub, _op_name


class RedactionTests(unittest.TestCase):
    def test_keys_that_name_a_secret_are_dropped_whatever_they_hold(self):
        out = scrub({"accessToken": "abc", "Session-Cookie": {"deep": "value"},
                     "csrf": 1, "refreshToken": ["a", "b"]})
        self.assertEqual(out, {"accessToken": "<redacted>", "Session-Cookie": "<redacted>",
                               "csrf": "<redacted>", "refreshToken": "<redacted>"})

    def test_a_jwt_is_caught_by_shape_under_an_innocent_key(self):
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27uhbUJU1p1r_wW1g"
        out = scrub({"note": f"bearer {jwt} attached"})
        self.assertNotIn("eyJ", out["note"])
        self.assertIn("<redacted>", out["note"])

    def test_long_opaque_strings_and_emails_go(self):
        out = scrub({"id": "a" * 64, "owner": "maxsteffen@example.com"})
        self.assertEqual(out["id"], "<redacted>")
        self.assertEqual(out["owner"], "<email>")

    def test_ordinary_data_survives_intact(self):
        payload = {"week": 2, "entryName": "Max 1", "team": "SF", "pickCount": 412,
                   "contestId": "contest_01KYWVFY74ESD500VH86BHRBJC"}
        self.assertEqual(scrub(payload), payload)

    def test_redaction_reaches_through_lists(self):
        out = scrub({"rows": [{"apiKey": "x"}, {"team": "GB"}]})
        self.assertEqual(out["rows"], [{"apiKey": "<redacted>"}, {"team": "GB"}])


class DigestTests(unittest.TestCase):
    def test_long_lists_collapse_to_a_length_and_a_sample(self):
        lines = digest({"entries": [{"name": f"E{i}"} for i in range(500)]})
        self.assertEqual(lines[0], "entries: [500]")
        self.assertLess(len(lines), 10)

    def test_depth_is_bounded(self):
        node = {}
        cur = node
        for i in range(40):
            cur["next"] = {}
            cur = cur["next"]
        self.assertLess(len(digest(node)), 20)

    def test_long_strings_are_truncated_not_dumped(self):
        line = digest({"blurb": "x" * 5000})[0]
        self.assertLess(len(line), 80)
        self.assertIn("...", line)

    def test_scalars_show_their_value(self):
        self.assertEqual(digest({"week": 2, "alive": True, "team": "SF"}),
                         ['week = 2', 'alive = true', 'team = "SF"'])


class ClassificationTests(unittest.TestCase):
    def test_a_payload_full_of_teams_is_flagged(self):
        notes = interesting({"picks": [{"team": "SF"}, {"team": "BAL"}, {"team": "GB"},
                                       {"week": 2}]})
        self.assertIn("3 team codes/names", notes)
        self.assertIn("weeks", notes)
        self.assertIn("picks", notes)

    def test_an_unrelated_payload_is_not(self):
        self.assertEqual(interesting({"banners": [{"imageUrl": "/a.png"}]}), [])


class OperationNameTests(unittest.TestCase):
    def test_explicit_operation_name(self):
        self.assertEqual(_op_name(json.dumps({"operationName": "GetEntries", "variables": {}})),
                         "GetEntries")

    def test_name_read_out_of_the_query_text(self):
        self.assertEqual(_op_name(json.dumps({"query": "mutation SubmitPick($id: ID!) { ... }"})),
                         "mutation SubmitPick")

    def test_batched_graphql_uses_the_first_operation(self):
        self.assertEqual(_op_name(json.dumps([{"operationName": "A"}, {"operationName": "B"}])), "A")

    def test_not_graphql_at_all(self):
        self.assertIsNone(_op_name(None))
        self.assertIsNone(_op_name("week=2&team=SF"))


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.session = {
            "url": "https://example.test/contest/entries",
            "pages": {"entriesUrl": "https://example.test/contest/entries",
                      "stats": "Week 2 — SF 41.2%"},
            "calls": [
                {"phase": "entries", "method": "POST", "url": "https://api.example.test/graphql",
                 "query": None, "status": 200, "operation": "GetEntries",
                 "requestBody": {"operationName": "GetEntries", "variables": {"contestId": "c1"}},
                 "body": {"data": {"entries": [{"entryName": "Max 1", "week": 2, "team": "SF"}]}}},
                {"phase": "pick", "method": "POST", "url": "https://api.example.test/graphql",
                 "query": None, "status": 200, "operation": "mutation SubmitPick",
                 "requestBody": {"operationName": "SubmitPick",
                                 "variables": {"entryId": "e1", "week": 2, "teamId": "SF"}},
                 "body": {"data": {"submitPick": {"ok": True}}}},
            ],
        }

    def test_the_report_names_each_endpoint_and_operation(self):
        text = report(self.session)
        self.assertIn("POST https://api.example.test/graphql", text)
        self.assertIn("GetEntries", text)
        self.assertIn("mutation SubmitPick", text)

    def test_the_pick_request_body_is_shown_since_that_is_how_a_pick_is_written(self):
        text = report(self.session)
        self.assertIn("Request body:", text)
        self.assertIn("entryId", text)

    def test_phases_are_kept_apart(self):
        text = report(self.session)
        self.assertIn("## Phase: entries", text)
        self.assertIn("## Phase: pick", text)
        self.assertLess(text.index("## Phase: entries"), text.index("## Phase: pick"))

    def test_identical_repeat_calls_are_shown_once(self):
        self.session["calls"].append(dict(self.session["calls"][0]))
        self.assertEqual(report(self.session).count("`GetEntries`"), 1)

    def test_the_report_is_small_enough_to_send(self):
        self.assertLess(len(report(self.session)), 20000)


if __name__ == "__main__":
    unittest.main()
