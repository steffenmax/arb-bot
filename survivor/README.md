# NFL Survivor Pool Optimizer

Recommends this week's pick for each survivor entry you control, using
sportsbook lines for win probabilities and an exact multi-entry survival
calculation so your entries hedge each other instead of stacking the same
favorite.

## Quick start

```bash
pip install -r survivor/requirements.txt
python3 -m survivor                       # 3 entries, nothing used yet
```

Each week, tell it which teams every entry has already burned:

```bash
python3 -m survivor --used A=LAC --used B=JAX --used C=CIN
python3 -m survivor --used A=LAC,SF --used B=JAX,LAC --used C=CIN,LAC   # week 3
```

Entries are named A, B, C, ... in order. `--entries N` changes the count.
If an entry is eliminated, drop it with `--entries` and re-letter the rest.

## What it does

1. **Data.** Downloads the nflverse games file (schedule, results, closing
   and current betting lines from 1999 to now) and caches it for 6 hours in
   `survivor/cache/`. Pass `--refresh` to force a new download.
2. **Win probabilities.** For each remaining game, in order of preference:
   a devigged moneyline, a point spread through a normal margin model
   (13.5-point standard deviation), or a power rating fitted by least squares
   to every spread posted this season, shrunk toward last season's
   closing-line ratings. Books post lines about six weeks out, so later weeks
   run on ratings.
3. **Future decay.** Probabilities for later weeks are pulled toward 50% by
   `exp(-decay * weeks_ahead)`. Default `--decay 0.03` means a 75% favorite
   ten weeks out counts as about 68%. This is what stops the optimizer from
   burning a great team now to protect a merely good matchup in December.
4. **Single-entry paths.** Choosing one team per week with no repeats to
   maximize survival through the horizon is an assignment problem on
   `-log(p)`, solved exactly with the Hungarian algorithm. For each entry we
   compute the best full path for every possible current-week pick; those
   are the entry's candidates (top `--top`, default 8).
5. **Joint selection.** All entries face the same game results, so we choose
   one candidate per entry to maximize the exact probability that at least
   one entry survives the horizon, computed by inclusion-exclusion over the
   entries. Two entries on opposing teams cannot both survive; two entries on
   the same team live or die together. `--objective expected` instead
   maximizes the expected number of survivors, which just stacks the best
   single path on every entry.

Only the current-week pick is a decision. The projected later weeks are
shown so you can see what the plan is protecting, and they are recomputed
from fresh lines every run.

## Horizon

`--end-week` (default 18) is the week you are optimizing to survive
through. Most pools end well before week 18. A useful rule: pick the week by
which you expect the pool to be down to a handful of entries. For a pool of
50 to 100 entries that is often around week 8 to 10; for a few hundred, week
12 or so. A shorter horizon makes the optimizer spend strong teams sooner.

## Crowd pick percentages (optional)

Survivor equity comes from outlasting the pool, so a pick the crowd is piled
on is worth less than its win probability suggests. Save the pool's (or a
public site's) pick distribution as a CSV and pass it in:

```
team,pct
LAC,31
JAX,22
DET,18
```

```bash
python3 -m survivor --pick-pct survivor/examples/pick_pct_example.csv
```

For each team the tool computes the expected share of the pool that survives
if that team wins, and adds `contrarian_weight * log(1 / share)` to the
current-week utility. `--contrarian-weight 0` reports the crowd column
without letting it move the picks; the default weight of 1 maximizes your
expected share of the remaining pool this week.

## Output

* Recommended pick per entry with win probability and the chance that entry
  survives to the horizon.
* Joint numbers: P(at least one survives), P(all survive), expected
  survivors, and the week-by-week curve for "at least one alive".
* Projected paths, the next-best pick combinations, the full board for the
  current week with probability sources, and `--show-paths` for every
  candidate path.

## Limits

* Ratings for later weeks are a rough guide. They know nothing about
  injuries that happen after the lines were posted.
* Probabilities from one book's line are treated as truth; the tool does
  not shop lines or blend sources. If you have Kalshi or Polymarket prices
  for a game, they are usually sharper than a stale moneyline.
* Pool-size dynamics (how many rivals are alive, what teams they have left)
  are not modeled beyond the optional pick-percentage adjustment.
* Ties count as losses in most pools; the model treats a tie as a loss.

## Tests

```bash
python3 -m unittest discover -s survivor/tests -t .
```
