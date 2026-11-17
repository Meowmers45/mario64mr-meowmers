"""
Your own characters (install_mario64mr.py --character, or the characters folder): packs with a model for Mario and
his voice clips, made into the game next to the original Mario. In the game, pause › R › Character picks one: its
model and its voice together, in the window and out in your room (it's the same Mario), kept for next time.

A pack is a folder (or a .zip of one) with either part, or both, in the sm64 PC port's usual layout:

  the model     geo.inc.c and model.inc.c, as Fast64 or a model mod for sm64ex makes them (its actors/mario folder),
                with their textures as .png files next to them (name.rgba16.png...)
  voice clips   .wav or .aiff files named like the game's own: sfx_mario/00_mario_jump_hoo.aiff, or 00.wav, or
                mario_jump_hoo.wav (clips the pack doesn't have stay the original ones)

The models are compiled into the game, each under its own names (mrc<n>_...); the textures and the sound banks made
with the clips go in a resource pack of their own, sm64/res/characters.zip.
"""
import re
import shutil
import struct
import subprocess
import sys
import wave
import zipfile
from pathlib import Path

import character_textures

VOICE_BANKS = ("sfx_mario", "sfx_mario_peach")
VOICE_FILES = (".wav", ".aiff", ".aif")
TEXTURE_FORMATS = ("rgba16", "rgba32", "ia16", "ia8", "ia4", "ia1", "i8", "i4", "ci8", "ci4")
MAX_NAME = 20
MAX_RATE = 32000  # the N64's own output rate: clips above it are brought down to it
ZIP_NAME = "characters.zip"
INCLUDE = re.compile(r'^(\s*)#\s*include\s+"([^"]+)"', re.M)
# A definition at the top of a source file: [ALIGNED8] [static] [const] type name[...] =
DEFINITION = re.compile(r"^(?:ALIGNED\d+\s+)?(?:static\s+)?(?:const\s+)?(?:struct\s+)?(\w+)\s+(?:const\s+)?\*?\s*(\w+)\s*"
                        r"(?:\[[^\]\n]*\]\s*)*=", re.M)
KEYWORDS = {"return", "if", "else", "for", "while", "do", "switch", "case", "sizeof", "typedef"}


class Pack:
    def __init__(self, source, root, name):
        self.source, self.root, self.name = source, root, name
        self.slug = ""
        self.model = None   # the folder with geo.inc.c and model.inc.c
        self.voices = []    # clip files
        self.textures = []  # (png, its path in characters.zip), once its sources are written
        self.voice_data = None  # (sound_data.ctl, sound_data.tbl), once its clips are made into sound banks
        self.geo = None     # its root geo layout's name, once its sources are written


def fail(message):
    sys.exit(message)


def display_name(text):
    """A pack's name as the options menu can show it: letters, digits and spaces."""
    name = " ".join(re.sub(r"[^A-Za-z0-9 ]+", " ", text).split())[:MAX_NAME].strip()
    return name


def unpack_zip(archive, target):
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True)
    root = target.resolve()
    try:
        with zipfile.ZipFile(archive) as z:
            for entry in z.infolist():
                path = (target / entry.filename).resolve()
                if root not in path.parents and path != root:
                    fail(f"{archive}: unexpected path inside it: {entry.filename}")
            z.extractall(target)
    except zipfile.BadZipFile:
        fail(f"{archive}: not a .zip file")
    return target


def model_folder(root):
    """The folder with both geo.inc.c and model.inc.c (Mario's, when there are several models)."""
    found = [g.parent for g in sorted(root.rglob("geo.inc.c")) if (g.parent / "model.inc.c").is_file()]
    if not found:
        return None
    marios = [f for f in found if "mario" in f.as_posix().lower()]
    return (marios or found)[0]


def find(paths, folder, work):
    """The character packs given (--character) and those in the characters folder, checked before anything is
    built: each with a model, voice clips or both."""
    sources = [Path(p) for p in paths or ()]
    if folder and Path(folder).is_dir():
        sources += sorted(p for p in Path(folder).iterdir()
                          if (p.is_dir() and not p.name.startswith(".")) or p.suffix.lower() == ".zip")
    packs, slugs = [], set()
    for source in sources:
        if not source.exists():
            fail(f"{source}: no such character pack (a folder, or a .zip of one)")
        stem = source.stem if source.is_file() else source.name
        if source.is_file():
            if source.suffix.lower() != ".zip":
                fail(f"{source}: a character pack is a folder, or a .zip of one")
            root = unpack_zip(source, work / "characters-unpacked" / re.sub(r"\W+", "_", stem))
        else:
            root = source
        name_file = next(iter(sorted(root.rglob("name.txt"))), None)
        given = name_file.read_text(errors="replace").strip() if name_file else ""
        name = display_name(given.splitlines()[0] if given else stem)
        pack = Pack(source, root, name or f"Character {len(packs) + 1}")
        pack.model = model_folder(root)
        pack.voices = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in VOICE_FILES)
        if not pack.model and not pack.voices:
            fail(f"{source}: no model (geo.inc.c and model.inc.c) and no voice clips (.wav, .aiff) in it")
        slug = re.sub(r"[^a-z0-9]+", "_", pack.name.lower()).strip("_") or "character"
        base, n = slug, 2
        while slug in slugs:
            slug, n = f"{base}_{n}", n + 1
        slugs.add(slug)
        pack.slug = slug
        packs.append(pack)
    names = [p.name for p in packs]
    for name in names:
        if names.count(name) > 1:
            fail(f"Two character packs are called \"{name}\": rename one (its folder, or a name.txt in it)")
    for pack in packs:
        parts = (["model"] if pack.model else []) + ([f"{len(pack.voices)} voice clips"] if pack.voices else [])
        print(f"Character: {pack.name} ({', '.join(parts)}) from {pack.source}", flush=True)
    return packs


# ------------------------------------------------------------------------------------------------ the models

def c_bytes(text):
    """A string as the bytes of an included .inc.c (sm64ex with its data outside: a texture is its name)."""
    return ",".join("0x%X" % b for b in text.encode() + b"\0") + ","


def texture_name(include):
    """The texture an include stands for ("actors/mario/mario_logo.rgba16" for "...rgba16.inc.c"), or None."""
    if not include.endswith(".inc.c"):
        return None
    name = include[:-len(".inc.c")]
    return name if name.rsplit(".", 1)[-1] in TEXTURE_FORMATS else None


def write_model(root, pack, index):
    """The pack's model sources into src/pc/characters/c<index>, their includes made to work there, and every
    texture in them made into a name the game loads (character_textures.py): the pack's own in characters.zip, the
    game's own (a texture it kept) as they are."""
    dest = root / "src/pc/characters" / f"c{index}"
    dest.mkdir(parents=True)
    files = sorted(p for p in pack.model.iterdir() if p.is_file() and p.suffix in (".c", ".h"))
    local = {p.name for p in files}
    texts = {p: p.read_text(errors="replace") for p in files}
    textures = character_textures.Textures(root, pack.slug, pack.model, "\n".join(texts.values()))
    names = []
    for source in files:

        def include(match):
            indent, path = match.group(1), match.group(2)
            name = path.rsplit("/", 1)[-1]
            if name in local and not texture_name(path):
                return f'{indent}#include "pc/characters/c{index}/{name}"'
            return match.group(0)

        try:
            text = textures.rewrite(texts[source])
        except character_textures.TextureError as error:
            fail(f"{pack.source}: {source.name}: {error}")
        text = INCLUDE.sub(include, text)
        (dest / source.name).write_text(text)
        names += [m.group(2) for m in DEFINITION.finditer(text) if m.group(2) not in KEYWORDS]
    pack.textures = textures.files
    print(f"  {pack.name}: {len(pack.textures)} textures of its own", flush=True)
    geo_text = (pack.model / "geo.inc.c").read_text(errors="replace")
    geos = [m.group(2) for m in DEFINITION.finditer(geo_text) if m.group(1) == "GeoLayout"]
    if not geos:
        fail(f"{pack.source}: its geo.inc.c has no geo layout (const GeoLayout ..._geo[] = {{ ... }})")
    pack.geo = "mario_geo" if "mario_geo" in geos else geos[-1]
    names = list(dict.fromkeys(names))
    lines = [f"/* {index}: {pack.name} ({pack.source.name}) */"]
    lines += [f"#define {n} mrc{index}_{n}" for n in names]
    lines += [f'#include "pc/characters/c{index}/model.inc.c"', f'#include "pc/characters/c{index}/geo.inc.c"']
    lines += [f"#undef {n}" for n in names]
    return "\n".join(lines)


def strings(packs):
    """The options menu's words for the characters (include/text_options_strings.h.in)."""
    lines = ['#define TEXT_MR_CHARACTER _("Character")', '#define TEXT_MR_CHAR_0 _("Original Mario")']
    lines += [f'#define TEXT_MR_CHAR_{i} _("{p.name}")' for i, p in enumerate(packs, 1)]
    return "\n".join(lines) + "\n"


def write_sources(root, packs):
    """src/pc/unity_characters.inc.h: every pack's model (unity_character_models.c), what each pack has
    (unity_characters.c), and the menu's choices (unity_options.inc.h). Written with no packs too."""
    shutil.rmtree(root / "src/pc/characters", ignore_errors=True)
    count = len(packs) + 1
    models = [write_model(root, p, i) for i, p in enumerate(packs, 1) if p.model]
    ids = ", ".join(['""'] + [f'"{p.slug}"' for p in packs])
    geos = ", ".join(["NULL"] + [f"mrc{i}_{p.geo}" if p.model else "NULL" for i, p in enumerate(packs, 1)])
    voices = ", ".join(["NULL"] + [f'"sound/characters/{p.slug}"' if p.voice_data else "NULL" for p in packs])
    choices = ", ".join(f"mrCharacterStr[{i}]" for i in range(count))
    text = f"""/* Made by characters.py from your character packs: each model under names of its own */
#define UNITY_CHARACTER_COUNT {count}
#ifdef UNITY_CHARACTER_MODELS
{chr(10).join(models)}
const int gUnityCharacterCount = UNITY_CHARACTER_COUNT;
const char *const gUnityCharacterIds[UNITY_CHARACTER_COUNT] = {{ {ids} }};
const void *const gUnityCharacterGeos[UNITY_CHARACTER_COUNT] = {{ {geos} }};
const char *const gUnityCharacterVoices[UNITY_CHARACTER_COUNT] = {{ {voices} }};
#endif
#ifdef UNITY_CHARACTER_MENU
static const u8 mrCharacterStr[][32] = {{ {", ".join("{ TEXT_MR_CHAR_%d }" % i for i in range(count))} }};
static const u8 *mrCharacterChoices[] = {{ {choices} }};
#endif
"""
    (root / "src/pc/unity_characters.inc.h").write_text(text)


# ------------------------------------------------------------------------------------------------ the voices

def f80(value):
    """An AIFF sample rate (80-bit extended float), for a whole number of samples a second."""
    value = int(value)
    exponent = value.bit_length() - 1
    return struct.pack(">HQ", 16383 + exponent, value << (63 - exponent))


def from_f80(data):
    exponent, mantissa = struct.unpack(">HQ", data[:10])
    return mantissa * 2.0 ** ((exponent & 0x7FFF) - 16383 - 63)


def to_mono16(raw, width, channels, big_endian, signed=True):
    """Interleaved PCM of any width as one channel of 16-bit samples."""
    count = len(raw) // (width * channels)
    order = "big" if big_endian else "little"
    out = []
    for i in range(count):
        total = 0
        for c in range(channels):
            at = (i * channels + c) * width
            value = int.from_bytes(raw[at:at + width], order, signed=signed)
            if not signed:  # (8-bit WAV: unsigned)
                value -= 128
            total += value
        value = total // channels
        out.append(value << (16 - width * 8) if width < 2 else value >> (width * 8 - 16))
    return out


def read_wav(path):
    try:
        with wave.open(str(path), "rb") as w:
            channels, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
            raw = w.readframes(w.getnframes())
    except (wave.Error, EOFError) as error:
        fail(f"{path}: can't read it ({error}): save it as a 16-bit PCM .wav")
    return to_mono16(raw, width, channels, False, signed=width > 1), rate


def read_aiff(path):
    data = path.read_bytes()
    if data[:4] != b"FORM" or data[8:12] not in (b"AIFF", b"AIFC"):
        fail(f"{path}: not an AIFF file")
    comm = ssnd = None
    at, little = 12, False
    while at + 8 <= len(data):
        kind, size = data[at:at + 4], struct.unpack(">I", data[at + 4:at + 8])[0]
        body = data[at + 8:at + 8 + size]
        if kind == b"COMM":
            comm = body
            if data[8:12] == b"AIFC":
                compression = body[18:22]
                if compression not in (b"NONE", b"sowt"):
                    fail(f"{path}: compressed AIFF-C ({compression.decode(errors='replace')}): save it as plain "
                         "AIFF or .wav")
                little = compression == b"sowt"
        elif kind == b"SSND":
            offset = struct.unpack(">I", body[:4])[0]
            ssnd = body[8 + offset:]
        at += 8 + size + (size & 1)
    if comm is None or ssnd is None:
        fail(f"{path}: an AIFF file with no sound in it")
    channels, frames, bits = struct.unpack(">hIh", comm[:8])
    width = (bits + 7) // 8
    return to_mono16(ssnd[:frames * channels * width], width, channels, not little), from_f80(comm[8:18])


def resample(samples, rate):
    """Down to the N64's own rate, if above it (in between: linear)."""
    if rate <= MAX_RATE or not samples:
        return samples, int(round(rate))
    step = rate / MAX_RATE
    out = []
    position = 0.0
    while position < len(samples) - 1:
        i = int(position)
        fraction = position - i
        out.append(int(samples[i] * (1 - fraction) + samples[i + 1] * fraction))
        position += step
    return out, MAX_RATE


def write_aiff(path, samples, rate):
    """A plain mono 16-bit AIFF, as the game's sound tools take them."""
    samples = [max(-32768, min(32767, s)) for s in samples]
    comm = struct.pack(">hIh", 1, len(samples), 16) + f80(rate)
    sound = struct.pack(">II", 0, 0) + struct.pack(">%dh" % len(samples), *samples)
    if len(sound) & 1:
        sound += b"\0"
    body = b"AIFF" + b"COMM" + struct.pack(">I", len(comm)) + comm + b"SSND" + struct.pack(">I", len(sound)) + sound
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"FORM" + struct.pack(">I", len(body)) + body)


def match_clip(clip, vanilla):
    """The game's clip a pack's file replaces, (bank, name), or None: by its name (00_mario_jump_hoo), its number
    (00), or its name without the number (mario_jump_hoo); in its folder's bank if that's one of Mario's."""
    stem = clip.stem
    banks = [clip.parent.name] if clip.parent.name in vanilla else list(VOICE_BANKS)
    for bank in banks:
        if stem in vanilla[bank]:
            return bank, stem
    number = re.match(r"([0-9A-Fa-f]{2})(?:[_ .-]|$)", stem)
    for bank in banks:
        for name in vanilla[bank]:
            if number and name[:2].upper() == number.group(1).upper():
                return bank, name
            if name.split("_", 1)[-1].lower() == stem.lower():
                return bank, name
    return None


def tool(root, name):
    path = root / "tools" / name
    return path.with_suffix(".exe") if not path.is_file() and path.with_suffix(".exe").is_file() else path


def build_voices(root, pack_build, packs):
    """Each pack's clips into a copy of the game's sound banks (sound_data.ctl and .tbl, with only Mario's samples
    changed), made as the game's are: tabledesign and vadpcm_enc, then assemble_sound.py."""
    samples = root / pack_build / "sound/samples"
    vanilla = {bank: sorted(p.stem for p in (samples / bank).glob("*.aifc")) for bank in VOICE_BANKS}
    if not all(vanilla.values()):
        fail(f"The game's voice clips aren't in {samples}: run the tool again without --character first")
    endian = (root / pack_build / "endian-and-bitwidth").read_text().split()
    for pack in packs:
        pack.voice_data = None
        if not pack.voices:
            continue
        build = root / "build/characters" / pack.slug
        shutil.rmtree(build, ignore_errors=True)
        for aifc in samples.rglob("*.aifc"):
            target = build / "samples" / aifc.relative_to(samples)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(aifc, target)
        replaced, unknown = {}, []
        for clip in pack.voices:
            found = match_clip(clip, vanilla)
            if not found:
                unknown.append(clip.name)
                continue
            if found in replaced:
                print(f"  {pack.name}: {clip.name} and {replaced[found].name} are both {found[1]}: using the first")
                continue
            replaced[found] = clip
            sound, rate = read_wav(clip) if clip.suffix.lower() == ".wav" else read_aiff(clip)
            if not sound:
                fail(f"{clip}: no sound in it")
            sound, rate = resample(sound, rate)
            bank, name = found
            aiff = build / "aiff" / bank / (name + ".aiff")
            write_aiff(aiff, sound, rate)
            table = aiff.with_suffix(".table")
            with open(table, "wb") as f:
                subprocess.run([str(tool(root, "aiff_extract_codebook")), str(aiff)], cwd=root, stdout=f, check=True)
            subprocess.run([str(tool(root, "vadpcm_enc")), "-c", str(table), str(aiff),
                            str(build / "samples" / bank / (name + ".aifc"))], cwd=root, check=True)
        if unknown:
            print(f"  {pack.name}: not one of Mario's clips, left out: {', '.join(unknown)}\n"
                  f"  (the game's are in {root / 'sound/samples/sfx_mario'} and sfx_mario_peach: name a clip like "
                  f"one of them, or start it with its number)", flush=True)
        if not replaced:
            continue
        ctl, tbl = build / "sound_data.ctl", build / "sound_data.tbl"
        subprocess.run([sys.executable, "tools/assemble_sound.py", str(build / "samples"), "sound/sound_banks",
                        str(ctl), str(tbl), "-DVERSION_US", "-D_LANGUAGE_C", "-DNON_MATCHING", "-DAVOID_UB"] + endian,
                       cwd=root, check=True)
        pack.voice_data = (ctl, tbl)
        print(f"  {pack.name}: {len(replaced)} of Mario's voice clips", flush=True)


def write_zip(out, packs):
    """sm64/res/characters.zip: the packs' textures and sound banks (none without packs)."""
    path = out / "sm64/res" / ZIP_NAME
    path.unlink(missing_ok=True)
    files = [entry for p in packs for entry in p.textures]
    for p in packs:
        if p.voice_data:
            files += [(p.voice_data[0], f"sound/characters/{p.slug}/sound_data.ctl"),
                      (p.voice_data[1], f"sound/characters/{p.slug}/sound_data.tbl")]
    if not files:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for src, name in files:
            if isinstance(src, bytes):
                z.writestr(name, src)
            else:
                z.write(src, name)
    print(f"{path}: {len(packs)} characters, {path.stat().st_size / 1e6:.1f} MB")
    return path
