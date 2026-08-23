# Slice: gamelogic_extract — GameLogicData JSON from `data.unity3d`

## 1. Summary

Per-tribe mapgen rates (`terrainModifier`, `resourceModifier`, `startingResource`)
are **not** hardcoded in `dump.cs`. They live in versioned **TextAsset** JSON blobs
bundled inside the Unity player data file, referenced by `PolytopiaDataHolder`.

This note records how those assets were extracted into
`polytopia_extracted/gamelogic/GameLogicData{N}.json` without AssetStudio / UABE /
AssetRipper — using **UnityPy** only.

## 2. Where the data lives in the game

| Piece | Location |
|-------|----------|
| Asset container | `polytopia_files/Polytopia.app/Contents/Resources/Data/data.unity3d` |
| Holder type | `PolytopiaDataHolder` (ScriptableObject) — `dump.cs` TypeDef ~316 |
| Fields | `gameLogicDatas: DataAsset[]`, plus avatar data |
| Load API | `GetGameLogicTextAssetWithVersion(int version)` → `LoadGameLogicData(int version)` |
| Schema (code) | `GameLogicData` + `TribeData.terrainModifier` / `resourceModifier` (`dump.cs` ~10826) |

`LoadDatabase(string path)` / `Parse(string jsonData)` consume the TextAsset string.
There is **no** loose `GameLogicData.json` under `StreamingAssets/`; the JSON is
embedded in `data.unity3d`.

Binary confirmation (before UnityPy):

```bash
# keys present in the asset file
python3 -c "
from pathlib import Path
b = Path('polytopia_files/Polytopia.app/Contents/Resources/Data/data.unity3d').read_bytes()
for n in (b'terrainModifier', b'PolytopiaDataHolder', b'resourceModifier'):
    print(n, b.find(n))
"
```

`terrainModifier` and `PolytopiaDataHolder` hit inside `data.unity3d`.
Addressables sprite bundles under `StreamingAssets/aa/` do **not** contain these keys.

## 3. Why many files (GameLogicData1 … 28)

`PolytopiaDataHolder.gameLogicDatas` is a **version ladder**. The runtime picks a
snapshot by integer version so older saves / online games keep matching logic:

- `GetGameLogicTextAssetWithVersion(version)`
- log strings: `[GameLogicData] Loaded database: {0}`, `Could not load gameLogicData version {0}`

Extracted TextAsset names are literally `GameLogicData1` … `GameLogicData28`.
Later versions add sections (e.g. diplomacy ~v10, skins ~v20) and grow in size.

**For current mapgen rates, use the newest:**  
`polytopia_extracted/gamelogic/GameLogicData28.json`

## 4. Extraction procedure (UnityPy)

Prerequisite (this machine already had it):

```bash
python3 -c "import UnityPy; print(UnityPy.__version__)"
# also available as: /Library/Frameworks/Python.framework/Versions/3.12/bin/unitypy
```

Reproduce:

```bash
python3 <<'PY'
import json
from pathlib import Path
import UnityPy

src = Path("polytopia_files/Polytopia.app/Contents/Resources/Data/data.unity3d")
out = Path("polytopia_extracted/gamelogic")
out.mkdir(parents=True, exist_ok=True)

env = UnityPy.load(str(src))
# Expect ~28k objects; TextAsset count is small (~38).

for obj in env.objects:
    if obj.type.name != "TextAsset":
        continue
    data = obj.read()
    name = getattr(data, "m_Name", None) or getattr(data, "name", "") or ""
    script = getattr(data, "script", None) or getattr(data, "m_Script", b"")
    if isinstance(script, bytes):
        text = script.decode("utf-8", "replace")
    else:
        text = str(script)

    if "terrainModifier" not in text and "resourceModifier" not in text:
        continue
    if not str(name).startswith("GameLogicData"):
        continue

    path = out / f"{name}.json"
    # Some older snapshots have trailing commas; strip then pretty-print.
    import re
    cleaned = re.sub(r",(\s*[}\]])", r"\1", text)
    try:
        path.write_text(json.dumps(json.loads(cleaned), indent=2))
    except json.JSONDecodeError:
        path.write_text(text)  # keep raw if still invalid
    print("wrote", path, "bytes", path.stat().st_size)
PY
```

Output directory:

```
polytopia_extracted/gamelogic/
  GameLogicData1.json
  …
  GameLogicData28.json
```

## 5. JSON shape (what to read for rates)

Top-level keys (v28):

`tribeData`, `techData`, `unitData`, `improvementData`, `terrainData`,
`resourceData`, `taskData`, `skinData`, `diplomacyData`

Per tribe under `tribeData.<id>` (e.g. `imperius`, `cymanti`):

| Field | Role |
|-------|------|
| `terrainModifier` | `Dict[terrainName → float]` mapgen terrain bias |
| `resourceModifier` | `Dict[resourceName → float]` mapgen resource bias |
| `startingResource` | list of resource names forced near capital |
| `startingTech` / `startingUnit` / `tribeAbilities` | unrelated to mapgen rates |

Example (v28):

```json
"cymanti": {
  "terrainModifier": { "mountain": 1.2 },
  "resourceModifier": { "spores": 0.3, "crop": 0 },
  "startingResource": ["spores", "spores"]
}
```

`resourceData` entries also list terrain affinity for each resource type (which
terrains can host fruit/fish/spores/etc.).

## 6. Tools used / not used

| Tool | Used? |
|------|-------|
| **UnityPy** (Python) | Yes — load `data.unity3d`, export TextAssets |
| Raw `Path.read_bytes()` / substring search | Yes — locate container before export |
| AssetStudio / UABE / AssetRipper | **No** |
| Addressables catalogs under `StreamingAssets/aa/` | Not needed for GameLogic |

## 7. Relation to mapgenerator

`pyrender_UPDATED/mapgenerator/gamedata.py` loads
`polytopia_extracted/gamelogic/GameLogicData28.json` (or the newest
`GameLogicData*.json` present) and drives:

- `resourceModifier` → `resource_weight` / specialty gates (spores, aquacrop)
- `terrainModifier` → `tribe_terrain_bias` (multiplies base forest/mountain rates)
- `resourceData.resourceTerrainRequirements` → which terrains can host a resource
- `startingResource` → capital starting resources

Whales are still listed in JSON but mapgen refuses to spawn them (current product
rule). Starfish stay on the dedicated `AddStarfish` path.

## 8. Quick verify

```bash
python3 -c "
import json
t = json.load(open('polytopia_extracted/gamelogic/GameLogicData28.json'))['tribeData']
for k in ('imperius','bardur','cymanti','polaris','vengir'):
    print(k, t[k].get('terrainModifier'), t[k].get('resourceModifier'))
"
```
