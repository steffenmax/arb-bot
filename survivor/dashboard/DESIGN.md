# Survivor — Design System Spec
Direction: EDITORIAL ("The Ruled Figure"). Default theme: light, paper & ink. Optional dark theme. Single-page app, six views. Primary: laptop 1280–1680px. Secondary: phone 360–430px. Vanilla HTML/CSS/JS, no build step.

---

## 1. Concept

Survivor is set like the sports section of a serious broadsheet crossed with a bond-desk ledger: a warm paper ground, one ink doing most of the work, a serif display face for the numbers that decide the week, and hairline rules instead of boxes. Density comes from typography, alignment and tabular figures, not from containers. Color is rationed to three jobs — which entry, how likely, what state — so when color appears it is a fact, never decoration.

**The one distinctive idea — the Ruled Figure.** Every probability in the product is typeset as a serif numeral (never a chip, pill or badge) with a hairline "rule" beneath it whose length equals the probability as a fraction of the cell width and whose ink comes from the five-step tone scale. `71.4` with a rule 71.4% wide, in sage. The same glyph appears in the hero, the Season Plan cell, the branch row, the schedule row, the joint stats and the team heatmap strip, so the user learns to read probability at a glance from any distance and the product reads as one printed instrument.

**Its structural companion — the Rail.** A persistent 18-week × 3-entry ribbon under the masthead on every view. Each tile is the planned pick's win probability for that entry in that week, filled with the same tone scale the Ruled Figure uses; locked tiles are solid ink, two-pick tiles split, eliminated lanes hatch. The Rail is status (the whole season's risk in 56px of height) and navigation (click a week to scope every view; click a tile to open the branch picker). Figure and Rail share one tone function, so the small and the large always agree.

---

## 2. Typography

### Families (Google Fonts, one link)
```
https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;0,9..144,600;1,9..144,400;1,9..144,500&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap
```

| Role | Family | Weights | Notes |
|---|---|---|---|
| Display: hero numerals, Ruled Figures, team names in heroes/cells, view titles, folios | **Fraunces** (variable) | 400, 500, 600; italic 400, 500 | `font-variation-settings: "opsz" <size>, "SOFT" 30, "WONK" 0`; `"opsz" 144` for ≥44px, `48` for 20–28px, `14` for ≤17px figures. Always `font-feature-settings: "tnum" 1, "lnum" 1`. |
| Body, labels, controls, nav, table text | **IBM Plex Sans** | 400, 500, 600 | `"tnum" 1` on any element containing numbers. |
| Data: odds, spreads, moneylines, kickoff times, timestamps, team codes in tables, IDs | **IBM Plex Mono** | 400, 500 | Monospace guarantees column alignment in ledgers. |

Fallbacks: `--font-display: "Fraunces","Iowan Old Style",Georgia,serif; --font-body: "IBM Plex Sans","Helvetica Neue",Arial,sans-serif; --font-data: "IBM Plex Mono","SFMono-Regular",Menlo,Consolas,monospace;`
Global: `html { font-feature-settings: "tnum" 1,"lnum" 1,"kern" 1; -webkit-font-smoothing: antialiased; }` and `font-variant-numeric: tabular-nums lining-nums` wherever numbers appear (do not rely on the Mono face alone).

### Scale (px size / line-height)

| Token | Family · weight | Size/LH | Tracking | Use |
|---|---|---|---|---|
| `--t-display-xl` | Fraunces 600 | 72/72 | −0.02em | Hero win % (one per hero) |
| `--t-display-l` | Fraunces 500 | 44/48 | −0.015em | Week folio ("Week 3"), team page name |
| `--t-display-m` | Fraunces 500 | 28/32 | −0.01em | Hero team name, view titles, joint-stat numerals |
| `--t-display-s` | Fraunces 500 | 20/26 | 0 | Section headings, branch candidate team, grid-cell team |
| `--t-figure` | Fraunces 500 | 17/20 | 0 | Ruled Figure in tables/cells |
| `--t-figure-s` | Fraunces 500 | 14/18 | 0 | Compact Ruled Figure (schedule, heatmap, two-pick sub-rows) |
| `--t-body-l` | Plex Sans 400 | 16/24 | 0 | News body, explanatory copy |
| `--t-body` | Plex Sans 400 | 14/20 | 0 | Default UI and table text |
| `--t-body-strong` | Plex Sans 600 | 14/20 | 0 | Row primary text, tabs |
| `--t-small` | Plex Sans 500 | 12/16 | 0 | Secondary cell text, meta |
| `--t-label` | Plex Sans 600 | 11/14 | 0.08em, uppercase | Column headers, kickers, entry labels, tags |
| `--t-data` | Plex Mono 400 | 13/18 | 0 | Odds, spreads, times, table numerals |
| `--t-data-s` | Plex Mono 400 | 11/14 | 0 | Timestamps, sources, axis ticks, Rail week numbers |
| `--t-kbd` | Plex Mono 400 | 10/14 | 0 | Keyboard hints |

Rules: percentages show one decimal (`71.4`) and never the `%` sign inside tables (the column header says `WIN %`); `%` appears only in prose and in the hero, where it is set at 40% size, superscript, weight 400. Never more than one decimal. Negative values use a true minus (U+2212): spreads `−3.5`, `PK`; moneylines `−165 / +140`. A negative sign is never colored on its own; tone comes only from the probability scale. Team codes are 2–3 uppercase letters in Mono (`<abbr title="Kansas City Chiefs">`); full names appear in heroes, grid cells, the team header and tooltips.

---

## 3. Color system

Default theme is light. All colors are CSS custom properties; components consume only tokens and never define a hex. Contrast: ink/ink-2/ink-3 on paper ≥ 4.5:1 at all sizes; ink-4 is decorative/disabled only (≥ 3:1).

```css
:root {
  /* Surfaces */
  --paper:         #F5F1E8;  /* page ground */
  --paper-2:       #EEE8DB;  /* table header rows, hero backdrop, drawers, popovers */
  --paper-3:       #E5DECD;  /* hover/pressed rows, active toggle track */
  --paper-inverse: #16150F;  /* locked cells, primary buttons */

  /* Ink */
  --ink:           #16150F;  /* primary text, strong rules */
  --ink-2:         #3E3B32;  /* secondary text */
  --ink-3:         #6F6B5F;  /* tertiary, column headers, final scores */
  --ink-4:         #A6A193;  /* placeholders, disabled, upcoming, beyond horizon */
  --ink-inverse:   #F5F1E8;  /* text on inverse surfaces */

  /* Rules */
  --rule:          #D9D2C2;  /* hairline, 1px */
  --rule-strong:   #16150F;  /* 1px ink rule under headers, drawer edge */
  --rule-heavy:    #16150F;  /* 2px, once per view: under the masthead (also the progress line) */

  /* Entries — identity only: labels, column heads, chart lines, left borders, pick squares */
  --entry-a:       #7E2A2A;  --entry-a-tint: #EFDFDB;   /* oxblood  */
  --entry-b:       #23486B;  --entry-b-tint: #DDE4EB;   /* prussian */
  --entry-c:       #7A5A12;  --entry-c-tint: #EDE4CC;   /* bronze   */

  /* Probability tone, bad -> good: numerals + the rule under the figure */
  --p1: #A63A1E;  /* vermilion */
  --p2: #B7791C;  /* amber     */
  --p3: #6F6B5F;  /* neutral = ink-3, "unremarkable" */
  --p4: #4B7A44;  /* sage      */
  --p5: #1E5A37;  /* bottle    */
  /* fills for Rail tiles, heatmap strips, path tiles, chart bands */
  --p1-fill: #E9C6BA; --p2-fill: #EAD6AE; --p3-fill: #DCD6C8; --p4-fill: #CBD9C3; --p5-fill: #B6CFBD;

  /* Status */
  --live:          #D1261F;  --live-tint: #F6DCD9;    /* brighter than p1; always with a pulsing dot + word */
  --final:         #6F6B5F;  /* = ink-3 */
  --upcoming:      #A6A193;  /* = ink-4 */
  --locked:        #16150F;  --locked-tint: #E5DECD;  /* inverse cell, filled-square lock mark */
  --override:      #5B3B78;  --override-tint: #E6DCEC; /* plum: the only cool purple; "you changed reality" */
  --eliminated:    #A6A193;  /* + strikethrough + hatch */
  --hatch: repeating-linear-gradient(135deg, transparent 0 3px, rgba(22,21,15,0.10) 3px 4px);
  --stale:         #B7791C;  /* = p2 */
  --error:         #A63A1E;  /* = p1 */
  --focus:         #23486B;  /* 2px outline, offset 2px, :focus-visible only */

  /* Charts */
  --chart-grid: #D9D2C2; --chart-axis: #6F6B5F;
  --chart-joint-any: #16150F;  /* P(≥1 survives): heavy ink line */
  --chart-joint-all: #6F6B5F;  /* P(all survive): dashed ink-3 line */
  --chart-band: #E5DECD;       /* shading past the horizon */
}
```

**Tone thresholds** are fixed, not quantiles, so a number always maps to the same ink. Win probability: `<50 → p1`, `50–59.9 → p2`, `60–67.9 → p3`, `68–77.9 → p4`, `≥78 → p5`. Survival-to-horizon (a product of many weeks, usually 5–30) uses its own thresholds on the same tokens: `<5 → p1`, `5–9.9 → p2`, `10–14.9 → p3`, `15–24.9 → p4`, `≥25 → p5`. One function `probTone(value, kind: "win" | "survival")` is used by every component; every column header names the scale it uses (`WIN %` vs `SURVIVE → W18`).

**Where entry colors may appear:** entry label text, Season Plan column headers, the 2px left border of a hero/row/card, chart lines, the Rail lane labels, 12px pick squares. Never on probability numerals, never as a fill behind text.
**Where plum may appear:** what-if override controls, override marks, `OVR`/`manual` tags, override ticks in the chart and Rail. Nowhere else.
**Where solid ink fills appear:** locked cells and tiles, primary buttons, the masthead rule. Locked is the only state rendered as inverse, so a black cell always means "you decided this."

**Optional dark theme** (`[data-theme="dark"]`, not default): `--paper #15140F`, `--paper-2 #1C1B15`, `--paper-3 #26241C`, `--paper-inverse #EDE7DA`, `--ink #EDE7DA`, `--ink-2 #C9C3B4`, `--ink-3 #8F8A7C`, `--ink-4 #5E5A4F`, `--ink-inverse #15140F`, `--rule #2E2C24`; tones lightened one step (`--p1 #D9694A`, `--p2 #D89A3A`, `--p3 #8F8A7C`, `--p4 #7BA574`, `--p5 #5E9C77`), fills replaced with 18% alpha of the same; entries `#C25C5C`, `#6C93BD`, `#C39B3E`; override `#A98BC4`.

**Phone degradation (≤640px):**
- Tone collapses from 5 to 3 for text ≤14px: p1+p2 → `--p1`, p3 → `--p3`, p4+p5 → `--p5`. The rule under the figure remains at every size, so the bar still carries the value. Five steps are kept for figures ≥17px and for fills.
- Entry identity moves from column headers to a 3px left border on each stacked row/card.
- State is always carried by a glyph or word (`● LIVE`, `FINAL`, `■ LOCKED`, `OVR`, strikethrough), never by color alone. Hatch is replaced by a solid `--ink-4` 2px top border plus the word.
- Tints and fills unchanged.

---

## 4. Layout

**Grid:** 12 columns, 24px gutter, content container `max-width: 1440px`, centered. Page margins 48px (≥1280), 32px (1024–1279), 24px (641–1023), 16px (≤640). Tables may bleed to the container edge, never past the page margin. Schedule and Teams may widen to 1680px.
**Reading widths:** ledgers (Season Plan, Schedule, Branches) use the full container. This Week: hero row at 1200 inner width, then an 8/4 split for chart and alternatives. Teams and News: 1040 max, 2/3 : 1/3. Prose `max-width: 68ch`.
**Spacing scale** (`--s-*`, px): 2, 4, 8, 12, 16, 24, 32, 48, 64, 96. Vertical rhythm 8px; table rows are multiples of 8 (32 compact, 40, 48, 56, 64). A `data-density="compact"` attribute on `<html>` (masthead toggle `DENSE`, key `d`) reduces every row height by 8px and cell padding by 2px.

**Vertical structure of every view:**
1. Masthead — 56px, sticky, `--paper`, 2px `--rule-heavy` at bottom (this rule doubles as the progress line).
2. The Rail — 56px, sticky under the masthead, hairline `--rule` at bottom.
3. Stale-data banner — 36px, conditional, not sticky.
4. View header — folio + title + view-local controls, 96px, hairline below.
5. View body.
6. Footer — 48px, `--t-data-s` `--ink-3`: book, model version, last computed timestamp, entries/teams-used count.
Sticky chrome totals 112px; a 768px-tall laptop still shows ≥ 650px of ledger.

**Navigation:** text tabs in the masthead — `This Week · Season Plan · Branches · Schedule · Teams · News` in `--t-body-strong`, gap 24px; no sidebar, no hamburger, no icons. Active: `--ink` with a 2px underline that notches into the masthead's heavy rule. Inactive: `--ink-3`, hover `--ink`. Tabs are `<a href="#/…">`; the URL is the single source of truth for view, focus week, selected entry, open drawer and team: `#/week/7`, `#/plan`, `#/branches/B/7`, `#/schedule/7`, `#/teams/KC`, `#/news?team=KC`.
**Keyboard:** `1`–`6` views · `[` `]` focus week · arrows move the roving cursor in the Rail and Season Plan · `Enter` opens the branch picker · `l` lock/unlock focused cell or branch row · `t` toggle two-pick on the focused row · `g` then a team code jumps to that team · `/` focuses search · `r` refresh · `d` density · `Esc` closes drawers/menus · `?` shows the shortcut sheet. Hints appear as `<kbd>` in tooltips.
**Phone (≤640):** masthead 48px with wordmark, freshness dots and `REFRESH`; tabs become a second 36px row of horizontally scrolling text tabs (scroll-snap, 24px right fade, active tab scrolled into view). Global controls move into a `SETTINGS` bottom sheet. The Rail stays, 40px tall, horizontally scrollable, current week snapped left.

---

## 5. Components

Unless stated: borders are 1px `--rule`; no drop shadows anywhere; corners are 0 (square) — the only rounded shape is the 6px live dot. Drawers use a 1px `--rule-strong` left edge instead of a shadow. Row hover `--paper-3` (80ms); `:focus-visible` 2px `--focus` outline offset 2px; disabled `--ink-4`, `cursor: not-allowed`. Hit targets ≥ 28×28 laptop, ≥ 40×40 phone. No icons anywhere: every affordance is text, a square, a dot, a rule or a figure. The lock mark is a filled 8px square `■` in `--ink` (the product's square language, matching the toggle knob); the refresh mark is the text glyph `↻`.

### 5.1 Masthead
- Left: wordmark `SURVIVOR` in Fraunces 600 18px, tracking 0.12em, uppercase; a 1px × 20px `--rule` divider; the season `2026` in `--t-data-s` `--ink-3`; then the view tabs.
- Right cluster, `--t-small`, gap 16px; each global control is a select typeset as `LABEL value ▾`: `HORIZON W18 ▾` (current..18) · `DECAY 0.97 ▾` (0.90/0.93/0.95/0.97/1.00) · `OBJECTIVE P(≥1) ▾` (P(≥1 alive) / P(all alive) / E[alive]) · `CONTRARIAN 0.30 ▾` (0/0.15/0.30/0.50/0.75) · `ENTRIES` text button · `DENSE` text toggle · **freshness cluster**: three 6px squares with `--t-data-s` labels `LINES 12m · INJ 41m · SCORES live`, square color `--p4` fresh, `--stale` aging, `--error` failed (thresholds: lines 60m, injuries 6h, scores 90s in live windows, model 60m); hover shows the absolute timestamp and source · `REFRESH ↻` text button (`r`); while refreshing the glyph rotates and the label reads `REFRESHING`.
- Open menus: `--paper-2` panel, 1px `--rule-strong`, 32px rows, selected row has a leading `•`. Hover on any control underlines its value 1px `--ink`.
- Changing a global control re-optimizes immediately; the heavy rule becomes the progress line (§5.18). If a recompute exceeds 400ms a `RECOMPUTING PLAN` label in `--t-data-s` appears under the freshness cluster.
- **Entries editor drawer** (from `ENTRIES`): right drawer 440px, `--paper-2`, 1px `--rule-strong` left edge, header `Entries` in `--t-display-s`. One block per entry, hairline-separated, 2px entry-colored left border: name text input (`--t-display-s`), `ALIVE` toggle (§5.8), and when off an `ELIMINATED W__` stepper; `Used teams` — 32 team codes in an 8×4 grid of 40×28 Mono cells: used = inverse (`--paper-inverse`/`--ink-inverse`) with the week in `--t-data-s` beneath when known, unused = plain `--ink-2`; click toggles; hovering a used cell exposes a small week stepper; count `7 used` right-aligned. Footer sticky: `Save` primary, `Cancel` text. Saving re-optimizes and the Rail animates its diff.

### 5.2 The Rail
- 56px tall (phone 40), `--paper`, hairline bottom. Left label column 56px: `WK` on row 0 in `--t-label` `--ink-3`; `A` `B` `C` on rows 1–3 in `--t-label` in their entry colors (phone: 24px column).
- 18 equal week columns fill the remaining width (min 28px each; narrower → the Rail scrolls horizontally, snapped to the current week). A 19th slot after the horizon week carries a thin `]` bracket in `--ink-3`.
- Row 0 (14px): week number in `--t-data-s` `--ink-3`; current week in `--ink` Fraunces 500 15px with a 2px `--ink` underline; two-pick weeks carry a superscript `²`; weeks beyond the horizon at 60% opacity. A what-if override in that week adds a 3px plum square under the number.
- Rows 1–3: tiles 10px tall, 2px gap, 1px `--paper` gap between columns, 0 radius.
  - **planned**: `--pN-fill` by `probTone(win)`.
  - **locked**: `--paper-inverse` solid.
  - **two-pick**: tile split into two 4px halves with a 1px `--paper` gap, each filled by its own tone.
  - **past, won**: hollow — 1px `--rule` border with a centered 3px `--ink` square.
  - **past, lost / eliminated from here on**: `--hatch` on `--paper-3`; every later tile in that lane is the same hatch.
  - **override-affected**: 1px dashed `--override` outline.
  - **no pick / beyond horizon**: `--paper-2` at 60% opacity.
- Current week column: 1px `--rule-strong` verticals on both sides, full height. Horizon: 1px dashed `--ink-3` vertical after the horizon week.
- Interactions: hover a tile (120ms delay) → tooltip on `--paper-2` `W7 · B · KC vs LV · 71.2 · locked` in `--t-data-s`. Click a week number → sets the focus week (all views follow). Click a tile → branch picker for that entry/week. Right-click / long-press a column → menu `Two picks this week · Branches A / B / C`. Roving-tabindex grid: arrows move, `Enter` opens, `l` locks. Phone: tap column = set week, long-press tile = picker.

### 5.3 Pick hero card (This Week)
Three equal columns (4 of 12 each) separated by vertical hairlines, not boxes; on phone they stack with hairlines. Padding 24px 24px 20px, 2px `--entry-x` left border.
1. Kicker `--t-label`: `ENTRY A · MAIN` in `--entry-a`; right: `7 USED` `--ink-3`; state word after the kicker when not default (`· LOCKED`, `· ELIMINATED W4`, `· WHAT-IF` in plum).
2. Team name Fraunces 500 28/32 `Baltimore`, then `BAL` in `--t-data` `--ink-3`.
3. Opponent line `--t-body`: `vs Cleveland · Sun 1:00p ET · −7.5 · −360` (spread and ML in Mono).
4. The Ruled Figure at `--t-display-xl` (72px) in its tone; `%` 28px superscript weight 400; rule 3px, spanning `p%` of the card's inner width. Right of it, stacked `--t-small` with `--t-label` keys: `SOURCE book ML` / `MODEL +1.2 vs book` / `CROWD 34.1%` (crowd carries a 1px `--ink-3` underline proportional to the value).
5. Bottom row `--t-small` `--ink-3`: `Survives to W18 18.4` as a small Ruled Figure (survival thresholds); text button `Alternatives ↓` (scrolls to and highlights §5.5).
6. Actions right-aligned: `Lock pick` text button (or `■ LOCKED · Unlock`), `Branches →` text link.
States: **default**; **hover** (underline on text buttons only); **locked** (kicker gains `· LOCKED`, team line gets a leading `■`, left border becomes 2px `--ink`); **two-pick** (two team blocks stacked, each with its own Ruled Figure at `--t-display-m`, hairline between, `Both win 52.6` figure at the bottom in the hero position); **eliminated** (card in `--ink-4`, team struck through, kicker `ENTRY B · ELIMINATED W4`, single line `Lost with DAL (W4, 17–24)`, no actions); **stale** (values stay, a `--stale` square precedes the source line); **live** (opponent line replaced by `● LIVE · BAL 21 – 10 CLE · Q3 4:12` in Mono 500 with the pulsing dot; if the backend supplies it the figure becomes the live win probability and the kicker reads `· LIVE WIN`, else the pregame figure at 60% opacity); **final** (`FINAL · W 27–17` or `L 17–24`; a loss switches the card to eliminated after a confirmation toast); **loading** (figure `—` at 40% opacity, rule at 0 width).
Phone: 120px compact — team + figure on one line, meta line below.

### 5.4 Joint stats block (This Week)
Under the heroes: a 4-column ledger, hairline above and below, cells 96px tall separated by hairline verticals. `P(≥1 SURVIVES) → W18 41.2` · `P(ALL SURVIVE) → W18 6.8` · `EXPECTED ALIVE 1.34` · `THIS WEEK ALL WIN 38.5`. Label `--t-label`; value Fraunces 500 28px as a Ruled Figure (survival thresholds; expected alive in `--ink` with no rule; this-week-all-win uses win thresholds). Under each value a `--t-data-s` delta vs the last computation: `+0.8` in `--p4`, `−1.1` in `--p1`. No tiles, no backgrounds.

### 5.5 Alternative combinations table (This Week, 4-col beside the chart)
Rows 40px. Columns: `#` Mono · `A` `B` `C` (team codes, Mono; a locked leg shows `■`) · `ALL WIN` (Ruled Figure, `--t-figure-s`) · `≥1 → H` · `ALL → H` (survival thresholds) · `E[ALIVE]` Mono · `Δ VS PLAN` Mono signed, `--p4`/`--p1` · action `Use` text button. Row 1 is the current plan with a leading `●` and `--paper-2` background. Max 12 rows, `Show more` text link. `Use` applies the combination: row flashes `--locked-tint` (§6), the Rail and heroes update, and a toast (§5.21) offers `Undo`.

### 5.6 Survival curve chart (This Week, 8-col)
320px tall (phone 100% × 240). No container border; the plot is bounded by an x-axis hairline only. X: weeks current..horizon, Mono 11 every week, current week in `--ink`. Y: 0–100, gridlines every 25 in `--chart-grid`, labels Mono 11 outside the left edge, no y line. Series: three entry lines 1.5px `--entry-x`; `P(≥1)` 2.5px `--chart-joint-any`; `P(all)` 1.5px dashed 4-3 `--chart-joint-all`. Stepped-after interpolation (probability drops at the week's games), never smoothed. Points are 3px squares on the joint lines only. Weeks past the horizon shaded `--chart-band`. Axis marks: locked weeks a 1px `--ink` vertical tick; two-pick weeks `²` after the label; overrides a plum tick. Direct labeling: each line ends with `A 18.4`, no legend box. Hover: a vertical hairline follows the cursor and a readout row above the axis (not a floating tooltip) reads `W7 · A 41.2 · B 38.9 · C 44.0 · ≥1 71.3 · ALL 7.1` in Mono 11 on `--paper-2`; touch taps to pin. Empty: axes drawn, `No plan — set horizon ≥ current week` in Fraunces italic 16 `--ink-3`.

### 5.7 Season Plan grid cell
Grid: rows = weeks (56px), columns `WEEK` 72px · `2×` 56px · one per entry (flex, min 200px) · `JOINT` 120px. Header row 40px, `--paper-2`, `--t-label`, entry names in their colors. Hairlines between rows, a `--rule-strong` under every 4th week, a 1px `--rule-strong` above and below the current week's row with its `WEEK` cell in Fraunces 500 17. Beyond-horizon rows at 60% opacity, still clickable. Built as CSS grid with `role="grid"` for keyboard navigation.
Cell (padding 8px 12px): line 1 team name Fraunces 500 20 + code `--t-data` `--ink-3` + opponent `v CLE` `--t-small`; line 2 the Ruled Figure `--t-figure` left, `--t-data-s` `−7.5 · 34% crowd` right.
States:
- **planned**: as above; cursor pointer; hover `--paper-3` with a `→ Branches` hint bottom-right in `--t-data-s`.
- **locked**: cell background `--paper-inverse`, text `--ink-inverse`, the rule under the figure in `--ink-inverse` with a 6px tone swatch at its end; `■` before the team name; hover reveals `Unlock` right.
- **two-pick**: two 24px sub-rows, each team + Ruled Figure at `--t-figure-s`; third line `both 52.6` `--t-data-s`; row grows to 80px.
- **past, won**: team `--ink-2`, figure replaced by `W 31–17` Mono, no rule, not clickable; hover tooltip shows the final and the pregame figure.
- **eliminated**: the elimination week shows the losing team struck through with `L 17–24` Mono; later cells in that column are `--hatch` on `--paper-2` with a centered `—` `--ink-4`, not clickable.
- **infeasible**: `NO PICK` in `--t-label` `--p1`, rule at 0, hatch background (a lock left no valid path).
- **override-affected**: 1px dashed `--override` inset outline and a plum `OVR` tag bottom-left.
- **stale**: figure at 60% opacity, a `·` after the number (carried-over data); the banner explains.
- **selected** (picker open for this cell): 1px `--rule-strong` inset outline.
- **changed** (after a re-optimization): 1px `--ink` top rule that fades over 1.2s so the eye finds what moved.
`JOINT` column: `≥1 71.3` and `all 7.1` stacked as compact Ruled Figures (survival thresholds).
Click a cell → branch picker: ≥1024 a right drawer 560px containing the Branches view for that entry/week with the grid still visible and the cell selected; narrower → navigates to `#/branches/:entry/:week`. Keyboard: arrows, `Enter`, `l`, `t`.
Phone: `WEEK` 40, `2×` 36, entries three ~90px columns, `JOINT` hidden; cells show name-less code + figure only.

### 5.8 Two-pick toggle
36×20 switch, 0 radius track, 16×16 square knob (square knobs are the product's toggle signature). Off: track `--paper-3`, knob `--paper` with 1px `--rule-strong`. On: track `--ink`, knob `--paper`. Label right `2×` `--t-small` (`--ink` when on). Disabled (past weeks, beyond horizon): 40% opacity. Toggling re-optimizes: the row's top rule becomes a 1px progress line, the row height animates 56→80, the Rail tile splits. Same component for `ALIVE` in the entries editor. Also present in the Branches header for the selected week.

### 5.9 Branch row (Branches view and picker drawer)
Header: `Entry B · Week 5` `--t-display-m`; kicker `--t-data`: `objective P(≥1) · horizon W18 · used: KC BUF PHI …`; controls: two-pick toggle, `SORT survive → H ▾` (survive, win %, crowd, contrarian value), filter text toggles `Hide < 55` · `Hide used`.
Row 64px, hairlines. Columns: `RANK` Mono 40px · `PICK` (team Fraunces 20 + opponent + `−6.5 · −280` Mono) · `WIN %` (Ruled Figure 17, 96px) · `CROWD` Mono · `SURVIVE → H` (Ruled Figure, survival thresholds, 120px, default sort key) · `Δ` Mono signed vs plan, `--p4`/`--p1`, `—` on the plan row · `PATH` flex (min 320px) · `ACTION` 96px.
`PATH`: one 28×22 tile per week from next week to horizon, team code Mono 11 on `--pN-fill` by that week's win%; locked downstream weeks get a 1px `--ink` outline; two-pick weeks two 10px stacked halves; hover a tile → `W7 · KC v DEN · 74.2`. Scrolls horizontally inside the cell when narrow.
States: **plan row** leading `●`, `--paper-2` background; **locked row** `■ LOCKED` in the action column with `Unlock` text button and a 2px `--ink` left border; **best** (rank 1) no extra mark — rank carries it; **hover** `--paper-3`; **dead end** (locking leaves no valid future path) `SURVIVE` shows `0.0` with a `DEAD END` tag `--t-label` `--p1`, no `Lock`; **used/ineligible** rows are collapsed into a footer `12 teams excluded: used (7), bye (4), ineligible (1) · Show`; when shown they are struck through at 50% with `USED W3`; **expanded** (click the row) reveals a mini ledger under it — week, team, opponent, win %, cumulative survival — and a reason line `Why: keeps DAL for W12 (+4.4 survival)` in `--t-small` `--ink-2`.
Action: `Lock` text button (primary style on hover). Locking: row flashes `--locked-tint`, the drawer closes (plan context), other entries re-optimize, a toast reads `Locked KC for B in W7 · ≥1 alive 41.7 → 43.1 · Undo`.
Phone: `CROWD` and `Δ` hidden; `PATH` on a second line (row 88px).

### 5.10 Schedule row
Filter row under the view header (28px): `WEEK` stepper following the focus week with an `All` option · text toggles `All · My picks · Live` · team search `/` · right: `1 override · Clear all` in plum when any exist.
Week group header 48px: `Week 3` Fraunces 500 20, `Sep 21–25` Mono 13 `--ink-3`, `16 games · 3 final · 1 live` right, `Collapse` text button; second line `BYE DET · GB · JAX · TB`. Sticky within scroll.
Row 48px (compact 40). Columns: `KICKOFF` Mono 13, 112px (`Sun 1:00p`) · `AWAY` 180px (code Mono + name `--t-body-strong`, pick squares immediately left of the code) · `@` `--ink-3` · `HOME` 180px · `SPREAD` Mono 72px, home-relative · `ML A / ML H` Mono 120px · `WIN % (FAV)` 112px: the favored team's code Mono + Ruled Figure `--t-figure-s` (`KC 74.1`), so the figure always reads as "the favorite's chance"; hover shows the other side · `SRC` Mono 11 `--ink-3` (`book`, `model`, `blend`, `live`, `manual`); hover any figure → `book 71.2 · model 74.0 · blend 72.4 · 12m ago` · `SCORE / STATUS` 140px · `PICKS`: 12px squares with the entry letter inside, hollow with entry-colored 1px border = planned, filled = locked; two entries on one team → adjacent squares · `WHAT-IF` 108px: 3-segment control `AWAY | — | HOME`.
States: **scheduled** status `—`. **live** kickoff replaced by `● Q3 4:12` with the pulsing `--live` dot; score Mono 500 `--ink`, leading side underlined 1px; row background `--live-tint` at 40%; live win% replaces the pregame figure with `SRC live` when supplied. **final** score Mono 500, winner `--ink`, loser `--ink-3`, `FINAL` `--t-label`; the figure is replaced by `W`/`L` against the picked side; row text `--ink-2`; a pick square on the losing team gets a 1px `--p1` outline and its letter turns `--p1` — elimination is visible at the game level; what-if disabled. **override** chosen segment filled plum with `--ink-inverse` text; figure shows `100.0`/`0.0` in plum with a plum rule; `SRC manual`; 2px plum left border; the forced winner's code gets a plum `↑`. **postponed/TBD** kickoff `TBD` `--ink-4`, odds `—`. **pick square hover** popover `Entry A · planned · Lock`. **hover** `--paper-3`.
Team codes link to the Teams view. Phone: two lines (teams + score; odds + figure + picks), 64px; the what-if control in a tap-to-expand third line.

### 5.11 Team header (Teams view)
Team switcher in the view header: `Team KC ▾` select plus `←`/`→` alphabetical.
2/3 column: name `--t-display-l` (44px) with code and record Mono; kicker `AFC NORTH · BYE W14`. A 4-stat ledger with hairlines: `RATING 6.8` · `INJ IMPACT −1.4` (`--p1` if ≤ −1.0, `--p2` if < 0, with a 32px magnitude rule) · `NEXT W7 vs LV 71.2` (Ruled Figure) · `OFF 2.1 / DEF −0.3`; each Fraunces 28 with `--t-label` above.
1/3 column: `Used by` list `A ■ W1`, `B —`, `C —`, and `Planned` list `B · W7 (locked)` in `--t-small` with entry-colored labels.
Below the header: the heatmap strip (§5.13), then a two-column area — `INJURIES` (§5.12) left, `STATS` ledger right (32px rows, `STAT · VALUE · RANK` with a 40px rank rule in `--ink-3`) — then `NEWS` filtered to this team.

### 5.12 Injury row
40px rows, hairlines. `POS` Mono 11 40px · `PLAYER` `--t-body-strong` · `STATUS` `--t-label` toned: OUT/IR `--p1`, DOUBTFUL `--p2`, QUESTIONABLE `--p3`, PROBABLE `--p4` · `INJURY` `--t-body` `--ink-2` · `IMPACT` Mono signed (`−0.6`, `--p1` if ≤ −0.5) with a 32px magnitude rule · `UPDATED` Mono 11 `--ink-3` relative time. Sorted by impact. Rows with impact ≤ −0.5 get a 2px `--p1` left border. Empty: `No reported injuries` Fraunces italic 16 `--ink-3` in a 48px row.

### 5.13 Probability heatmap strip (Teams view; the same tile family as PATH and the Rail)
One tile per remaining week including byes, 1fr each, 56px tall, 1px gap (gap shows `--paper`, no borders). Tile: week number Mono 11 `--ink-3` top-left; opponent `--t-small` (`@DEN` away); win % Ruled Figure `--t-figure-s` bottom-left. Background `--pN-fill`; bye `--paper-2` with `BYE`; played weeks show `W`/`L` and the score Mono with the fill by result (W → `--p5-fill`, L → `--p1-fill`). Markers: planned pick = 1px entry-colored bottom rule; locked = 2px `--ink` bottom rule; override = 3px plum square top-right; if the team is already used by an entry every remaining tile carries a 1px inner outline in that entry color at 50%, so "who can still use this team when" is visible. Hover: a readout below the strip `W9 · @DEN · Sun 4:25p · −3.0 · 62.8 book / 65.1 model`. Click: opens the branch picker for that week with this team highlighted (a 3-option entry popover if ambiguous). Phone: horizontal scroll, tiles fixed 64px, 12px fade both ends.

### 5.14 News row
64px rows, hairlines. Left 96px: `--t-data-s` time (`2h ago` / `Sep 8`). Main: headline `--t-body-strong` (max 2 lines; unread weight 600 `--ink`, read 400 `--ink-2`, marked read on scroll-past), then meta `--t-small`: team codes Mono uppercase with middle dots (click filters), kind tag `--t-label` (`INJURY · OUT`, `INJURY · Q`, `TRANSACTION`, `WEATHER`, `LINE MOVE`, `NOTE`) in the matching status tone, source `--ink-3`. Rows about a team planned or locked this week get a 2px entry-colored left border (stacked when several). Filters above: text toggles `All · My teams · Injuries · Lines`, team select, `Affects my picks` toggle (default on during the current week). Phone: time and source on line 2.

### 5.15 Buttons and controls
- **Primary**: `--paper-inverse` bg, `--ink-inverse` text, `--t-body-strong`, height 36, padding 0 16, 0 radius. Hover `--ink-2`; active `--ink` with text at 80%; disabled `--paper-3`/`--ink-4`; loading: label replaced by three 4px squares blinking. One primary per surface (`Save`, `Lock` in drawers).
- **Secondary**: transparent, 1px `--rule-strong`, `--ink` text; hover `--paper-3`.
- **Text button**: no border, `--ink`, 1px underline on hover; the default action style in ledgers (`Lock`, `Unlock`, `Use`, `Clear`, `Show`).
- **Danger text**: `--p1` (`Clear all overrides`, `Mark eliminated`).
- **Segmented (what-if)**: 3 segments 36×28, 1px `--rule-strong` outer border, hairline dividers, Mono 11 uppercase; selected fills plum; middle `—` is clear/default.
- **Select**: text with `▾`; menu as §5.1.
- **Toggle**: §5.8. **Stepper**: `−` value `+`, 28px, borders as segmented. **Checkbox**: 14px square, 1px `--rule-strong`, checked = `--ink` fill with a 4px `--paper` inner square.
- **Inputs**: 32px, `--paper`, 1px `--rule-strong` bottom rule only; Mono for numeric, Body for text; focus = the bottom rule 2px `--focus`.
- **Tags**: `--t-label` text only, no fill, optional 1px border in the same tone at 50%.
- **Kbd hints**: `--t-kbd` `--ink-3` in a 1px `--rule` box, 16px tall.
- Focus everywhere: 2px `--focus` outline offset 2, keyboard only.

### 5.16 Entries editor — see §5.1.

### 5.17 Empty states
No boxes, no illustrations. A hairline-bounded area at the natural content height (min 160px), left-aligned to the table's first column: Fraunces italic 400 20 headline (`No plan yet.`), `--t-body` `--ink-3` explanation (`Add at least one entry with its used teams, then refresh.`), one text button. Branches: `No feasible pick for Entry B in Week 12.` + `Every remaining team is used or on bye. Change an earlier lock.` First run: three hero columns with `Add entry →` and `—` figures; the Rail shows `--paper-2` tiles.

### 5.18 Loading and recompute
Skeleton = the real ledger structure with values as `—` in `--ink-4` and rules at 0 width; no shimmer, no gray blocks; headers and labels render immediately. Any recomputation shows the **progress line**: the 2px heavy rule under the masthead sweeps `--rule` → `--ink` left-to-right (indeterminate, 1.2s loop) until done; row-local recomputes (toggle, lock) show a 1px version on that row's top rule. Values being recomputed dim to 40% opacity and stay readable; content is never blanked. Refresh: the refreshing source's freshness square blinks `--stale` until done. Data carried over from a failed fetch shows a trailing `·` after the number (`71.2·`) and the banner explains.

### 5.19 Error states
Inline at the point of failure: 2px `--error` left rule on the affected block, message `--t-body-strong` `--ink` (`Optimizer failed for Week 7.`), detail `--t-small` `--ink-3` (server text, Mono if a code), `Retry` text button. Form validation: bottom rule `--error` with a `--t-data-s` message. Fatal (backend unreachable): a single left-aligned block `Backend unreachable — last plan cached 2:14 PM · Retry`; the Rail renders from cache at 50% opacity. Never a modal.

### 5.20 Stale-data banner
36px under the Rail, `--paper-2`, 3px left rule `--stale`, hairline bottom, `--t-small`: `Lines are 2h 14m old · injuries 41m · model computed 2h 15m ago` then text buttons `Refresh now` and `Dismiss` (dismiss lasts until the next staleness change). Appears when lines > 60m, injuries > 6h, model > 60m, or scores > 90s in a live window. Error variant: left rule `--error`, `Could not refresh odds (HTTP 503). Showing data from 2:14 PM.` Live variant: `Scores updating every 60s` with the pulsing dot, no dismiss. Only one banner; issues joined with `·`. Phone: `Lines 2h old · Refresh`.

### 5.21 Toast
One line under the masthead's heavy rule, `--paper-2`, hairline bottom, `--t-small` `--ink`, 36px, left-aligned to the container: `Locked KC for B in W7 · ≥1 alive 41.7 → 43.1` with `Undo` text button. 4s hold. Used for lock/unlock, `Use` combination, override set/clear, entries saved, and an entry elimination confirmation.

---

## 6. Motion

Nothing moves unless it explains a change of state. Easing `cubic-bezier(0.2,0,0,1)` entrances, `cubic-bezier(0.4,0,1,1)` exits. `prefers-reduced-motion`: all durations → 0, the live dot is static. No parallax, no scale-ups, no bounce, no blur, no shimmer.

| What | Duration | Detail |
|---|---|---|
| View switch | 160ms | Outgoing fades out; incoming fades in rising 4px; tab underline slides along the masthead rule 200ms |
| Ruled Figure value change | 320ms | Number counts to the new value (tabular figures prevent jitter); rule width animates; tone crossfades |
| Rail tile recolor | 240ms | Fill crossfade; changed tiles flash a 1px `--ink` outline fading over 600ms |
| Season Plan cell re-plan | 320ms | Old team fades 120ms, new fades in 200ms; changed cells get the 1px `--ink` top rule fading over 1.2s |
| Row height change (two-pick) | 200ms | 56→80 with content clipped; sub-rows fade in |
| Drawer (branches, entries) | 240ms in / 160ms out | Slides from right 24px + fade; underlying content does not dim; the `--rule-strong` edge appears |
| Menu / tooltip | 120ms | Fade + 2px rise |
| Live dot | 1.6s loop | Opacity 1→0.3→1, no scale |
| Live score change | 600ms | Score flashes `--ink` → `--live` → `--ink` |
| Progress line | 1.2s loop | Indeterminate left-to-right sweep of `--ink` over `--rule` |
| Lock / use confirmation | 200 in · 1200 hold · 400 out | Row background to `--locked-tint` and back |
| Toast | 160 in · 4s hold · 200 out | Fades in under the masthead; no slide |
| Hover backgrounds | 80ms | Background color only |
| Chart series update | 400ms | Paths interpolate; horizon band width animates when horizon changes |
| Banner | 160ms | Height 0→36 with fade |
| Toggle knob | 120ms | Translate 16px |
| Refresh glyph | 900ms loop | `↻` rotates while fetching |

---

## 7. ASCII wireframes (laptop ~1440px)

### 7.1 This Week
```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ SURVIVOR │ 2026  This Week  Season Plan  Branches  Schedule  Teams  News   HORIZON W18▾ DECAY 0.97▾     │
│                  ‾‾‾‾‾‾‾‾‾                                  OBJECTIVE P(≥1)▾ CONTRARIAN 0.30▾ ENTRIES DENSE │
│                                                             ■LINES 12m ■INJ 41m ■SCORES live  REFRESH ↻ │
╞════════════════════════════════════════════════════════════════════════════════════════════════════════╡
│ WK    1    2   [3]   4    5    6²   7    8    9   10   11   12   13   14   15   16   17   18 ]           │
│ A    [·]  [·]  ▓▓▓  ▒▒▒  ▒▒▒  ▒/▒  ▒▒▒  ▒▒▒  ▒▒▒  ▒▒▒  ▒▒▒  ▒▒▒  ▒▒▒  ▒▒▒  ▒▒▒  ▒▒▒  ▒▒▒  ▒▒▒           │
│ B    [·]  [·]  ████ ▒▒▒  ▒▒▒  ▒/▒  ┊▒▒┊ ▒▒▒  ▒▒▒  ▒▒▒  ▒▒▒  ▒▒▒  ▒▒▒  ▒▒▒  ▒▒▒  ▒▒▒  ▒▒▒  ▒▒▒           │
│ C    [·]  ░░░  ░░░  ░░░  ░░░  ░░░  ░░░  ░░░  ░░░  ░░░  ░░░  ░░░  ░░░  ░░░  ░░░  ░░░  ░░░  ░░░           │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ▌ Lines are 2h 14m old · model computed 2h 15m ago                            Refresh now   Dismiss    │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  Week 3                                                          Sep 21–25 · 16 games · 2 entries alive│
│  The plan                                                                                              │
│ ───────────────────────────────────────────────────────────────────────────────────────────────────── │
│ ▎ENTRY A · MAIN            7 USED │ ▎ENTRY B · SECOND · LOCKED  7 USED │ ▎ENTRY C · ELIMINATED W2      │
│ ▎ Baltimore  BAL                  │ ▎ ■ Kansas City  KC              │ ▎ S̶a̶n̶ ̶F̶r̶a̶n̶c̶i̶s̶c̶o̶  SF          │
│ ▎ vs Cleveland · Sun 1:00p · −7.5 │ ▎ vs Denver · Sun 4:25p · −6.5   │ ▎ Lost with KC (W2, 17–24)    │
│ ▎                                 │ ▎                                │ ▎                             │
│ ▎ 78.2%      SOURCE  book ML      │ ▎ 74.1%      SOURCE  blend       │ ▎  —                          │
│ ▎ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │ ▎ ━━━━━━━━━━━━━━━━━━━━━━━━━━━     │ ▎                             │
│ ▎             MODEL  +1.2 vs book │ ▎             MODEL  −0.4        │ ▎                             │
│ ▎             CROWD  34.1%        │ ▎             CROWD  21.7%       │ ▎                             │
│ ▎ Survives to W18  18.4 ▁▁▁       │ ▎ Survives to W18  16.9 ▁▁▁      │ ▎                             │
│ ▎ Alternatives ↓  Lock pick  Branches → │ ▎ Alternatives ↓  Unlock  Branches → │ ▎                    │
│ ───────────────────────────────────────────────────────────────────────────────────────────────────── │
│  P(≥1 SURVIVES) → W18   P(ALL SURVIVE) → W18   EXPECTED ALIVE        THIS WEEK ALL WIN                │
│  41.2 ▁▁▁▁  +0.8         6.8 ▁  −0.2            1.34  +0.02           40.3 ▁▁▁▁                        │
│ ───────────────────────────────────────────────────────────────────────────────────────────────────── │
│  SURVIVAL TO HORIZON      W7 · A 41.2 · B 38.9 · ≥1 71.3 · ALL 7.1 │  ALTERNATIVE COMBINATIONS        │
│ 100 ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈        │  #  A    B    C  ALL WIN ≥1→H  Δ     │
│     ━━━━┓                                                          │  ● BAL  ■KC   —  40.3    41.2   —    │
│  75 ┈┈┈┈┗━━━┓┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈        │  2 BUF  ■KC   —  42.1    40.9  −0.3  │
│         ─┐  ┗━━━┓                                                  │  3 BAL  ■KC   —  38.8    40.4  −0.8  │
│  50 ┈┈┈┈┈┗──┐┈┈┈┗━━━━┓┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈        │  4 PHI  ■KC   —  40.3    39.7  −1.5  │
│             └──┐     ┗━━━┓                                         │  5 DET  ■KC   —  41.0    39.1  −2.1  │
│  25 ┈┈┈┈┈┈┈┈┈┈┈└───┐┈┈┈┈┈┗━━━━━━━┓┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈        │  …                                   │
│                    └────┐        ┗━━━━━━━┓  ≥1 41.2                │  Show more                           │
│   0 ┈┈┈┈╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌└───────┐╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌  A 18.4  B 16.9    │                                      │
│     W3   W5   W7   W9   W11  W13  W15  W17  ]  ░░░░░░░░ (band)     │                                      │
│               ²         ▲lock                                      │                                      │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Book: DraftKings · Model v3.2 · computed 2:14 PM ET · 3 entries · 9 teams used                        │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```
Rail legend: `▒` planned tile in its tone fill · `█` locked (solid ink) · `▒/▒` two-pick split · `[·]` past won (hollow with ink square) · `░` eliminated hatch · `┊ ┊` dashed plum override outline · `[3]` current week with ink underline · `]` horizon bracket.

### 7.2 Season Plan (branch drawer open for Entry B · Week 5)
```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ SURVIVOR │ 2026  This Week  Season Plan  Branches  Schedule  Teams  News   HORIZON W18▾ DECAY 0.97▾ …  │
│                            ‾‾‾‾‾‾‾‾‾‾‾                                                                 │
╞════════════════════════════════════════════════════════════════════════════════════════════════════════╡
│ WK    1    2   [3]   4    5    6²   7    8    9   10  …  18 ]     (Rail as above)                       │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  Season plan                                                       ≥1 → W18  41.2   all → W18  6.8    │
│  Objective P(≥1 alive) · horizon W18 · decay 0.97 · contrarian 0.30 · 1 lock · 1 override            │
│ ───────────────────────────────────────────────────────────────────────────┬─────────────────────────── │
│ WEEK  2×   ENTRY A · MAIN        ENTRY B · SECOND       ENTRY C · THIRD    │ Entry B · Week 5         │
│ ───────────────────────────────────────────────────────────────────────────│ used: KC BUF PHI · obj ≥1│
│  1    ○   Buffalo BUF  v ARI     Kansas City KC v BAL   Philadelphia  v GB │ [○ 2×]  SORT survive→H ▾ │
│           W 34–28               W 27–20                W 24–20            │ Hide < 55 · Hide used    │
│ ───────────────────────────────────────────────────────────────────────────│ ───────────────────────── │
│  2    ○   Dallas DAL  v NO       Buffalo BUF  v MIA     K̶a̶n̶s̶a̶s̶ ̶C̶i̶t̶y̶ @ CIN │ 1 Detroit DET   v CHI    │
│           W 31–17               W 24–21                L 17–24            │   72.4 ━━━━━━━━━━━━━━━   │
│ ═══════════════════════════════════════════════════════════════════════════│   crowd 18 · →H 17.1 ▁▁▁ │
│ [3]   ○   Baltimore BAL  v CLE   ███████████████████████ ░░░░░ — ░░░░░░░░ │   ▦▦▦▦▦▦▦▦▦▦▦▦▦   Lock  │
│           78.2 ━━━━━━━━━━━━━━━   █■ Kansas City KC v DEN█ ░░░░░░░░░░░░░░░░ │ ───────────────────────── │
│           −7.5 · 34% crowd      █74.1 ━━━━━━━━━━━━━━ ▪ █ ░░░░░░░░░░░░░░░░ │ ● Green Bay GB  v NYJ    │
│ ═══════════════════════════════════════════════════════════════════════════│   68.9 ━━━━━━━━━━━━━━    │
│  4    ○   Detroit DET  v LV      Philadelphia PHI v TB  ░░░░░ — ░░░░░░░░ │   crowd 31 · →H 16.9 ▁▁▁ │
│           75.0 ━━━━━━━━━━━━━━    71.3 ━━━━━━━━━━━━━      ░░░░░░░░░░░░░░░░ │   ▦▦▦▦▦▦▦▦▦▦▦▦▦   Lock  │
│ ───────────────────────────────────────────────────────────────────────────│ ───────────────────────── │
│  5    ○   Houston HOU  @ CAR    ┌Green Bay GB  v NYJ ┐  ░░░░░ — ░░░░░░░░ │ 3 Houston HOU  @ CAR     │
│           70.1 ━━━━━━━━━━━━━    │68.9 ━━━━━━━━━━━━━  │  ░░░░░░░░░░░░░░░░ │   70.1 ━━━━━━━━━━━━━━    │
│                                └────────→ Branches ─┘                     │   crowd 12 · →H 16.2 ▁▁▁ │
│ ───────────────────────────────────────────────────────────────────────────│   ▦▦▦▦▦▦▦▦▦▦▦▦▦   Lock  │
│  6    ●   Miami MIA  v NE       Baltimore BAL  v WAS    ░░░░░ — ░░░░░░░░ │ ───────────────────────── │
│      2×   64.0 ━━━━━━━━━━━      69.7 ━━━━━━━━━━━━━      ░░░░░░░░░░░░░░░░ │ 4 Minnesota MIN v TEN    │
│           Green Bay GB @ CHI    Detroit DET  @ NYG                        │   67.4 ━━━━━━━━━━━━      │
│           61.5 ━━━━━━━━━━       66.0 ━━━━━━━━━━━                          │   crowd 8 · →H 15.8 ▁▁▁  │
│           both 39.4             both 46.0                                 │   ▦▦▦▦▦▦▦▦▦▦▦▦▦   Lock  │
│ ───────────────────────────────────────────────────────────────────────────│ ───────────────────────── │
│  7    ○   ┊Seattle SEA v LAR┊   Denver DEN  v LV        ░░░░░ — ░░░░░░░░ │ 9 Cleveland CLE @ PIT    │
│           ┊100.0 ━━━━━━ OVR ┊   66.2 ━━━━━━━━━━━                          │   52.0 ━━━━━━━━  DEAD END│
│ ───────────────────────────────────────────────────────────────────────────│   →H 0.0                 │
│  …                                                                         │ ───────────────────────── │
│ 18]   ○   Cincinnati CIN v CLE   NO PICK                 ░░░░░ — ░░░░░░░░ │ 12 teams excluded · Show │
│           58.8 ━━━━━━━━━         ━                                         │                          │
│ ───────────────────────────────────────────────────────────────────────────┴─────────────────────────── │
│ JOINT →H   A 18.4 ▁▁▁▁            B 16.9 ▁▁▁▁            C —               ≥1 41.2 ▁▁▁▁▁  all 6.8 ▁   │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```
Legend: `○/●` two-pick toggle off/on · `█…█` locked cell rendered inverse with `■` and a tone swatch `▪` at the rule's end · `░` hatch (eliminated) · `┊ ┊` dashed plum override outline with `OVR` tag · `═══` strong rules around the current week · `▦` downstream path tiles in tone fills · the right block is the 560px branch drawer with its `--rule-strong` edge.

### 7.3 Schedule
```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ SURVIVOR │ 2026  This Week  Season Plan  Branches  Schedule  Teams  News   HORIZON W18▾ DECAY 0.97▾ …  │
│                                                     ‾‾‾‾‾‾‾‾                                           │
╞════════════════════════════════════════════════════════════════════════════════════════════════════════╡
│ WK    1    2   [3]   4    5    6²   7    8    9   10  …  18 ]     (Rail as above)                       │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  Schedule                                                                                              │
│  WEEK [− 3 +] All     All · My picks · Live     TEAM /____                   1 override · Clear all    │
│ ───────────────────────────────────────────────────────────────────────────────────────────────────── │
│  Week 3   Sep 21–25 · 16 games · 3 final · 1 live · BYE  DET · GB · JAX · TB                  Collapse│
│ ───────────────────────────────────────────────────────────────────────────────────────────────────── │
│ KICKOFF    AWAY             @  HOME             SPREAD  ML A / ML H   WIN % (FAV)   SRC    SCORE/STATUS   WHAT-IF      │
│ ───────────────────────────────────────────────────────────────────────────────────────────────────── │
│ FINAL      □C CIN Cincinnati @  NYJ New York     −2.5   +120 / −140   L             book   17  24 FINAL  [AWY][—][HOM]│
│ Thu 8:15p     (□C outlined vermilion: C lost here)                                                     │
│ ───────────────────────────────────────────────────────────────────────────────────────────────────── │
│ ● Q3 4:12     CLE Cleveland  @  □A BAL Baltimore  −7.5   +290 / −360   BAL 84.0 ━━━━━━━━ live  10  21     [AWY][—][HOM]│
│ ───────────────────────────────────────────────────────────────────────────────────────────────────── │
│ Sun 1:00p     ARI Arizona    @  SF  San Francisco −5.0   +190 / −230   SF 69.5 ━━━━━━━  model  —         [AWY][—][HOM]│
│ ───────────────────────────────────────────────────────────────────────────────────────────────────── │
│ Sun 1:00p     DEN Denver     @  ■B KC Kansas City −6.5   +230 / −280   KC 74.1 ━━━━━━━  blend  —         [AWY][—][HOM]│
│ ───────────────────────────────────────────────────────────────────────────────────────────────────── │
│▌Sun 4:05p     LV  Las Vegas  @  CAR Carolina ↑   +1.5   −115 / −105   CAR 100.0 ━━━━━━━━━ manual —      [AWY][—][███]│
│ ───────────────────────────────────────────────────────────────────────────────────────────────────── │
│ Sun 4:25p     NO  New Orleans@  DAL Dallas        −3.0   +140 / −165   DAL 59.4 ━━━━━━   book   —         [AWY][—][HOM]│
│ ───────────────────────────────────────────────────────────────────────────────────────────────────── │
│ Sun 8:20p     PHI Philadelphia @ TB Tampa Bay     +1.0   −110 / −110   PHI 51.4 ━━━━━    book   —         [AWY][—][HOM]│
│ ───────────────────────────────────────────────────────────────────────────────────────────────────── │
│ TBD           …                                                       —              —      —         (disabled)     │
│ ───────────────────────────────────────────────────────────────────────────────────────────────────── │
│  Week 4   Sep 28–Oct 2 · 14 games · BYE  BUF · LAC · MIN · SEA                                 Expand │
│ ───────────────────────────────────────────────────────────────────────────────────────────────────── │
│  Week 5   …                                                                                            │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Book: DraftKings · lines 12m · scores 30s · model v3.2                                                 │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```
Legend: `□A` planned pick square (hollow, entry-colored border) placed left of the picked team · `■B` locked pick (filled) · `▌` plum override left border with the HOME segment filled plum and a plum `↑` on the forced winner · `●` pulsing live dot with the row tinted `--live-tint` · `L` in the WIN % column of a final row = outcome mark against the picked side.

### Phone notes
- This Week: heroes stack at 120px; joint stats 2×2; chart 240px; alternatives show `A B C ALL ≥1→H` with the rest in a tap-to-expand row.
- Season Plan: one week per block with the three entries as stacked 44px rows carrying a 3px entry-colored left border; the `2×` toggle sits in the block header; `JOINT` in the header as Mono text.
- Schedule: two-line rows; the what-if control in a tap-to-expand line; week headers sticky.
- Rail: 40px, 16px columns, 8px lanes, horizontal scroll snapped to the current week.

---

## 8. Implementation notes
- **Ruled Figure** is one component: `<span class="fig" style="--v:71.4; --tone:var(--p4)">71.4<i></i></span>` with `.fig i { display:block; height:var(--rule-w,1px); width:calc(var(--v)*1%); background:var(--tone); margin-top:2px; }`. Sizes `xl|m|s|xs` set font size and rule thickness (xl 3px, m 2px, s/xs 1px). The rule sits 2px below the baseline inside a block whose width is the cell's content width. `inverse` swaps the rule to `--ink-inverse` and appends the 6px tone swatch. Never gradient-fill a rule.
- `probTone(value, kind)` is the only place tone thresholds live; the Rail, PATH tiles, heatmap strip, chart bands and every figure call it.
- Read-only ledgers (Schedule, Branches list, Injuries, News, Stats) are `<table>` with `table-layout: fixed`, sticky `<thead>` under the Rail (`top: 112px`), inside an `overflow-x: auto` wrapper so the body never scrolls sideways. The Season Plan and the Rail are CSS Grid with `role="grid"/"row"/"gridcell"` and roving tabindex, because their cells are interactive.
- Fixed column widths from §5; numeric columns right-aligned; text columns left-aligned. Tabular figures everywhere so nothing reflows on data change.
- Every number from a source exposes provenance on hover: source, timestamp, model delta.
- Route state (`#/…`, focus week, drawer entry/week, team) is the source of truth; the UI never holds a selection that is not in the URL. Reload restores context.
- No `box-shadow`, no border-radius, no icon font, no emoji, no gradients other than `--hatch`. Elevation is expressed only by `--paper-*` steps and `--rule-*` hairlines.
- All state colors are accompanied by a glyph or word (`■`, `OVR`, `LIVE`, `FINAL`, strikethrough); color is never the sole carrier.