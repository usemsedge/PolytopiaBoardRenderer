"""Brush catalogs for the board editor (enums + GameLogic unit costs)."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PY = os.path.join(_ROOT, "pyrender_UPDATED")
if _PY not in sys.path:
    sys.path.insert(0, _PY)

from enums import Improvement, Resource, Terrain, Unit  # noqa: E402


def _label(name: str) -> str:
    return name.replace("_", " ").title()


def _latest_gamelogic() -> Optional[dict]:
    gdir = os.path.join(_ROOT, "polytopia_extracted", "gamelogic")
    if not os.path.isdir(gdir):
        return None
    files = []
    for name in os.listdir(gdir):
        if name.startswith("GameLogicData") and name.endswith(".json"):
            try:
                n = int(name[len("GameLogicData") : -len(".json")])
            except ValueError:
                continue
            files.append((n, os.path.join(gdir, name)))
    if not files:
        return None
    files.sort()
    with open(files[-1][1]) as f:
        return json.load(f)


def _unit_costs() -> Dict[int, int]:
    data = _latest_gamelogic()
    if not data:
        return {}
    out: Dict[int, int] = {}
    for entry in (data.get("unitData") or {}).values():
        if not isinstance(entry, dict):
            continue
        idx = entry.get("idx")
        if idx is None:
            continue
        out[int(idx)] = int(entry.get("cost", 0))
    return out


def _unit_health() -> Dict[int, int]:
    data = _latest_gamelogic()
    if not data:
        return {}
    out: Dict[int, int] = {}
    for entry in (data.get("unitData") or {}).values():
        if not isinstance(entry, dict):
            continue
        idx = entry.get("idx")
        if idx is None:
            continue
        out[int(idx)] = int(entry.get("health", 100))
    return out


UNIT_COST = _unit_costs()
UNIT_HEALTH = _unit_health()


def build_catalog() -> Dict[str, Any]:
    terrains = [
        {"id": int(t), "name": t.name, "label": _label(t.name)}
        for t in Terrain
        if t != Terrain.NONE
    ]
    resources = [
        {"id": int(r), "name": r.name, "label": _label(r.name)}
        for r in Resource
        if r != Resource.NONE
    ]
    improvements = [
        {"id": int(i), "name": i.name, "label": _label(i.name)}
        for i in Improvement
        if i not in (Improvement.NONE, Improvement.ROAD)
    ]
    units = []
    for u in Unit:
        if u == Unit.NONE:
            continue
        cost = UNIT_COST.get(int(u), 0)
        units.append({
            "id": int(u),
            "name": u.name,
            "label": _label(u.name),
            "cost": cost,
        })
    units.sort(key=lambda e: (e["cost"], e["id"]))

    menus = [
        {
            "id": "terrain",
            "label": "Terrain",
            "items": terrains,
            "can_remove": True,
        },
        {
            "id": "improvement",
            "label": "Improvement",
            "items": improvements,
            "can_remove": True,
        },
        {
            "id": "resource",
            "label": "Resource",
            "items": resources,
            "can_remove": True,
        },
        {
            "id": "road",
            "label": "Road",
            "items": [{"id": 1, "name": "ROAD", "label": "Place Road"}],
            "can_remove": True,
        },
        {
            "id": "unit",
            "label": "Unit",
            "items": units,
            "can_remove": True,
        },
    ]
    return {"menus": menus}


def unit_max_health(unit_type: int) -> int:
    return UNIT_HEALTH.get(int(unit_type), 100)
