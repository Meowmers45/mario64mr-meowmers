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
