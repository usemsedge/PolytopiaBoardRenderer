# Verification Brief

The Polytopia renderer is built and composites all layers. Your job: rigorously
verify ONE aspect and produce a precise, prioritized defect list for fixing.

Working dir: `/Users/owfei/testing/biblical_greed`. Render scenes with
`python3 pyrender/scenes.py` (writes /tmp/scene_*.png: terrains, resources, units,
cities, territory, roads, fog, example). You can also build custom GameStates
(see pyrender/scenes.py for the pattern) and render via
`render.render(gs, pad=N).save_png(path)` then Read the PNG.

## Two kinds of verification

### IMAGE verifier
Render the relevant scene(s) AND a couple of focused custom boards, VIEW them, and
judge against (a) how the real Battle of Polytopia looks and (b) the recon spec for
that layer (recon/<layer>.md). Check: correct sprite chosen; object sits correctly
on the tile (not floating/sunk/offset); correct depth/occlusion vs neighbours and
other layers; correct tint/color; correct flip/orientation; no gaps, no missing
sprites (orange checkerboard or blank = missing/placeholder), no double-draw.

### CODE verifier
Compare the Python module against the decompiled logic. Re-derive the layer's rules
from il2cpp_dump/dump.cs and the dylib (use `python3 tools/re_tools.py disasm/callees/sym/rng`)
and confirm the Python matches: sprite-name selection (DoSpriteLookup order), the
sub-layer sort offset (SORT_* in enums.py vs the spec's offset), constants, tint
formulas, neighbour/bitmask logic, geometry. Read recon/<layer>.md as the reference
(it already cites RVAs). Flag any deviation between code and spec/binary.

## Report format (return structured)
For each defect: severity (critical | major | minor), layer, symptom (what's wrong),
evidence (scene/file/line/RVA), suspected_cause, fix_suggestion. Be specific and
actionable — these go straight to a fix pass. Distinguish "faithful to the game,
looks unusual" (NOT a defect) from real errors. Confirm what is CORRECT too.

Known-accepted limitations (do NOT report as defects unless worse than described):
- No pivot data in catalog → object anchoring is visually calibrated, not pixel-exact.
- City house placement is deterministic-but-not-engine-RNG-identical.
- Shoreline/border edge sprites can't be rotated (only flipped) so edges approximate.
- Status-effect overlay hues are approximate.
