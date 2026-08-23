"""MapGenerator — dump.cs TypeDef 10664.

Same C# method names/signatures; working generate pipeline for all map presets.
Seed-bit parity vs the game binary needs RVA rebinding (see package README).
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from enums import Improvement, MapPreset, Resource, Terrain, Tribe
from gamestate import (
    GameState,
    ImprovementState,
    MapData,
    PlayerState,
    ResourceState,
    Shoreline,
    Shorelines,
    TileData,
    WorldContinent,
    WorldCoordinates,
)
from mapgenerator.enums_extra import MapGenerationType
from mapgenerator.gamedata import (
    ResourceData,
    TechData,
    TribeData,
    default_resources,
    resource_allowed_for_climate,
    resource_weight,
    resources_for_terrain,
    starting_resources_for_tribe,
    tribe_terrain_bias,
)
from mapgenerator.random_compat import XXHash, SystemRandom, fisher_yates_shuffle
from mapgenerator.settings import MapGeneratorSettings


class MapGenerator:
    """dump.cs MapGenerator — method names match C# exactly (including typos)."""

    LOG_PREFIX = "<color=#639ad8>[MapGenerator]</color>"
    MINIMUM_DOMAIN_SIZE = 3
    DESIRED_DOMAIN_SIZE = 5
    DEFAULT_CLIMATE = int(Tribe.IMPERIUS)  # TribeType = 7

    def __init__(self) -> None:
        self.random: SystemRandom = SystemRandom(0)
        self.mapGenerationType: int = int(MapGenerationType.DEFAULT)

    # ------------------------------------------------------------------ entry

    def GenerateWithSeed(
        self,
        seed: int,
        state: GameState,
        settings: MapGeneratorSettings,
        onComplete: Optional[Callable[[], None]],
    ) -> None:
        """MapGenerator.GenerateWithSeed."""
        state.seed = int(seed)
        self.random = SystemRandom(seed)
        self.Generate(state, settings, onComplete, numIterations=-1)

    def Generate(
        self,
        state: GameState,
        settings: MapGeneratorSettings,
        onComplete: Optional[Callable[[], None]],
        numIterations: int = -1,
    ) -> None:
        """MapGenerator.Generate — optional equality re-roll loop via settings."""
        if state.seed == 0:
            state.seed = self.random.Next()
            self.random = SystemRandom(state.seed)

        iterations = numIterations
        if iterations < 0:
            iterations = max(1, int(settings.equalityIterations) + 1)

        best_map: Optional[MapData] = None
        for _ in range(iterations):
            m = self.GenerateInternal(state.seed, state, settings)
            best_map = m
            # Phase 1: no inequality metric yet; single pass unless caller asks more.
            if settings.equalityIterations <= 0:
                break
            state.seed = self.random.Next()
            self.random = SystemRandom(state.seed)

        state.map = best_map
        if onComplete is not None:
            onComplete()

    # --------------------------------------------------------------- internal

    def GenerateInternal(
        self,
        seed: int,
        gameState: GameState,
        settings: MapGeneratorSettings,
    ) -> MapData:
        """MapGenerator.GenerateInternal — ordered pipeline (plan call graph)."""
        self.random = SystemRandom(seed)
        gameState.seed = int(seed)

        width = self._resolve_width(gameState, settings)
        height = width
        map_data = self._new_map(width, height, self.DEFAULT_CLIMATE)
        gameState.map = map_data

        self.ClearMapData(map_data)
        self.PrepareAlienClimates(gameState)

        land_indices: List[int] = []
        players = self._real_players(gameState)
        player_count = max(1, len(players))

        # Capitals first (noise path), then land bridges / noise fill.
        capital_indices = self.GeneratePlayerCapitalPositions(width, player_count)
        self.ReassignCapitalsBasedOnPlacementSettingsNoise(
            gameState, capital_indices, width
        )

        for i, idx in enumerate(capital_indices):
            if i >= len(players):
                break
            tile = map_data.tiles[idx]
            self.SetTileAsCapital(gameState, players[i], tile)
            land_indices.append(idx)
            # Seed a small land blob around each capital so noise has anchors.
            for nidx in self.GetCapitalNeighborIndices([idx], width):
                if nidx not in land_indices:
                    land_indices.append(nidx)
                    map_data.tiles[nidx].terrain = int(Terrain.FIELD)

        suburb_count = self.random.Next(
            settings.maxSuburbCount - settings.minSuburbCount + 1
        ) + settings.minSuburbCount
        suburbs = self.GenerateSuburbs(
            gameState, capital_indices, suburb_count, land_indices
        )
        land_indices.extend(suburbs)

        pre_city_count = int(
            settings.preTerrainCityDensity * width * height * 0.02
        )
        cities = self.GeneratePreTerrainCities(
            map_data, list(capital_indices), pre_city_count
        )

        use_islands = int(settings.mapType) in (
            int(MapPreset.CONTINENTS),
            int(MapPreset.ARCHIPELAGO),
            int(MapPreset.WATER_WORLD),
        )
        if use_islands:
            ok = self.TryGenerateMapFromIslands(
                map_data, gameState, settings, land_indices
            )
            if not ok:
                self.GenerateMapFromNoise(map_data, gameState, settings, land_indices)
        else:
            self.GenerateMapFromNoise(map_data, gameState, settings, land_indices)

        # Collect land after terrain pass.
        land_indices = [
            i
            for i, t in enumerate(map_data.tiles)
            if t.terrain
            in (
                int(Terrain.FIELD),
                int(Terrain.MOUNTAIN),
                int(Terrain.FOREST),
                int(Terrain.ICE),
                int(Terrain.WETLAND),
                int(Terrain.MANGROVE),
            )
        ]

        populated = max(1, player_count)
        noise = self.GenerateNoise(width, height, land_indices, settings.wetness)
        self.AddContinents(
            map_data,
            gameState,
            gameState.version,
            settings,
            capital_indices,
            noise,
            populated,
        )
        self.AddCitiesToContintents(map_data)
        if not self.TryAddCapitalsToContintents(gameState, map_data, populated):
            self.TryAddCapitalsToContentsTight(gameState, map_data)

        self.AddClimates(
            map_data, players, gameState.version, settings, land_indices
        )
        self.AddTerrain(
            map_data, players, gameState.version, settings, land_indices
        )
        self.MakeOcean(map_data, gameState, shouldConvertShallows=True)
        self.patchContinents(map_data)

        # postTerrainCityDensity scales extra villages (apart from capitals).
        # Log: "Will attempt to add another {1} cities apart from capitals, max {2}".
        # Spacing (≈2 tiles) is the real limiter; budget must not starve small maps.
        n_caps = sum(1 for t in map_data.tiles if t.capital_of)
        n_land = max(1, len(land_indices))
        extra_villages = max(
            player_count,
            int(settings.postTerrainCityDensity * n_land / 7.0),
        )
        self.AddPostTerrainCities(
            map_data,
            maxCityCount=n_caps + extra_villages,
        )

        self.AddResources(map_data, gameState, richness=settings.richness)
        for p in players:
            starts = self.getStartingResourcesForPlayer(gameState, p)
            self.addStartingResourcesToCapital(
                map_data, gameState, p, starts, minResourcesCount=2
            )

        ruin_amount = max(1, (width * height) // 40)
        self.AddRuins(map_data, ruin_amount, gameState)
        self.AddStarfish(map_data, amount=settings.richness)
        self.AddLightHouseImprovements(map_data, gameState)
        # Drop inland water pockets before coastal shallows (continents/islands).
        if int(settings.mapType) in (
            int(MapPreset.CONTINENTS),
            int(MapPreset.ARCHIPELAGO),
            int(MapPreset.WATER_WORLD),
            int(MapPreset.PANGEA),
        ):
            self.FillEnclosedWaterHoles(map_data, onlyIfDisconnectedFromEdge=True)
        else:
            # Still erase true 1×1 holes on lakes/dryland noise maps.
            self._fill_single_tile_water_holes(map_data)
        # Final coastal pass: any water/ocean 4-adjacent to land becomes shallow.
        self.ConvertLandAdjacentWaterToShallows(map_data)
        self.FinalizeCapitals(map_data, gameState)
        self.GenerateShoreLines(map_data)
        self.RevealAllTiles(map_data, gameState)
        return map_data

    def _fill_single_tile_water_holes(self, map: MapData) -> None:
        """Fill WATER/OCEAN tiles whose four orthogonal neighbours are all land."""
        width, height = map.width, map.height
        waterish = {int(Terrain.WATER), int(Terrain.OCEAN)}
        land = {
            int(Terrain.FIELD),
            int(Terrain.MOUNTAIN),
            int(Terrain.FOREST),
            int(Terrain.ICE),
            int(Terrain.WETLAND),
            int(Terrain.MANGROVE),
        }
        for tile in map.tiles:
            if tile.terrain not in waterish:
                continue
            ok = True
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                n = map.tile_at(tile.x + dx, tile.y + dy)
                if n is None or n.terrain not in land:
                    ok = False
                    break
            if ok:
                tile.terrain = int(Terrain.FIELD)

    def RevealAllTiles(self, map: MapData, gameState: GameState) -> None:
        """Mark every tile explored by all real players (fog-free render / SP start).

        Lighthouse *discovery* (tower height) is separate from fog — see
        ``built_unique_improvements`` / lighthouse renderer; corners stay
        height 0 until discovered even when tiles are revealed.
        """
        ids = [p.id for p in self._real_players(gameState)]
        if not ids:
            return
        for tile in map.tiles:
            for pid in ids:
                if pid not in tile.explorers:
                    tile.explorers.append(pid)

    def GenerateShoreLines(self, map: MapData) -> None:
        """MapDataExtensions.GenerateShoreLines — Water tiles bordered by land."""
        width, height = map.width, map.height
        land = {
            int(Terrain.FIELD),
            int(Terrain.MOUNTAIN),
            int(Terrain.FOREST),
            int(Terrain.ICE),
            int(Terrain.WETLAND),
            int(Terrain.MANGROVE),
        }

        def is_land(x: int, y: int) -> bool:
            if not (0 <= x < width and 0 <= y < height):
                return False
            return map.tiles[y * width + x].terrain in land

        for y in range(height):
            for x in range(width):
                tile = map.tiles[y * width + x]
                tile.shorelines = Shorelines()
                if tile.terrain != int(Terrain.WATER):
                    continue
                # Skip frozen shallow (climate==Polaris often); Phase 2 simple gate.
                if tile.climate == int(Tribe.POLARIS):
                    continue
                n = is_land(x, y + 1)
                s = is_land(x, y - 1)
                e = is_land(x + 1, y)
                w = is_land(x - 1, y)
                tile.shorelines = Shorelines(
                    any=n or s or e or w,
                    N=Shoreline(visible=n),
                    S=Shoreline(visible=s),
                    E=Shoreline(visible=e),
                    W=Shoreline(visible=w),
                )

    # --------------------------------------------------------------- clear

    def ClearMapData(self, map: MapData) -> None:
        """Reset tile contents; keep coordinates / grid."""
        for t in map.tiles:
            t.improvement = None
            t.resource = None
            t.unit = None
            t.owner = 0
            t.capital_of = 0
            t.has_road = False
            t.has_route = False
            t.had_route = False
            t.continent = None
            t.ruling_city_coordinates = WorldCoordinates(-1, -1)
            t.effects = []
            t.explorers = []
        map.continents = []

    def ClearCitiesFromMap(self, map: MapData) -> None:
        for t in map.tiles:
            if t.improvement is not None and t.improvement.type == int(Improvement.CITY):
                t.improvement = None
                t.capital_of = 0
                t.owner = 0

    # ---------------------------------------------------------- noise path

    def GenerateMapFromNoise(
        self,
        map: MapData,
        state: GameState,
        settings: MapGeneratorSettings,
        landIndices: List[int],
    ) -> None:
        width, height = map.width, map.height
        noise = self.GenerateNoise(width, height, landIndices, settings.wetness)
        self.SmoothNoise(
            width,
            height,
            noise,
            landIndices,
            settings.smoothIterations,
            settings.surroundingSpaceValue,
        )
        capitals = [
            i
            for i, t in enumerate(map.tiles)
            if t.capital_of and t.capital_of != PlayerState.NATURE_PLAYER_ID
        ]
        cities = [
            i
            for i, t in enumerate(map.tiles)
            if t.improvement is not None
            and t.improvement.type == int(Improvement.CITY)
        ]
        self.SetTerrainFromNoise(
            map,
            state,
            noise,
            cities,
            capitals,
            landIndices,
            settings.wetness,
            settings.shallowPercentOfWater,
        )

    def GenerateNoise(
        self,
        width: int,
        height: int,
        landIndices: List[int],
        wetness: float,
    ) -> List[float]:
        n = width * height
        noise = [self.random.NextFloat() for _ in range(n)]
        # Bias capital/land anchors toward land (above wetness cut).
        for idx in landIndices:
            if 0 <= idx < n:
                noise[idx] = max(noise[idx], min(0.99, wetness + 0.15))
        return noise

    def SmoothNoise(
        self,
        width: int,
        height: int,
        noise: List[float],
        landIndices: List[int],
        iterations: int,
        surroundingSpaceValue: float,
    ) -> None:
        land = set(landIndices)
        for _ in range(max(0, iterations)):
            nxt = list(noise)
            for y in range(height):
                for x in range(width):
                    i = y * width + x
                    acc = noise[i]
                    count = 1.0
                    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < width and 0 <= ny < height:
                            acc += noise[ny * width + nx]
                            count += 1.0
                        else:
                            acc += surroundingSpaceValue
                            count += 1.0
                    nxt[i] = acc / count
                    if i in land:
                        nxt[i] = min(nxt[i], noise[i])
            noise[:] = nxt

    def SetTerrainFromNoise(
        self,
        map: MapData,
        state: GameState,
        noise: List[float],
        cityTileIndices: List[int],
        capitalTileIndices: List[int],
        landTileIndices: List[int],
        wetness: float,
        percentShallows: float,
    ) -> None:
        forced_land = set(capitalTileIndices) | set(cityTileIndices) | set(landTileIndices)
        # Wetness = fraction of non-forced tiles that should be water/ocean.
        # After SmoothNoise the raw [0,1] cut is unreliable, so use a quantile.
        free = [noise[i] for i in range(len(noise)) if i not in forced_land]
        free_sorted = sorted(free)
        wet = max(0.0, min(1.0, wetness))
        if free_sorted:
            cut_idx = min(len(free_sorted) - 1, int(wet * len(free_sorted)))
            water_cut = free_sorted[cut_idx]
        else:
            water_cut = wet

        for i, tile in enumerate(map.tiles):
            if i in forced_land:
                tile.terrain = int(Terrain.FIELD)
                continue
            v = noise[i]
            if v < water_cut:
                # Deeper (lower) values → ocean; near-cut → shallow water.
                if free_sorted and water_cut > free_sorted[0]:
                    depth = (water_cut - v) / (water_cut - free_sorted[0])
                else:
                    depth = 1.0
                shallow_keep = max(0.0, min(1.0, percentShallows))
                if depth > 0.45 + 0.50 * (1.0 - shallow_keep):
                    tile.terrain = int(Terrain.OCEAN)
                else:
                    tile.terrain = int(Terrain.WATER)
            else:
                # Land band by how far above the cut.
                span = max(1e-6, (free_sorted[-1] if free_sorted else 1.0) - water_cut)
                band = (v - water_cut) / span
                if band > 0.75:
                    tile.terrain = int(Terrain.MOUNTAIN)
                elif band > 0.35:
                    tile.terrain = int(Terrain.FOREST)
                else:
                    tile.terrain = int(Terrain.FIELD)
        for i in set(capitalTileIndices) | set(cityTileIndices):
            if 0 <= i < len(map.tiles):
                map.tiles[i].terrain = int(Terrain.FIELD)

    def TryGenerateMapFromIslands(
        self,
        map: MapData,
        gameState: GameState,
        settings: MapGeneratorSettings,
        landIndices: List[int],
    ) -> bool:
        """Grow separate landmasses from capital seeds (Continents / Archipelago / WaterWorld).

        Target land fraction ≈ 1 - wetness. Each capital owns a blob; candidates that
        touch another owner's land (Chebyshev ≤ 1) are rejected so continents stay
        ≥1 tile apart (wiki).
        """
        width, height = map.width, map.height
        n = width * height
        noise = self.GenerateNoise(width, height, landIndices, settings.wetness)
        self.SmoothNoise(
            width,
            height,
            noise,
            landIndices,
            settings.smoothIterations,
            settings.surroundingSpaceValue,
        )

        for tile in map.tiles:
            tile.terrain = int(Terrain.OCEAN)

        capitals = [
            i for i, t in enumerate(map.tiles) if t.capital_of and t.capital_of != 0
        ]
        if not capitals:
            capitals = [i for i in landIndices if 0 <= i < n][
                : max(1, gameState.PlayerCount)
            ]
        if not capitals:
            return False

        land_frac = max(0.05, min(0.95, 1.0 - settings.wetness))
        if int(settings.mapType) == int(MapPreset.ARCHIPELAGO):
            land_frac *= 0.75
        elif int(settings.mapType) == int(MapPreset.WATER_WORLD):
            land_frac = min(land_frac, 0.18)

        target_land = max(len(capitals) * 6, int(n * land_frac))
        per_seed = max(4, target_land // max(1, len(capitals)))

        owner = [-1] * n  # capital-index owner, -1 = sea

        def touches_other(idx: int, oid: int) -> bool:
            x, y = idx % width, idx // width
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        o = owner[ny * width + nx]
                        if o >= 0 and o != oid:
                            return True
            return False

        for oid, cap in enumerate(capitals):
            owner[cap] = oid
            map.tiles[cap].terrain = int(Terrain.FIELD)

        for oid, cap in enumerate(capitals):
            grown = 1
            frontier = [cap]
            while frontier and grown < per_seed:
                candidates: List[Tuple[float, int]] = []
                for idx in frontier:
                    x, y = idx % width, idx // width
                    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        nx, ny = x + dx, y + dy
                        if not (0 <= nx < width and 0 <= ny < height):
                            continue
                        nidx = ny * width + nx
                        if owner[nidx] >= 0:
                            continue
                        if touches_other(nidx, oid):
                            continue
                        candidates.append((noise[nidx], nidx))
                if not candidates:
                    break
                candidates.sort(key=lambda t: t[0], reverse=True)
                top = candidates[: max(1, min(5, len(candidates)))]
                _, pick = top[self.random.Next(len(top))]
                owner[pick] = oid
                map.tiles[pick].terrain = int(Terrain.FIELD)
                frontier.append(pick)
                grown += 1
                if pick not in landIndices:
                    landIndices.append(pick)

        # Secondary islands (archipelago): small blobs that keep the gap rule.
        remaining = target_land - sum(1 for o in owner if o >= 0)
        if remaining > 0 and int(settings.mapType) == int(MapPreset.ARCHIPELAGO):
            spots = list(range(n))
            self.Shuffle_ints(spots)
            next_oid = len(capitals)
            for idx in spots:
                if remaining <= 0:
                    break
                if owner[idx] >= 0 or noise[idx] < 0.6:
                    continue
                if touches_other(idx, next_oid):
                    continue
                # Grow a tiny 3–6 tile islet.
                islet = [idx]
                owner[idx] = next_oid
                map.tiles[idx].terrain = int(Terrain.FIELD)
                remaining -= 1
                landIndices.append(idx)
                size = 3 + self.random.Next(4)
                grown = 1
                while grown < size and remaining > 0:
                    cands = []
                    for i2 in islet:
                        x, y = i2 % width, i2 // width
                        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                            nx, ny = x + dx, y + dy
                            if not (0 <= nx < width and 0 <= ny < height):
                                continue
                            nidx = ny * width + nx
                            if owner[nidx] >= 0:
                                continue
                            if touches_other(nidx, next_oid):
                                continue
                            cands.append(nidx)
                    if not cands:
                        break
                    pick = cands[self.random.Next(len(cands))]
                    owner[pick] = next_oid
                    map.tiles[pick].terrain = int(Terrain.FIELD)
                    islet.append(pick)
                    landIndices.append(pick)
                    grown += 1
                    remaining -= 1
                next_oid += 1

        for i, tile in enumerate(map.tiles):
            if tile.terrain != int(Terrain.FIELD) or owner[i] < 0:
                continue
            if i in capitals:
                continue
            band = noise[i]
            if band > 0.85:
                tile.terrain = int(Terrain.MOUNTAIN)
            elif band > 0.65:
                tile.terrain = int(Terrain.FOREST)

        self._paint_shallows(map, percentShallows=settings.shallowPercentOfWater)
        # Island growth can ring-fence ocean cells; fill pockets not open to the rim.
        self.FillEnclosedWaterHoles(map, onlyIfDisconnectedFromEdge=True)
        return True

    def FillEnclosedWaterHoles(
        self, map: MapData, onlyIfDisconnectedFromEdge: bool = True
    ) -> None:
        """Remove inland water pockets left inside landmasses.

        Continent/island growth attaches land tile-by-tile and can enclose OCEAN
        cells. The later shallows pass turns those into 1×1 WATER holes. Water
        that still reaches the map rim (true sea) is kept.
        """
        width, height = map.width, map.height
        waterish = {int(Terrain.WATER), int(Terrain.OCEAN)}
        n = width * height
        sea_connected = [False] * n

        def is_water(i: int) -> bool:
            return map.tiles[i].terrain in waterish

        # Flood from every water tile on the map border.
        stack: List[int] = []
        for x in range(width):
            for y in (0, height - 1):
                i = y * width + x
                if is_water(i):
                    stack.append(i)
        for y in range(height):
            for x in (0, width - 1):
                i = y * width + x
                if is_water(i):
                    stack.append(i)
        while stack:
            i = stack.pop()
            if sea_connected[i] or not is_water(i):
                continue
            sea_connected[i] = True
            x, y = i % width, i // width
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    stack.append(ny * width + nx)

        for i, tile in enumerate(map.tiles):
            if not is_water(i):
                continue
            if onlyIfDisconnectedFromEdge and sea_connected[i]:
                continue
            # Enclosed (or forced fill): turn into land.
            tile.terrain = int(Terrain.FIELD)

    def _paint_shallows(self, map: MapData, percentShallows: float = 0.2) -> None:
        """Ocean tiles adjacent to land become Water (shallow)."""
        width, height = map.width, map.height
        land = {
            int(Terrain.FIELD),
            int(Terrain.MOUNTAIN),
            int(Terrain.FOREST),
            int(Terrain.ICE),
            int(Terrain.WETLAND),
            int(Terrain.MANGROVE),
        }
        to_shallow: List[int] = []
        for y in range(height):
            for x in range(width):
                i = y * width + x
                tile = map.tiles[i]
                if tile.terrain != int(Terrain.OCEAN):
                    continue
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        if map.tiles[ny * width + nx].terrain in land:
                            to_shallow.append(i)
                            break
        # Optionally keep only a fraction as shallow (rest stay ocean for steep coasts).
        self.Shuffle_ints(to_shallow)
        keep = max(1, int(len(to_shallow) * max(0.15, min(1.0, 0.5 + percentShallows))))
        for i in to_shallow[:keep]:
            map.tiles[i].terrain = int(Terrain.WATER)

    # --------------------------------------------------------- capitals

    def GeneratePlayerCapitalPositions(
        self, width: int, playerCount: int
    ) -> List[int]:
        """Quadrant-aware probability-table capital placement.

        Dryland/Lakes/Archipelago/WaterWorld place one capital per unoccupied
        quadrant (wiki). Continents/Pangea still use the global probability table
        with DomainSize / MinCapitalDistance exclusion.
        """
        n = width * width
        domain = self.DomainSize(width, playerCount)
        min_dist = self.MinCapitalDistance(width, playerCount)
        exclude = max(domain, min_dist)
        capitals: List[int] = []
        probabilities = [1] * n
        # Keep a 1-tile margin from map edge (wiki / common RE), and never
        # spawn within 1 tile (Chebyshev) of reserved corner lighthouse sites.
        for y in range(width):
            for x in range(width):
                if x < 1 or y < 1 or x >= width - 1 or y >= width - 1:
                    probabilities[y * width + x] = 0
                elif self.IsNearReservedLighthouse(x, y, width, width, radius=1):
                    probabilities[y * width + x] = 0

        side = self._domain_grid_side(playerCount)
        cell = max(1, width // side)
        used_quadrants: set = set()

        for p in range(playerCount):
            # Prefer an unused quadrant.
            q_order = list(range(side * side))
            self.Shuffle_ints(q_order)
            picked = False
            for q in q_order:
                if q in used_quadrants and len(used_quadrants) < side * side:
                    continue
                qx, qy = q % side, q // side
                x0, y0 = qx * cell, qy * cell
                x1 = width if qx == side - 1 else (qx + 1) * cell
                y1 = width if qy == side - 1 else (qy + 1) * cell
                total = self.CalculateProbabilityInRange(
                    probabilities, width, x0, x1, y0, y1
                )
                if total <= 0:
                    continue
                value = self.random.Next(total)
                pick = self.IndexForProbabilityValueInRange(
                    probabilities, width, value, x0, x1, y0, y1
                )
                capitals.append(pick)
                used_quadrants.add(q)
                coords = WorldCoordinates(pick % width, pick // width)
                self.AddDistanceToProbabilityTable(
                    probabilities, width, coords, exclude
                )
                picked = True
                break
            if picked:
                continue
            # Global fallback.
            total = self.CalculateProbabilityInRange(
                probabilities, width, 0, width, 0, width
            )
            if total <= 0:
                candidates = [
                    i
                    for i in range(n)
                    if i not in capitals
                    and not self.IsNearReservedLighthouse(
                        i % width, i // width, width, width, radius=1
                    )
                ]
                if not candidates:
                    break
                pick = candidates[self.random.Next(len(candidates))]
            else:
                value = self.random.Next(total)
                pick = self.IndexForProbabilityValueInRange(
                    probabilities, width, value, 0, width, 0, width
                )
            capitals.append(pick)
            coords = WorldCoordinates(pick % width, pick // width)
            self.AddDistanceToProbabilityTable(
                probabilities, width, coords, exclude
            )
        return capitals

    @staticmethod
    def _domain_grid_side(playerCount: int) -> int:
        """Wiki Map Generation: 1–4→4 domains, 5–9→9, 10–16→16."""
        if playerCount <= 4:
            return 2
        if playerCount <= 9:
            return 3
        return 4

    @staticmethod
    def MinCapitalDistance(mapWidth: int, playerCount: int) -> int:
        """Roughly one domain width; clamped to MINIMUM_DOMAIN_SIZE."""
        if playerCount <= 1:
            return MapGenerator.MINIMUM_DOMAIN_SIZE
        side = MapGenerator._domain_grid_side(playerCount)
        return max(MapGenerator.MINIMUM_DOMAIN_SIZE, mapWidth // side)

    @staticmethod
    def DomainSize(mapWidth: int, playerCount: int) -> int:
        """Desired exclusion radius for capital probability table."""
        if playerCount <= 0:
            return MapGenerator.DESIRED_DOMAIN_SIZE
        side = MapGenerator._domain_grid_side(playerCount)
        return max(
            MapGenerator.MINIMUM_DOMAIN_SIZE,
            min(MapGenerator.DESIRED_DOMAIN_SIZE, mapWidth // side),
        )

    def AddDistanceToProbabilityTable(
        self,
        probabilities: List[int],
        width: int,
        coordinates: WorldCoordinates,
        domainSize: int,
    ) -> None:
        for y in range(width):
            for x in range(width):
                i = y * width + x
                dx = abs(x - coordinates.x)
                dy = abs(y - coordinates.y)
                d = max(dx, dy)  # Chebyshev
                if d < domainSize:
                    probabilities[i] = 0
                elif probabilities[i] > 0:
                    # Farther tiles keep / gain weight.
                    probabilities[i] = max(1, probabilities[i] + d)

    def CalculateProbabilityInRange(
        self,
        probabilities: List[int],
        width: int,
        startX: int,
        endX: int,
        startY: int,
        endY: int,
    ) -> int:
        total = 0
        for y in range(startY, endY):
            for x in range(startX, endX):
                total += probabilities[y * width + x]
        return total

    def IndexForProbabilityValueInRange(
        self,
        probabilities: List[int],
        width: int,
        value: int,
        startX: int,
        endX: int,
        startY: int,
        endY: int,
    ) -> int:
        running = 0
        last = startY * width + startX
        for y in range(startY, endY):
            for x in range(startX, endX):
                i = y * width + x
                p = probabilities[i]
                if p <= 0:
                    continue
                running += p
                last = i
                if running > value:
                    return i
        return last

    def ReassignCapitalsBasedOnPlacementSettingsNoise(
        self, gameState: GameState, playerCapitals: List[int], width: int
    ) -> None:
        # Phase 1: honor WestMapPlacementUserId later; keep generated order.
        return

    def ReassignCapitalsBasedOnPlacementSettingsContinents(
        self, gameState: GameState, playerCapitals: List[TileData], width: int
    ) -> None:
        return

    def SetTileAsCapital(
        self, gameState: GameState, playerState: PlayerState, tile: TileData
    ) -> None:
        tile.terrain = int(Terrain.FIELD)
        tile.owner = playerState.id
        tile.capital_of = playerState.id
        tile.climate = playerState.climate or playerState.tribe or self.DEFAULT_CLIMATE
        tile.improvement = ImprovementState(
            type=int(Improvement.CITY),
            owner=playerState.id,
            founder=playerState.id,
            level=1,
            border_size=1,
            production=2,  # default capital income (2★/turn)
            name=self._village_name(tile),
        )
        playerState.start_tile = WorldCoordinates(tile.x, tile.y)
        playerState.cities = max(1, playerState.cities)

    def FinalizeCapitals(self, map: MapData, gameState: GameState) -> None:
        """After gen: capitals are level-1 named cities with a 3×3 owned border."""
        for tile in map.tiles:
            if not tile.capital_of:
                continue
            pid = int(tile.capital_of)
            if tile.improvement is None or tile.improvement.type != int(Improvement.CITY):
                tile.improvement = ImprovementState(
                    type=int(Improvement.CITY),
                    owner=pid,
                    founder=pid,
                    level=1,
                    border_size=1,
                    production=2,
                )
            tile.improvement.level = 1
            tile.improvement.owner = pid
            tile.improvement.founder = pid
            tile.improvement.border_size = 1
            if tile.improvement.production <= 0:
                tile.improvement.production = 2
            if not (tile.improvement.name or "").strip():
                tile.improvement.name = self._village_name(tile)
            tile.owner = pid
            tile.terrain = int(Terrain.FIELD)

            # Claim Chebyshev radius 1 (3×3) for territory borders.
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    n = map.tile_at(tile.x + dx, tile.y + dy)
                    if n is None:
                        continue
                    if n.capital_of and n.capital_of != pid:
                        continue
                    n.owner = pid

            # Keep player.start_tile in sync.
            for p in gameState.player_states:
                if p.id == pid:
                    p.start_tile = WorldCoordinates(tile.x, tile.y)
                    p.cities = max(1, p.cities)
                    break

    def SetTileAsCity(self, tile: TileData) -> None:
        # Villages sit on field (same as capitals); keep climate for village art.
        if not tile.capital_of:
            tile.terrain = int(Terrain.FIELD)
        if tile.improvement is None:
            tile.improvement = ImprovementState(type=int(Improvement.CITY), level=1)
        else:
            tile.improvement.type = int(Improvement.CITY)
            tile.improvement.level = max(1, tile.improvement.level)
        if not (tile.improvement.name or "").strip():
            tile.improvement.name = self._village_name(tile)

    def _village_name(self, tile: TileData) -> str:
        """Deterministic short village label from tile coords."""
        syllables = (
            "ba", "di", "lo", "mu", "na", "ro", "sa", "te", "vi", "xo", "yu", "zi",
        )
        n = (tile.x * 73856093) ^ (tile.y * 19349663) ^ 0xC0FFEE
        a = syllables[n % len(syllables)]
        b = syllables[(n >> 8) % len(syllables)]
        c = syllables[(n >> 16) % len(syllables)]
        return (a + b + c).capitalize()

    def GetCapitalNeighborIndices(
        self, capitals: List[int], mapWidth: int
    ) -> List[int]:
        out: List[int] = []
        for idx in capitals:
            x, y = idx % mapWidth, idx // mapWidth
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < mapWidth and 0 <= ny < mapWidth:
                    out.append(ny * mapWidth + nx)
        return out

    def GenerateSuburbs(
        self,
        state: GameState,
        capitalIndices: List[int],
        suburbCount: int,
        landIndices: List[int],
    ) -> List[int]:
        width = state.map.width if state.map else 0
        if width <= 0:
            return []
        suburbs: List[int] = []
        for cap in capitalIndices:
            neighbors = self.GetCapitalNeighborIndices([cap], width)
            self.Shuffle_ints(neighbors)
            added = 0
            for n in neighbors:
                if added >= suburbCount:
                    break
                if n in capitalIndices or n in suburbs:
                    continue
                suburbs.append(n)
                if n not in landIndices:
                    landIndices.append(n)
                added += 1
        return suburbs

    def GeneratePreTerrainCities(
        self, map: MapData, cities: List[int], cityCount: int
    ) -> List[int]:
        """Pre-terrain village anchors. Skip ocean rim; keep clear of capitals."""
        width = map.width
        out = list(cities)
        if cityCount <= 0:
            return out
        spots = [
            i
            for i in range(width * map.height)
            if (i % width) not in (0, width - 1)
            and (i // width) not in (0, map.height - 1)
        ]
        self.Shuffle_ints(spots)
        min_sep = max(2, self.MinCapitalDistance(width, max(2, len(cities))))
        for idx in spots:
            if len(out) - len(cities) >= cityCount:
                break
            if idx in out:
                continue
            if self.IsWithinRangeOfIndices(
                WorldCoordinates(idx % width, idx // width), out, width, range=min_sep
            ):
                continue
            tile = map.tiles[idx]
            if tile.capital_of:
                continue
            # Soft FIELD seed so later terrain passes treat it as land-friendly.
            if tile.terrain in (int(Terrain.OCEAN), int(Terrain.WATER), int(Terrain.NONE)):
                tile.terrain = int(Terrain.FIELD)
            self.SetTileAsCity(tile)
            out.append(idx)
        return out

    def AddPostTerrainCities(self, map: MapData, maxCityCount: int = 200) -> None:
        """Place villages on valid land, spaced away from capitals and each other."""
        width = map.width
        spots = self.GetAllValidCitySpotIndices(map)
        self.Shuffle_ints(spots)
        existing_idx = [
            i
            for i, t in enumerate(map.tiles)
            if t.improvement and t.improvement.type == int(Improvement.CITY)
        ]
        # Drop villages that ended up in water after terrain gen (keep capitals).
        for i in list(existing_idx):
            t = map.tiles[i]
            if t.terrain in (int(Terrain.WATER), int(Terrain.OCEAN), int(Terrain.NONE)):
                if not t.capital_of:
                    t.improvement = None
                    existing_idx.remove(i)

        existing = len(existing_idx)
        # Wiki Map Generation: villages ≥2 tiles apart (non-overlapping borders).
        # Capitals keep a slightly larger keep-out so starts aren't crushed.
        village_sep = 2
        capital_sep = max(2, width // 5)
        for idx in spots:
            if existing >= maxCityCount:
                break
            tile = map.tiles[idx]
            if tile.capital_of:
                continue
            if not self.IsValidCityLocation(tile, map):
                continue
            if self.IsNearCapital(map, tile, radius=capital_sep, includeCenter=True):
                continue
            if self.IsNearCity(map, tile, radius=village_sep):
                continue
            if tile.resource is not None:
                tile.resource = None
            self.SetTileAsCity(tile)
            existing_idx.append(idx)
            existing += 1

    def GetAllValidCitySpotIndices(self, map: MapData) -> List[int]:
        return [
            i
            for i, t in enumerate(map.tiles)
            if self.IsValidCityLocation(t, map)
        ]

    def GetAllValidCapitalSpotIndices(
        self, gameState: GameState, map: MapData
    ) -> List[int]:
        return [
            i
            for i, t in enumerate(map.tiles)
            if self.IsValidCapitalLocation(gameState, map, t)
        ]

    def IsValidCityLocation(self, tile: TileData, map: MapData) -> bool:
        if tile.capital_of:
            return False
        if tile.terrain not in (
            int(Terrain.FIELD),
            int(Terrain.FOREST),
            int(Terrain.WETLAND),
        ):
            return False
        if tile.improvement is not None and tile.improvement.type != int(Improvement.NONE):
            return False
        # Prefer tiles with at least one land neighbour (not a lone rock).
        land = {
            int(Terrain.FIELD),
            int(Terrain.MOUNTAIN),
            int(Terrain.FOREST),
            int(Terrain.ICE),
            int(Terrain.WETLAND),
        }
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            n = map.tile_at(tile.x + dx, tile.y + dy)
            if n and n.terrain in land:
                return True
        return False

    def IsGoodCityLocation(self, tile: TileData, map: MapData) -> bool:
        capital_sep = max(2, map.width // 5)
        return self.IsValidCityLocation(tile, map) and not self.IsNearCapital(
            map, tile, radius=capital_sep, includeCenter=True
        )

    def IsValidForcedCityLocationOnSameContinent(
        self, tile: TileData, map: MapData
    ) -> bool:
        return self.IsValidCityLocation(tile, map)

    def IsValidCapitalLocation(
        self, gameState: GameState, map: MapData, tile: TileData
    ) -> bool:
        return self.IsCapitalPositionPossible(gameState, map, tile)

    def IsCapitalPositionPossible(
        self, gameState: GameState, map: MapData, tile: TileData
    ) -> bool:
        if self.IsNearReservedLighthouse(
            tile.x, tile.y, map.width, map.height, radius=1
        ):
            return False
        return tile.terrain in (
            int(Terrain.FIELD),
            int(Terrain.FOREST),
            int(Terrain.MOUNTAIN),
        )

    def IsWithinRangeOfIndices(
        self,
        coordinates: WorldCoordinates,
        indices: List[int],
        width: int,
        range: int = 2,
    ) -> bool:
        for idx in indices:
            x, y = idx % width, idx // width
            if max(abs(coordinates.x - x), abs(coordinates.y - y)) <= range:
                return True
        return False

    def AddLandIndicesBetweenTiles(
        self,
        fromCoordinate: WorldCoordinates,
        toIndex: int,
        landIndices: List[int],
        width: int,
    ) -> None:
        tx, ty = toIndex % width, toIndex // width
        x, y = fromCoordinate.x, fromCoordinate.y
        while x != tx or y != ty:
            if x < tx:
                x += 1
            elif x > tx:
                x -= 1
            if y < ty:
                y += 1
            elif y > ty:
                y -= 1
            idx = y * width + x
            if idx not in landIndices:
                landIndices.append(idx)

    def RemoveIndicesNearIndex(
        self, indices: List[int], index: int, width: int, range: int
    ) -> None:
        cx, cy = index % width, index // width
        keep = []
        for idx in indices:
            x, y = idx % width, idx // width
            if max(abs(x - cx), abs(y - cy)) > range:
                keep.append(idx)
        indices[:] = keep

    # ------------------------------------------------------- continents

    def AddContinents(
        self,
        map: MapData,
        gameState: GameState,
        version: int,
        settings: MapGeneratorSettings,
        startingPositions: List[int],
        noise: List[float],
        populatedContinentsCount: int,
    ) -> None:
        width = map.width
        visited = set()
        continents: List[WorldContinent] = []

        def flood(start: int) -> WorldContinent:
            stack = [start]
            tiles: List[WorldCoordinates] = []
            while stack:
                i = stack.pop()
                if i in visited:
                    continue
                visited.add(i)
                t = map.tiles[i]
                if t.terrain in (int(Terrain.WATER), int(Terrain.OCEAN), int(Terrain.NONE)):
                    continue
                tiles.append(WorldCoordinates(t.x, t.y))
                t.continent = None  # set after
                x, y = t.x, t.y
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < map.height:
                        stack.append(ny * width + nx)
            cont = WorldContinent(tiles=tiles, land_tile_count=len(tiles))
            for c in tiles:
                map.tiles[c.y * width + c.x].continent = cont
            return cont

        for i, t in enumerate(map.tiles):
            if i in visited:
                continue
            if t.terrain in (int(Terrain.WATER), int(Terrain.OCEAN), int(Terrain.NONE)):
                visited.add(i)
                continue
            continents.append(flood(i))

        # Expand from starting positions if needed.
        for idx in startingPositions:
            if 0 <= idx < len(map.tiles) and map.tiles[idx].continent is None:
                continents.append(flood(idx))

        map.continents = continents
        for cont in continents:
            self._expandContinent(cont, map, noise, settings)

    def _expandContinent(
        self,
        continent: WorldContinent,
        map: MapData,
        noise: List[float],
        settings: MapGeneratorSettings,
    ) -> None:
        """Compiler-generated <AddContinents>g__expandContinent|28_0 stand-in."""
        # Phase 1: no extra expansion beyond flood fill.
        continent.land_tile_count = len(continent.tiles)

    def expandContinent_28_0(
        self,
        continent: WorldContinent,
        brokenTiles: set,
        map: MapData,
        noise: List[float],
        settings: MapGeneratorSettings,
        panic: int,
        completedTileCount: int,
    ) -> None:
        self._expandContinent(continent, map, noise, settings)

    def AddCitiesToContintents(self, map: MapData) -> None:
        for cont in map.continents:
            if cont.land_tile_count >= self.MINIMUM_DOMAIN_SIZE:
                self.AddCityToContinent(cont, map)

    def AddCityToContinent(self, continent: WorldContinent, map: MapData) -> bool:
        width = map.width
        candidates = [
            map.tiles[c.y * width + c.x]
            for c in continent.tiles
            if self.IsGoodCityLocation(map.tiles[c.y * width + c.x], map)
        ]
        if not candidates:
            candidates = [
                map.tiles[c.y * width + c.x]
                for c in continent.tiles
                if self.IsValidCityLocation(map.tiles[c.y * width + c.x], map)
            ]
        if not candidates:
            return False
        self.Shuffle(candidates)
        tile = candidates[0]
        if tile.resource is not None:
            tile.resource = None
        self.SetTileAsCity(tile)
        return True

    def TryAddCapitalsToContintents(
        self, gameState: GameState, map: MapData, populatedContinentsCount: int
    ) -> bool:
        players = self._real_players(gameState)
        capitals = [
            t for t in map.tiles if t.capital_of and t.capital_of != 0
        ]
        if len(capitals) >= len(players):
            return True
        conts = sorted(
            map.continents, key=lambda c: c.land_tile_count, reverse=True
        )
        for i, p in enumerate(players):
            if any(t.capital_of == p.id for t in map.tiles):
                continue
            if i >= len(conts):
                break
            if not self.TryAddCapitalToContinent(
                gameState, p, conts[i], map, capitals
            ):
                return False
        return True

    def TryAddCapitalsToContentsTight(
        self, gameState: GameState, map: MapData
    ) -> bool:
        return self.TryAddCapitalsToContintents(
            gameState, map, populatedContinentsCount=len(map.continents)
        )

    def TryAddCapitalToContinent(
        self,
        gameState: GameState,
        player: PlayerState,
        targetContinent: WorldContinent,
        map: MapData,
        capitals: List[TileData],
    ) -> bool:
        width = map.width
        tiles = [
            WorldCoordinates(c.x, c.y)
            for c in targetContinent.tiles
            if self.IsCapitalPositionPossible(
                gameState, map, map.tiles[c.y * width + c.x]
            )
        ]
        if not tiles:
            pos = self.GetEmergencyCityPosition(gameState, map)
            tile = map.tile_at(pos.x, pos.y)
            if tile is None:
                return False
            self.SetTileAsCapital(gameState, player, tile)
            capitals.append(tile)
            return True
        best = self.GetBestCityCoordinates(gameState, map, tiles, capitals)
        tile = map.tile_at(best.x, best.y)
        if tile is None:
            return False
        self.SetTileAsCapital(gameState, player, tile)
        capitals.append(tile)
        return True

    def GetBestCityCoordinates(
        self,
        gameState: GameState,
        map: MapData,
        tiles: List[WorldCoordinates],
        currentCities: List[TileData],
    ) -> WorldCoordinates:
        best = tiles[0]
        best_score = -1.0
        for c in tiles:
            score = self.DistanceSqrToClosestCity(map, c)
            if score > best_score:
                best_score = score
                best = c
        return best

    def GetEmergencyCityPosition(
        self, gameState: GameState, map: MapData
    ) -> WorldCoordinates:
        spots = self.GetAllValidCapitalSpotIndices(gameState, map)
        if not spots:
            return WorldCoordinates(map.width // 2, map.height // 2)
        idx = spots[self.random.Next(len(spots))]
        return WorldCoordinates(idx % map.width, idx // map.width)

    def patchContinents(self, map: MapData) -> None:
        for cont in map.continents:
            cont.land_tile_count = len(cont.tiles)

    # ---------------------------------------------------- climate / terrain

    def PrepareAlienClimates(self, gameState: GameState) -> None:
        for p in gameState.player_states:
            if p.tribe in (int(Tribe.POLARIS), int(Tribe.CYMANTI)):
                p.climate = p.tribe

    def AddClimates(
        self,
        map: MapData,
        playerStates: List[PlayerState],
        version: int,
        settings: MapGeneratorSettings,
        landTileIndices: List[int],
    ) -> None:
        if not playerStates:
            return
        by_id = {p.id: p for p in playerStates if p.id}
        # Continent climate from capital sitting on that landmass (island maps).
        for cont in map.continents:
            owner_climate = 0
            for c in cont.tiles:
                t = map.tiles[c.y * map.width + c.x]
                if not t.capital_of:
                    continue
                p = by_id.get(t.capital_of)
                if p:
                    owner_climate = p.climate or p.tribe or self.DEFAULT_CLIMATE
                    break
            cont.climate = owner_climate

        capitals = [
            (p, p.start_tile) for p in playerStates if p.id and p.start_tile
        ]

        def nearest_climate(tile: TileData) -> int:
            if not capitals:
                return self.DEFAULT_CLIMATE
            best_p = capitals[0][0]
            best_d = 10**9
            for p, st in capitals:
                d = (tile.x - st.x) ** 2 + (tile.y - st.y) ** 2
                if d < best_d:
                    best_d = d
                    best_p = p
            return best_p.climate or best_p.tribe or self.DEFAULT_CLIMATE

        for idx in landTileIndices:
            tile = map.tiles[idx]
            if tile.continent is not None and tile.continent.climate:
                tile.climate = tile.continent.climate
            else:
                tile.climate = nearest_climate(tile)

        # Paint shallow/ocean fringe from nearest land climate so shores match.
        for t in map.tiles:
            if t.climate:
                continue
            if t.terrain not in (int(Terrain.WATER), int(Terrain.OCEAN)):
                t.climate = nearest_climate(t)
                continue
            found = 0
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                n = map.tile_at(t.x + dx, t.y + dy)
                if n and n.climate and n.terrain not in (
                    int(Terrain.WATER),
                    int(Terrain.OCEAN),
                ):
                    found = n.climate
                    break
            t.climate = found or nearest_climate(t)

        for t in map.tiles:
            if not t.climate:
                t.climate = self.DEFAULT_CLIMATE

    def AddTerrain(
        self,
        map: MapData,
        playerStates: List[PlayerState],
        version: int,
        settings: MapGeneratorSettings,
        landTileIndices: List[int],
    ) -> None:
        """Retouch FIELD tiles using climate-tribe forest/mountain/ice bias."""
        for idx in landTileIndices:
            tile = map.tiles[idx]
            if tile.terrain not in (int(Terrain.FIELD), int(Terrain.FOREST), int(Terrain.MOUNTAIN)):
                continue
            # Capitals and villages stay on FIELD (city footprint).
            if tile.capital_of or (
                tile.improvement is not None
                and tile.improvement.type == int(Improvement.CITY)
            ):
                tile.terrain = int(Terrain.FIELD)
                continue
            forest_w, mountain_w, ice_w = tribe_terrain_bias(tile.climate)
            # Ice tiles only on Polaris climate (never on Bardur/etc.).
            if tile.climate != int(Tribe.POLARIS):
                ice_w = 0.0
            # Only convert plain fields; keep existing forest/mountain from noise.
            if tile.terrain != int(Terrain.FIELD):
                if tile.climate == int(Tribe.POLARIS) and tile.terrain == int(Terrain.FOREST):
                    if self.random.NextFloat() < ice_w * 0.5:
                        tile.terrain = int(Terrain.ICE)
                continue
            r = self.random.NextFloat()
            if ice_w > 0 and r < ice_w:
                tile.terrain = int(Terrain.ICE)
            elif r < ice_w + mountain_w:
                tile.terrain = int(Terrain.MOUNTAIN)
            elif r < ice_w + mountain_w + forest_w:
                tile.terrain = int(Terrain.FOREST)

        # Strip any ice that landed on non-Polaris climate.
        for idx in landTileIndices:
            tile = map.tiles[idx]
            if tile.terrain == int(Terrain.ICE) and tile.climate != int(Tribe.POLARIS):
                tile.terrain = int(Terrain.FIELD)

    def MakeOcean(
        self,
        map: MapData,
        gameState: GameState,
        shouldConvertShallows: bool = True,
    ) -> None:
        width, height = map.width, map.height

        def is_land(t: TileData) -> bool:
            return t.terrain in (
                int(Terrain.FIELD),
                int(Terrain.MOUNTAIN),
                int(Terrain.FOREST),
                int(Terrain.ICE),
                int(Terrain.WETLAND),
                int(Terrain.MANGROVE),
            )

        for y in range(height):
            for x in range(width):
                if x == 0 or y == 0 or x == width - 1 or y == height - 1:
                    tile = map.tiles[y * width + x]
                    if not tile.capital_of and tile.improvement is None:
                        if tile.terrain in (
                            int(Terrain.WATER),
                            int(Terrain.OCEAN),
                            int(Terrain.NONE),
                        ):
                            tile.terrain = int(Terrain.OCEAN)

        for y in range(height):
            for x in range(width):
                tile = map.tiles[y * width + x]
                if tile.terrain != int(Terrain.WATER):
                    continue
                touches_land = False
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        if is_land(map.tiles[ny * width + nx]):
                            touches_land = True
                            break
                if not touches_land and shouldConvertShallows:
                    tile.terrain = int(Terrain.OCEAN)

    def ConvertLandAdjacentWaterToShallows(self, map: MapData) -> None:
        """Any WATER/OCEAN tile 4-adjacent to land becomes shallow WATER."""
        width, height = map.width, map.height
        land = {
            int(Terrain.FIELD),
            int(Terrain.MOUNTAIN),
            int(Terrain.FOREST),
            int(Terrain.ICE),
            int(Terrain.WETLAND),
            int(Terrain.MANGROVE),
        }
        to_shallow: List[int] = []
        for i, tile in enumerate(map.tiles):
            if tile.terrain not in (int(Terrain.WATER), int(Terrain.OCEAN)):
                continue
            x, y = tile.x, tile.y
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    if map.tiles[ny * width + nx].terrain in land:
                        to_shallow.append(i)
                        break
        for i in to_shallow:
            map.tiles[i].terrain = int(Terrain.WATER)

    def AddResources(
        self, map: MapData, gameState: GameState, richness: float = 1.0
    ) -> None:
        resources = default_resources()
        fixed = XXHash(gameState.seed ^ 0xA5A5)
        for tile in map.tiles:
            if tile.resource is not None or tile.improvement is not None:
                continue
            # Wiki: resources spawn only within 2 tiles of a city/village.
            if not self.IsNearCity(map, tile, radius=2):
                continue
            if self.random.NextFloat() > 0.35 * richness:
                continue
            self.AddResource(tile, resources, map, fixed)

    def AddResource(
        self,
        tile: TileData,
        resources: List[ResourceData],
        map: MapData,
        fixedRng: XXHash,
    ) -> Optional[ResourceData]:
        candidates = [
            c
            for c in resources_for_terrain(tile.terrain)
            if resource_allowed_for_climate(tile.climate, c.type)
            and c.type != int(Resource.WHALE)
            and c.type != int(Resource.STARFISH)  # starfish via AddStarfish
        ]
        if not candidates:
            return None
        weights = [
            resource_weight(tile.climate, c.type, c.score) for c in candidates
        ]
        total = sum(weights)
        if total <= 0:
            return None
        roll = fixedRng.NextFloat() * total
        acc = 0.0
        pick = candidates[-1]
        for c, w in zip(candidates, weights):
            acc += w
            if roll <= acc:
                pick = c
                break
        tile.resource = ResourceState(type=pick.type)
        return pick

    def AddResourcesInTutorial_54_0(
        self,
        neighborTile: TileData,
        resources: List[ResourceData],
        currentResources: Dict[int, int],
        map: MapData,
    ) -> None:
        """Compiler-generated <AddResources>g__AddResourcesInTutorial|54_0."""
        if neighborTile.resource is not None:
            return
        self.AddResource(neighborTile, resources, map, XXHash(0))

    def getStartingResourcesForPlayer(
        self, gameState: GameState, player: PlayerState
    ) -> List[ResourceData]:
        return starting_resources_for_tribe(player.tribe)

    def addStartingResourcesToCapital(
        self,
        map: MapData,
        gameState: GameState,
        player: PlayerState,
        startingResources: List[ResourceData],
        minResourcesCount: int = 2,
    ) -> None:
        for res in startingResources:
            self.addStartingResourceToCapital(
                map, gameState, player, res, minResourcesCount
            )
        # Guarantee at least minResourcesCount fruit/crop/fish near capital.
        placed = sum(
            1
            for t in map.tiles
            if t.resource is not None
            and max(abs(t.x - player.start_tile.x), abs(t.y - player.start_tile.y)) <= 2
        )
        if placed < minResourcesCount:
            fallback = starting_resources_for_tribe(player.tribe)
            if fallback:
                self.addStartingResourceToCapital(
                    map,
                    gameState,
                    player,
                    fallback[0],
                    minResourcesCount - placed,
                )

    def addStartingResourceToCapital(
        self,
        map: MapData,
        gameState: GameState,
        player: PlayerState,
        startingResource: ResourceData,
        minResourcesCount: int = 2,
    ) -> None:
        width = map.width
        cx, cy = player.start_tile.x, player.start_tile.y
        placed = 0
        ring = [
            (x, y)
            for y in range(cy - 2, cy + 3)
            for x in range(cx - 2, cx + 3)
            if not (x == cx and y == cy)
        ]
        self.Shuffle_coords(ring)
        for x, y in ring:
            if placed >= minResourcesCount:
                break
            tile = map.tile_at(x, y)
            if tile is None or tile.resource is not None:
                continue
            if startingResource.terrains and tile.terrain not in startingResource.terrains:
                # Convert a land tile if needed.
                if int(Terrain.FIELD) in startingResource.terrains:
                    if tile.terrain in (int(Terrain.WATER), int(Terrain.OCEAN)):
                        continue
                    tile.terrain = int(Terrain.FIELD)
            tile.resource = ResourceState(type=startingResource.type)
            placed += 1

    def GetResourceForTech(
        self, tech: TechData, tribe: TribeData, state: GameState
    ) -> Optional[ResourceData]:
        if tech.resource:
            return ResourceData(type=tech.resource)
        return None

    def FindLandTileToConvert(
        self,
        map: MapData,
        capitalTile: WorldCoordinates,
        landTileIndices: List[int],
    ) -> Optional[TileData]:
        width = map.width
        best = None
        best_d = 10**9
        for idx in landTileIndices:
            t = map.tiles[idx]
            d = (t.x - capitalTile.x) ** 2 + (t.y - capitalTile.y) ** 2
            if d < best_d and t.resource is None:
                best_d = d
                best = t
        return best

    def AddRuins(self, map: MapData, amount: int, gameState: GameState) -> None:
        spots = [t for t in map.tiles if self.ValidRuinLocation(t, map)]
        self.Shuffle(spots)
        # Wiki: at most ~1/3 of ruins on water.
        water = [
            t
            for t in spots
            if t.terrain in (int(Terrain.WATER), int(Terrain.OCEAN))
        ]
        land = [
            t
            for t in spots
            if t.terrain not in (int(Terrain.WATER), int(Terrain.OCEAN))
        ]
        max_water = max(0, amount // 3)
        placed = 0
        for tile in water[:max_water]:
            tile.improvement = ImprovementState(type=int(Improvement.RUIN))
            placed += 1
        for tile in land:
            if placed >= amount:
                break
            tile.improvement = ImprovementState(type=int(Improvement.RUIN))
            placed += 1

    def ValidRuinLocation(self, tile: TileData, map: MapData) -> bool:
        """Ruins on land or water; keep clear of villages/cities.

        Land: ≥1 tile away (Chebyshev distance ≥ 2).
        Ocean/water: ≥2 tiles away (Chebyshev distance ≥ 3).
        """
        if tile.improvement is not None or tile.resource is not None:
            return False
        if tile.capital_of:
            return False
        land = (
            int(Terrain.FIELD),
            int(Terrain.FOREST),
            int(Terrain.MOUNTAIN),
            int(Terrain.ICE),
            int(Terrain.WETLAND),
        )
        water = (int(Terrain.WATER), int(Terrain.OCEAN))
        if tile.terrain in land:
            return not self.IsNearCity(map, tile, radius=1)
        if tile.terrain in water:
            return not self.IsNearCity(map, tile, radius=2)
        return False

    def AddStarfish(self, map: MapData, amount: float) -> None:
        water = [
            t
            for t in map.tiles
            if t.terrain in (int(Terrain.WATER), int(Terrain.OCEAN))
            and t.resource is None
        ]
        self.Shuffle(water)
        count = max(0, int(len(water) * 0.02 * amount))
        for tile in water[:count]:
            tile.resource = ResourceState(type=int(Resource.STARFISH))

    def AddLightHouseImprovements(
        self, map: MapData, gameState: GameState
    ) -> None:
        """Always place four corner lighthouses; undiscovered (0 tower height).

        Fog is handled later by ``RevealAllTiles``. Tower drums come from
        players' ``built_unique_improvements``, which stay empty at mapgen.
        """
        width, height = map.width, map.height
        if width < 1 or height < 1:
            return
        corners = self.lighthouse_corners(width, height)
        # Clear any prior random lighthouses elsewhere.
        for tile in map.tiles:
            if (
                tile.improvement is not None
                and tile.improvement.type == int(Improvement.LIGHTHOUSE)
            ):
                tile.improvement = None

        for x, y in corners:
            tile = map.tiles[y * width + x]
            # Corners are open ocean; drop cities/resources that shouldn't sit here.
            if tile.capital_of:
                continue
            tile.terrain = int(Terrain.OCEAN)
            tile.resource = None
            tile.owner = 0
            tile.improvement = ImprovementState(type=int(Improvement.LIGHTHOUSE))

    # -------------------------------------------------------------- queries

    def GetRandomIsolatedTile(
        self, map: MapData
    ) -> Tuple[bool, WorldCoordinates]:
        spots = [
            t
            for t in map.tiles
            if t.terrain == int(Terrain.FIELD) and t.improvement is None
        ]
        if not spots:
            return False, WorldCoordinates(-1, -1)
        t = spots[self.random.Next(len(spots))]
        return True, WorldCoordinates(t.x, t.y)

    def DistanceSqrToClosestCity(
        self, map: MapData, from_: WorldCoordinates
    ) -> float:
        best = 1e18
        for t in map.tiles:
            if t.improvement and t.improvement.type == int(Improvement.CITY):
                d = (t.x - from_.x) ** 2 + (t.y - from_.y) ** 2
                if d < best:
                    best = float(d)
        return best if best < 1e18 else 0.0

    def IsNearCity(self, map: MapData, tile: TileData, radius: int) -> bool:
        for t in map.tiles:
            if t.improvement and t.improvement.type == int(Improvement.CITY):
                if max(abs(t.x - tile.x), abs(t.y - tile.y)) <= radius:
                    return True
        return False

    def IsNearRuin(self, map: MapData, tile: TileData, radius: int) -> bool:
        for t in map.tiles:
            if t.improvement and t.improvement.type == int(Improvement.RUIN):
                if max(abs(t.x - tile.x), abs(t.y - tile.y)) <= radius:
                    return True
        return False

    @staticmethod
    def lighthouse_corners(width: int, height: int) -> Tuple[Tuple[int, int], ...]:
        """Reserved map-corner lighthouse sites (always placed after gen)."""
        return (
            (0, 0),
            (width - 1, 0),
            (0, height - 1),
            (width - 1, height - 1),
        )

    @staticmethod
    def IsNearReservedLighthouse(
        x: int, y: int, width: int, height: int, radius: int = 1
    ) -> bool:
        """True if (x,y) is within Chebyshev ``radius`` of a corner lighthouse."""
        for cx, cy in MapGenerator.lighthouse_corners(width, height):
            if max(abs(x - cx), abs(y - cy)) <= radius:
                return True
        return False

    @staticmethod
    def IsNearCapital(
        map: MapData, tile: TileData, radius: int, includeCenter: bool = True
    ) -> bool:
        for t in map.tiles:
            if not t.capital_of:
                continue
            d = max(abs(t.x - tile.x), abs(t.y - tile.y))
            if d == 0 and not includeCenter:
                continue
            if d <= radius:
                return True
        return False

    # -------------------------------------------------------------- shuffle

    def Shuffle(self, list_: List) -> None:
        """Overload for List[TileData] / List[WorldCoordinates]."""
        fisher_yates_shuffle(self.random, list_)

    def Shuffle_ints(self, list_: List[int]) -> None:
        fisher_yates_shuffle(self.random, list_)

    def Shuffle_coords(self, list_: List[Tuple[int, int]]) -> None:
        fisher_yates_shuffle(self.random, list_)

    # --------------------------------------------------------------- helpers

    def _real_players(self, gameState: GameState) -> List[PlayerState]:
        return [
            p
            for p in gameState.player_states
            if p.id not in (PlayerState.NO_PLAYER_ID, PlayerState.NATURE_PLAYER_ID)
        ]

    def _resolve_width(
        self, gameState: GameState, settings: MapGeneratorSettings
    ) -> int:
        if gameState.settings is not None:
            return gameState.settings.map_width()
        from enums import MAP_SIZE_WIDTH, MapSize
        return MAP_SIZE_WIDTH[MapSize.NORMAL]

    def _new_map(self, width: int, height: int, climate: int) -> MapData:
        tiles = [
            TileData(
                coordinates=WorldCoordinates(x, y),
                terrain=int(Terrain.OCEAN),
                climate=climate,
                altitude=0,
            )
            for y in range(height)
            for x in range(width)
        ]
        return MapData(width=width, height=height, tiles=tiles, continents=[])
