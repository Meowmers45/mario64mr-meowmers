# Tests for character packs' textures (character_textures.py + characters.py): every texture form made into a name
# the game loads (sm64ex EXTERNAL_DATA), the pngs in characters.zip, the error path, and earlier behaviour.
import io
import re
import struct
import subprocess
import sys
import wave
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, "/app/native/fullgame")
import characters  # noqa: E402
import character_textures  # noqa: E402

from PIL import Image  # noqa: E402

SLUG = "test_hero"


def hexdump(data):
    return ", ".join("0x%02X" % b for b in data)


def save_png(path, size, colour):
    Image.new("RGBA", size, colour).save(path)


GEO = """const GeoLayout mario_geo[] = {
    GEO_NODE_START(),
    GEO_OPEN_NODE(),
        GEO_DISPLAY_LIST(LAYER_OPAQUE, mario_body_dl),
    GEO_CLOSE_NODE(),
    GEO_END(),
};
"""


def model_text():
    raw = struct.pack(">H", 0xF801) * (32 * 32)          # (f) red, 32x32 rgba16
    fast = struct.pack(">H", 0x07C1) * (16 * 64)         # (g) green, 16x64 rgba16
    ci = bytes([0x01]) * (16 * 16 // 2)                  # (h) ci4 16x16: texels 0,1,0,1...
    pal = struct.pack(">HH", 0x0001, 0x003F) + b"\0" * 28  # black, blue
    return f"""
ALIGNED8 static const u8 mario_cap_tex[] = {{
#include "actors/mario/cap.rgba16.inc.c"
}};

ALIGNED8 static const u8 mario_eyes_tex[] = {{
#include "actors/mario/eyes.rgba16.inc.c"
}};

ALIGNED8 static const u8 mario_hexonly_tex[] = {{
#include "actors/mario/hexonly.ia8.inc.c"
}};

ALIGNED8 static const u8 mario_luigi_tex[] = "actors/luigi/luigi_cap.rgba16";

ALIGNED8 static const u8 mario_metal_tex[] = {{
#include "actors/mario/mario_metal.rgba16.inc.c"
}};

ALIGNED8 static const u8 raw_block[] = {{
    {hexdump(raw)}
}};

Texture fast_tex[] = {{
    {hexdump(fast)}
}};

ALIGNED8 static const u8 ci_tex[] = {{
    {hexdump(ci)}
}};

ALIGNED8 static const u8 ci_pal[] = {{
    {hexdump(pal)}
}};

static const Vtx mario_vtx[] = {{
    {{{{{{0, 0, 0}}, 0, {{0, 0}}, {{0xff, 0xff, 0xff, 0xff}}}}}},
}};

const Gfx mario_body_dl[] = {{
    gsDPLoadTextureBlock(mario_cap_tex, G_IM_FMT_RGBA, G_IM_SIZ_16b, 32, 32, 0, G_TX_CLAMP, G_TX_CLAMP, 5, 5, G_TX_NOLOD, G_TX_NOLOD),
    gsDPLoadTextureBlock(mario_hexonly_tex, G_IM_FMT_IA, G_IM_SIZ_8b, 16, 16, 0, G_TX_CLAMP, G_TX_CLAMP, 4, 4, G_TX_NOLOD, G_TX_NOLOD),
    gsDPLoadTextureBlock(raw_block, G_IM_FMT_RGBA, G_IM_SIZ_16b, 32, 32, 0, G_TX_CLAMP, G_TX_CLAMP, 5, 5, G_TX_NOLOD, G_TX_NOLOD),
    gsDPSetTextureImage(G_IM_FMT_RGBA, G_IM_SIZ_16b_LOAD_BLOCK, 1, fast_tex),
    gsDPSetTile(G_IM_FMT_RGBA, G_IM_SIZ_16b_LOAD_BLOCK, 0, 0, 7, 0, G_TX_WRAP | G_TX_NOMIRROR, 6, 0, G_TX_WRAP | G_TX_NOMIRROR, 4, 0),
    gsDPLoadBlock(7, 0, 0, 1023, 256),
    gsDPSetTile(G_IM_FMT_RGBA, G_IM_SIZ_16b, 4, 0, 0, 0, G_TX_WRAP | G_TX_NOMIRROR, 6, 0, G_TX_WRAP | G_TX_NOMIRROR, 4, 0),
    gsDPSetTileSize(0, 0, 0, (16 - 1) << G_TEXTURE_IMAGE_FRAC, 252),
    gsDPLoadTLUT_pal16(0, ci_pal),
    gsDPLoadTextureBlock_4b(ci_tex, G_IM_FMT_CI, 16, 16, 0, G_TX_CLAMP, G_TX_CLAMP, 4, 4, G_TX_NOLOD, G_TX_NOLOD),
    gsSPVertex(mario_vtx, 1, 0),
    gsSPEndDisplayList(),
}};
"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    base = tmp_path_factory.mktemp("ct")
    pack, root, work, out = base / "Test Hero", base / "root", base / "work", base / "out"
    model = pack / "actors" / "mario"
    model.mkdir(parents=True)
    (model / "geo.inc.c").write_text(GEO)
    (model / "model.inc.c").write_text(model_text())
    save_png(model / "cap.rgba16.png", (32, 32), (255, 0, 0, 255))          # (a)
    save_png(model / "eyes.png", (32, 32), (0, 0, 255, 255))               # (b) no format in the name
    (model / "hexonly.ia8.inc.c").write_text(hexdump(bytes([0xF0]) * 256) + ",\n")  # (c)
    save_png(model / "luigi_cap.rgba16.png", (16, 16), (0, 255, 0, 255))   # (d)
    (root / "actors/mario").mkdir(parents=True)
    save_png(root / "actors/mario/mario_metal.rgba16.png", (32, 32), (128, 128, 128, 255))  # (e) vanilla
    work.mkdir()
    packs = characters.find([pack], None, work)
    characters.write_sources(root, packs)
    zpath = characters.write_zip(out, packs)
    return {"packs": packs, "root": root, "out": out, "zip": zpath}


def arrays(text):
    """name -> body of every { } or "..." array."""
    found = {}
    for m in re.finditer(r"(\w+)\s*\[\s*\]\s*=\s*(\{[^}]*\}|\"[^\"]*\")", text):
        found[m.group(1)] = m.group(2)
    return found


def as_name(body):
    if body.startswith('"'):
        return body[1:-1]
    values = [int(v, 16) for v in re.findall(r"0x([0-9A-Fa-f]+)", body)]
    assert values and values[-1] == 0, f"not zero-terminated: {body[:80]}"
    assert "#include" not in body
    return bytes(values[:-1]).decode()


# --- the rewritten model source
class TestModelSource:
    def test_slug_and_count(self, built):
        assert built["packs"][0].slug == SLUG
        h = (built["root"] / "src/pc/unity_characters.inc.h").read_text()
        assert "#define UNITY_CHARACTER_COUNT 2" in h
        assert "mrc1_mario_geo" in h

    @pytest.mark.parametrize("array,expected", [
        ("mario_cap_tex", f"characters/{SLUG}/cap.rgba16"),
        ("mario_eyes_tex", f"characters/{SLUG}/eyes.rgba16"),
        ("mario_hexonly_tex", f"characters/{SLUG}/hexonly.ia8"),
        ("mario_luigi_tex", f"characters/{SLUG}/luigi_cap.rgba16"),
        ("mario_metal_tex", "actors/mario/mario_metal.rgba16"),
        ("raw_block", f"characters/{SLUG}/raw_block.rgba16"),
        ("fast_tex", f"characters/{SLUG}/fast_tex.rgba16"),
        ("ci_tex", f"characters/{SLUG}/ci_tex.ci4"),
    ])
    def test_texture_array_is_name(self, built, array, expected):
        text = (built["root"] / "src/pc/characters/c1/model.inc.c").read_text()
        assert as_name(arrays(text)[array]) == expected

    def test_palette_untouched(self, built):
        text = (built["root"] / "src/pc/characters/c1/model.inc.c").read_text()
        values = [int(v, 16) for v in re.findall(r"0x([0-9A-Fa-f]+)", arrays(text)["ci_pal"])]
        assert bytes(values) == struct.pack(">HH", 0x0001, 0x003F) + b"\0" * 28

    def test_vtx_and_gfx_kept(self, built):
        text = (built["root"] / "src/pc/characters/c1/model.inc.c").read_text()
        assert "gsDPLoadTLUT_pal16(0, ci_pal)" in text and "mario_vtx[]" in text


# --- characters.zip
EXPECTED = {
    "cap.rgba16": ((32, 32), (255, 0, 0, 255)),
    "eyes.rgba16": ((32, 32), (0, 0, 255, 255)),
    "hexonly.ia8": ((16, 16), (255, 255, 255, 0)),
    "luigi_cap.rgba16": ((16, 16), (0, 255, 0, 255)),
    "raw_block.rgba16": ((32, 32), (255, 0, 0, 255)),
    "fast_tex.rgba16": ((16, 64), (0, 255, 0, 255)),
    "ci_tex.ci4": ((16, 16), (0, 0, 0, 255)),
}


class TestZip:
    def test_zip_location(self, built):
        assert built["zip"] == built["out"] / "sm64/res/characters.zip" and built["zip"].is_file()

    def test_zip_entries(self, built):
        names = set(zipfile.ZipFile(built["zip"]).namelist())
        want = {f"gfx/characters/{SLUG}/{n}.png" for n in EXPECTED}
        assert names == want, names ^ want

    @pytest.mark.parametrize("name", sorted(EXPECTED))
    def test_png(self, built, name):
        data = zipfile.ZipFile(built["zip"]).read(f"gfx/characters/{SLUG}/{name}.png")
        img = Image.open(io.BytesIO(data))
        img.verify()
        img = Image.open(io.BytesIO(data)).convert("RGBA")
        size, colour = EXPECTED[name]
        assert img.size == size
        assert img.getpixel((0, 0)) == colour

    def test_ci4_second_texel_from_palette(self, built):
        data = zipfile.ZipFile(built["zip"]).read(f"gfx/characters/{SLUG}/ci_tex.ci4.png")
        img = Image.open(io.BytesIO(data)).convert("RGBA")
        assert img.getpixel((1, 0)) == (0, 0, 255, 255)


# --- error path and edge cases
def make_pack(base, body, extra=None):
    model = base / "pack" / "mario"
    model.mkdir(parents=True)
    (model / "geo.inc.c").write_text(GEO)
    (model / "model.inc.c").write_text(body)
    for name, size in (extra or {}).items():
        save_png(model / name, size, (1, 2, 3, 255))
    (base / "root").mkdir()
    (base / "work").mkdir()
    return characters.find([base / "pack"], None, base / "work")


def test_missing_texture_stops(tmp_path):
    packs = make_pack(tmp_path, 'u8 t[] = {\n#include "actors/mario/missing_thing.rgba16.inc.c"\n};\n')
    with pytest.raises(SystemExit) as e:
        characters.write_sources(tmp_path / "root", packs)
    assert "missing_thing" in str(e.value.code)


def test_missing_string_literal_texture_stops(tmp_path):
    packs = make_pack(tmp_path, 'u8 t[] = "actors/luigi/nowhere.rgba16";\n')
    with pytest.raises(SystemExit) as e:
        characters.write_sources(tmp_path / "root", packs)
    assert "nowhere" in str(e.value.code)


def test_pack_without_textures(tmp_path):
    packs = make_pack(tmp_path, "const Gfx dl[] = { gsSPEndDisplayList(), };\n")
    characters.write_sources(tmp_path / "root", packs)
    assert packs[0].textures == []
    assert characters.write_zip(tmp_path / "out", packs) is None


def test_no_packs(tmp_path):
    (tmp_path / "src/pc").mkdir(parents=True)  # (as in sm64ex's tree)
    characters.write_sources(tmp_path, [])
    assert "#define UNITY_CHARACTER_COUNT 1" in (tmp_path / "src/pc/unity_characters.inc.h").read_text()
    assert characters.write_zip(tmp_path / "out", []) is None


def test_square_size_from_name_without_display_list(tmp_path):
    packs = make_pack(tmp_path, "u8 lonely_i8[] = {\n" + hexdump(bytes([0x80]) * 64) + "\n};\n")
    characters.write_sources(tmp_path / "root", packs)
    data, name = packs[0].textures[0]
    assert name.endswith("/lonely_i8.png")
    img = Image.open(io.BytesIO(data)).convert("RGBA")
    assert img.size == (8, 8) and img.getpixel((0, 0)) == (128, 128, 128, 255)


def test_decode_units():
    assert character_textures.rgba16(0xF801) == (255, 0, 0, 255)
    assert bytes(character_textures.decode(bytes([0xF0]), "ia8", 1, 1)) == bytes((255, 255, 255, 0))
    assert bytes(character_textures.decode(bytes([0x1F]), "i4", 2, 1)) == bytes((17, 17, 17, 255, 255, 255, 255, 255))
    with pytest.raises(character_textures.TextureError):
        character_textures.decode(b"\0", "ci4", 2, 1)


# --- voices (regression)
def write_wav(path, rate, samples, channels=1):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<%dh" % len(samples), *samples))


def test_read_wav_and_resample(tmp_path):
    write_wav(tmp_path / "a.wav", 44100, [1000, -1000] * 2205)
    samples, rate = characters.read_wav(tmp_path / "a.wav")
    assert rate == 44100 and len(samples) == 4410 and samples[0] == 1000
    out, r = characters.resample(samples, rate)
    assert r == 32000 and abs(len(out) - 3200) <= 2
    same, r2 = characters.resample(samples[:10], 22050)
    assert r2 == 22050 and same == samples[:10]


def test_aiff_round_trip(tmp_path):
    samples = [0, 100, -100, 32767, -32768, 5]
    characters.write_aiff(tmp_path / "x.aiff", samples, 32000)
    back, rate = characters.read_aiff(tmp_path / "x.aiff")
    assert back == samples and rate == 32000


def test_match_clip():
    vanilla = {"sfx_mario": ["00_mario_jump_hoo", "01_mario_jump_wah"], "sfx_mario_peach": ["00_mario_peach"]}
    assert characters.match_clip(Path("p/00_mario_jump_hoo.wav"), vanilla) == ("sfx_mario", "00_mario_jump_hoo")
    assert characters.match_clip(Path("p/01.wav"), vanilla) == ("sfx_mario", "01_mario_jump_wah")
    assert characters.match_clip(Path("p/mario_jump_wah.wav"), vanilla) == ("sfx_mario", "01_mario_jump_wah")
    assert characters.match_clip(Path("sfx_mario_peach/00.wav"), vanilla) == ("sfx_mario_peach", "00_mario_peach")
    assert characters.match_clip(Path("p/nothing.wav"), vanilla) is None


def test_installer_help():
    r = subprocess.run([sys.executable, "/app/install_mario64mr.py", "--help"], capture_output=True, text=True)
    assert r.returncode == 0 and "--character" in r.stdout
