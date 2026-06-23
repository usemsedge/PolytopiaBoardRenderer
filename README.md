# PolytopiaBoardRenderer

Isometric board renderer for [The Battle of Polytopia](https://polytopia.io/), reverse-engineered from the Unity client.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Render

```bash
python3 polytopia_python/render_board.py --example -o board.png
python3 polytopia_python/render_board.py --all -o boards/
```

Sprites ship in `sprites/` (~27 MB). Optional: install `UnityPy` and place `Polytopia.app` beside this repo for extra per-tribe pivot metadata.
# PolytopiaBoardRenderer
