# Tests for the example character pack (characters/_example/Halo Mario): skipped in the folder, usable via
# --character, its clip matched/read, its model sources written and renamed, its texture in characters.zip,
# its C sane, its docs present and the files tracked by git.
import io
import re
import subprocess
import sys
import wave
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, "/app/native/fullgame")
import characters  # noqa: E402

APP = Path("/app")
FOLDER = APP / "characters"
PACK = FOLDER / "_example" / "Halo Mario"
MODEL = PACK / "actors/mario"
CLIP = PACK / "sound/samples/sfx_mario/00_jump.wav"


def strip_comments(text):
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", text, flags=re.S)


# --- find(): folder skip and --character
def test_find_folder_skips_example(tmp_path, capsys):
    assert characters.find(None, FOLDER, tmp_path) == []
    assert "Character:" not in capsys.readouterr().out


def test_find_explicit_example(tmp_path, capsys):
    packs = characters.find([PACK], None, tmp_path)
    assert len(packs) == 1
    p = packs[0]
    assert p.name == "Halo Mario" and p.slug == "halo_mario"
    assert p.model == MODEL
    assert p.voices == [CLIP]
    out = capsys.readouterr().out
    assert "Character: Halo Mario (model, 1 voice clip)" in out
    assert "1 voice clips" not in out, f"plural used for one clip: {out!r}"


# --- voice clip
def test_match_clip():
    vanilla = {"sfx_mario": ["00_mario_jump_hoo", "01_mario_jump_wah", "02_mario_yah"],
               "sfx_mario_peach": ["00_mario_peach_x", "01_y"]}
    assert characters.match_clip(CLIP, vanilla) == ("sfx_mario", "00_mario_jump_hoo")


def test_read_wav_and_aiff_round_trip(tmp_path):
    samples, rate = characters.read_wav(CLIP)
    assert rate == 22050
    assert len(samples) > 1000 and max(abs(s) for s in samples) > 1000
    out, r2 = characters.resample(samples, rate)
    assert r2 == 22050 and out == samples
    aiff = tmp_path / "x.aiff"
    characters.write_aiff(aiff, samples, rate)
    back, brate = characters.read_aiff(aiff)
    assert back == samples and brate == 22050


# --- write_sources / write_zip
@pytest.fixture
def written(tmp_path):
    root = tmp_path / "sm64ex"
    (root / "src/pc").mkdir(parents=True)
    packs = characters.find([PACK], None, tmp_path)
    characters.write_sources(root, packs)
    return root, packs


def test_write_sources_header(written):
    root, packs = written
    h = (root / "src/pc/unity_characters.inc.h").read_text()
    for n in ("mario_geo", "example_halo_texture", "example_halo_vertices", "example_halo_dl"):
        assert f"#define {n} mrc1_{n}" in h
    assert "mario_geo_load_body" not in h and "mario_geo_render_body" not in h
    assert re.search(r"gUnityCharacterGeos\[UNITY_CHARACTER_COUNT\] = \{ NULL, mrc1_mario_geo \}", h)
    assert '"halo_mario"' in h
    assert packs[0].geo == "mario_geo"


def test_written_model_texture_bytes(written):
    root, packs = written
    text = (root / "src/pc/characters/c1/model.inc.c").read_text()
    expected = characters.c_bytes("characters/halo_mario/example_halo.rgba16")
    assert expected in text
    assert "example_halo.rgba16.inc.c" not in text
    assert (root / "src/pc/characters/c1/geo.inc.c").is_file()


def test_pack_textures_and_zip(written, tmp_path):
    root, packs = written
    tex = [(Path(s) if not isinstance(s, bytes) else s, n) for s, n in packs[0].textures]
    assert tex == [(MODEL / "example_halo.rgba16.png", "gfx/characters/halo_mario/example_halo.rgba16.png")]
    out = tmp_path / "out"
    z = characters.write_zip(out, packs)
    assert z and z.is_file()
    with zipfile.ZipFile(z) as zf:
        data = zf.read("gfx/characters/halo_mario/example_halo.rgba16.png")
    from PIL import Image
    img = Image.open(io.BytesIO(data))
    assert img.size == (32, 32) and img.mode == "RGBA"


# --- the example's C
def test_model_c_sanity():
    text = strip_comments((MODEL / "model.inc.c").read_text())
    assert text.count("{") == text.count("}") and text.count("(") == text.count(")")
    vtx = re.search(r"example_halo_vertices\[(\d+)\]\s*=\s*\{(.*?)\n\};", text, re.S)
    declared = int(vtx.group(1))
    rows = re.findall(r"\{\{\{", vtx.group(2))
    assert declared == 16 and len(rows) == 16
    assert re.search(r"gsSPVertex\(example_halo_vertices,\s*16,\s*0\)", text)
    tris = re.findall(r"gsSP2Triangles\(([^)]*)\)", text)
    assert tris
    for t in tris:
        nums = [int(x, 0) for x in t.split(",")]
        assert len(nums) == 8
        for i in nums[:3] + nums[4:7]:
            assert 0 <= i < 16
    assert text.rstrip().endswith("};") and "gsSPEndDisplayList()" in text


def test_geo_c_sanity():
    text = strip_comments((MODEL / "geo.inc.c").read_text())
    assert text.count("{") == text.count("}") and text.count("(") == text.count(")")
    assert text.count("GEO_OPEN_NODE()") == text.count("GEO_CLOSE_NODE()") == 3
    body = text.strip()
    assert re.search(r"GEO_END\(\),\s*\};$", body)
    assert "example_halo_dl" in text
    depth = 0
    for tok in re.findall(r"GEO_(OPEN|CLOSE)_NODE", text):
        depth += 1 if tok == "OPEN" else -1
        assert depth >= 0


# --- docs and git
def test_readmes():
    r = (PACK / "README.md").read_text()
    assert "--character" in r and "_example" in r and "name.txt" in r
    assert "_example" in (FOLDER / "README.md").read_text()
    assert "characters/_example/Halo Mario" in (APP / "README.md").read_text()
    assert (PACK / "name.txt").read_text().strip() == "Halo Mario"


def test_git_not_ignored():
    files = [str(p.relative_to(APP)) for p in PACK.rglob("*") if p.is_file()]
    files.append("characters/README.md")
    r = subprocess.run(["git", "check-ignore", *files], cwd=APP, capture_output=True, text=True)
    assert r.returncode == 1 and r.stdout == "", r.stdout
    # a user's own pack in characters/ is still ignored
    r = subprocess.run(["git", "check-ignore", "-q", "--no-index", "characters/Luigi/geo.inc.c"], cwd=APP)
    assert r.returncode == 0


def test_installer_help():
    r = subprocess.run([sys.executable, str(APP / "install_mario64mr.py"), "--help"], capture_output=True,
                       text=True, timeout=60)
    assert r.returncode == 0 and "--character" in r.stdout
