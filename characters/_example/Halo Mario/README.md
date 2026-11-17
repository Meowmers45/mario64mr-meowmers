# Halo Mario: an example character pack

Everything in it is made for this example. It shows each part of a pack:

| File | What it is |
| --- | --- |
| `name.txt` | The name in the game's Character option |
| `actors/mario/geo.inc.c` | The model's layout (`mario_geo`). This one keeps Mario's own body, using the game's `mario_geo_load_body` and `mario_geo_render_body`, and adds a halo above his head |
| `actors/mario/model.inc.c` | The model's own parts: the halo's vertices, its display list, and its texture |
| `actors/mario/example_halo.rgba16.png` | The halo's texture, included in `model.inc.c` as `actors/mario/example_halo.rgba16.inc.c` |
| `sound/samples/sfx_mario/00_jump.wav` | A voice clip: it replaces the game's clip 00 (Mario's first jump), matched by its number |

To try it, copy the `Halo Mario` folder out of `_example` into `characters`, or give it to the installer:

```
python3 install_mario64mr.py "Super Mario 64 (USA).z64" --push --character "characters/_example/Halo Mario"
```

Then pause in the game, press R, and pick Halo Mario under Character.

A pack with a whole new model has `geo.inc.c` and `model.inc.c` as Fast64 exports them for Mario instead, with the
same layout of bones (so Mario's animations move it), and as many clips as you like. The clips are named like the
game's own, which are in `Mario64MRData-work/sm64ex/sound/samples/sfx_mario` and `sfx_mario_peach` once you've
installed.
