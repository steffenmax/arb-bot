/* Survivor dashboard — core: state, API, routing, chrome (masthead, rail, banner, toast). */
'use strict';

const S = window.S = {
  config: null, dash: null, lastGood: null, loading: false, error: null, refreshing: false,
  route: { view: 'week', entry: null, week: null, team: null, q: {} },
  ui: { focusWeek: null, drawer: null, scheduleWeek: 'focus', scheduleFilter: 'all', teamSearch: '',
        newsFilter: 'all', newsTeam: '', sort: 'survive', hideLow: false, showExcluded: false, chartWeek: null,
        dismissedBanner: null, shortcuts: false },
  prevJoint: null, undo: null, toastTimer: null, gameMap: new Map(), teamIndex: [],
  mock: new URLSearchParams(location.search).get('mock') === '1',
};

const VIEWS = [
  ['week', 'This Week'], ['plan', 'Season Plan'], ['branches', 'Branches'],
  ['schedule', 'Schedule'], ['teams', 'Teams'], ['news', 'News'],
];
const ENTRY_CLASSES = ['entry-a', 'entry-b', 'entry-c', 'entry-d', 'entry-e'];
const DECAY_OPTIONS = [0, 0.01, 0.02, 0.03, 0.05, 0.08];
const OBJECTIVES = { any: 'E[weeks ≥1]', final: 'P(≥1 at H)', expected: 'E[alive]' };
const CONTRARIAN = [0, 0.5, 1, 1.5, 2];

/* ---------------------------------------------------------------- utils */
const $ = (sel, el = document) => el.querySelector(sel);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const pct = (x, d = 1) => (x == null || Number.isNaN(x)) ? '—' : (100 * x).toFixed(d);
const signed = (x, d = 1) => x == null ? '—' : (x > 0 ? '+' : x < 0 ? '−' : '') + Math.abs(x).toFixed(d);
const minus = (s) => String(s).replace('-', '−');
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));

function tone(v, kind = 'win') {
  if (v == null || Number.isNaN(v)) return 'tone-none';
  const p = v * 100;
  if (kind === 'survival') return p < 5 ? 'tone-p1' : p < 10 ? 'tone-p2' : p < 15 ? 'tone-p3' : p < 25 ? 'tone-p4' : 'tone-p5';
  return p < 50 ? 'tone-p1' : p < 60 ? 'tone-p2' : p < 68 ? 'tone-p3' : p < 78 ? 'tone-p4' : 'tone-p5';
}
/* The Ruled Figure: a serif numeral with a rule beneath whose length is the value. */
function fig(v, size = 's', kind = 'win', opts = {}) {
  const cls = ['fig', 'fig-' + size, opts.tone || tone(v, kind), opts.inverse ? 'inverse' : '', opts.plain ? 'plain' : '', v == null ? 'dim' : ''].filter(Boolean).join(' ');
  const val = v == null ? '—' : pct(v, opts.decimals ?? 1);
  const sup = opts.sup ? '<sup>%</sup>' : '';
  const title = opts.title ? ` title="${esc(opts.title)}"` : '';
  return `<span class="${cls}" style="--v:${v == null ? 0 : (100 * v).toFixed(2)}"${title}><b>${val}${sup}</b><i></i></span>`;
}
function entryClass(name) {
  const i = S.teamIndex.indexOf(name);
  return ENTRY_CLASSES[(i < 0 ? 0 : i) % ENTRY_CLASSES.length];
}
function team(code) { return (S.dash && S.dash.teams[code]) || { code, name: code, city: '', color: '#444', logo: '' }; }
function teamCity(code) { const t = team(code); return t.city ? t.city : t.name; }
function game(id) { return S.gameMap.get(id); }
function teamP(gameId, code) { const g = game(gameId); if (!g || g.pHome == null) return null; return g.home === code ? g.pHome : 1 - g.pHome; }
function teamPRaw(gameId, code) { const g = game(gameId); if (!g || g.pHomeRaw == null) return null; return g.home === code ? g.pHomeRaw : 1 - g.pHomeRaw; }
function weekIdx(week) { const w = S.dash.joint.weeks; const i = w.indexOf(week); return i; }
function entryByName(name) { return S.dash.entries.find((e) => e.name === name); }
function cfgEntry(name) { return S.config.entries.find((e) => e.name === name); }
function fmtKick(iso, style = 'short') {
  if (!iso) return 'TBD';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 'TBD';
  const day = d.toLocaleDateString('en-US', { weekday: 'short', timeZone: 'America/New_York' });
  let t = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', timeZone: 'America/New_York' }).toLowerCase();
  t = t.replace(' am', 'a').replace(' pm', 'p');
  if (style === 'long') return `${day} ${d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'America/New_York' })} ${t} ET`;
  return `${day} ${t}`;
}
function fmtDate(iso) { if (!iso) return ''; const d = new Date(iso + (iso.length <= 10 ? 'T12:00:00' : '')); return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }); }
function ageMinutes(iso) { if (!iso) return null; const t = new Date(iso).getTime(); if (Number.isNaN(t)) return null; return Math.max(0, (Date.now() - t) / 60000); }
function rel(iso) {
  const m = ageMinutes(iso);
  if (m == null) return '—';
  if (m < 1) return 'now';
  if (m < 60) return `${Math.round(m)}m`;
  if (m < 60 * 36) { const h = Math.floor(m / 60); const mm = Math.round(m % 60); return mm ? `${h}h ${mm}m` : `${h}h`; }
  return `${Math.round(m / 1440)}d`;
}
function relShort(iso) { const m = ageMinutes(iso); if (m == null) return ''; if (m < 60) return `${Math.round(m)}m ago`; if (m < 1440) return `${Math.floor(m / 60)}h ago`; return fmtDate(iso); }
function srcLabel(s) { return { moneyline: 'book ML', spread: 'book spread', rating: 'model', final: 'final', live: 'live', override: 'manual' }[s] || s || '—'; }
function ml(v) { if (v == null) return '—'; return v > 0 ? `+${v}` : minus(String(v)); }
function spreadTxt(g, code) {
  if (!g || g.spread == null) return '—';
  const s = g.home === code ? -g.spread : g.spread;   // negative = this team favored
  if (s === 0) return 'PK';
  return minus(s > 0 ? `+${s}` : String(s));
}
function effOverride(gameId) { const g = game(gameId); return g && g.source === 'override' ? g.override : null; }
function hasOverride(gameIds) { return (gameIds || []).some((id) => effOverride(id)); }
function effectiveOverrideCount() { return Object.keys(S.config.overrides || {}).filter((id) => effOverride(id)).length; }
function snapshotConfig() { return JSON.parse(JSON.stringify(S.config)); }
function isWide() { return window.innerWidth >= 1024; }

/* ---------------------------------------------------------------- API */
async function api(method, path, body) {
  const r = await fetch(path, { method, headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `${r.status} ${r.statusText}`);
  return j;
}
async function loadConfig() {
  if (S.mock) { S.config = { entries: [{ name: 'A', used: [], locks: {}, alive: true }, { name: 'B', used: [], locks: {}, alive: true }, { name: 'C', used: [], locks: {}, alive: true }], picksPerWeek: {}, horizon: 18, decay: 0.03, objective: 'any', topBranches: 10, contrarianWeight: 1, hedge: 0.1, pickPct: {}, overrides: {}, injuryAdjust: true }; return; }
  S.config = await api('GET', '/api/config');
}
let runTimer = null;
function scheduleRun(opts) { clearTimeout(runTimer); S.pending = true; runTimer = setTimeout(() => run(opts), 300); }
async function run(opts = {}) {
  clearTimeout(runTimer);
  S.pending = false;
  S.loading = true; renderChrome();
  try {
    let d;
    if (S.mock) {
      const r = await fetch('mock-dashboard.json'); if (!r.ok) throw new Error('mock-dashboard.json missing');
      d = await r.json(); d.config = { ...d.config, ...S.config };
    } else {
      d = await api('POST', '/api/dashboard', S.config);
    }
    S.prevJoint = S.dash ? S.dash.joint : null;
    S.dash = d; S.lastGood = d; S.error = null;
    S.config = JSON.parse(JSON.stringify(d.config));
    indexDash();
    if (!S.mock && opts.save !== false) await api('PUT', '/api/config', S.config).catch(() => {});
    if (opts.toast) toast(opts.toast.msg, opts.toast.undo);
  } catch (e) {
    S.error = e.message || String(e);
    if (opts.revert) { S.config = opts.revert; toast(`Change rejected: ${S.error}`); }
    if (!S.dash && S.lastGood) S.dash = S.lastGood;
  }
  S.loading = false;
  renderAll();
}
function indexDash() {
  S.gameMap = new Map(S.dash.games.map((g) => [g.id, g]));
  S.teamIndex = S.dash.entries.map((e) => e.name);
  if (S.ui.focusWeek == null || S.ui.focusWeek < 1) S.ui.focusWeek = S.dash.meta.currentWeek;
}
async function refreshData() {
  if (S.refreshing) return;
  S.refreshing = true; renderChrome();
  try { if (!S.mock) await api('POST', '/api/refresh'); } catch (e) { S.error = e.message; }
  S.refreshing = false;
  await run({ save: false });
}

/* ---------------------------------------------------------------- config mutations */
function mutate(fn, opts = {}) {
  const before = snapshotConfig();
  fn(S.config);
  const undo = () => { S.config = before; run({ toast: null }); };
  scheduleRun({ toast: opts.toast ? { msg: opts.toast, undo } : null, revert: before });
  renderChrome();
}
function setLock(entryName, week, teams, msg) {
  mutate((c) => {
    const e = c.entries.find((x) => x.name === entryName); if (!e) return;
    e.locks = e.locks || {};
    if (teams && teams.length) e.locks[String(week)] = teams; else delete e.locks[String(week)];
  }, { toast: msg || (teams && teams.length ? `Locked ${teams.join(' + ')} for ${entryName} in W${week}` : `Unlocked ${entryName} in W${week}`) });
}
function setTwoPick(week, on) {
  mutate((c) => { c.picksPerWeek = c.picksPerWeek || {}; if (on) c.picksPerWeek[String(week)] = 2; else delete c.picksPerWeek[String(week)]; },
    { toast: on ? `Two picks required in W${week}` : `One pick in W${week}` });
}
function setOverride(gameId, side) {
  const g = game(gameId);
  mutate((c) => { c.overrides = c.overrides || {}; if (side) c.overrides[gameId] = side; else delete c.overrides[gameId]; },
    { toast: side ? `What-if: ${side === 'home' ? g.home : g.away} beats ${side === 'home' ? g.away : g.home} in W${g.week}` : `Cleared what-if for ${g.away} @ ${g.home}` });
}
function clearOverrides() { mutate((c) => { c.overrides = {}; }, { toast: 'Cleared all what-ifs' }); }
function useCombination(picks) {
  const wk = S.dash.meta.currentWeek;
  mutate((c) => { for (const [name, teams] of Object.entries(picks)) { const e = c.entries.find((x) => x.name === name); if (e) { e.locks = e.locks || {}; e.locks[String(wk)] = teams; } } },
    { toast: `Locked ${Object.entries(picks).map(([n, t]) => `${n} ${t.join('+')}`).join(' · ')} for W${wk}` });
}

/* ---------------------------------------------------------------- toast */
function toast(msg, undo) {
  const el = $('#toast');
  S.undo = undo || null;
  el.innerHTML = `<div class="toast-inner"><span>${esc(msg)}</span>${undo ? '<button class="tlink" data-act="undo">Undo</button>' : ''}<button class="tlink muted" data-act="toast-close" style="margin-left:auto">Dismiss</button></div>`;
  el.hidden = false;
  clearTimeout(S.toastTimer);
  S.toastTimer = setTimeout(() => { el.hidden = true; }, 6000);
}

/* ---------------------------------------------------------------- routing */
function parseRoute() {
  const h = location.hash.replace(/^#\/?/, '');
  const q = new URLSearchParams(location.search);
  const [pathPart, queryPart] = h.split('?');
  const parts = pathPart.split('/').filter(Boolean);
  const qp = Object.fromEntries(new URLSearchParams(queryPart || ''));
  let view = parts[0] || q.get('view') || 'week';
  if (view === 'this-week') view = 'week';
  if (!VIEWS.some(([k]) => k === view)) view = 'week';
  const r = { view, entry: null, week: null, team: null, q: qp };
  if (view === 'branches') { r.entry = parts[1] || null; r.week = parts[2] ? Number(parts[2]) : null; }
  else if (view === 'schedule') { r.week = parts[1] ? (parts[1] === 'all' ? 'all' : Number(parts[1])) : null; }
  else if (view === 'teams') { r.team = parts[1] || null; }
  else if (view === 'week' || view === 'plan') { r.week = parts[1] ? Number(parts[1]) : null; }
  S.route = r;
  if (r.week && r.week !== 'all' && !Number.isNaN(r.week)) S.ui.focusWeek = r.week;
  if (view === 'schedule' && r.week) S.ui.scheduleWeek = r.week === 'all' ? 'all' : 'focus';
  if (view === 'news' && qp.team) S.ui.newsTeam = qp.team;
}
function go(hash) { if (location.hash !== hash) location.hash = hash; else { parseRoute(); renderAll(); } }

/* ---------------------------------------------------------------- chrome */
function renderAll() { renderChrome(); renderView(); renderDrawer(); syncMastHeight(); }
function syncMastHeight() { const m = $('#mast'); if (m) document.documentElement.style.setProperty('--mast-h', m.offsetHeight + 'px'); }
function renderChrome() { renderMasthead(); renderRail(); renderBanner(); renderFoot(); syncMastHeight(); }

function renderMasthead() {
  const m = $('#mast');
  m.classList.toggle('loading', S.loading);
  const d = S.dash, c = S.config || {};
  $('#mast-season').textContent = d ? d.meta.season : '';
  const tabs = $('#tabs');
  tabs.innerHTML = VIEWS.map(([k, label]) => `<a href="#/${k}" class="${S.route.view === k ? 'active' : ''}" data-view="${k}">${label}</a>`).join('');
  const ctl = $('#controls');
  if (!d) { ctl.innerHTML = ''; return; }
  const cw = d.meta.currentWeek, max = d.meta.weeksInSeason;
  const withCurrent = (values, current, eq) => (values.some((v) => eq(v, current)) ? values : [...values, current].sort((x, y) => x - y));
  const horizonVals = withCurrent(Array.from({ length: max - cw + 1 }, (_, i) => cw + i), Number(c.horizon), (a, b) => a === b);
  const horizonOpts = horizonVals.map((w) => `<option value="${w}" ${c.horizon === w ? 'selected' : ''}>W${w}</option>`).join('');
  const decayVals = withCurrent(DECAY_OPTIONS, Number(c.decay ?? 0.03), (a, b) => Math.abs(a - b) < 1e-9);
  const decayOpts = decayVals.map((v) => `<option value="${v}" ${Math.abs((c.decay ?? 0.03) - v) < 1e-9 ? 'selected' : ''}>${Math.exp(-v).toFixed(2)}</option>`).join('');
  const objOpts = Object.entries(OBJECTIVES).map(([k, v]) => `<option value="${k}" ${c.objective === k ? 'selected' : ''}>${v}</option>`).join('');
  const conVals = withCurrent(CONTRARIAN, Number(c.contrarianWeight), (a, b) => Math.abs(a - b) < 1e-9);
  const conOpts = conVals.map((v) => `<option value="${v}" ${Math.abs(Number(c.contrarianWeight) - v) < 1e-9 ? 'selected' : ''}>${v.toFixed(2)}</option>`).join('');
  const ages = d.meta.dataAge || {};
  const live = d.games.some((g) => g.status === 'in_progress');
  const fresh = (key, label, limitMin) => {
    const a = ageMinutes(ages[key]);
    const cls = a == null ? 'failed' : a > limitMin ? 'aging' : '';
    const blink = S.refreshing ? 'blink' : '';
    return `<span title="${esc(key)} fetched ${esc(ages[key] || 'never')}"><i class="${cls} ${blink}"></i>${label} ${a == null ? 'n/a' : rel(ages[key])}</span>`;
  };
  ctl.innerHTML = `
    <label class="ctl"><span class="k">Horizon</span><span class="sel"><select data-act="horizon">${horizonOpts}</select></span></label>
    <label class="ctl opt"><span class="k">Decay</span><span class="sel"><select data-act="decay" title="Future win probabilities are multiplied toward 50% by this factor per week">${decayOpts}</select></span></label>
    <label class="ctl opt"><span class="k">Objective</span><span class="sel"><select data-act="objective">${objOpts}</select></span></label>
    <label class="ctl opt"><span class="k">Contrarian</span><span class="sel"><select data-act="contrarian">${conOpts}</select></span></label>
    <button class="tbtn" data-act="open-entries">Entries</button>
    <button class="tbtn" data-act="open-crowd">Crowd</button>
    <button class="tbtn" data-act="density" aria-pressed="${document.documentElement.dataset.density === 'compact'}">Dense</button>
    <button class="tbtn" data-act="theme" aria-pressed="${document.documentElement.dataset.theme === 'dark'}">Dark</button>
    <div class="fresh">${fresh('espn', 'LINES', 60)}${fresh('injuries', 'INJ', 360)}<span title="scores"><i class="${live ? '' : ''}"></i>SCORES ${live ? 'live' : rel(ages.espn)}</span></div>
    <button class="tbtn refresh ${S.refreshing ? 'busy' : ''}" data-act="refresh"><span>${S.refreshing ? 'Refreshing' : 'Refresh'}</span> <span class="glyph">↻</span></button>`;
  const rc = $('#recomputing');
  rc.hidden = !S.loading;
}

function renderRail() {
  const el = $('#rail');
  const d = S.dash;
  if (!d) { el.innerHTML = ''; return; }
  const c = S.config;
  const weeks = d.weeks; const cw = d.meta.currentWeek; const H = d.meta.horizon;
  const entries = d.entries;
  const wkCells = weeks.map((w) => {
    const two = (c.picksPerWeek || {})[String(w.week)] > 1;
    const ovr = w.gameIds.some((id) => effOverride(id));
    const cls = ['rail-wk', w.week === cw ? 'current' : '', w.week > H ? 'beyond' : '', w.week === S.ui.focusWeek && w.week !== cw ? 'focus' : '', w.week === cw ? 'rail-col-current' : '', w.week === H ? 'rail-col-horizon' : ''].filter(Boolean).join(' ');
    return `<button class="${cls}" data-act="focus-week" data-week="${w.week}" title="Week ${w.week} · ${esc(w.label || '')}">${w.week}${two ? '<sup>2</sup>' : ''}${ovr ? '<i class="ovr"></i>' : ''}</button>`;
  }).join('') + '<div class="rail-bracket">]</div>';
  const lanes = entries.map((e) => {
    const ec = entryClass(e.name);
    const planByWeek = new Map((e.plan || []).map((p) => [p.week, p]));
    const tiles = weeks.map((w) => {
      const wk = w.week;
      let cls = 'tile', style = '', title = `W${wk} · ${e.name}`;
      if (!e.alive) { cls += ' dead'; title += ' · eliminated'; }
      else if (wk < cw) { cls += ' past'; title += ' · past'; }
      else if (wk > H) { cls += ' beyond'; title += ' · beyond horizon'; }
      else {
        const p = planByWeek.get(wk);
        if (!p || !p.teams.length) { cls += ' none'; title += ' · no pick'; }
        else {
          const ps = p.teams.map((t, i) => teamP(p.gameIds[i], t));
          if (p.locked) cls += ' locked';
          else if (p.teams.length > 1) { cls += ' two ' + tone(ps[0]); style = `--tone2-fill:var(--${tone(ps[1]).replace('tone-', '')}-fill)`; }
          else cls += ' planned ' + tone(ps[0]);
          if (hasOverride(p.gameIds)) cls += ' override';
          title += ' · ' + p.teams.map((t, i) => `${t} ${p.home[i] ? 'vs' : '@'} ${p.opponents[i]} ${pct(ps[i])}`).join(' + ') + (p.locked ? ' · locked' : '');
        }
      }
      if (wk === cw) cls += ' rail-col-current';
      if (wk === H) cls += ' rail-col-horizon';
      return `<button class="${cls}" style="${style}" data-act="open-branches" data-entry="${esc(e.name)}" data-week="${wk}" title="${esc(title)}"></button>`;
    }).join('') + '<div></div>';
    return tiles;
  }).join('');
  el.innerHTML = `<div class="rail-inner" style="--lanes:${entries.length}">
    <div class="rail-labels"><span class="label">WK</span>${entries.map((e) => `<span class="label ${entryClass(e.name)} entry-color">${esc(e.name)}</span>`).join('')}</div>
    <div class="rail-grid" style="--weeks:${weeks.length};--lanes:${entries.length}">${wkCells}${lanes}</div></div>`;
}

function renderBanner() {
  const el = $('#banner');
  const d = S.dash;
  if (!d) { el.hidden = true; return; }
  const issues = []; let cls = '';
  if (S.error) { issues.push(`Backend error: ${S.error}. Showing the last good plan from ${new Date(d.meta.generatedAt).toLocaleTimeString()}.`); cls = 'error'; }
  const ages = d.meta.dataAge || {};
  const linesAge = ageMinutes(ages.espn), injAge = ageMinutes(ages.injuries), modelAge = ageMinutes(d.meta.generatedAt);
  if (linesAge != null && linesAge > 60) issues.push(`Lines are ${rel(ages.espn)} old`);
  if (injAge != null && injAge > 360) issues.push(`injuries ${rel(ages.injuries)} old`);
  if (modelAge != null && modelAge > 60) issues.push(`model computed ${rel(d.meta.generatedAt)} ago`);
  for (const w of d.meta.warnings || []) issues.push(w);
  const live = d.games.some((g) => g.status === 'in_progress');
  if (!issues.length && live) { cls = 'live'; issues.push('<span class="dot"></span>Games in progress · refresh for scores'); }
  const key = issues.join('|');
  if (!issues.length || (S.ui.dismissedBanner === key && cls !== 'error')) { el.hidden = true; return; }
  el.className = 'banner ' + cls;
  el.innerHTML = `<div class="banner-inner"><span>${issues.map((i) => i.startsWith('<span') ? i : esc(i)).join(' · ')}</span><button class="tbtn" data-act="refresh">Refresh now</button>${cls !== 'live' ? '<button class="tbtn muted" data-act="dismiss-banner" data-key="' + esc(key) + '">Dismiss</button>' : ''}</div>`;
  el.hidden = false;
}

function renderFoot() {
  const el = $('#foot');
  const d = S.dash;
  if (!d) { el.innerHTML = ''; return; }
  const used = d.entries.reduce((n, e) => n + (e.used || []).length, 0);
  const book = (d.games.find((g) => g.oddsProvider) || {}).oddsProvider || 'nflverse lines';
  el.innerHTML = `<span>Book: ${esc(book)}</span><span>Model v${esc(d.meta.version)} · ${esc(d.meta.ratingsFrom || '')} · HFA ${d.meta.hfa}</span><span>computed ${new Date(d.meta.generatedAt).toLocaleTimeString()}</span><span>${d.entries.length} entries · ${used} teams used</span><span style="margin-left:auto">sources: ${Object.entries(d.meta.sources || {}).map(([k, v]) => `${k} ${v}`).join(' · ')}</span>`;
}

/* ---------------------------------------------------------------- events */
function onAction(act, el, ev) {
  const d = S.dash, c = S.config;
  const week = el.dataset.week ? Number(el.dataset.week) : null;
  const entry = el.dataset.entry || null;
  switch (act) {
    case 'horizon': mutate((cfg) => { cfg.horizon = Number(el.value); }); break;
    case 'decay': mutate((cfg) => { cfg.decay = Number(el.value); }); break;
    case 'objective': mutate((cfg) => { cfg.objective = el.value; }); break;
    case 'contrarian': mutate((cfg) => { cfg.contrarianWeight = Number(el.value); }); break;
    case 'refresh': refreshData(); break;
    case 'density': { const on = document.documentElement.dataset.density !== 'compact'; document.documentElement.dataset.density = on ? 'compact' : ''; try { localStorage.setItem('density', on ? 'compact' : ''); } catch (e) {} renderMasthead(); break; }
    case 'theme': { const on = document.documentElement.dataset.theme !== 'dark'; document.documentElement.dataset.theme = on ? 'dark' : ''; try { localStorage.setItem('theme', on ? 'dark' : ''); } catch (e) {} renderMasthead(); break; }
    case 'undo': if (S.undo) { const u = S.undo; S.undo = null; $('#toast').hidden = true; u(); } break;
    case 'toast-close': $('#toast').hidden = true; break;
    case 'dismiss-banner': S.ui.dismissedBanner = el.dataset.key; renderBanner(); break;
    case 'focus-week': S.ui.focusWeek = week; if (S.route.view === 'schedule') { S.ui.scheduleWeek = 'focus'; } if (S.route.view === 'branches') { go(`#/branches/${S.route.entry || d.entries[0].name}/${week}`); return; } renderAll(); break;
    case 'open-branches': {
      const e = entry || (d.entries.find((x) => x.alive) || d.entries[0]).name;
      const w = week || S.ui.focusWeek || d.meta.currentWeek;
      if (S.route.view === 'plan' && isWide()) { S.ui.drawer = { type: 'branches', entry: e, week: w }; renderDrawer(); renderView(); }
      else go(`#/branches/${e}/${w}`);
      break;
    }
    case 'lock': if (el.closest('#drawer')) { S.ui.drawer = null; renderDrawer(); } setLock(entry, week, (el.dataset.teams || '').split('+').filter(Boolean)); break;
    case 'unlock': if (el.closest('#drawer')) { S.ui.drawer = null; renderDrawer(); } setLock(entry, week, null); break;
    case 'twopick': setTwoPick(week, el.getAttribute('aria-pressed') !== 'true'); break;
    case 'override': setOverride(el.dataset.game, el.dataset.side || null); break;
    case 'clear-overrides': clearOverrides(); break;
    case 'use-alt': useCombination(JSON.parse(el.dataset.picks)); break;
    case 'open-entries': S.ui.drawer = { type: 'entries', draft: JSON.parse(JSON.stringify(c.entries)) }; renderDrawer(); break;
    case 'open-crowd': { const wk = String(d.meta.currentWeek); S.ui.drawer = { type: 'crowd', week: Number(wk), draft: { ...((c.pickPct || {})[wk] || {}) } }; renderDrawer(); break; }
    case 'close-drawer': S.ui.drawer = null; renderDrawer(); renderView(); break;
    case 'set-team': go(`#/teams/${el.dataset.team || el.value}`); break;
    case 'team-prev': case 'team-next': { const codes = Object.keys(d.teams).sort(); const i = codes.indexOf(S.route.team || codes[0]); const j = (i + (act === 'team-next' ? 1 : codes.length - 1)) % codes.length; go(`#/teams/${codes[j]}`); break; }
    case 'branch-entry': go(`#/branches/${el.value}/${S.route.week || S.ui.focusWeek}`); break;
    case 'branch-week': go(`#/branches/${S.route.entry}/${el.value}`); break;
    case 'week-step': { const cur = S.ui.focusWeek || d.meta.currentWeek; const nw = clamp(cur + Number(el.dataset.dir), 1, d.meta.weeksInSeason); S.ui.focusWeek = nw; if (S.route.view === 'branches') { go(`#/branches/${S.route.entry}/${nw}`); return; } S.ui.scheduleWeek = 'focus'; renderAll(); break; }
    case 'sched-week': S.ui.scheduleWeek = el.dataset.mode; renderView(); break;
    case 'sched-filter': S.ui.scheduleFilter = el.dataset.mode; renderView(); break;
    case 'team-search': { S.ui.teamSearch = el.value.trim().toUpperCase(); const box = $('#sched-ledger'); if (box && typeof scheduleLedger === 'function') box.innerHTML = scheduleLedger(); else renderView(); break; }
    case 'sort': S.ui.sort = el.value; renderView(); break;
    case 'hide-low': S.ui.hideLow = !S.ui.hideLow; renderView(); break;
    case 'show-excluded': S.ui.showExcluded = !S.ui.showExcluded; renderView(); break;
    case 'news-filter': S.ui.newsFilter = el.dataset.mode; renderView(); break;
    case 'news-team': S.ui.newsTeam = el.value; renderView(); break;
    case 'chart-week': S.ui.chartWeek = week; renderView(); break;
    case 'shortcuts': S.ui.shortcuts = !S.ui.shortcuts; $('#shortcuts').hidden = !S.ui.shortcuts; break;
    default: if (window.onDrawerAction) window.onDrawerAction(act, el, ev);
  }
}

function bindEvents() {
  document.body.addEventListener('click', (ev) => {
    const el = ev.target.closest('[data-act]');
    if (!el || el.tagName === 'SELECT' || el.tagName === 'INPUT') return;
    ev.preventDefault();
    onAction(el.dataset.act, el, ev);
  });
  document.body.addEventListener('change', (ev) => {
    const el = ev.target.closest('[data-act]');
    if (!el) return;
    onAction(el.dataset.act, el, ev);
  });
  document.body.addEventListener('input', (ev) => {
    const el = ev.target.closest('[data-act="team-search"]');
    if (el) onAction('team-search', el, ev);
  });
  window.addEventListener('hashchange', () => { parseRoute(); renderAll(); });
  window.addEventListener('resize', syncMastHeight);
  document.addEventListener('keydown', (ev) => {
    if (ev.target.matches('input, select, textarea')) { if (ev.key === 'Escape') ev.target.blur(); return; }
    if (ev.metaKey || ev.ctrlKey || ev.altKey) return;
    const n = Number(ev.key);
    if (n >= 1 && n <= 6) { go('#/' + VIEWS[n - 1][0]); return; }
    if (ev.key === 'Escape') { if (S.ui.drawer) { S.ui.drawer = null; renderDrawer(); renderView(); } $('#shortcuts').hidden = true; S.ui.shortcuts = false; return; }
    if (ev.key === 'r') { refreshData(); return; }
    if (ev.key === 'd') { onAction('density', { dataset: {} }); return; }
    if (ev.key === '[' || ev.key === ']') { onAction('week-step', { dataset: { dir: ev.key === '[' ? -1 : 1 } }); return; }
    if (ev.key === '?') { onAction('shortcuts', { dataset: {} }); return; }
    if (ev.key === '/' && S.route.view === 'schedule') { const inp = $('[data-act="team-search"]'); if (inp) { ev.preventDefault(); inp.focus(); } }
  });
  // tooltips for tiles and figures with a title attribute (native title has a delay; keep native for simplicity)
}

/* ---------------------------------------------------------------- boot */
async function boot() {
  try { document.documentElement.dataset.density = localStorage.getItem('density') || ''; document.documentElement.dataset.theme = localStorage.getItem('theme') || ''; } catch (e) {}
  parseRoute();
  bindEvents();
  renderMasthead();
  try { await loadConfig(); } catch (e) { S.error = e.message; }
  if (S.config) await run({ save: false });
  else renderAll();
}
document.addEventListener('DOMContentLoaded', boot);
