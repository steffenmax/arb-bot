"""Dashboard config: defaults, validation and persistence."""
from __future__ import annotations

import copy
import json
import os
import threading

from .. import data

CONFIG_FILE = os.path.join(data.CACHE_DIR, "config.json")

DEFAULT_CONFIG = {
    "season": None,
    "entries": [
        {"name": "A", "used": [], "locks": {}, "alive": True},
        {"name": "B", "used": [], "locks": {}, "alive": True},
        {"name": "C", "used": [], "locks": {}, "alive": True},
    ],
    "picksPerWeek": {},
    "horizon": 18,
    "decay": 0.03,
    "objective": "any",
    "topBranches": 10,
    "contrarianWeight": 1.0,
    "hedge": 0.1,
    "pickPct": {},
    "overrides": {},
    "injuryAdjust": True,
}


class ConfigError(ValueError):
    pass


def _team_list(teams, field: str) -> list[str]:
    if teams is None:
        return []
    if not isinstance(teams, list):
        raise ConfigError(f"{field} must be a list of team codes")
    out = []
    for t in teams:
        try:
            code = data.normalize_team(str(t))
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
        if code not in out:
            out.append(code)
    return out


def normalize(raw: dict | None) -> dict:
    """Fill defaults and validate. Raises ConfigError on bad input."""
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    raw = raw or {}
    if not isinstance(raw, dict):
        raise ConfigError("config must be an object")
    for key in cfg:
        if key in raw and raw[key] is not None:
            cfg[key] = raw[key]

    if cfg["season"] is not None:
        try:
            cfg["season"] = int(cfg["season"])
        except (TypeError, ValueError) as exc:
            raise ConfigError("season must be an integer") from exc

    entries = cfg["entries"]
    if not isinstance(entries, list) or not entries:
        raise ConfigError("entries must be a non-empty list")
    names = set()
    clean_entries = []
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            raise ConfigError("each entry must be an object")
        name = str(e.get("name") or chr(ord("A") + i)).strip()[:12]
        if not name or name in names:
            raise ConfigError(f"entry names must be unique and non-empty (problem with '{name}')")
        names.add(name)
        locks = {}
        for wk, teams in (e.get("locks") or {}).items():
            try:
                week = int(wk)
            except (TypeError, ValueError) as exc:
                raise ConfigError(f"lock week '{wk}' is not a number") from exc
            if not 1 <= week <= 18:
                raise ConfigError(f"lock week {week} out of range")
            tl = _team_list(teams, f"entry {name} lock week {week}")
            if tl:
                locks[str(week)] = tl
        clean_entries.append({
            "name": name,
            "used": _team_list(e.get("used"), f"entry {name} used"),
            "locks": locks,
            "alive": bool(e.get("alive", True)),
        })
    cfg["entries"] = clean_entries

    ppw = {}
    for wk, n in (cfg["picksPerWeek"] or {}).items():
        try:
            week, count = int(wk), int(n)
        except (TypeError, ValueError) as exc:
            raise ConfigError("picksPerWeek must map week numbers to counts") from exc
        if not 1 <= week <= 18 or not 1 <= count <= 3:
            raise ConfigError(f"picksPerWeek week {week} count {count} out of range")
        if count > 1:
            ppw[str(week)] = count
    cfg["picksPerWeek"] = ppw

    try:
        cfg["horizon"] = int(cfg["horizon"])
        cfg["decay"] = float(cfg["decay"])
        cfg["topBranches"] = int(cfg["topBranches"])
        cfg["contrarianWeight"] = float(cfg["contrarianWeight"])
        cfg["hedge"] = float(cfg["hedge"])
    except (TypeError, ValueError) as exc:
        raise ConfigError("horizon, decay, topBranches, contrarianWeight and hedge must be numbers") from exc
    if not 1 <= cfg["horizon"] <= 18:
        raise ConfigError("horizon must be between 1 and 18")
    if not 0.0 <= cfg["decay"] <= 0.5:
        raise ConfigError("decay must be between 0 and 0.5")
    if not 1 <= cfg["topBranches"] <= 32:
        raise ConfigError("topBranches must be between 1 and 32")
    if not 0.0 <= cfg["contrarianWeight"] <= 5.0:
        raise ConfigError("contrarianWeight must be between 0 and 5")
    if not 0.0 <= cfg["hedge"] <= 2.0:
        raise ConfigError("hedge must be between 0 and 2")
    if cfg["objective"] not in ("any", "final", "expected"):
        raise ConfigError("objective must be 'any', 'final' or 'expected'")

    pct = {}
    for wk, table in (cfg["pickPct"] or {}).items():
        try:
            week = int(wk)
        except (TypeError, ValueError) as exc:
            raise ConfigError("pickPct must be keyed by week") from exc
        if not isinstance(table, dict):
            raise ConfigError("pickPct entries must be objects of team to percent")
        clean = {}
        for t, v in table.items():
            try:
                code = data.normalize_team(str(t))
                val = float(v)
            except (TypeError, ValueError) as exc:
                raise ConfigError(f"bad pickPct entry {t}={v}") from exc
            if val > 0:
                clean[code] = val
        if clean:
            pct[str(week)] = clean
    cfg["pickPct"] = pct

    overrides = {}
    for gid, side in (cfg["overrides"] or {}).items():
        if side not in ("home", "away"):
            raise ConfigError(f"override for {gid} must be 'home' or 'away'")
        overrides[str(gid)] = side
    cfg["overrides"] = overrides
    cfg["injuryAdjust"] = bool(cfg["injuryAdjust"])
    return cfg


def load() -> dict:
    try:
        with open(CONFIG_FILE) as fh:
            return normalize(json.load(fh))
    except (FileNotFoundError, json.JSONDecodeError, ConfigError):
        return normalize(None)


def save(cfg: dict) -> dict:
    cfg = normalize(cfg)
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    tmp = f"{CONFIG_FILE}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(tmp, "w") as fh:
        json.dump(cfg, fh, indent=2)
    os.replace(tmp, CONFIG_FILE)
    return cfg
