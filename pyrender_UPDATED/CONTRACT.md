
This file is handwritten. It serves as a single source of truth for the project's structure



Code structure:

Keep all json files

Keep these files
assets.py
enums.py
gamestate.py
image.py
projection.py
spritelookup.py
spritemeta.py

render.py
- Takes in input GameState and outputs a canvas
- Goes along the x, y grid in correct order
- renders each tile in their correct location
- renders diagonally, starting from top corner and going down horizontally
- Assumption: lower tiles always cover upper ones
- Does not know anything about tiles, merely places pre-created tiles from create_tile.py on the board



create_tile.py
- Takes in input (x, y) and a GameState
- Renders the whole tile by building calling create_{}.py for every tile attribute and placing them in correct sublayer order on the tile (or renders fog)
- Outputs a reference to a composite tile image stored in memory (may be cached if exact same)
- Does not know exactly where the tile will be rendered on the full board
- Internal z-order (composite back -> front; engine sub-layer offset in parens, from recon/draworder_color.md):
    1.  border back edges (N/E)            (0)   create_border
    2.  terrain base, or fog if hidden     (1)   create_terrain
    3.  transport (roads/routes), shoreline(2)   create_transport, create_shoreline
    4.  terrain features (mountain/forest) (3)   create_terrain
    5.  resource outline                   (4)   create_resource
    6.  resource                           (5)   create_resource
    7.  city houses                        (6)   create_improvement
    8.  walls                              (97)  create_improvement
    9.  buildings + units                  (98)  create_improvement, create_unit
    10. border front edges (S/W)           (99)  create_border
    11. labels                             (top) create_labels   (UI, above all art)
  Note: create_border and create_terrain each emit at two different sub-layers (back/front,
  base/features), so a component may contribute to more than one z-order slot.


create_{terrain, resource, improvement, transport, unit, border, shoreline, labels}.py
- Takes in input (x, y) and a GameState
- Renderes the tile component
- Outputs a reference to a possibly composite tile component stored in memory (may be cached if exact same). Also emits dx and dy for create_tile to know.
- Almost all logic is in one of these files.