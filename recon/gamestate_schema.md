# gamestate_schema — Input schema for `render(GameState) -> Image`

## 1. Summary

This slice defines the **input data contract** the renderer consumes: a trimmed,
render-only projection of the game's authoritative `GameState`. The real game
walks `GameState.Map.Tiles[]` (a flat `TileData[]`, indexed `y*width + x`) and
for each cell reads terrain/climate/skin, resource, improvement (cities &
buildings live here, *not* a separate array), unit, owner/territory, shorelines,
roads/routes, and per-player fog (`explorers`). Per-player visuals (terrain
theme, tribe house art, unit/building skins, border tint) come from the owning
`PlayerState` (`tribe`, `skinType`, `color`) plus the tile's own `climate`
(== a `TribeType` value, drives terrain art theme) and `_skin` (`SkinType`,
drives magma/swamp/etc. variants). I propose a flat Python dataclass schema
mirroring these fields exactly (same enum integer values as the IL2CPP dump so
sprite-selection code can switch on them directly), give the full enum value
tables, and ship a hand-authored 4x4 `example_gamestate.json` the renderer team
can load for testing. (`board_from_game_assets.txt` referenced in the brief is
**not present** in this checkout — see §8; the schema is derived purely from the
dump and reconciled against `sprite_catalog.json`.)

## 2. Constants

These are field offsets / enum domains and a few sentinel constants — the
numeric *render* constants (TILE_WIDTH etc.) belong to the geometry/MapRenderer
slice; reproduced here only as they bound the schema.

| Constant | Value | Source |
|----------|-------|--------|
| `PlayerState.NO_PLAYER_ID` | `0` | dump.cs 776690 |
| `PlayerState.NATURE_PLAYER_ID` | `255` | dump.cs 776691 |
| `WorldCoordinates` | `(int x @0x0, int y @0x4)` | dump.cs 780058-780059 |
| `MapData.tiles` index | `coords.ToIndex(width) = y*width + x` | dump.cs 774338; doc D.3/E.7 |
| `TileData.Shoreline.SPRITE_EXT_DEFAULT` | `""` | dump.cs 774561 |
| `TileData.Shoreline.SPRITE_EXT_SWAMP` | `"_swamp"` | dump.cs 774562 |
| `GAME_LOGIC_DATA_VERSION` | `25` | doc D.8 |
| Projection (for completeness) | `posX=(x-y)*0.4811, posY=(x+y)*0.288` | MapExtensions$$ToPosition @0x2CC11AC (brief) |
| `DEPTH_INCREASE_PER_ROW` | `100` | doc E.3 |

The renderer needs **no** simulation-only fields (CommandStack, ActionStack,
randomHash, aiState, tasks, relations, currency, score, etc.). They are listed
in §8 as deliberately dropped.

## 3. Sprite selection (which fields drive which sprite)

The schema's job is to *carry the inputs* each later slice keys on. The exact
filename rules are owned by the terrain/resource/improvement/unit/border slices;
this section states **which fields are load-bearing** and confirms representative
filenames exist in `pyrender/sprite_catalog.json` (2051 entries).

**Terrain theme suffix** = lowercase name of the tile's *climate* tribe (or skin
override). The 22 ground themes present in the catalog are exactly:
`aibo, aimo, aquarion, arty, bardur, cymanti, darkelf, elyrion, hoodrick,
imperius, kickoo, luxidoor, magma, mercenary, oumaji, polaris, quetzali, swamp,
vengir, xinxi, yadakk, zebasi` (confirmed). The TribeType-named ones map 1:1 to
`TribeType` (§5). `magma`/`swamp`/`darkelf`/`mercenary`/`arty`/`aibo`/`aimo` are
`SkinType`-driven art variants.

| GameState field(s) read | Layer | Example confirmed sprite(s) |
|-------------------------|-------|-----------------------------|
| `tile.terrain==Field`, `tile.climate`/`_skin` | terrain base | `ground`, `ground_imperius`, `ground_bardur`, `ground_magma` |
| `terrain==Mountain` + theme | terrain feature | `mountain_bardur`, `mountain_imperius`, `mountain_magma` |
| `terrain==Forest` + theme | terrain feature | `Forest_kickoo`, `Forest_imperius`, `Forest_magma` |
| `terrain==Water/Ocean` | terrain base | `water`, `ocean` |
| `terrain==Ice` (+skin) | terrain base | `ice`, `ice_magma` |
| `terrain==Wetland/Mangrove` (+swamp) | terrain | `wetland`, `wetland_swamp` |
| not `GetExplored(viewer)` | fog | `hidden` |
| `tile.shorelines.{N,S,E,W}.visible`, `.spriteExt` | shoreline | (shoreline slice; `spriteExt` ∈ {``,`_swamp`}) |
| `resource.type==Fruit` + theme | resource | `ResourceGFX_fruit_imperius`, `..._bardur` (+`_Outline`) |
| `resource.type==Game` + theme | resource (animal) | `animal_bardur`, `animal_aibo` (+`_Outline`) |
| `resource.type==Crop/Fish/Whale/Metal/Spores/Starfish/AquaCrop` | resource | `ResourceGFX_crop`, `ResourceGFX_fish`, `ResourceGFX_whale`, `ResourceGFX_metal`, `ResourceGFX_spores`, `ResourceGFX_starfish`, `ResourceGFX_aquacrop` (all +`_Outline`) |
| `improvement.type==Farm/Mine/Forge/Sawmill/Windmill/Port` (+`level`) | building | `Farm`, `Mine`, `Forge_1`, `Sawmill_1`, `Port` |
| `improvement.type==LumberHut` | building | `Lumber_Hut` |
| `improvement.type==CustomsHouse` (+`level`) | building | `Customs_House_1`..`Customs_House_5` |
| `improvement.type==Market` | building | `Market_base`,`Market_roof`,`MarketIcon` |
| `improvement.type==Ruin` | resource-layer object | `ResourceGFX_ruin` (+`_Outline`) |
| `improvement.type==Temple/Forest/Water/Mountain/Ice Temple` (+`level`) | building | `Forest_Temple_1`, `Water_Temple_1`, `Mountain_Temple_1`, `Ice_Temple_1` |
| `improvement.type==City` + owner `tribe`/`skin` (+`level`) | city/houses | `House_1_imperius`, `House_1_bardur`, `CityWallGFX` |
| `tile.hasRoad`/`hasRoute` | transport | `Road` |
| `unit.type` (+ owner tribe/skin, `flipped`) | unit | `warrior_icon`, `warrior_0_tint_ranger`, `rider_icon`, `archer_icon` |
| `tile.owner` → `PlayerState.color` | border tint | (border slice; color from player) |

NOTE: sprite filenames use **underscores**, not the spaces seen in the
`SpriteData` name constants (e.g. dump constant `"Lumber Hut"` → file
`Lumber_Hut`; `"Customs House_1"` → `Customs_House_1`). The schema stores the
*enum value*; the name-mapping is each render slice's responsibility.

## 4. Geometry

The schema carries only the data; placement is the geometry slice's job. The two
fields the schema must expose for placement are:

- `tile.x`, `tile.y` (grid coords from `WorldCoordinates`) → world position via
  `posX=(x-y)*0.4811`, `posY=(x+y)*0.288`, with row depth `y*100` + sub-layer
  offset (terrain 1, transport 2, features 3, resource-outline 4, resource 5,
  houses 6, walls 97, buildings 98, borders 0/99) — doc E.3.
- `unit.flipped` (bool, `UnitState.flipped` @0x54) and `unit.direction`
  (`GridDirection`, @0x50) → horizontal flip / facing for the unit slice.

`map.width`/`map.height` define the iteration grid and the flat-index order
(`y*width + x`). Tiles must be rendered in index order (row-major) so the
depth-sort matches the real `RenderMap` loop.

## 5. Enum value tables (use these exact integers)

**TerrainData.Type** (dump.cs 784062): None=0, Water=1, Ocean=2, Field=3,
Mountain=4, Forest=5, Ice=6, Wetland=7, Mangrove=8.

**ResourceData.Type** (dump.cs 783747): None=0, Game=1, Crop=2, Fish=3, Whale=4,
Metal=5, Fruit=6, Spores=7, Starfish=8, AquaCrop=9.

**ImprovementData.Type** (dump.cs 783585): None=0, City=1, Ruin=2, Road=3,
CustomsHouse=4, Farm=5, Windmill=6, Fishing=7, Port=8, Hunting=9, ClearForest=10,
BurnForest=11, LumberHut=12, Sawmill=13, GrowForest=14, HarvestFruit=15,
WhaleHunting=16, Temple=17, ForestTemple=18, WaterTemple=19, MountainTemple=20,
Mine=21, Forge=22, Monument1..7=23..29, EnchantAnimal=30, EnchantWhale=31,
Sanctuary=32, Outpost=33, IceBank=34, IceTemple=35, PolarisClimate=36, Fungi=37,
Algae=38, Mycelium=39, BurnSpores=40, Clathrus=41, HiddenSanctuary=42,
HarvestSpores=43, NullBuilding=44, Cultivate=45, StarFishing=46, LightHouse=47,
Bridge=48, Aquafarm=49, Market=50, Atoll=51, Canal=52, Fertilize=53, LandFill=54,
AlgaeSpawn=55.

**UnitData.Type** (dump.cs 784325): None=0, Scout=1, Warrior=2, Rider=3, Knight=4,
Defender=5, Ship=6, Battleship=7, Catapult=8, Archer=9, MindBender=10,
Swordsman=11, Giant=12, Bunny=13, Boat=14, Polytaur=15, Navalon=16, DragonEgg=17,
BabyDragon=18, FireDragon=19, Amphibian=20, Tridention=21, Mooni=22, BattleSled=23,
IceFortress=24, IceArcher=25, Crab=26, Gaami=27, Hexapod=28, Doomux=29, Phychi=30,
Kiton=31, Exida=32, Centipede=33, Segment=34, Raychi=35, Shaman=36, Dagger=37,
Cloak=38, Cloak_Boat=39, Pirate=40, Bombership=41, Scoutship=42, Transportship=43,
Rammership=44, Juggernaut=45, MermaidWarrior=46, MermaidArcher=47,
MermaidSwordsman=48, MermaidDefender=49, MermaidCloak=50, MermaidDagger=51,
Jelly=52, Shark=53, Siren=54, Aquapult=55, Boomchi=56, Island=57, Ciru=58,
Mantis=59, BugEgg=60, Moth=61, Larva=62.

**TribeType** (dump.cs 878951): None=0, Nature=1, Aimo=2, Aquarion=3, Bardur=4,
Elyrion=5, Hoodrick=6, Imperius=7, Kickoo=8, Luxidoor=9, Oumaji=10, Quetzali=11,
Vengir=12, Xinxi=13, Yadakk=14, Zebasi=15, Polaris=16, Cymanti=17.
Theme suffix = lowercase enum name (Imperius→`imperius`). Confirmed present in
catalog: aimo, aquarion, bardur, elyrion, hoodrick, imperius, kickoo, luxidoor,
oumaji, quetzali, vengir, xinxi, yadakk, zebasi, polaris, cymanti.

**SkinType** (dump.cs 878915): None=-1, Default=0, Ranger=1, Ninja=2, Baerion=3,
Scholar=5, Mercenary=7, Sfinx=8, Skeleton=9, Arty=10, Pirate=11, Aibo=12,
Urkaz=13, Ikarus=14, DarkElf=15, Swamp=17, Magma=18, Test=2000. Skin art suffix =
lowercase name (`magma`, `swamp`, `darkelf`, `arty`, `aibo`, `mercenary`).

**TileData.EffectType** (dump.cs 774595): None=0, Flooded=1, Swamped=2,
Tentacle=3, Algae=4.

**UnitEffect** (dump.cs 776841): Frozen=0, Poisoned=1, Boosted=2, Invisible=3,
Bubble=4, Petrified=5, Swift=6, DoubleReady=7.

**ImprovementEffect** (dump.cs 776535): decomposing=0, robbed=1.

**GridDirection** (dump.cs 774964): SW=0, W=1, NW=2, N=3, NE=4, E=5, SE=6, S=7,
NONE=8.

**GameState.State** (doc D.2): Unknown=0, Lobby=1, Started=2, FinalTurn=3, Ended=4.

`climate` (`TileData.climate`, int @0x1C, dump.cs 774612) holds a **TribeType
value** (1..17) selecting the terrain art theme; it is independent of `owner`
(unclaimed tiles still have a climate). `_skin` (`TileData._skin`, `SkinType`
@0x20, dump.cs 774613) overrides to skin art (e.g. Magma/Swamp).

### Proposed Python dataclasses

```python
from dataclasses import dataclass, field
from typing import Optional
from enum import IntEnum

# (Enums Terrain, Resource, Improvement, Unit, Tribe, Skin, TileEffect,
#  UnitEffect, GridDirection, ImprovementEffect — values exactly as §5.)

@dataclass
class Shoreline:
    visible: bool = False
    sprite_ext: str = ""          # "" or "_swamp"  (TileData.Shoreline @0x18)

@dataclass
class Shorelines:                  # TileData.Shorelines
    any: bool = False
    N: Shoreline = field(default_factory=Shoreline)
    S: Shoreline = field(default_factory=Shoreline)
    E: Shoreline = field(default_factory=Shoreline)
    W: Shoreline = field(default_factory=Shoreline)

@dataclass
class ResourceState:               # dump.cs 776823 — type only
    type: int                      # ResourceData.Type

@dataclass
class ImprovementState:            # dump.cs 776587
    type: int                      # ImprovementData.Type
    level: int = 1                 # ushort @0x16  -> sprite level suffix
    population: int = 0            # short  @0x1C
    border_size: int = 0           # ushort @0x22  -> territory radius
    founder: int = 0               # byte   @0x15
    connected_to_capital_of: int = 0  # byte @0x26
    effects: list[int] = field(default_factory=list)  # ImprovementEffect

@dataclass
class UnitState:                   # dump.cs 776856
    id: int
    type: int                      # UnitData.Type
    owner: int                     # byte player id
    x: int; y: int                 # coordinates @0x30
    health: int = 100              # ushort tenths; display = ceil(health/10)
    promotion_level: int = 0       # ushort @0x4A
    direction: int = 8             # GridDirection @0x50 (default NONE)
    flipped: bool = False          # @0x54  -> horizontal flip
    moved: bool = False            # @0x4E
    attacked: bool = False         # @0x4F
    skin_type: int = 0             # SkinType @0x20
    style: int = 0                 # short @0x1E
    effects: list[int] = field(default_factory=list)  # UnitEffect
    passenger_type: Optional[int] = None  # passengerUnit.type if embarked

@dataclass
class TileData:                    # dump.cs 774607
    x: int; y: int                 # coordinates @0x10
    terrain: int                   # TerrainData.Type @0x18
    climate: int                   # TribeType value @0x1C -> terrain theme
    skin: int = 0                  # SkinType @0x20 (-1/0 = default)
    altitude: int = 0              # @0x30
    owner: int = 0                 # byte @0x34 (0 = unowned)
    capital_of: int = 0            # byte @0x35
    effects: list[int] = field(default_factory=list)  # TileData.EffectType
    explorers: list[int] = field(default_factory=list)  # byte player ids
    shorelines: Shorelines = field(default_factory=Shorelines)
    ruling_city_x: int = -1        # rulingCityCoordinates @0x48
    ruling_city_y: int = -1
    improvement: Optional[ImprovementState] = None  # @0x50 (city lives here)
    resource: Optional[ResourceState] = None        # @0x58
    unit: Optional[UnitState] = None                 # @0x60
    has_road: bool = False         # @0x68
    has_route: bool = False        # @0x69

@dataclass
class PlayerState:                 # dump.cs 776687 (render-relevant subset)
    id: int                        # byte @0x10
    tribe: int                     # TribeType @0x40
    skin_type: int = 0             # SkinType @0x98
    color: int = 0                 # int @0xC0 (packed RGB, border/unit tint)
    known_players: list[int] = field(default_factory=list)

@dataclass
class MapData:                     # dump.cs 774333
    width: int                     # ushort @0x10
    height: int                    # ushort @0x12
    tiles: list[TileData]          # flat, index = y*width + x  @0x18

@dataclass
class GameState:                   # dump.cs 776002 (render-relevant subset)
    map: MapData
    players: list[PlayerState]     # PlayerStates @0x38
    current_player_index: int = 0  # byte @0x1C; the fog-of-war "viewer"
    current_turn: int = 0          # uint @0x18
```

`tile_at(x, y)` and `player_by_id(id)` helpers are implied. The renderer iterates
`for y in range(height): for x in range(width): tile = tiles[y*width + x]`.

## 6. Tint / color

The only schema-carried color input is `PlayerState.color` (int @0xC0,
dump.cs 776725). It is a packed 32-bit color used for territory borders and unit
team tinting; `PlayerState.GetPlayerColor(version, tribe, skin)` (RVA 0x7EE554)
derives the default per-tribe color when not overridden. The exact pack order
(ARGB vs RGBA) and the per-tribe palette are owned by the **border/unit-tint
slice** — the schema just transports the int and the owning `tribe`/`skinType`
so that slice can resolve it. Fog is binary (rendered or `hidden` sprite),
keyed by `current_player_index ∈ tile.explorers`; no opacity blend is stored in
state.

## 7. RVAs verified

- `MapData` fields — dump.cs 774336-774339: `width`/`height` ushort, `tiles`
  `TileData[]`, `continents`. `MapData.Serialize` @0x7D62B8.
- `TileData` fields — dump.cs 774610-774631: coordinates, terrain, climate,
  `_skin`, effects, altitude, owner, capitalOf, explorers, shorelines,
  rulingCityCoordinates, improvement, resource, `<unit>` backing, hasRoad,
  hasRoute, continent, hadRoute, upgradeTech. Confirms city is on the tile via
  `improvement` (no city array).
- `TileData.Shorelines`/`Shoreline` — dump.cs 774558-774592: N/S/E/W each with
  `visible` + `spriteExt` (`""`/`"_swamp"`).
- `ImprovementState` fields — dump.cs 776590-776605: type, owner(obsolete),
  founder, level, founded, xp, population, production, baseScore, borderSize,
  upgrade, connectedToCapitalOfPlayer, name, rewards, effects.
- `ResourceState` — dump.cs 776826: single `type` field (ResourceData.Type).
- `UnitState` fields — dump.cs 776859-776879: id, leader, follower, owner, style,
  skinType, type, coordinates, home, passengerUnit, health, promotionLevel, xp,
  moved, attacked, direction, flipped, createdTurn, UnitData, effects.
- `PlayerState` fields — dump.cs 776693-776730: Id, tribe, skinType, color, plus
  sim-only fields; `GetPlayerColor` @0x7EE554.
- `GameState` fields — dump.cs 776005-776033: Map @0x30, PlayerStates @0x38,
  CurrentPlayerIndex @0x1C, CurrentTurn @0x18, etc.
- Enum tables verified by direct read at the line numbers cited in §5.
- `WorldCoordinates` — dump.cs 780058-780063: `int x`, `int y`.
- Sprite names cross-checked against `pyrender/sprite_catalog.json` (2051 keys):
  every filename cited in §3 was confirmed present (ground_*, mountain_*,
  Forest_*, water, ocean, ice, ice_magma, wetland, wetland_swamp, hidden,
  ResourceGFX_{crop,fish,whale,metal,spores,starfish,aquacrop} + _Outline,
  ResourceGFX_fruit_<theme>, animal_<theme>, ResourceGFX_ruin, Farm, Mine,
  Forge_1, Sawmill_1, Port, Lumber_Hut, Customs_House_1..5, Market_base,
  MarketIcon, Forest_Temple_1, Water_Temple_1, Mountain_Temple_1, Ice_Temple_1,
  House_1_<theme>, CityWallGFX, Road, warrior_icon, *_icon).

## 8. Open questions / risks

- **`board_from_game_assets.txt` is missing** from this checkout (only
  `polytopia_extracted/sprites/UI_clipboard.png` matched a `*board*` search).
  The schema could not be reconciled against its tile-notation codes; if it
  exists elsewhere, confirm the terrain/resource/building letter codes map onto
  the enum integers in §5 before authoring the parser.
- **`climate` == TribeType assumption.** `TileData.climate` is a bare `int`. The
  ground-theme suffixes match `TribeType` lowercase names 1:1, strongly implying
  `climate` holds a TribeType value, but I did not disassemble
  `TerrainRenderer.UpdateGraphics`/`SkinVisualsTransientData.SetupForTile`
  (@0x2D9F0DC) to confirm whether terrain art keys on `climate`, on the owner's
  `tribe`, or on `_skin` priority. The **terrain-render slice must confirm** the
  exact precedence (climate vs owner tribe vs `_skin`). Schema carries all three
  so either resolution works.
- **Resource "Game" vs "Fruit" naming.** `Game` (animal) uses `animal_<theme>`
  (no `ResourceGFX_` prefix) and `Fruit` uses `ResourceGFX_fruit_<theme>`; both
  are theme-suffixed, whereas Crop/Fish/Whale/Metal/Spores/Starfish/AquaCrop are
  theme-agnostic single sprites. Selection rule lives in the resource slice.
- **Player color packing** (ARGB/RGBA byte order) is unverified here; resolve in
  the tint slice via `GetPlayerColor` @0x7EE554.
- **Multi-tile units** (`leader`/`follower`, `passengerUnit`) are carried
  minimally (`passenger_type`); full transport-stack rendering is the unit slice's
  concern.
- **Skin vs climate sentinel.** `SkinType.None=-1`, `Default=0`. Treat both `<=0`
  as "no skin override → use climate theme"; confirm `-1` handling in the skin
  slice.
- Fields intentionally dropped (not needed for rendering): CommandStack,
  ActionStack, randomHash, pendingCommandTriggers, aiState, tasks, relations,
  messages, aggressions, currency, score/kills, upgradeTech,
  availablePopulation, continents, Seed/Version. Add back only if a future slice
  needs them.
