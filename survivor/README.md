# NFL Survivor Pool Optimizer

Recommends this week's pick for each survivor entry you control, using
sportsbook lines for win probabilities and an exact multi-entry survival
calculation so your entries hedge each other instead of stacking the same
favorite. Ships as a command-line tool and a local web dashboard.

## Quick start

Every command below is run from the top of this repository, not from your home
directory. If you have not cloned it yet:

```bash
git clone -b claude/fantasy-football-repos-0ulhzj \
  https://github.com/steffenmax/arb-bot.git ~/arb-bot
cd ~/arb-bot
```

If you cloned it earlier, `cd` into it and make sure you are on that branch:

```bash
cd ~/arb-bot
git checkout claude/fantasy-football-repos-0ulhzj
git pull
```

Then:

```bash
./survivor/start.sh
```

That is the whole thing. The script installs the three Python packages it
needs into `survivor/.venv` the first time, picks the first free port from
8765, starts the server and opens your browser. Press Ctrl+C to stop it.

```bash
./survivor/start.sh --port 9000     # a specific port
./survivor/start.sh --no-open       # do not open a browser
```

If you would rather manage the environment yourself:

```bash
pip install -r survivor/requirements.txt
python3 -m survivor.dashboard --open

# Command line, no browser
python3 -m survivor --end-week 10
python3 -m survivor --end-week 10 --used A=LAC --used B=JAX --used C=DET   # week 2
```

No API keys are needed. Everything comes from public feeds and is cached
under `survivor/cache/`. Your entries, locks and settings are saved in
`survivor/cache/config.json`, so the dashboard picks up where you left off.

## Dashboard

`python3 -m survivor.dashboard` serves a single-page app with six views:

* **This Week**: the recommended pick per entry with win probability,
  opponent, crowd percentage, the joint numbers (P at least one entry
  survives, P all survive, expected survivors, expected weeks with a live
  entry), the survival curve, and the next-best pick combinations.
* **Season Plan**: weeks by entries grid with the planned team and win
  probability for every remaining week, lock state, and a two-pick toggle
  on each week row. Click any cell to open its branches.
* **Branches**: for one entry and week, every alternative pick with its
  fully re-optimized downstream path and survival odds. Lock a branch to
  pin it; everything after it re-optimizes.
* **Schedule**: every game of the season with kickoff, lines, win
  probability and its source, live score and status, pick markers, and a
  what-if override. A what-if assumes a result: the game counts as
  decided, so nobody can pick it any more except an entry that has locked
  it, and the whole plan re-optimizes around that result.
* **Teams**: rating, injury impact, the injury report with per-player
  impact, efficiency stats, and the remaining schedule as a probability
  strip.
* **News**: ESPN headlines tagged by team and kind (injury, transaction,
  news).

Global controls: horizon week, decay, objective, contrarian weight, an
entries editor (name, alive, used teams), crowd pick percentages for the
current week, and a refresh button. Config is saved server-side in
`survivor/cache/config.json`, so the dashboard remembers your entries.

The API contract between the backend and the page is in
`survivor/dashboard/API.md`. The design system is in
`survivor/dashboard/DESIGN.md`.

## Sharing a snapshot

To send someone the plan without asking them to run anything:

```bash
python3 -m survivor.snapshot                     # -> survivor-snapshot.html
python3 -m survivor.snapshot -o plan.html --refresh
```

That writes one self-contained HTML file with the stylesheet, both scripts and
the current payload inlined. It opens straight from disk, and every view and
every game is there to read. Anything that writes — locking a pick, moving the
horizon, refreshing a feed — needs the real app, and the page says so in a
banner across the top.

## Data sources

| Feed | Used for | Refresh |
|---|---|---|
| nflverse `games.csv` | Schedule, results, closing lines, quarterbacks | 6 h |
| ESPN scoreboard | Live status and scores, current DraftKings lines for all 272 games, broadcast, weather | 5 min |
| ESPN injuries | Injury report per team (status, body part, return date) | 30 min |
| ESPN news | Headlines with team tags | 15 min |
| ESPN teams and standings | Names, colors, logos, records, points | 1 h to 24 h |
| nflverse team stats | EPA per play, turnover margin, sacks (previous season until week 1 is published) | 6 h |
| nflverse depth charts | Starting quarterback per team (first 1.5 MB of the daily snapshot) | 24 h |

Feeds fall back to the cached copy when a download fails, and the
dashboard shows a warning with the age of the data.

## How it works

1. **Win probabilities.** For each game, in order of preference: a final
   score or a what-if override (probability 1 or 0), a devigged moneyline,
   a point spread through a normal margin model (13.5-point standard
   deviation), or a power rating fitted by least squares to every posted
   spread, shrunk toward last season's closing lines. Games in progress
   keep their pre-game probability but cannot be picked.
2. **Injuries.** The rating fallback is adjusted by an injury impact
   model: each player listed Out, Doubtful, Questionable, on IR or
   suspended costs a position-based number of points (a starting
   quarterback dominates at 4.5 points; a backup quarterback is worth
   0.4), scaled by how certain the absence is and capped at 9 points per
   team. Short-term absences fade with a two-week half-life; IR and
   suspensions persist. Posted lines already price injuries in, so the
   adjustment only touches games without a line.
3. **Future decay.** Probabilities for later weeks are pulled toward 50%
   by `exp(-decay * weeks_ahead)`. Default decay 0.03 means a 75%
   favorite ten weeks out counts as about 68%. This stops the optimizer
   burning a great team now to protect a merely good matchup in December.
4. **Single-entry paths.** Choosing teams week by week with no repeats to
   maximize survival through the horizon is an assignment problem on
   `-log(p)`, solved exactly with the Hungarian algorithm. Weeks that
   require two picks contribute two rows and both picks must win. Locked
   weeks pin their teams.
5. **Joint selection.** All entries face the same game results, so the
   tool chooses one candidate path per entry to maximize the joint
   objective, computed exactly by inclusion-exclusion over the entries.
   Two entries on opposing teams cannot both survive; two entries on the
   same team live or die together. Later weeks are hedged with a soft
   penalty for sharing a team with another entry, and the selection is
   repeated until the current-week picks settle.
6. **Branches.** For every week of every entry's plan, each alternative
   pick is expanded into its own fully re-optimized downstream path, so
   you can see what each choice commits you to before locking it.

Only the current-week pick is a decision. Later weeks are a forecast,
recomputed from fresh lines every run.

### Objectives

* `any` (default): expected number of weeks, through the horizon, with at
  least one entry alive. Pools can end any week, so this values both
  near-term hedging and long-term survival.
* `final`: P(at least one entry alive at the horizon). With a long
  horizon this barely values week-one diversification, because both
  entries reaching the horizon is unlikely anyway.
* `expected`: expected number of entries alive at the horizon. No
  diversification pressure; every entry takes its own best path.

### Horizon

`--end-week` (CLI) or the horizon control (dashboard) is the week you are
optimizing to survive through. Pick the week by which you expect the pool
to be down to a handful of entries. For 50 to 100 entries that is often
around week 8 to 10; for a few hundred, week 12 or so. A shorter horizon
spends strong teams sooner.

### Crowd pick percentages

Survivor equity comes from outlasting the pool, so a pick the crowd is
piled on is worth less than its win probability suggests. Enter the
pool's pick distribution for the current week (dashboard) or pass a CSV
with `team,pct` columns (`--pick-pct`). For each team the tool computes
the expected share of the pool that survives if that team wins and adds
`contrarian_weight * log(1 / share)` to the current-week utility. Weight
0 reports the crowd column without letting it move the picks.

## Command line reference

```
python3 -m survivor [--season Y] [--week N] [--end-week N] [--entries N]
                    [--used A=KC,BUF ...] [--lock A=3:DET ...]
                    [--two-pick-weeks 12,18] [--decay 0.03] [--top 8]
                    [--hedge 0.1] [--pick-pct file.csv] [--contrarian-weight 1]
                    [--objective any|final|expected] [--refresh] [--show-paths]
```

## Recording what you played

The optimizer can only avoid a team it knows you burned, so each week's pick
has to be recorded. There are two ways, and both end up in the same place.

**Lock it.** Press Lock on the pick you actually submitted. When that week
ends the lock becomes a permanent entry in your history, the result is read
from the schedule, and a loss marks the entry eliminated. Nothing to do on
Monday.

**Sync it from your pool.** Open Entries, scroll to Import picks, put in the
web address of your pool's entries page and press Sync from my pool. This
reads your entries, and the whole pool's pick percentages, out of the page
using a browser on this machine. See Connecting your pool below.

**Paste it.** Open Entries, scroll to Import picks, and paste from your
pool's entries page. No pool site offers an export, so this reads ordinary
copied text: it looks for a week number and a team on each line and handles
full names, cities, nicknames and capitalised codes.

```
Entry 1
Week 1   Philadelphia Eagles   WIN
Week 2   Buffalo Bills         LOSS
```

Compact lines work too (`A: W1 PHI, W2 BUF`), as does a week header with the
team underneath. Nothing is written until you review the preview, where each
block it found gets a dropdown to choose which of your entries it belongs to.
Picks read as history show in the burned-team grid with their week, outlined
so you can tell them from teams you marked by hand.

A pool site behind a login cannot be read directly, so copy and paste is the
route. Nothing about your account is needed or stored.

## Connecting your pool

Pool sites sit behind a login and publish no export, so the sync drives a
browser on your own machine that you have signed into. Your password is never
typed into this tool, never sent anywhere, and never stored. The session lives
in a Chrome profile under `survivor/cache/browser/`, which is yours to delete
whenever you like.

```bash
survivor/.venv/bin/python -m pip install playwright
survivor/.venv/bin/python -m playwright install chromium

# once: a window opens, you sign in, then press Enter in the terminal
python3 -m survivor.splash --login --url "https://your-pool.example.com/contests/…/entries"

# after that, any time:
python3 -m survivor.splash --me "your name"
```

`--me` is the text that appears in your own entries' names, which is how your
entries are told apart from everyone else's. Once it is set it is remembered.

Rather than scrape the page's HTML, which changes whenever a site is
redesigned, this records the JSON the site's own front end fetches and reads
the picks out of that. Every capture is saved under `survivor/cache/splash/`
so you can see exactly what came back. Nothing is written into your plan until
you review the preview in the dashboard and map each entry.

### Teaching it your pool's pages

The site is behind a login and documents nothing, so rather than guess at its
API there is a recorder that watches your own browser use it:

```bash
python3 -m survivor.discover
```

A window opens in the profile you signed into. It walks you through three
phases — your entries page, making a pick, then the league statistics page —
and records every JSON call each one makes. It writes a short readable report
of the endpoints and response shapes, plus the full capture, to
`survivor/cache/splash/`. The report is what an exact parser gets written
from.

Request headers are never recorded, and every key named like a token, every
JWT, every long opaque string and every email address is redacted from both
files before they are written.

Once the statistics page is known, point the sync at it and the pick
percentages come from the whole pool instead of from however many entries the
listing happened to render:

```bash
python3 -m survivor.splash --stats-url "https://.../statistics"
```

### Keeping it up to date

The sync also captures what percentage of the pool is on each team, which is
the input the contrarian setting wants, so it is worth re-running after the
week's games.

```bash
python3 -m survivor.splash --watch 30        # re-read every 30 minutes
```

For something that survives a reboot, on macOS use `launchd`:

```xml
<!-- ~/Library/LaunchAgents/com.survivor.sync.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0"><dict>
  <key>Label</key><string>com.survivor.sync</string>
  <key>ProgramArguments</key>
  <array>
    <string>/path/to/arb-bot/survivor/.venv/bin/python</string>
    <string>-m</string><string>survivor.splash</string>
  </array>
  <key>WorkingDirectory</key><string>/path/to/arb-bot</string>
  <key>StartInterval</key><integer>1800</integer>
</dict></plist>
```

Then `launchctl load ~/Library/LaunchAgents/com.survivor.sync.plist`. On Linux
a cron line does the same: `*/30 * * * * cd /path/to/arb-bot && survivor/.venv/bin/python -m survivor.splash`.

If the site signs you out, the sync says so and you run `--login` again.

One thing to weigh up: reading a site you are signed into may sit awkwardly
with its terms of service, even though this only reads your own contest at a
gentle rate. That is your call to make.

## If something goes wrong

The launcher checks the server and builds the plan once before opening your
browser, so most problems are printed in the terminal rather than left for
the page to discover.

**"certificate verify failed" / "Backend unreachable".** Python installed
from python.org on macOS does not read the system keychain, so every
download fails until its certificate store is populated. The downloader
handles this by falling back to `certifi`, which `start.sh` installs. If you
run the modules directly and still see it, either `pip install certifi` or
run the installer that ships with Python:

```bash
open "/Applications/Python 3.12/Install Certificates.command"   # your version
```

**Behind a corporate proxy.** Point `SSL_CERT_FILE` at your organization's
CA bundle before starting; it takes precedence over everything else.

**The page keeps saying the backend is unreachable.** Check the terminal
running `start.sh` is still alive, and that the port in your browser's
address bar matches the one it printed. A second launch picks a different
port, so an old tab will point at a dead one.

**Stale or missing data.** Delete `survivor/cache/` and start again. Your
entries and settings live in `survivor/cache/config.json`, so copy that
first if you want to keep them.

## Limits

* Lines are treated as truth; the tool does not shop books or blend
  sources. The rating fallback is a rough guide for games without a line.
* The injury model is a heuristic on ESPN's report. It does not know who
  replaces an injured starter.
* Pool dynamics (how many rivals are alive, what teams they have left)
  are only modeled through the optional pick-percentage adjustment.
* Ties count as losses for both sides.
* A locked pick whose game is final stays with the entry; if it lost, the
  entry is reported eliminated.

## Tests

```bash
python3 -m unittest discover -s survivor/tests -t .      # engine, feeds, config

# Browser test against a running dashboard (needs: pip install playwright,
# and a Chromium binary; edit CH in the script if yours lives elsewhere)
python3 -m survivor.dashboard --port 8765 &
python3 survivor/tests/e2e_dashboard.py
```

The browser test drives the real page through locks, undo, two-pick
toggles, the branch drawer, what-if overrides, the entries and crowd
editors, routing and phone layouts. It resets the saved config to three
empty entries when it finishes.
