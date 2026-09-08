"""End-to-end interaction test for the survivor dashboard (real backend on :8765)."""
import json, sys, time, urllib.request
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8765"
CH = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
errors, fails = [], []

def get_config():
    with urllib.request.urlopen(BASE + "/api/config") as r:
        return json.load(r)

def put_config(cfg):
    req = urllib.request.Request(BASE + "/api/config", data=json.dumps(cfg).encode(), method="PUT", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)

def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        fails.append(name)

def wait_idle(page):
    page.wait_for_timeout(50)
    page.wait_for_function("() => window.S && window.S.dash && !window.S.pending && !window.S.loading", timeout=30000)
    page.wait_for_timeout(100)

clean = {"entries": [{"name": "A", "used": [], "locks": {}, "alive": True}, {"name": "B", "used": [], "locks": {}, "alive": True}, {"name": "C", "used": [], "locks": {}, "alive": True}],
         "picksPerWeek": {}, "horizon": 10, "decay": 0.03, "objective": "any", "topBranches": 10, "contrarianWeight": 1.0, "hedge": 0.1, "pickPct": {}, "overrides": {}, "injuryAdjust": True}
put_config(clean)

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CH, args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "favicon" not in m.text and "fonts" not in m.text else None)

    # ---- This Week loads
    page.goto(BASE + "/#/week"); wait_idle(page)
    check("heroes render", page.locator(".hero").count() == 3)
    cw = page.evaluate("S.dash.meta.currentWeek")
    plan_b = page.evaluate("S.dash.entries[1].plan[0].teams")

    # ---- lock from the hero, then undo
    page.locator(".hero").nth(1).get_by_text("Lock pick").click(); wait_idle(page)
    cfg = get_config()
    check("hero lock persists", cfg["entries"][1]["locks"].get(str(cw)) == plan_b, json.dumps(cfg["entries"][1]["locks"]))
    check("hero shows locked", "Locked" in page.locator(".hero").nth(1).inner_text())
    check("toast visible", page.locator("#toast").is_visible())
    page.locator("#toast").get_by_text("Undo").click(); wait_idle(page)
    cfg = get_config()
    check("undo removes lock", str(cw) not in cfg["entries"][1]["locks"], json.dumps(cfg["entries"][1]["locks"]))

    # ---- horizon control
    page.select_option('select[data-act="horizon"]', "12"); wait_idle(page)
    check("horizon persists", get_config()["horizon"] == 12)
    check("rail bracket follows horizon", page.evaluate("S.dash.meta.horizon") == 12)
    page.select_option('select[data-act="horizon"]', "10"); wait_idle(page)

    # ---- season plan: two-pick toggle and drawer lock
    page.goto(BASE + "/#/plan"); wait_idle(page)
    wk2 = cw + 1
    page.locator(f'.plangrid .toggle[data-week="{wk2}"]').click(); wait_idle(page)
    cfg = get_config()
    check("two-pick persists", cfg["picksPerWeek"].get(str(wk2)) == 2, json.dumps(cfg["picksPerWeek"]))
    teams_wk2 = page.evaluate(f"S.dash.entries[0].plan.find(p => p.week === {wk2}).teams")
    check("plan shows two teams in two-pick week", len(teams_wk2) == 2, str(teams_wk2))
    check("two-pick cell styled", page.locator(f'.plangrid .cell.two[data-week="{wk2}"]').count() == 3)
    page.locator(f'.plangrid .toggle[data-week="{wk2}"]').click(); wait_idle(page)
    check("two-pick cleared", str(wk2) not in get_config()["picksPerWeek"])
    past_disabled = page.evaluate(f"(() => {{ const t = document.querySelector('.plangrid .toggle[data-week=\"{cw}\"]'); return t && !t.disabled; }})()")
    check("current week toggle enabled", past_disabled)

    wk4 = cw + 3
    page.locator(f'.plangrid .cell[data-entry="C"][data-week="{wk4}"]').click(); page.wait_for_timeout(300)
    check("drawer opens for C", page.locator("#drawer").is_visible() and f"Entry C · Week {wk4}" in page.locator("#drawer").inner_text())
    first_lock = page.locator('#drawer table.ledger tbody tr').first.get_by_text("Lock", exact=True)
    rank1_teams = page.evaluate(f"(() => {{ const b = S.dash.entries[2].branches['{wk4}']; return b[0].teams; }})()")
    first_lock.click(); wait_idle(page)
    cfg = get_config()
    check("drawer lock persists", cfg["entries"][2]["locks"].get(str(wk4)) is not None, json.dumps(cfg["entries"][2]["locks"]))
    check("locked cell rendered", page.locator(f'.plangrid .cell.locked[data-entry="C"][data-week="{wk4}"]').count() == 1)
    check("locked branch marked in rail", page.locator(f'.rail .tile.locked[data-entry="C"][data-week="{wk4}"]').count() == 1)
    page.locator(f'.plangrid .cell[data-entry="C"][data-week="{wk4}"]').click(); page.wait_for_timeout(300)
    page.locator("#drawer").get_by_text("Unlock").first.click(); wait_idle(page)
    check("drawer unlock persists", str(wk4) not in get_config()["entries"][2]["locks"])

    # ---- schedule what-if
    page.goto(BASE + "/#/schedule"); wait_idle(page)
    row = page.locator("table.ledger tbody tr:not(.week-head)").nth(3)
    gid = row.locator('[data-act="override"]').first.get_attribute("data-game")
    row.locator('[data-act="override"][data-side="home"]').click(); wait_idle(page)
    cfg = get_config()
    check("override persists", cfg["overrides"].get(gid) == "home", json.dumps(cfg["overrides"]))
    check("override row styled", page.locator("table.ledger tbody tr.override").count() >= 1)
    check("override game decided in payload", page.evaluate(f"S.gameMap.get('{gid}').source") == "override")
    page.locator(f'[data-act="override"][data-game="{gid}"][data-side=""]').click(); wait_idle(page)
    check("override cleared", gid not in get_config()["overrides"])
    page.fill('input[data-act="team-search"]', "KC"); page.wait_for_timeout(200)
    check("team search filters", page.locator("table.ledger tbody tr:not(.week-head)").count() <= 2)
    page.locator('[data-act="sched-week"][data-mode="all"]').click(); page.wait_for_timeout(300)
    check("all weeks shows every game", page.locator("table.ledger tbody tr.week-head").count() == 18)

    # ---- entries editor
    page.locator('[data-act="open-entries"]').first.click(); page.wait_for_timeout(200)
    page.locator('[data-act="entry-add"]').click(); page.wait_for_timeout(100)
    page.locator('[data-act="entry-used"][data-idx="3"][data-team="KC"]').click()
    page.locator('[data-act="entries-save"]').click(); wait_idle(page)
    cfg = get_config()
    check("entry added with used team", len(cfg["entries"]) == 4 and cfg["entries"][3]["used"] == ["KC"], json.dumps(cfg["entries"][3:]))
    check("rail shows 4 lanes", page.locator(".rail-labels .label").count() == 5)
    page.locator('[data-act="open-entries"]').first.click(); page.wait_for_timeout(200)
    page.locator('[data-act="entry-remove"][data-idx="3"]').click()
    page.locator('[data-act="entries-save"]').click(); wait_idle(page)
    check("entry removed", len(get_config()["entries"]) == 3)
    page.locator('[data-act="open-entries"]').first.click(); page.wait_for_timeout(200)
    page.locator('[data-act="entry-alive"][data-idx="1"]').click()
    page.locator('[data-act="close-drawer"]').first.click(); page.wait_for_timeout(200)
    check("cancel discards draft", get_config()["entries"][1]["alive"] is True)

    # ---- crowd editor
    page.goto(BASE + "/#/week"); wait_idle(page)
    page.locator('[data-act="open-crowd"]').first.click(); page.wait_for_timeout(200)
    page.fill('input[data-act="crowd-input"][data-team="LAC"]', "40")
    page.locator('input[data-act="crowd-input"][data-team="LAC"]').dispatch_event("change")
    page.locator('[data-act="crowd-save"]').click(); wait_idle(page)
    cfg = get_config()
    check("crowd persists", cfg["pickPct"].get(str(cw), {}).get("LAC") == 40, json.dumps(cfg["pickPct"]))
    check("crowd reaches branches", page.evaluate("S.dash.entries.some(e => (e.branches[String(S.dash.meta.currentWeek)]||[]).some(b => b.teams[0] === 'LAC' && b.crowdPct === 40))"))
    check("contrarian fade moves picks off LAC", page.evaluate("!S.dash.entries.some(e => e.plan[0].teams.includes('LAC'))"))

    # ---- routing
    page.goto(BASE + "/#/branches/B/3"); wait_idle(page)
    check("branches route", "Entry B · Week 3" in page.locator("#view").inner_text())
    page.goto(BASE + "/#/teams/KC"); wait_idle(page)
    check("teams route", "Kansas City" in page.locator(".team-head").inner_text())
    check("heatmap tiles", page.locator(".heat .ht").count() == 18)
    page.goto(BASE + "/#/news"); wait_idle(page)
    page.locator('[data-act="news-filter"][data-mode="injury"]').click(); page.wait_for_timeout(200)
    check("news injury filter", all("Injury" in t for t in page.locator(".news-row .tag").all_inner_texts()) if page.locator(".news-row").count() else True)
    page.keyboard.press("2"); page.wait_for_timeout(300)
    check("keyboard view switch", page.evaluate("location.hash") == "#/plan")

    # ---- phone overflow
    phone = browser.new_page(viewport={"width": 390, "height": 844})
    phone.on("pageerror", lambda e: errors.append("phone: " + str(e)))
    for route in ("week", "plan", "schedule", "teams/KC"):
        phone.goto(BASE + "/#/" + route); wait_idle(phone)
        sw, iw = phone.evaluate("[document.scrollingElement.scrollWidth, window.innerWidth]")
        check(f"phone {route} no horizontal overflow", sw <= iw + 1, f"{sw} > {iw}")
    browser.close()

put_config(clean)
print("\nconsole/page errors:", len(errors))
for e in errors[:10]:
    print("  ", e[:200])
print("\nRESULT:", "OK" if not fails and not errors else f"{len(fails)} failed checks, {len(errors)} errors")
sys.exit(0 if not fails and not errors else 1)
