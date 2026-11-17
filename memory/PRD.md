# Mario 64 MR — character packs (custom Mario models + voice clips)

## Problem statement
"make this able to load different models and voiceclips for mario, both in your room and in the game window"
User choices: players supply their own files; choice remembered on the device; model + voice chosen together as one pack.

## Architecture (as found)
- Closed Unity APK + game code built on the user's PC by install_mario64mr.py from sm64ex (pinned) with native/fullgame patches.
- Mario in the room is the same sm64ex Mario (draw batches tagged 1), so a model swap covers window + room.

## Implemented (2026-06)
- native/fullgame/characters.py: finds packs (--character, ./characters, Steam Frame "Downloads/Mario64MR characters"),
  compiles each model (geo.inc.c/model.inc.c, symbols renamed mrc<n>_*, textures to characters.zip), builds voice banks
  (WAV/AIFF -> AIFF -> vadpcm -> assemble_sound.py) per pack, writes sm64/res/characters.zip.
- unity_characters.c: runtime switch of Mario's graph (sharedChild) + swap of sound bank headers / reload of loaded banks;
  choice kept in <save>/mr_character.txt. unity_character_models.c compiles the packs.
- Options menu (pause > R): "Character" choice (only when packs exist).
- Installer pushes/removes characters.zip; Steam Frame installer copies it; README section.

## Not verified
- Not compiled or run against a real ROM/NDK/headset (no ROM in this environment). Python helpers unit-checked only.

## Backlog
- P1: verify build + on-headset test; P2: per-pack name/icon in the menu, custom animations, title-screen voice.

## 2026-06 bug fix: character purple/black (missing textures)
- New native/fullgame/character_textures.py: every texture form in a pack's model (include+png, png without format,
  hex .inc.c without png, string-literal paths, raw hex arrays sized from the display lists, CI4/CI8 with palette)
  becomes a name + PNG in characters.zip; pngs found anywhere in the pack. Installer checks characters.zip reached the headset.
- Tested (Python only): tests/test_character_textures.py, 31 passing. Game build/headset still unverified.

## 2026-06 example pack
- characters/_example/Halo Mario: original example (halo with own texture over Mario's own body, own jump clip 00),
  README per part. Folders starting with _ are skipped by the folder scan; use --character or copy it out.
- Tests: tests/test_example_pack.py + test_character_textures.py, 43 passing (Python only).
