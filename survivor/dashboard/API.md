# Survivor Dashboard API contract

The backend is a local Python HTTP server (`python3 -m survivor.dashboard`,
default http://127.0.0.1:8765). It serves the static frontend from
`survivor/dashboard/static/` at `/` and a JSON API under `/api/`.
All timestamps are ISO-8601 strings. Team codes are nflverse codes
(ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LA LAC LV MIA
MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS).

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/config` | Saved dashboard config (see Config). Returns defaults if none saved. |
| PUT | `/api/config` | Save config. Body: Config. Returns the saved Config. |
| POST | `/api/dashboard` | Run everything with a Config in the body. Returns Dashboard. |
| POST | `/api/refresh` | Force re-download of all external data. Returns `{"ok": true, "dataAge": {...}}`. |
| GET | `/api/health` | `{"ok": true, "version": "..."}` |

`POST /api/dashboard` is the only call the UI needs in normal use. It is
idempotent and typically completes in 1 to 3 seconds. Any invalid Config
returns HTTP 400 with `{"error": "message"}`.

## Config (request body)

```json
{
  "season": 2026,
  "entries": [
    {"name": "A", "used": ["LAC"], "locks": {"3": ["DET"]}, "alive": true},
    {"name": "B", "used": ["JAX"], "locks": {}, "alive": true},
    {"name": "C", "used": [],      "locks": {}, "alive": true}
  ],
  "picksPerWeek": {"12": 2, "18": 2},
  "horizon": 10,
  "decay": 0.03,
  "objective": "any",
  "topBranches": 10,
  "contrarianWeight": 1.0,
  "pickPct": {"1": {"LAC": 31, "JAX": 22, "DET": 18}},
  "overrides": {"2026_01_NE_SEA": "home"},
  "injuryAdjust": true
}
```

* `entries[].used`: teams that entry has already burned (any week).
* `entries[].locks`: week (string key) to the list of teams the user has
  manually chosen for that week. A locked week is not re-optimized. The
  list length must equal `picksPerWeek` for that week (default 1). A lock
  on a game that is already decided or in progress keeps that team for the
  entry (the pick was made before kickoff); a locked team that lost marks
  the entry eliminated. Locks in weeks before the current week are
  treated as used teams.
* `entries[].alive`: false means eliminated; the entry is shown but excluded
  from optimization.
* `picksPerWeek`: weeks that require more than one pick (the "two picks"
  toggle). Omitted weeks require one pick. All picks in a multi-pick week
  must win for the entry to survive.
* `horizon`: last week to optimize survival through (1 to 18).
* `decay`: per-week shrink of future win probabilities toward 50%.
* `objective`: `"any"` (default) maximizes the expected number of weeks with
  at least one entry alive through the horizon, which rewards staying
  represented every week; `"final"` maximizes P(at least one entry alive at
  the horizon); `"expected"` maximizes the expected number of survivors.
* `hedge` (default 0.1): penalty, in log-probability units, for planning the
  same team in the same later week as another entry. 0 disables hedging.
* `topBranches`: how many candidate picks to expand per entry per week.
* `pickPct`: crowd pick percentages, keyed by week then team. Optional.
* `overrides`: what-if outcomes for games: `"home"`, `"away"`, or omit.
  A game with an override is treated as decided with that winner: it can
  no longer be picked by anyone, except an entry that has locked one of
  its teams for that week, whose pick then wins or loses for certain.
  Overrides on games that are already final or in progress are ignored
  with a warning in `meta.warnings`.
* `injuryAdjust`: apply the injury impact model to rating-based
  probabilities (weeks without posted lines).

## Dashboard (response)

```json
{
  "meta": {
    "season": 2026,
    "currentWeek": 1,
    "generatedAt": "2026-09-06T14:02:11Z",
    "horizon": 10,
    "decay": 0.03,
    "weeksInSeason": 18,
    "sources": {"moneyline": 112, "spread": 0, "rating": 160},
    "dataAge": {"games": "2026-09-06T13:40:00Z", "espn": "2026-09-06T14:01:50Z", "injuries": "...", "news": "...", "teams": "...", "standings": "...", "stats": "...", "depthChart": "..."},
    "warnings": ["ESPN news unavailable; showing cached headlines"],
    "version": "1.0.0",
    "hfa": 1.66,
    "ratingsFrom": "272 posted spreads, prior from 2025 closing lines"
  },
  "config": { "...the Config used, with defaults filled in..." },
  "teams": {
    "KC": {
      "code": "KC", "name": "Chiefs", "city": "Kansas City",
      "color": "#E31837", "altColor": "#FFB81C",
      "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/kc.png",
      "record": {"wins": 0, "losses": 0, "ties": 0, "summary": "0-0", "streak": null},
      "rating": 4.2,
      "injuryImpact": -1.5,
      "ratingAdjusted": 2.7,
      "qb1": "Patrick Mahomes",
      "stats": {
        "pointsFor": 0, "pointsAgainst": 0, "pointDiff": 0,
        "lastSeason": {"wins": 14, "losses": 3, "ties": 0, "pointDiff": 120, "record": "14-3"},
        "efficiency": {"games": 17, "offEpaPerPlay": 0.03, "defEpaPerPlay": -0.02, "passEpaPerDropback": 0.04, "rushEpaPerCarry": 0.02, "cpoe": -0.9, "turnoverMargin": -1, "sacksTaken": 47, "sacksMade": 33, "passYards": 3947, "rushYards": 1812},
        "efficiencySeason": 2025
      },
      "injuries": [
        {"player": "Patrick Mahomes", "position": "QB", "status": "Questionable", "detail": "Ankle", "returnDate": "2026-09-13", "comment": "...", "impact": -1.8, "isStarterQb": true, "updated": "2026-09-05T18:00Z"}
      ],
      "schedule": [
        {"week": 1, "bye": false, "opponent": "DEN", "home": true, "p": 0.572, "pRaw": 0.572, "source": "moneyline", "gameId": "2026_01_DEN_KC", "status": "scheduled", "won": null},
        {"week": 10, "bye": true}
      ]
    }
  },
  "weeks": [
    {"week": 1, "picksRequired": 1, "start": "2026-09-06", "end": "2026-09-16", "label": "Sep 6-15", "status": "upcoming", "gameIds": ["2026_01_NE_SEA", "..."], "byes": []}
  ],
  "games": [
    {
      "id": "2026_01_NE_SEA", "week": 1, "kickoff": "2026-09-10T00:20:00Z",
      "home": "SEA", "away": "NE", "neutral": false,
      "spread": 3.5, "homeMoneyline": -185, "awayMoneyline": 154, "total": 44.5,
      "lineSource": "nflverse", "oddsProvider": "DraftKings",
      "pHome": 0.622, "pHomeRaw": 0.622, "source": "moneyline",
      "status": "scheduled", "statusDetail": "9/9 - 8:20 PM EDT", "clock": "0:00", "period": 0,
      "homeScore": null, "awayScore": null,
      "override": null,
      "headline": null,
      "broadcast": "NBC", "venue": "Lumen Field", "weather": "Mostly sunny",
      "homeQb": "Sam Darnold", "awayQb": "Drake Maye",
      "picks": [{"entry": "A", "team": "SEA"}]
    }
  ],
  "entries": [
    {
      "name": "A", "alive": true, "used": ["LAC"], "locks": {"3": ["DET"]},
      "warnings": [],
      "pHorizon": 0.051,
      "survivalCurve": [0.82, 0.68, 0.52],
      "plan": [
        {"week": 1, "teams": ["LAC"], "opponents": ["ARI"], "home": [true], "p": 0.822, "pRaw": 0.822, "sources": ["moneyline"], "locked": false, "required": 1, "gameIds": ["2026_01_ARI_LAC"]}
      ],
      "branches": {
        "1": [
          {"teams": ["LAC"], "p": 0.822, "pHorizon": 0.051, "recommended": true, "crowdPct": 31, "crowdBonus": 0.9, "path": [ "...same objects as plan[]..." ]},
          {"teams": ["JAX"], "p": 0.772, "pHorizon": 0.047, "recommended": false, "crowdPct": 22, "crowdBonus": 1.1, "path": [ "..." ]}
        ]
      }
    }
  ],
  "joint": {
    "pAny": 0.061, "pAll": 0.028, "expectedAlive": 0.14, "expectedWeeksAny": 5.5,
    "weeks": [1, 2, 3],
    "curveAny": [0.99, 0.90, 0.79], "curveAll": [0.46, 0.30, 0.18],
    "alternatives": [
      {"picks": {"A": ["LAC"], "B": ["JAX"], "C": ["DET"]}, "value": 5.52, "score": 1.71, "recommended": true},
      {"picks": {"A": ["LAC"], "B": ["JAX"], "C": ["CIN"]}, "value": 5.44, "score": 1.69, "recommended": false}
    ]
  },
  "news": [
    {"id": "...", "headline": "...", "description": "...", "published": "2026-09-05T20:11:00Z", "url": "https://...", "teams": ["KC"], "leagueWide": false, "athleteIds": ["3139477"], "kind": "injury", "type": "HeadlineNews", "byline": "Adam Schefter"}
  ]
}
```

### Semantics

* `weeks[].status`: `upcoming` (no game started), `live` (a game is in
  progress or some finals), `final` (all games final).
* `games[].status`: `scheduled`, `in_progress`, `final`, `postponed`.
  `statusDetail` is display text from ESPN (clock and quarter when live).
* `games[].pHome`: decayed probability used by the optimizer.
  `pHomeRaw`: the market or rating probability before decay (kept even for
  final games). For final games or overrides, `pHome` is 1 or 0; a tie is 0
  for both sides.
* `games[].timeValid`: false when the kickoff time is a placeholder (late
  season flex games); show the date only.
* `games[].source`: `moneyline`, `spread`, `rating`, `final`, `live`, `override`.
  `live` is a game in progress: it keeps its pre-game probability but can
  no longer be picked.
* `joint.weeks`: the week numbers that `curveAny`, `curveAll` and each
  entry's `survivalCurve` index into (current week through horizon).
* `joint.alternatives[].value`: the objective's value for that combination
  (expected live weeks for `any`, a probability for `final`, expected
  survivors for `expected`).
* `teams[].injuryImpact`: point-spread adjustment applied to rating-based
  probabilities this week (0 or negative). `teams[].rating` is the
  market-implied power rating in points; `hfa` in meta is home-field
  advantage in points.
* `meta.sources` counts probability sources for games from the current
  week onward.
* `entries[].plan`: one element per week from `currentWeek` to `horizon`
  for alive entries. Weeks before `currentWeek` are not included; the
  entry's history is in `used`. `p` is the product of that week's pick
  probabilities (decayed).
* `entries[].branches[week]`: candidate picks for that week given the
  plan's picks in every earlier week. Sorted best first. `recommended`
  marks the branch that equals the plan. `path` starts at `week` and runs
  to the horizon. Only present for alive entries. Weeks with a lock have a
  single branch.
* `entries[].survivalCurve[i]`: P(entry alive after plan week i).
* `joint.curveAny[i]`, `joint.curveAll[i]`: after plan week i.
* `joint.alternatives`: other current-week pick combinations, best first,
  including the recommended one.
* `news[].kind`: `injury`, `transaction`, `news`.

Frontend requirements that follow from this contract:

* The UI calls `POST /api/dashboard` on load with the saved config
  (`GET /api/config`), and again after any control changes. Debounce
  rapid changes (300 ms).
* Every control that changes a Config field persists it via
  `PUT /api/config` after the dashboard call succeeds.
* When the server is unreachable, show a clear banner and keep the last
  good Dashboard on screen.
* `?mock=1` in the URL loads a bundled fixture (`static/mock-dashboard.json`)
  instead of calling the API, so the UI can be developed and screenshotted
  without the backend.
