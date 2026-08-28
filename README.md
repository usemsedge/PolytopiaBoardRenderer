# PolytopiaBoardRenderer

Isometric board renderer for [The Battle of Polytopia](https://polytopia.io/), reverse-engineered from the Unity client.

Also contains **replayextractor** (Polytopia JWT + share link → final `GameState`) and **mapgenerator** (random map → `GameState`).

## New machine setup

Assets and RE material (sprites, il2cpp dump, `GameAssembly`, extractors) live in a
separate repo: **[biblical_greed](https://github.com/usemsedge/biblical_greed)**.

```bash
git clone https://github.com/usemsedge/biblical_greed.git
cd biblical_greed && ./reassemble_large_files.sh && cd ..

git clone https://github.com/usemsedge/PolytopiaBoardRenderer.git
cd PolytopiaBoardRenderer
python3 -m venv .venv && source .venv/bin/activate
pip install -r ../biblical_greed/requirements.txt

# Symlink assets into this tree (renderer expects them at repo root)
ln -sf ../biblical_greed/polytopia_extracted .
ln -sf ../biblical_greed/il2cpp_dump .
ln -sf ../biblical_greed/GameAssembly_arm64.dylib .
```

See [biblical_greed/README.md](https://github.com/usemsedge/biblical_greed/blob/main/README.md) for full layout.

## Render

```bash
python3 pyrender_UPDATED/scenes.py
```

Output goes in `/tmp`.

## Replay extract

```bash
cd pyrender_UPDATED/replayextractor
python3 get_game_data.py https://share.polytopia.io/g/<uuid> --bin game.bin
python3 deserialize_gamestate.py game.bin -o state.json --summary
python3 ../render.py state.json board.png
```

## Repo layout

| Path | What |
|------|------|
| `pyrender_UPDATED/` | Renderer, replayextractor, mapgenerator |
| `recon/` | Render-pipeline RE specs (also in biblical_greed) |
| `polytopia_extracted/` | Symlink → biblical_greed (sprites, gamelogic, audio) |
| `il2cpp_dump/` | Symlink → biblical_greed (decompiled signatures) |
| `GameAssembly_arm64.dylib` | Symlink → biblical_greed (native logic binary) |
