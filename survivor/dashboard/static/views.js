/* Survivor dashboard — views, drawers and the survival chart. Depends on app.js globals. */
'use strict';

function renderView() {
  const el = $('#view');
  el.classList.toggle('wide', ['schedule', 'teams'].includes(S.route.view));
  if (!S.dash) {
    el.innerHTML = S.error ? errorBlock('Backend unreachable', S.error) : `<div class="view-head"><div><div class="folio">Survivor</div><div class="sub">loading plan…</div></div></div>`;
    return;
  }
  let html = '';
  switch (S.route.view) {
    case 'plan': html = viewPlan(); break;
    case 'branches': html = viewBranches(); break;
    case 'schedule': html = viewSchedule(); break;
    case 'teams': html = viewTeams(); break;
    case 'news': html = viewNews(); break;
    default: html = viewWeek();
  }
  el.innerHTML = `<div class="view">${html}</div>`;
  afterRender();
}

function errorBlock(title, detail) {
  return `<div class="errblock"><span class="strong">${esc(title)}</span><span class="detail">${esc(detail || '')}</span> <button class="text-btn" data-act="refresh">Retry</button></div>`;
}
function emptyBlock(title, text, action) {
  return `<div class="empty"><h3>${esc(title)}</h3><p>${esc(text)}</p>${action || ''}</div>`;
}
function weekInfo(week) { return S.dash.weeks.find((w) => w.week === week); }
function weekRange(w) { return w ? `${fmtDate(w.start)} – ${fmtDate(w.end)}` : ''; }
function planAt(entry, week) { return (entry.plan || []).find((p) => p.week === week); }
function isLocked(entryName, week, teams) {
  const e = cfgEntry(entryName); const l = e && e.locks && e.locks[String(week)];
  return !!(l && teams && l.length === teams.length && l.every((t) => teams.includes(t)));
}
function gameLine(g, code) {
  if (!g) return '';
  return `${spreadTxt(g, code)} · ${ml(g.home === code ? g.homeMoneyline : g.awayMoneyline)}`;
}
function statusLine(g) {
  if (!g) return '';
  if (g.status === 'in_progress') return `<span class="live"><span class="dot"></span>LIVE · ${esc(g.away)} ${g.awayScore ?? 0} – ${g.homeScore ?? 0} ${esc(g.home)} · ${esc(g.statusDetail || '')}</span>`;
  if (g.status === 'final') return `<span class="data">FINAL · ${esc(g.away)} ${g.awayScore} – ${g.homeScore} ${esc(g.home)}</span>`;
  return null;
}

/* ================================================================ This Week */
function viewWeek() {
  const d = S.dash, cw = d.meta.currentWeek, H = d.meta.horizon, wi = weekInfo(cw);
  const alive = d.entries.filter((e) => e.alive && e.plan && e.plan.length);
  const heroes = d.entries.map((e) => heroCard(e)).join('');
  const j = d.joint, pj = S.prevJoint;
  const delta = (k, v) => { if (!pj || pj[k] == null || v == null) return ''; const dv = (v - pj[k]) * (k === 'expectedAlive' || k === 'expectedWeeksAny' ? 1 : 100); if (Math.abs(dv) < 0.05) return '<div class="delta">—</div>'; return `<div class="delta ${dv > 0 ? 'up' : 'down'}">${signed(dv, k === 'expectedAlive' ? 2 : 1)} vs last run</div>`; };
  const allWin = j.curveAll && j.curveAll.length ? j.curveAll[0] : null;
  const joint = alive.length ? `<div class="joint">
      <div><span class="label">P(≥1 survives) → W${H}</span>${fig(j.pAny, 'm', 'survival')}${delta('pAny', j.pAny)}</div>
      <div><span class="label">P(all survive) → W${H}</span>${fig(j.pAll, 'm', 'survival')}${delta('pAll', j.pAll)}</div>
      <div><span class="label">Expected alive at W${H}</span><span class="fig fig-m plain" style="--tone:var(--ink)"><b>${j.expectedAlive == null ? '—' : j.expectedAlive.toFixed(2)}</b></span>${delta('expectedAlive', j.expectedAlive)}</div>
      <div><span class="label">E[weeks with ≥1 alive]</span><span class="fig fig-m plain" style="--tone:var(--ink)"><b>${j.expectedWeeksAny == null ? '—' : j.expectedWeeksAny.toFixed(2)}</b><span class="data-s muted"> of ${j.weeks.length}</span></span>${delta('expectedWeeksAny', j.expectedWeeksAny)}</div>
      <div><span class="label">This week all win</span>${fig(allWin, 'm', 'win')}</div>
    </div>` : '';
  const warnings = d.entries.flatMap((e) => (e.warnings || []).map((w) => `<span>${esc(e.name)}: ${esc(w)}</span>`));
  return `<div class="view-head"><div><div class="folio">Week ${cw}</div><div class="sub">${esc(weekRange(wi))} · ${wi ? wi.gameIds.length : 0} games · ${alive.length} of ${d.entries.length} entries alive · horizon W${H}</div></div>
      <div class="tools"><button class="text-btn" data-act="open-crowd">Crowd %</button><a class="text-btn" href="#/plan">Season plan →</a></div></div>
    ${warnings.length ? `<div class="warnlist">${warnings.join('')}</div>` : ''}
    <div class="heroes" style="--n:${d.entries.length}">${heroes}</div>
    ${joint}
    <div class="twocol">
      <div class="chart-wrap"><div class="section-title">Survival to horizon <span class="label">stepped at each week's games</span></div>${survivalChart()}</div>
      <div><div class="section-title">Alternative combinations <span class="label">this week</span></div>${alternativesTable()}</div>
    </div>`;
}

function heroCard(e) {
  const d = S.dash, cw = d.meta.currentWeek, H = d.meta.horizon, ec = entryClass(e.name);
  const usedTxt = `${(e.used || []).length} used`;
  if (!e.alive) {
    return `<div class="hero dead ${ec}"><div class="kicker label"><span>Entry ${esc(e.name)} · Eliminated</span><span class="used">${usedTxt}</span></div>
      <div class="team">—</div><div class="opp muted">Out of the pool. Toggle Alive in Entries to bring it back.</div></div>`;
  }
  const p = planAt(e, cw);
  if (!p || !p.teams.length) {
    return `<div class="hero ${ec}"><div class="kicker label"><span>Entry ${esc(e.name)}</span><span class="used">${usedTxt}</span></div>
      <div class="team">No pick</div><div class="opp muted">${esc((e.warnings || [])[0] || 'No feasible path this week.')}</div>
      <div class="bottom"><div class="actions"><a class="text-btn" href="#/branches/${esc(e.name)}/${cw}">Branches →</a></div></div></div>`;
  }
  const locked = p.locked;
  const ovr = hasOverride(p.gameIds);
  const branch = ((e.branches || {})[String(cw)] || []).find((b) => b.recommended) || {};
  const crowd = branch.crowdPct;
  const two = p.teams.length > 1;
  const picks = p.teams.map((t, i) => {
    const g = game(p.gameIds[i]); const pw = teamP(p.gameIds[i], t);
    const st = statusLine(g);
    const oppLine = st || `${p.home[i] ? 'vs' : '@'} ${esc(teamCity(p.opponents[i]))} · ${esc(g && g.timeValid === false ? 'TBD' : fmtKick(g && g.kickoff))} · <span class="data">${gameLine(g, t)}</span>`;
    return { t, g, pw, oppLine };
  });
  const state = locked ? ' · Locked' : ovr ? ' · <span class="plum">What-if</span>' : '';
  let body;
  if (!two) {
    const k = picks[0];
    body = `<div class="team">${esc(teamCity(k.t))} <span class="code">${esc(k.t)}</span></div>
      <div class="opp">${k.oppLine}</div>
      <div class="figrow">${fig(k.pw, 'xl', 'win', { sup: true, tone: ovr ? 'tone-override' : undefined })}
        <div class="meta"><span class="label">Source</span><span>${esc(srcLabel(p.sources[0]))}</span>
          <span class="label">Book</span><span class="data">${k.g ? gameLine(k.g, k.t) : '—'}</span>
          <span class="label">Crowd</span><span class="crowd" style="--v:${crowd || 0}">${crowd == null ? '—' : crowd.toFixed(1) + '%'}<i></i></span></div></div>`;
  } else {
    body = `<div class="team">${picks.map((k) => `${esc(teamCity(k.t))} <span class="code">${esc(k.t)}</span>`).join(' + ')}</div>
      ${picks.map((k) => `<div class="subpick"><span class="opp">${k.oppLine}</span>${fig(k.pw, 'm', 'win')}</div>`).join('')}
      <div class="figrow"><div><span class="label muted">Both win</span><br>${fig(p.p, 'l', 'win')}</div>
        <div class="meta"><span class="label">Crowd</span><span>${crowd == null ? '—' : crowd.toFixed(1) + '%'}</span></div></div>`;
  }
  const teamsAttr = p.teams.join('+');
  return `<div class="hero ${ec} ${locked ? 'locked' : ''} ${two ? 'two' : ''}">
    <div class="kicker label"><span>Entry ${esc(e.name)}<span class="state">${state}</span></span><span class="used">${usedTxt}</span></div>
    ${body}
    <div class="bottom"><span>Survives to W${H} ${fig(e.pHorizon, 'xs', 'survival')}</span>
      <div class="actions">${locked ? `<button class="text-btn" data-act="unlock" data-entry="${esc(e.name)}" data-week="${cw}">■ Locked · Unlock</button>` : `<button class="text-btn" data-act="lock" data-entry="${esc(e.name)}" data-week="${cw}" data-teams="${esc(teamsAttr)}">Lock pick</button>`}
        <a class="text-btn" href="#/branches/${esc(e.name)}/${cw}">Branches →</a></div></div></div>`;
}

function alternativesTable() {
  const d = S.dash, j = d.joint, cw = d.meta.currentWeek;
  if (!j.alternatives || !j.alternatives.length) return emptyBlock('No alternatives.', 'Every alive entry is locked this week or has no feasible pick.');
  const names = Object.keys(j.alternatives[0].picks);
  const planValue = j.alternatives.find((a) => a.recommended) || j.alternatives[0];
  const rows = j.alternatives.map((a, i) => {
    let allWin = 1;
    const cells = names.map((n) => {
      const teams = a.picks[n] || [];
      const e = entryByName(n);
      const br = ((e && e.branches && e.branches[String(cw)]) || []).find((b) => b.teams.length === teams.length && b.teams.every((t) => teams.includes(t)));
      if (br && br.p != null) allWin *= br.p; else allWin = NaN;
      const lk = isLocked(n, cw, teams);
      return `<td class="code">${lk ? '■ ' : ''}${esc(teams.join('+') || '—')}</td>`;
    }).join('');
    const dv = a.value != null && planValue.value != null ? a.value - planValue.value : null;
    const dTxt = i === 0 ? '—' : dv == null ? '—' : `<span class="${dv >= 0 ? 'tone-p4' : 'tone-p1'}" style="color:var(--tone)">${signed(dv * (d.config.objective === 'final' ? 100 : 1), 2)}</span>`;
    return `<tr class="${a.recommended ? 'plan' : ''}"><td class="code">${a.recommended ? '●' : i + 1}</td>${cells}<td class="num">${fig(Number.isNaN(allWin) ? null : allWin, 'xs', 'win')}</td><td class="num data">${a.value == null ? '—' : d.config.objective === 'final' ? pct(a.value) : a.value.toFixed(2)}</td><td class="num data">${dTxt}</td><td class="num">${a.recommended ? '' : `<button class="text-btn" data-act="use-alt" data-picks='${esc(JSON.stringify(a.picks))}'>Use</button>`}</td></tr>`;
  }).join('');
  const objLabel = { any: 'E[wks ≥1]', final: 'P(≥1→H)', expected: 'E[alive]' }[d.config.objective];
  return `<div class="ledger-wrap"><table class="ledger"><colgroup><col style="width:36px">${names.map(() => '<col>').join('')}<col style="width:72px"><col style="width:80px"><col style="width:64px"><col style="width:52px"></colgroup>
    <thead><tr><th>#</th>${names.map((n) => `<th class="${entryClass(n)} entry-color">${esc(n)}</th>`).join('')}<th class="num">All win</th><th class="num">${objLabel}</th><th class="num">Δ</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

/* ================================================================ chart */
function survivalChart() {
  const d = S.dash, j = d.joint, weeks = j.weeks || [];
  const alive = d.entries.filter((e) => e.alive && e.survivalCurve && e.survivalCurve.length);
  if (!weeks.length || !alive.length) return emptyBlock('No plan.', 'Set the horizon at or after the current week and make sure at least one entry is alive.');
  const W = 820, Hh = 320, L = 36, R = 64, T = 12, B = 28;
  const n = weeks.length;
  const x = (i) => L + ((W - L - R) * i) / n;          // i = 0 (now) .. n
  const y = (v) => T + (Hh - T - B) * (1 - v);
  const series = [];
  alive.forEach((e) => series.push({ key: e.name, cls: '', color: `var(--${entryClass(e.name)})`, vals: e.survivalCurve, label: e.name }));
  series.push({ key: 'any', cls: 'any', color: 'var(--chart-joint-any)', vals: j.curveAny, label: '≥1' });
  if (alive.length > 1) series.push({ key: 'all', cls: 'all', color: 'var(--chart-joint-all)', vals: j.curveAll, label: 'all' });
  const stepPath = (vals) => { let p = `M${x(0).toFixed(1)},${y(1).toFixed(1)}`; let prev = 1; for (let i = 0; i < n; i++) { p += ` H${x(i + 1).toFixed(1)} V${y(vals[i] ?? prev).toFixed(1)}`; prev = vals[i] ?? prev; } return p; };
  const grid = [0, 0.25, 0.5, 0.75, 1].map((v) => `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/><text x="${L - 6}" y="${(y(v) + 4).toFixed(1)}" text-anchor="end">${Math.round(v * 100)}</text>`).join('');
  const ticks = weeks.map((w, i) => {
    const locks = d.entries.some((e) => cfgEntry(e.name) && cfgEntry(e.name).locks && cfgEntry(e.name).locks[String(w)]);
    const wi = weekInfo(w); const ovr = wi && wi.gameIds.some((id) => S.config.overrides[id]);
    const two = (S.config.picksPerWeek || {})[String(w)] > 1;
    return `<text x="${x(i + 1).toFixed(1)}" y="${Hh - 8}" text-anchor="middle" style="${i === 0 ? 'fill:var(--ink)' : ''}">W${w}${two ? '²' : ''}</text>${locks ? `<line class="tick-lock" x1="${x(i + 1).toFixed(1)}" x2="${x(i + 1).toFixed(1)}" y1="${Hh - B}" y2="${Hh - B + 5}"/>` : ''}${ovr ? `<line class="tick-ovr" x1="${(x(i + 1) - 3).toFixed(1)}" x2="${(x(i + 1) + 3).toFixed(1)}" y1="${Hh - B + 3}" y2="${Hh - B + 3}"/>` : ''}`;
  }).join('');
  const lines = series.map((s) => `<path class="line ${s.cls}" style="stroke:${s.color}" d="${stepPath(s.vals)}"/>`).join('');
  const pts = ['any', 'all'].flatMap((k) => { const s = series.find((q) => q.key === k); if (!s) return []; return s.vals.map((v, i) => `<rect class="pt" x="${(x(i + 1) - 1.5).toFixed(1)}" y="${(y(v) - 1.5).toFixed(1)}" width="3" height="3" style="fill:${s.color}"/>`); }).join('');
  // end labels, spread apart when they collide
  const ends = series.map((s) => ({ s, yv: y(s.vals[n - 1] ?? 0) })).sort((a, b) => a.yv - b.yv);
  for (let i = 1; i < ends.length; i++) if (ends[i].yv - ends[i - 1].yv < 13) ends[i].yv = ends[i - 1].yv + 13;
  const labels = ends.map(({ s, yv }) => `<text class="endlabel" x="${W - R + 6}" y="${(yv + 4).toFixed(1)}" style="fill:${s.color}">${esc(s.label)} ${pct(s.vals[n - 1])}</text>`).join('');
  const cursorWeek = S.ui.chartWeek && weeks.includes(S.ui.chartWeek) ? S.ui.chartWeek : weeks[n - 1];
  const ci = weeks.indexOf(cursorWeek);
  const cursor = `<line class="cursor" x1="${x(ci + 1).toFixed(1)}" x2="${x(ci + 1).toFixed(1)}" y1="${T}" y2="${Hh - B}"/>`;
  const hot = weeks.map((w, i) => `<rect data-act="chart-week" data-week="${w}" x="${x(i).toFixed(1)}" y="0" width="${(x(i + 1) - x(i)).toFixed(1)}" height="${Hh}" fill="transparent" style="cursor:pointer"/>`).join('');
  const readout = (wk) => { const i = weeks.indexOf(wk); return `W${wk} · ` + series.map((s) => `${s.label} ${pct(s.vals[i])}`).join(' · '); };
  return `<div class="chart-readout" id="chart-readout" data-default="${esc(readout(cursorWeek))}">${esc(readout(cursorWeek))}</div>
    <svg class="chart" viewBox="0 0 ${W} ${Hh}" width="100%" preserveAspectRatio="none" style="height:320px" data-weeks="${weeks.join(',')}" data-series='${esc(JSON.stringify(series.map((s) => ({ label: s.label, vals: s.vals }))))}'>
      ${grid}<line class="axis" x1="${L}" x2="${W - R}" y1="${Hh - B}" y2="${Hh - B}"/>${ticks}${lines}${pts}${cursor}${labels}${hot}</svg>`;
}

function afterRender() {
  const svg = $('svg.chart');
  if (svg) {
    const ro = $('#chart-readout');
    const series = JSON.parse(svg.dataset.series || '[]'); const weeks = svg.dataset.weeks.split(',').map(Number);
    svg.addEventListener('mousemove', (ev) => { const r = ev.target.closest('[data-week]'); if (!r) return; const w = Number(r.dataset.week); const i = weeks.indexOf(w); ro.textContent = `W${w} · ` + series.map((s) => `${s.label} ${pct(s.vals[i])}`).join(' · '); });
    svg.addEventListener('mouseleave', () => { ro.textContent = ro.dataset.default; });
  }
  const heat = $('.heat');
  if (heat) {
    const ro = $('#heat-readout');
    heat.addEventListener('mouseover', (ev) => { const t = ev.target.closest('.ht'); if (t && ro) ro.textContent = t.dataset.readout || ''; });
    heat.addEventListener('mouseleave', () => { if (ro) ro.textContent = ro.dataset.default || ''; });
  }
  const sel = $('.plangrid .cell.selected'); if (sel) sel.scrollIntoView({ block: 'nearest' });
}

/* ================================================================ Season Plan */
function viewPlan() {
  const d = S.dash, c = S.config, cw = d.meta.currentWeek, H = d.meta.horizon, j = d.joint;
  const entries = d.entries;
  const locks = c.entries.reduce((n, e) => n + Object.keys(e.locks || {}).length, 0);
  const ovr = Object.keys(c.overrides || {}).length;
  const head = `<div class="head"><span class="label">Week</span></div><div class="head"><span class="label">2×</span></div>` +
    entries.map((e) => `<div class="head entry ${entryClass(e.name)}"><span class="label">Entry ${esc(e.name)}${e.alive ? '' : ' · out'}</span></div>`).join('') +
    `<div class="head joint"><span class="label">Joint → W${H}</span></div>`;
  const drawer = S.ui.drawer && S.ui.drawer.type === 'branches' ? S.ui.drawer : null;
  const rows = d.weeks.map((w) => {
    const wk = w.week; const past = wk < cw; const beyond = wk > H; const ji = j.weeks.indexOf(wk);
    const two = (c.picksPerWeek || {})[String(wk)] > 1;
    const wkCell = `<div class="wk ${wk === cw ? 'current' : ''}"><span>${wk}</span><span class="sub">${esc(w.label || weekRange(w))}</span></div>`;
    const tog = `<div class="two-toggle"><button class="toggle" data-act="twopick" data-week="${wk}" aria-pressed="${two}" ${past ? 'disabled' : ''} title="Two picks required this week"></button><span class="tog-label">2×</span></div>`;
    const cells = entries.map((e) => {
      const ec = entryClass(e.name);
      if (!e.alive) return `<div class="cell dead ${ec}">—</div>`;
      if (past) return `<div class="cell past ${ec}"><span class="data-s muted">past</span></div>`;
      if (beyond) return `<div class="cell beyond ${ec}"><span class="data-s muted">beyond horizon</span></div>`;
      const p = planAt(e, wk);
      if (!p || !p.teams.length) return `<div class="cell nopick ${ec}"><span class="label">No pick</span></div>`;
      const ov = hasOverride(p.gameIds);
      const sel = drawer && drawer.entry === e.name && drawer.week === wk;
      const ps = p.teams.map((t, i) => teamP(p.gameIds[i], t));
      const g0 = game(p.gameIds[0]);
      const crowd = wk === cw ? (((e.branches || {})[String(cw)] || []).find((b) => b.recommended) || {}).crowdPct : null;
      let inner;
      if (p.teams.length === 1) {
        inner = `<div class="l1"><span class="name">${esc(teamCity(p.teams[0]))}</span><span class="code">${esc(p.teams[0])}</span><span class="opp">${p.home[0] ? 'v' : '@'} ${esc(p.opponents[0])}</span></div>
          <div class="l2">${fig(ps[0], 's', 'win', { inverse: p.locked, tone: ov ? 'tone-override' : undefined })}<span class="meta">${g0 ? spreadTxt(g0, p.teams[0]) : ''}${crowd != null ? ` · ${crowd.toFixed(0)}% crowd` : ''}${p.sources[0] === 'rating' ? ' · model' : ''}</span></div>`;
      } else {
        inner = p.teams.map((t, i) => `<div class="sub"><span><span class="name" style="font-size:16px">${esc(teamCity(t))}</span> <span class="code">${esc(t)}</span> <span class="opp">${p.home[i] ? 'v' : '@'} ${esc(p.opponents[i])}</span></span>${fig(ps[i], 'xs', 'win', { inverse: p.locked })}</div>`).join('') + `<div class="both">both ${pct(p.p)}</div>`;
      }
      return `<div class="cell ${ec} ${p.locked ? 'locked' : ''} ${p.teams.length > 1 ? 'two' : ''} ${ov ? 'override' : ''} ${sel ? 'selected' : ''}" data-act="open-branches" data-entry="${esc(e.name)}" data-week="${wk}" role="gridcell" tabindex="0">${inner}${ov ? '<span class="ovr">OVR</span>' : ''}<span class="hint">→ Branches</span></div>`;
    }).join('');
    const jc = ji >= 0 ? `<div class="jointcell"><span>≥1 ${fig(j.curveAny[ji], 'xs', 'survival')}</span><span>all ${fig(j.curveAll[ji], 'xs', 'survival')}</span></div>` : `<div class="jointcell"></div>`;
    const cur = wk === cw ? ' cur' : '';
    return [wkCell, tog, cells, jc].join('').replace(/<div class="/g, `<div class="${cur.trim()} `);
  }).join('');
  const sub = `Objective ${OBJECTIVES[c.objective]} · horizon W${H} · decay ${Math.exp(-c.decay).toFixed(2)} · contrarian ${Number(c.contrarianWeight).toFixed(2)} · hedge ${c.hedge} · ${locks} lock${locks === 1 ? '' : 's'} · ${ovr} what-if${ovr === 1 ? '' : 's'}`;
  return `<div class="view-head"><div><div class="folio">Season plan</div><div class="sub">${esc(sub)}</div></div>
      <div class="tools"><span>≥1 → W${H} ${fig(j.pAny, 's', 'survival')}</span><span>all → W${H} ${fig(j.pAll, 's', 'survival')}</span></div></div>
    <div class="plangrid" style="--n:${entries.length}" role="grid">${head}${rows}</div>
    <p class="small muted" style="margin:12px 0 0">Click a cell to see every alternative pick for that entry and week with its re-optimized path. Locked cells are solid ink. Later weeks are a forecast and are re-planned every run.</p>`;
}

/* ================================================================ Branches */
function branchesContent(entryName, week, inDrawer) {
  const d = S.dash, cw = d.meta.currentWeek, H = d.meta.horizon;
  const e = entryByName(entryName) || d.entries[0];
  const cfg = cfgEntry(e.name) || { used: [], locks: {} };
  const branches = ((e.branches || {})[String(week)] || []).slice();
  const plan = planAt(e, week);
  const wi = weekInfo(week);
  const entryOpts = d.entries.map((x) => `<option value="${esc(x.name)}" ${x.name === e.name ? 'selected' : ''}>Entry ${esc(x.name)}</option>`).join('');
  const weekOpts = (d.joint.weeks || []).map((w) => `<option value="${w}" ${w === week ? 'selected' : ''}>Week ${w}</option>`).join('');
  const two = (S.config.picksPerWeek || {})[String(week)] > 1;
  const head = `<div class="branch-head"><div><div class="display-m">Entry ${esc(e.name)} · Week ${week}</div>
      <div class="kicker">objective ${esc(OBJECTIVES[S.config.objective])} · horizon W${H} · used: ${esc((cfg.used || []).join(' ') || 'none')}${wi && wi.byes.length ? ` · bye: ${esc(wi.byes.join(' '))}` : ''}</div>
      <div class="kicker">● is the plan, chosen jointly with the other entries (hedged); rank 1 is this entry's own best path in isolation.</div></div>
    <div class="tools" style="display:flex;gap:16px;align-items:center;flex-wrap:wrap">
      <label class="ctl"><span class="sel"><select data-act="branch-entry">${entryOpts}</select></span></label>
      <span class="stepper"><button data-act="week-step" data-dir="-1" title="previous week">−</button><span class="sel"><select data-act="branch-week" style="border:0;background:transparent;font-family:var(--font-data)">${weekOpts}</select></span><button data-act="week-step" data-dir="1" title="next week">+</button></span>
      <span style="display:inline-flex;gap:6px;align-items:center"><button class="toggle" data-act="twopick" data-week="${week}" aria-pressed="${two}" ${week < cw ? 'disabled' : ''}></button><span class="tog-label">2×</span></span>
      <label class="ctl"><span class="k">Sort</span><span class="sel"><select data-act="sort"><option value="survive" ${S.ui.sort === 'survive' ? 'selected' : ''}>survive → H</option><option value="win" ${S.ui.sort === 'win' ? 'selected' : ''}>win %</option><option value="crowd" ${S.ui.sort === 'crowd' ? 'selected' : ''}>crowd</option></select></span></label>
      <button class="ftog" data-act="hide-low" aria-pressed="${S.ui.hideLow}">Hide &lt; 55</button>
      ${inDrawer ? `<a class="text-btn" href="#/branches/${esc(e.name)}/${week}">Full view →</a>` : ''}</div></div>`;
  if (!e.alive) return head + emptyBlock(`Entry ${e.name} is eliminated.`, 'Toggle Alive in the Entries editor to plan for it again.');
  if (!d.joint.weeks.includes(week)) return head + emptyBlock(`Week ${week} is outside the plan.`, week < cw ? 'That week is already played. Its pick lives in the used-teams list.' : `Raise the horizon to at least W${week} to plan it.`);
  if (!branches.length) return head + emptyBlock(`No feasible pick for Entry ${e.name} in Week ${week}.`, 'Every remaining team is used, on bye, or reserved by a later lock. Change an earlier lock or the used list.');
  const key = { survive: (b) => -b.pHorizon, win: (b) => -b.p, crowd: (b) => (b.crowdPct ?? 0) }[S.ui.sort] || ((b) => -b.pHorizon);
  branches.sort((a, b) => key(a) - key(b));
  const shown = branches.filter((b) => !S.ui.hideLow || b.p >= 0.55);
  const planH = plan && branches.find((b) => b.recommended) ? branches.find((b) => b.recommended).pHorizon : null;
  const showCrowd = week === cw && branches.some((b) => b.crowdPct != null);
  const lockedTeams = (cfg.locks || {})[String(week)] || [];
  const rows = shown.map((b, i) => {
    const locked = lockedTeams.length && b.teams.length === lockedTeams.length && b.teams.every((t) => lockedTeams.includes(t));
    const first = b.path[0];
    const pickCells = b.teams.map((t, k) => { const g = game(first.gameIds[k]); return `<div><span class="display-s">${esc(teamCity(t))}</span> <span class="code muted">${esc(t)}</span> <span class="small muted">${first.home[k] ? 'v' : '@'} ${esc(first.opponents[k])}</span> <span class="data muted">${gameLine(g, t)}</span></div>`; }).join('');
    const dv = planH == null || b.recommended ? null : (b.pHorizon - planH) * 100;
    const dead = b.pHorizon != null && b.pHorizon <= 1e-9;
    const path = b.path.slice(1).map((wp) => pathTile(e.name, wp, cfg)).join('');
    const action = locked ? `<button class="text-btn" data-act="unlock" data-entry="${esc(e.name)}" data-week="${week}">■ Locked · Unlock</button>` : dead ? '' : `<button class="text-btn" data-act="lock" data-entry="${esc(e.name)}" data-week="${week}" data-teams="${esc(b.teams.join('+'))}">Lock</button>`;
    return `<tr class="${b.recommended ? 'plan' : ''} ${locked ? 'locked' : ''}"><td class="code">${b.recommended ? '●' : i + 1}</td><td>${pickCells}</td><td class="num">${fig(b.p, 's', 'win')}</td>${showCrowd ? `<td class="num data">${b.crowdPct == null ? '—' : b.crowdPct.toFixed(0)}</td>` : ''}<td class="num">${dead ? '<span class="tag p1">Dead end</span>' : fig(b.pHorizon, 's', 'survival')}</td><td class="num data">${dv == null ? '—' : `<span style="color:var(--${dv >= 0 ? 'p4' : 'p1'})">${signed(dv)}</span>`}</td><td><div class="path">${path}</div></td><td class="num">${action}</td></tr>`;
  }).join('');
  const all = Object.keys(d.teams);
  const covered = new Set(branches.flatMap((b) => b.teams));
  const usedN = (cfg.used || []).length, byeN = wi ? wi.byes.length : 0;
  const excluded = all.filter((t) => !covered.has(t));
  const excl = `<div class="excluded">${excluded.length} teams not available: used ${usedN} · bye ${byeN} · other ${Math.max(0, excluded.length - usedN - byeN)} <button class="text-btn" data-act="show-excluded">${S.ui.showExcluded ? 'Hide' : 'Show'}</button>${S.ui.showExcluded ? `<div class="data" style="margin-top:4px">${excluded.map((t) => `<span style="margin-right:8px">${esc(t)}${(cfg.used || []).includes(t) ? ' <span class="muted">used</span>' : wi && wi.byes.includes(t) ? ' <span class="muted">bye</span>' : ''}</span>`).join('')}</div>` : ''}</div>`;
  const cols = `<colgroup><col style="width:52px"><col style="width:${inDrawer ? 220 : 320}px"><col style="width:88px">${showCrowd ? '<col style="width:64px">' : ''}<col style="width:110px"><col style="width:64px"><col><col style="width:120px"></colgroup>`;
  return head + `<div class="ledger-wrap"><table class="ledger">${cols}<thead><tr><th>Rank</th><th>Pick</th><th class="num">Win %</th>${showCrowd ? '<th class="num">Crowd</th>' : ''}<th class="num">Survive → W${H}</th><th class="num">Δ</th><th>Path after W${week}</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>${excl}`;
}
function pathTile(entryName, wp, cfg) {
  const ps = wp.teams.map((t, i) => teamP(wp.gameIds[i], t));
  const locked = !!((cfg.locks || {})[String(wp.week)]);
  const ov = hasOverride(wp.gameIds);
  const title = `W${wp.week} · ${wp.teams.map((t, i) => `${t} ${wp.home[i] ? 'v' : '@'} ${wp.opponents[i]} ${pct(ps[i])}`).join(' + ')}`;
  if (wp.teams.length > 1) return `<span class="ptile two ${tone(ps[0])} ${locked ? 'locked' : ''} ${ov ? 'override' : ''}" style="--tone2-fill:var(--${tone(ps[1]).replace('tone-', '')}-fill)" title="${esc(title)}">${esc(wp.teams[0])}<span class="h">${esc(wp.teams[1])}</span></span>`;
  return `<span class="ptile ${tone(ps[0])} ${locked ? 'locked' : ''} ${ov ? 'override' : ''}" title="${esc(title)}">${esc(wp.teams[0] || '—')}</span>`;
}
function viewBranches() {
  const d = S.dash;
  const entry = S.route.entry || (d.entries.find((e) => e.alive) || d.entries[0]).name;
  const week = S.route.week || S.ui.focusWeek || d.meta.currentWeek;
  return `<div class="view-head"><div><div class="folio">Branches</div><div class="sub">every alternative pick, each with its fully re-optimized path to the horizon</div></div></div>` + branchesContent(entry, week, false);
}

/* ================================================================ Schedule */
function viewSchedule() {
  const d = S.dash, c = S.config, cw = d.meta.currentWeek;
  const focus = S.ui.focusWeek || cw;
  const mode = S.ui.scheduleWeek === 'all' ? 'all' : 'focus';
  const weeks = mode === 'all' ? d.weeks : d.weeks.filter((w) => w.week === focus);
  const ovrCount = Object.keys(c.overrides || {}).length;
  const filters = `<div class="filters">
      <span class="stepper"><button data-act="week-step" data-dir="-1">−</button><span>W${focus}</span><button data-act="week-step" data-dir="1">+</button></span>
      <button class="ftog" data-act="sched-week" data-mode="focus" aria-pressed="${mode === 'focus'}">Week</button><button class="ftog" data-act="sched-week" data-mode="all" aria-pressed="${mode === 'all'}">All weeks</button>
      <span class="divider"></span>
      ${['all', 'picks', 'live'].map((m) => `<button class="ftog" data-act="sched-filter" data-mode="${m}" aria-pressed="${S.ui.scheduleFilter === m}">${{ all: 'All', picks: 'My picks', live: 'Live' }[m]}</button>`).join('')}
      <input type="search" placeholder="team /" value="${esc(S.ui.teamSearch)}" data-act="team-search" aria-label="team search">
      <span class="spacer"></span>
      ${ovrCount ? `<span class="plum">${ovrCount} what-if${ovrCount === 1 ? '' : 's'}</span><button class="text-btn danger" data-act="clear-overrides">Clear all</button>` : '<span class="muted">What-if: assume a result. The game counts as decided, so only an entry that locked it can still hold that team.</span>'}
    </div>`;
  const groups = weeks.map((w) => {
    let games = w.gameIds.map(game).filter(Boolean);
    if (S.ui.scheduleFilter === 'picks') games = games.filter((g) => g.picks && g.picks.length);
    if (S.ui.scheduleFilter === 'live') games = games.filter((g) => g.status === 'in_progress');
    if (S.ui.teamSearch) games = games.filter((g) => g.home.includes(S.ui.teamSearch) || g.away.includes(S.ui.teamSearch) || teamCity(g.home).toUpperCase().includes(S.ui.teamSearch) || teamCity(g.away).toUpperCase().includes(S.ui.teamSearch));
    games.sort((a, b) => (a.kickoff || '').localeCompare(b.kickoff || ''));
    const finals = w.gameIds.map(game).filter((g) => g && g.status === 'final').length;
    const live = w.gameIds.map(game).filter((g) => g && g.status === 'in_progress').length;
    const head = `<tr class="week-head"><td colspan="12"><span class="display-s">Week ${w.week}</span> <span class="data muted">${esc(weekRange(w))} · ${w.gameIds.length} games${finals ? ` · ${finals} final` : ''}${live ? ` · ${live} live` : ''}${w.picksRequired > 1 ? ' · two picks' : ''}</span>${w.byes.length ? `<span class="data muted" style="margin-left:16px">BYE ${esc(w.byes.join(' · '))}</span>` : ''}</td></tr>`;
    const rows = games.map(scheduleRow).join('') || `<tr><td colspan="12" class="muted">No games match.</td></tr>`;
    return head + rows;
  }).join('');
  return `<div class="view-head"><div><div class="folio">Schedule</div><div class="sub">every game · lines, probabilities, scores and your picks</div></div></div>${filters}
    <div class="ledger-wrap"><table class="ledger"><colgroup><col style="width:104px"><col style="width:190px"><col style="width:24px"><col style="width:190px"><col style="width:72px"><col style="width:120px"><col style="width:120px"><col style="width:64px"><col style="width:150px"><col style="width:80px"><col style="width:120px"></colgroup>
      <thead><tr><th>Kickoff</th><th>Away</th><th></th><th>Home</th><th class="num">Spread</th><th class="num">ML A / ML H</th><th>Win % (fav)</th><th>Src</th><th>Score / status</th><th>Picks</th><th>What-if</th></tr></thead><tbody>${groups}</tbody></table></div>`;
}
function pickSquares(g, code) {
  return (g.picks || []).filter((p) => p.team === code).map((p) => {
    const lk = isLocked(p.entry, g.week, [code]);
    const lost = g.status === 'final' && ((g.home === code && g.homeScore <= g.awayScore) || (g.away === code && g.awayScore <= g.homeScore));
    return `<span class="pick-sq ${entryClass(p.entry)} ${lk ? 'locked' : ''} ${lost ? 'lost' : ''}" title="Entry ${esc(p.entry)} · ${lk ? 'locked' : 'planned'}">${esc(p.entry)}</span>`;
  }).join('');
}
function scheduleRow(g) {
  const live = g.status === 'in_progress', final = g.status === 'final';
  const ovr = g.override;
  const favHome = g.pHome >= 0.5; const fav = favHome ? g.home : g.away; const favP = favHome ? g.pHome : 1 - g.pHome;
  let kick = g.timeValid === false ? '<span class="faint">TBD</span>' : esc(fmtKick(g.kickoff));
  if (live) kick = `<span class="live"><span class="dot"></span>${esc(g.statusDetail || 'LIVE')}</span>`;
  else if (final) kick = '<span class="tag">Final</span>';
  else if (g.status === 'postponed') kick = '<span class="faint">TBD</span>';
  let score = '—';
  if (live || final) {
    const hw = (g.homeScore ?? 0) > (g.awayScore ?? 0), aw = (g.awayScore ?? 0) > (g.homeScore ?? 0);
    score = `<span class="score"><span class="${aw ? 'w' : 'l'}">${g.awayScore ?? 0}</span> <span class="muted">–</span> <span class="${hw ? 'w' : 'l'}">${g.homeScore ?? 0}</span></span>${final ? ' <span class="tag muted">final</span>' : ` <span class="data muted">${esc(g.clock || '')}</span>`}`;
  } else if (g.headline) score = `<span class="small muted">${esc(g.headline)}</span>`;
  let win;
  if (final) { const winner = g.homeScore > g.awayScore ? g.home : g.awayScore > g.homeScore ? g.away : null; win = winner ? `<span class="code">${esc(winner)}</span> <span class="tag">W</span>` : '<span class="tag">Tie</span>'; }
  else if (ovr) win = `<span class="code plum">${esc(ovr === 'home' ? g.home : g.away)} ↑</span> ${fig(1, 'xs', 'win', { tone: 'tone-override', decimals: 0 })}`;
  else win = `<span class="code">${esc(fav)}</span> ${fig(favP, 'xs', 'win', { title: `${fav} ${pct(favP)} · raw ${pct(favHome ? g.pHomeRaw : 1 - g.pHomeRaw)} · ${srcLabel(g.source)}` })}`;
  const src = ovr ? 'manual' : g.source === 'moneyline' ? 'book' : g.source === 'spread' ? 'spread' : g.source === 'rating' ? 'model' : g.source;
  const disabled = live || final || g.status === 'postponed';
  const seg = `<span class="seg"><button data-act="override" data-game="${esc(g.id)}" data-side="away" aria-pressed="${ovr === 'away'}" ${disabled ? 'disabled' : ''} title="Force ${esc(g.away)} to win">Awy</button><button data-act="override" data-game="${esc(g.id)}" data-side="" aria-pressed="${!ovr}" ${disabled ? 'disabled' : ''} title="No override">—</button><button data-act="override" data-game="${esc(g.id)}" data-side="home" aria-pressed="${ovr === 'home'}" ${disabled ? 'disabled' : ''} title="Force ${esc(g.home)} to win">Hom</button></span>`;
  const teamCell = (code) => `${pickSquares(g, code)}<a class="code" href="#/teams/${esc(code)}">${esc(code)}</a> <span class="team-name">${esc(teamCity(code))}</span>`;
  const spread = g.spread == null ? '—' : g.spread === 0 ? 'PK' : minus(String(-g.spread));
  return `<tr class="${live ? 'live' : ''} ${final ? 'final' : ''} ${ovr ? 'override' : ''}"><td class="data">${kick}${g.neutral ? ' <span class="data-s muted">N</span>' : ''}</td><td>${teamCell(g.away)}</td><td class="muted">@</td><td>${teamCell(g.home)}</td><td class="num data">${spread}</td><td class="num data">${ml(g.awayMoneyline)} / ${ml(g.homeMoneyline)}</td><td>${win}</td><td class="data-s muted">${esc(src)}</td><td>${score}</td><td>${(g.picks || []).map((p) => `<span class="pick-sq ${entryClass(p.entry)} ${isLocked(p.entry, g.week, [p.team]) ? 'locked' : ''}" title="${esc(p.entry)} on ${esc(p.team)}">${esc(p.entry)}</span>`).join('')}</td><td>${seg}</td></tr>`;
}

/* ================================================================ Teams */
function viewTeams() {
  const d = S.dash, c = S.config, cw = d.meta.currentWeek;
  const codes = Object.keys(d.teams).sort();
  const code = codes.includes(S.route.team) ? S.route.team : ((d.entries[0] && d.entries[0].plan && d.entries[0].plan[0] && d.entries[0].plan[0].teams[0]) || codes[0]);
  const t = d.teams[code];
  const opts = codes.map((k) => `<option value="${k}" ${k === code ? 'selected' : ''}>${esc(d.teams[k].displayName || d.teams[k].name)}</option>`).join('');
  const bye = (t.schedule.find((s) => s.bye) || {}).week;
  const next = t.schedule.find((s) => !s.bye && s.week >= cw && s.status !== 'final');
  const usedBy = d.entries.filter((e) => (e.used || []).includes(code)).map((e) => `<span class="${entryClass(e.name)} entry-color">${esc(e.name)}</span> used`);
  const planned = d.entries.flatMap((e) => (e.plan || []).filter((p) => p.teams.includes(code)).map((p) => `<span class="${entryClass(e.name)} entry-color">${esc(e.name)}</span> · W${p.week}${p.locked ? ' (locked)' : ''}`));
  const eff = (t.stats && t.stats.efficiency) || {};
  const rec = t.record || {};
  const inj = t.injuryImpact || 0;
  const head = `<div class="view-head"><div><div class="folio">Teams</div><div class="sub">rating, injuries, stats and the remaining schedule as a probability strip</div></div>
      <div class="tools"><span class="stepper"><button data-act="team-prev">←</button><span class="sel"><select data-act="set-team" style="border:0;background:transparent;min-width:220px">${opts}</select></span><button data-act="team-next">→</button></span></div></div>
    <div class="team-head"><div>
      <div class="name"><img src="${esc(t.logo)}" alt="" loading="lazy" onerror="this.style.display='none'">${esc(t.displayName || t.name)} <span class="code">${esc(code)} · ${esc(rec.summary || '0-0')}${rec.streak ? ` · ${esc(rec.streak)}` : ''}</span></div>
      <div class="kicker label muted" style="margin-top:6px">${bye ? `Bye W${bye}` : ''}${t.qb1 ? ` · QB ${esc(t.qb1)}` : ''} · last season ${esc((t.stats.lastSeason || {}).record || '—')}</div>
      <div class="statrow">
        <div><span class="label">Rating (pts)</span><span class="v">${t.rating == null ? '—' : signed(t.rating, 1)}</span></div>
        <div><span class="label">Injury impact</span><span class="v ${inj <= -1 ? 'tone-p1' : inj < 0 ? 'tone-p2' : 'tone-p3'}" style="color:var(--tone)">${signed(inj, 1)}</span><span class="magrule" style="--v:${Math.min(100, Math.abs(inj) * 11)}"></span></div>
        <div><span class="label">Next ${next ? `W${next.week} ${next.home ? 'vs' : '@'} ${esc(next.opponent)}` : ''}</span>${next ? fig(next.p, 'm', 'win') : '<span class="v">—</span>'}</div>
        <div><span class="label">Off / Def EPA per play (${esc(String(t.stats.efficiencySeason || ''))})</span><span class="v data" style="font-size:20px">${eff.offEpaPerPlay == null ? '—' : signed(eff.offEpaPerPlay, 3)} / ${eff.defEpaPerPlay == null ? '—' : signed(eff.defEpaPerPlay, 3)}</span></div>
      </div></div>
      <div class="uselist"><span class="label">Used by</span>${usedBy.length ? usedBy.join('<br>') : '<span class="muted">nobody</span>'}<br><br><span class="label">Planned</span>${planned.length ? planned.join('<br>') : '<span class="muted">not in any plan</span>'}</div></div>`;
  const heat = `<div class="section-title">Schedule <span class="label">win probability by week · click for branches</span></div>
    <div class="heat" style="--n:${t.schedule.length}">${t.schedule.map((s) => heatTile(code, s)).join('')}</div><div class="heat-readout" id="heat-readout" data-default="hover a week for details"></div>`;
  const injuries = (t.injuries || []).length ? `<div class="ledger-wrap"><table class="ledger"><colgroup><col style="width:44px"><col><col style="width:110px"><col style="width:120px"><col style="width:90px"><col style="width:90px"><col style="width:70px"></colgroup>
      <thead><tr><th>Pos</th><th>Player</th><th>Status</th><th>Injury</th><th class="num">Impact</th><th>Return</th><th>Updated</th></tr></thead><tbody>
      ${t.injuries.map((i) => { const st = i.status.toLowerCase(); const cls = /out|reserve|susp/.test(st) ? 'p1' : /doubt/.test(st) ? 'p2' : /quest/.test(st) ? 'p3' : 'p4'; return `<tr class="${(i.impact || 0) <= -0.5 ? 'hurt' : ''}"><td class="data-s muted">${esc(i.position)}</td><td><span class="strong">${esc(i.player)}</span>${i.isStarterQb ? ' <span class="tag p1">QB1</span>' : ''}<div class="small muted" style="white-space:normal">${esc((i.comment || '').slice(0, 140))}</div></td><td><span class="tag ${cls}">${esc(i.status)}</span></td><td class="small">${esc(i.detail || '')}</td><td class="num data ${(i.impact || 0) <= -0.5 ? 'tone-p1' : ''}" style="color:var(--tone, inherit)">${i.impact == null ? '—' : signed(i.impact, 1)}</td><td class="data-s muted">${esc(i.returnDate || '')}</td><td class="data-s muted">${esc(relShort(i.updated))}</td></tr>`; }).join('')}
      </tbody></table></div>` : emptyBlock('No reported injuries.', 'ESPN lists nobody out, doubtful, questionable, on IR or suspended.');
  const st = t.stats || {}; const ls = st.lastSeason || {};
  const statRows = [
    ['Record', rec.summary || '0-0'], ['Points for / against', `${st.pointsFor ?? 0} / ${st.pointsAgainst ?? 0}`], ['Point differential', signed(st.pointDiff ?? 0, 0)],
    [`Last season`, `${ls.record || '—'} · diff ${ls.pointDiff == null ? '—' : signed(ls.pointDiff, 0)}`],
    [`Pass EPA / dropback (${st.efficiencySeason || ''})`, eff.passEpaPerDropback == null ? '—' : signed(eff.passEpaPerDropback, 3)],
    ['Rush EPA / carry', eff.rushEpaPerCarry == null ? '—' : signed(eff.rushEpaPerCarry, 3)],
    ['CPOE', eff.cpoe == null ? '—' : signed(eff.cpoe, 1)], ['Turnover margin', eff.turnoverMargin == null ? '—' : signed(eff.turnoverMargin, 0)],
    ['Sacks made / taken', `${eff.sacksMade ?? '—'} / ${eff.sacksTaken ?? '—'}`], ['Rating adjusted', t.ratingAdjusted == null ? '—' : signed(t.ratingAdjusted, 1)],
  ];
  const stats = `<table class="ledger"><colgroup><col><col style="width:150px"></colgroup><thead><tr><th>Stat</th><th class="num">Value</th></tr></thead><tbody>${statRows.map(([k, v]) => `<tr><td>${esc(k)}</td><td class="num data">${esc(v)}</td></tr>`).join('')}</tbody></table>`;
  const news = d.news.filter((n) => (n.teams || []).includes(code));
  return head + heat + `<div class="team-cols"><div><div class="section-title">Injuries <span class="label">sorted by status</span></div>${injuries}</div><div><div class="section-title">Stats</div>${stats}</div></div>
    <div class="section-title">News <span class="label">${news.length} tagged</span></div>${news.length ? news.map(newsRow).join('') : '<p class="muted small">No recent headlines tagged to this team.</p>'}`;
}
function heatTile(code, s) {
  if (s.bye) return `<div class="ht bye" data-readout="W${s.week} · bye"><span class="w">${s.week}</span><span class="o muted">BYE</span><span></span></div>`;
  const d = S.dash, cw = d.meta.currentWeek;
  const g = game(s.gameId);
  let cls = 'ht ' + tone(s.p);
  let mid = `<span class="o">${s.home ? 'vs' : '@'} ${esc(s.opponent)}</span>`;
  let bottom = fig(s.p, 'xs', 'win');
  if (s.status === 'final' && s.won != null) { cls = `ht ${s.won ? 'win' : 'loss'}`; bottom = `<span class="data">${s.won ? 'W' : 'L'} ${g ? `${g.awayScore}–${g.homeScore}` : ''}</span>`; }
  const pickers = d.entries.filter((e) => (e.plan || []).some((p) => p.week === s.week && p.teams.includes(code)));
  const locked = pickers.some((e) => isLocked(e.name, s.week, [code]));
  if (pickers.length) cls += ` ${entryClass(pickers[0].name)} ${locked ? 'locked' : 'planned'}`;
  const usedBy = d.entries.find((e) => (e.used || []).includes(code));
  if (usedBy && s.week >= cw) cls += ` usedby ${entryClass(usedBy.name)}`;
  if (g && g.override) cls += ' override';
  const readout = `W${s.week} · ${s.home ? 'vs' : '@'} ${s.opponent} · ${fmtKick(g && g.kickoff)} · ${g ? spreadTxt(g, code) : ''} · ${pct(s.p)} ${srcLabel(s.source)} (raw ${pct(s.pRaw)})${pickers.length ? ` · planned by ${pickers.map((e) => e.name).join(', ')}` : ''}`;
  return `<div class="${cls}" data-act="open-branches" data-entry="${esc(pickers.length ? pickers[0].name : (d.entries.find((e) => e.alive) || d.entries[0] || {}).name || '')}" data-week="${s.week}" data-readout="${esc(readout)}"><span class="w">${s.week}</span>${mid}${bottom}</div>`;
}

/* ================================================================ News */
function newsRow(n) {
  const d = S.dash, cw = d.meta.currentWeek;
  const mine = d.entries.filter((e) => (planAt(e, cw) || { teams: [] }).teams.some((t) => (n.teams || []).includes(t)));
  const kind = n.kind === 'injury' ? '<span class="tag p1">Injury</span>' : n.kind === 'transaction' ? '<span class="tag p3">Transaction</span>' : '<span class="tag muted">News</span>';
  return `<div class="news-row ${mine.length ? 'mine ' + entryClass(mine[0].name) : ''}"><div class="t">${esc(relShort(n.published))}</div><div>
      <a class="h" href="${esc(n.url || '#')}" target="_blank" rel="noopener">${esc(n.headline)}</a>
      <div class="d">${esc(n.description || '')}</div>
      <div class="m"><span class="teams">${(n.teams || []).map((t) => `<button data-act="news-team" value="${esc(t)}">${esc(t)}</button>`).join(' · ')}${n.leagueWide ? 'league-wide' : ''}</span>${kind}<span>${esc(n.byline || n.type || '')}</span>${mine.length ? `<span class="${entryClass(mine[0].name)} entry-color">affects ${mine.map((e) => e.name).join(', ')}</span>` : ''}</div></div></div>`;
}
function viewNews() {
  const d = S.dash, cw = d.meta.currentWeek;
  const myTeams = new Set(d.entries.flatMap((e) => (planAt(e, cw) || { teams: [] }).teams));
  let items = d.news.slice();
  if (S.ui.newsFilter === 'mine') items = items.filter((n) => (n.teams || []).some((t) => myTeams.has(t)));
  if (S.ui.newsFilter === 'injury') items = items.filter((n) => n.kind === 'injury');
  if (S.ui.newsFilter === 'transaction') items = items.filter((n) => n.kind === 'transaction');
  if (S.ui.newsTeam) items = items.filter((n) => (n.teams || []).includes(S.ui.newsTeam));
  const codes = Object.keys(d.teams).sort();
  const filters = `<div class="filters">${[['all', 'All'], ['mine', 'My teams this week'], ['injury', 'Injuries'], ['transaction', 'Transactions']].map(([m, l]) => `<button class="ftog" data-act="news-filter" data-mode="${m}" aria-pressed="${S.ui.newsFilter === m}">${l}</button>`).join('')}
      <label class="ctl"><span class="k">Team</span><span class="sel"><select data-act="news-team"><option value="">all</option>${codes.map((k) => `<option value="${k}" ${S.ui.newsTeam === k ? 'selected' : ''}>${k}</option>`).join('')}</select></span></label>
      <span class="spacer"></span><span class="data-s muted">ESPN · ${d.news.length} items · fetched ${rel((d.meta.dataAge || {}).news)} ago</span></div>`;
  return `<div class="view-head"><div><div class="folio">News</div><div class="sub">headlines tagged by team; injury items flagged by keyword</div></div></div>${filters}
    <div style="max-width:1040px">${items.length ? items.map(newsRow).join('') : emptyBlock('Nothing here.', 'No headlines match the current filter.')}</div>`;
}

/* ================================================================ drawers */
function renderDrawer() {
  const el = $('#drawer');
  const dr = S.ui.drawer;
  if (!dr || !S.dash) { el.hidden = true; el.innerHTML = ''; return; }
  let html = '';
  if (dr.type === 'branches') {
    html = `<div class="dhead"><div><span class="label muted">Branch picker</span></div><button class="text-btn" data-act="close-drawer">Close ✕</button></div><div class="dbody">${branchesContent(dr.entry, dr.week, true)}</div>`;
    el.className = 'drawer';
  } else if (dr.type === 'entries') {
    const codes = Object.keys(S.dash.teams).sort();
    const blocks = dr.draft.map((e, idx) => `<div class="entry-block ${ENTRY_CLASSES[idx % ENTRY_CLASSES.length]}">
        <div class="eh"><input class="name" value="${esc(e.name)}" data-act="entry-name" data-idx="${idx}" maxlength="12" aria-label="entry name">
          <button class="toggle" data-act="entry-alive" data-idx="${idx}" aria-pressed="${e.alive !== false}"></button><span class="tog-label">Alive</span>
          <span class="spacer" style="flex:1"></span><span class="data-s muted">${(e.used || []).length} used</span><button class="text-btn danger" data-act="entry-remove" data-idx="${idx}">Remove</button></div>
        <div class="label muted" style="margin:8px 0 4px">Used teams</div>
        <div class="teamgrid">${codes.map((t) => `<button data-act="entry-used" data-idx="${idx}" data-team="${t}" aria-pressed="${(e.used || []).includes(t)}" title="${esc(S.dash.teams[t].displayName || t)}">${t}</button>`).join('')}</div>
        ${Object.keys(e.locks || {}).length ? `<div class="data-s muted" style="margin-top:8px">locks: ${Object.entries(e.locks).map(([w, t]) => `W${w} ${t.join('+')}`).join(' · ')} <button class="text-btn" data-act="entry-clear-locks" data-idx="${idx}">clear</button></div>` : ''}
      </div>`).join('');
    html = `<div class="dhead"><div class="display-s">Entries</div><button class="text-btn" data-act="close-drawer">Close ✕</button></div>
      <div class="dbody">${blocks}<div style="padding:16px 0">${dr.draft.length < 5 ? '<button class="btn-secondary" data-act="entry-add">Add entry</button>' : ''}</div></div>
      <div class="dfoot"><button class="btn-primary" data-act="entries-save">Save and re-plan</button><button class="text-btn" data-act="close-drawer">Cancel</button><span class="data-s muted" style="margin-left:auto">used = burned in an earlier week</span></div>`;
    el.className = 'drawer narrow';
  } else if (dr.type === 'crowd') {
    const wi = weekInfo(dr.week);
    const teams = wi ? wi.gameIds.flatMap((id) => { const g = game(id); return g ? [g.away, g.home] : []; }).sort() : [];
    const total = Object.values(dr.draft).reduce((a, b) => a + (Number(b) || 0), 0);
    html = `<div class="dhead"><div><div class="display-s">Crowd picks · Week ${dr.week}</div><div class="small muted">Share of the pool on each team. Used for the contrarian adjustment (weight ${Number(S.config.contrarianWeight).toFixed(2)}).</div></div><button class="text-btn" data-act="close-drawer">Close ✕</button></div>
      <div class="dbody"><div class="crowd-grid" style="padding-top:12px">${teams.map((t) => `<label><span>${t}</span><input type="number" min="0" max="100" step="0.5" value="${dr.draft[t] ?? ''}" data-act="crowd-input" data-team="${t}" placeholder="%"></label>`).join('')}</div>
        <p class="small muted">Total ${total.toFixed(1)}% · leave blank for 0. Sources: your pool site, or public consensus.</p></div>
      <div class="dfoot"><button class="btn-primary" data-act="crowd-save">Save and re-plan</button><button class="text-btn" data-act="crowd-clear">Clear</button><button class="text-btn" data-act="close-drawer">Cancel</button></div>`;
    el.className = 'drawer narrow';
  }
  el.innerHTML = html;
  el.hidden = false;
}

window.onDrawerAction = function (act, el) {
  const dr = S.ui.drawer; if (!dr) return;
  const idx = el.dataset.idx != null ? Number(el.dataset.idx) : null;
  switch (act) {
    case 'entry-name': dr.draft[idx].name = el.value.trim().slice(0, 12) || dr.draft[idx].name; break;
    case 'entry-alive': dr.draft[idx].alive = el.getAttribute('aria-pressed') !== 'true'; renderDrawer(); break;
    case 'entry-used': { const e = dr.draft[idx]; e.used = e.used || []; const t = el.dataset.team; if (e.used.includes(t)) e.used = e.used.filter((x) => x !== t); else e.used.push(t); renderDrawer(); break; }
    case 'entry-clear-locks': dr.draft[idx].locks = {}; renderDrawer(); break;
    case 'entry-remove': dr.draft.splice(idx, 1); renderDrawer(); break;
    case 'entry-add': { const names = new Set(dr.draft.map((e) => e.name)); let n = 'A'; while (names.has(n)) n = String.fromCharCode(n.charCodeAt(0) + 1); dr.draft.push({ name: n, used: [], locks: {}, alive: true }); renderDrawer(); break; }
    case 'entries-save': { const draft = dr.draft; S.ui.drawer = null; renderDrawer(); mutate((c) => { c.entries = draft; }, { toast: 'Entries saved' }); break; }
    case 'crowd-input': { const v = Number(el.value); if (el.value === '' || Number.isNaN(v) || v <= 0) delete dr.draft[el.dataset.team]; else dr.draft[el.dataset.team] = v; break; }
    case 'crowd-clear': dr.draft = {}; renderDrawer(); break;
    case 'crowd-save': { const wk = String(dr.week), draft = dr.draft; S.ui.drawer = null; renderDrawer(); mutate((c) => { c.pickPct = c.pickPct || {}; if (Object.keys(draft).length) c.pickPct[wk] = draft; else delete c.pickPct[wk]; }, { toast: `Crowd picks saved for W${wk}` }); break; }
    default: break;
  }
};
