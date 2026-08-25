# PolytopiaBoardRenderer

Isometric board renderer for [The Battle of Polytopia](https://polytopia.io/), reverse-engineered from the Unity client.

(Reverse-engineered too)

Also contains replayextractor (input polytopia jwt + share link, output GameState of the final position)

Also contains mapgenerator (output GameState like a real random map)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Render

```bash
python3 pyrender_UPDATED/scenes.py
```

Output goes in /tmp

## Details

polytopia_extracted/ contains images

il2cpp_dump/ contains decompiled source code

polytopia_files/ contains original polytopia app

recon/ contains instructions on how to read the source code and dump (may not contain all neccesary info)


