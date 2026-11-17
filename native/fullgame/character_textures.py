"""
A character pack's textures, whichever way its model.inc.c holds them, made into what the game reads with its data
outside (EXTERNAL_DATA): each texture array is the texture's name, and the texture a .png in a resource pack.

  #include "actors/mario/x.rgba16.inc.c"   with x.rgba16.png in the pack (Fast64, model mods): that .png
                                            with x.rgba16.inc.c in the pack instead (its pixels, as hex): decoded
                                            neither, but one of the game's own (mario_logo...): the game's
  "actors/luigi/x.rgba16"                   (a model already made for sm64ex's external data): its .png in the pack
  { 0x12, 0x34, ... }                       (pixels written into the source): decoded

Decoded pixels need their format and size: from the display list that loads them (gsDPLoadTextureBlock, or
gsDPSetTextureImage ... gsDPSetTile ... gsDPSetTileSize), or else from the name (.rgba16) and a square size.
"""
import re
import struct
import zlib

FORMATS = ("rgba16", "rgba32", "ia16", "ia8", "ia4", "ia1", "i8", "i4", "ci8", "ci4")
BITS = {"rgba16": 16, "rgba32": 32, "ia16": 16, "ia8": 8, "ia4": 4, "ia1": 1, "i8": 8, "i4": 4, "ci8": 8, "ci4": 4}
# u8 name[...] = followed by { ... } or "..."
ARRAY = re.compile(r"^[ \t]*(?:ALIGNED\d+\s+)?(?:static\s+)?(?:const\s+)?(u8|s8|u16|Texture|unsigned\s+char)\s+(\w+)"
                   r"\s*\[[^\]\n]*\]\s*=\s*", re.M)
INCLUDE = re.compile(r'#\s*include\s+"([^"]+)"')
COMMENTS = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)
NUMBER = re.compile(r"0[xX][0-9A-Fa-f]+|\d+")


class TextureError(Exception):
    pass


def format_of(name):
    """rgba16 for "x.rgba16", "x_rgba16" or "x_rgba16_..."; else None."""
    for part in reversed(re.split(r"[._]", name.lower())):
        if part in FORMATS:
            return part
    return None


def png(width, height, rgba):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    rows = b"".join(b"\0" + bytes(rgba[y * width * 4:(y + 1) * width * 4]) for y in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def rgba16(value):
    return ((value >> 11 & 31) * 255 // 31, (value >> 6 & 31) * 255 // 31, (value >> 1 & 31) * 255 // 31,
            255 if value & 1 else 0)


def texels(data, bits):
    """Each texel's value, in order (4 and 1 bits: high bits first, as the N64 reads them)."""
    if bits == 32:
        return [data[i:i + 4] for i in range(0, len(data) - 3, 4)]
    if bits == 16:
        return [data[i] << 8 | data[i + 1] for i in range(0, len(data) - 1, 2)]
    if bits == 8:
        return list(data)
    per = 8 // bits
    mask = (1 << bits) - 1
    return [byte >> (8 - bits * (k + 1)) & mask for byte in data for k in range(per)]


def decode(data, fmt, width, height, palette=None):
    """RGBA8 pixels, as the game's own importers make them (gfx_pc.c)."""
    values = texels(data, BITS[fmt])[:width * height]
    if len(values) < width * height:
        raise TextureError(f"{len(data)} bytes are too few for {width}x{height} {fmt}")
    out = bytearray()
    for v in values:
        if fmt == "rgba32":
            out += bytes(v)
        elif fmt == "rgba16":
            out += bytes(rgba16(v))
        elif fmt == "ia16":
            out += bytes((v >> 8, v >> 8, v >> 8, v & 255))
        elif fmt == "ia8":
            out += bytes(((v >> 4) * 17,) * 3 + ((v & 15) * 17,))
        elif fmt == "ia4":
            out += bytes(((v >> 1) * 255 // 7,) * 3 + ((255 if v & 1 else 0),))
        elif fmt == "ia1":
            out += bytes((255 * v,) * 4)
        elif fmt == "i8":
            out += bytes((v, v, v, 255))
        elif fmt == "i4":
            out += bytes((v * 17, v * 17, v * 17, 255))
        else:  # ci4, ci8
            if not palette or v * 2 + 1 >= len(palette):
                raise TextureError("a colour-indexed texture without its palette")
            out += bytes(rgba16(palette[v * 2] << 8 | palette[v * 2 + 1]))
    return out


def number(expression):
    """A size in a display list ((32 - 1) << G_TEXTURE_IMAGE_FRAC, 124, 0x7C...)."""
    text = expression.replace("G_TEXTURE_IMAGE_FRAC", "2").replace("G_TX_RENDERTILE", "0").replace("G_TX_LOADTILE", "7")
    if not re.fullmatch(r"[\s0-9xXa-fA-F+\-*/()<>]*", text) or not text.strip():
        raise TextureError(f"can't read the size {expression.strip()}")
    return int(eval(text, {"__builtins__": {}}))  # (digits and operators only, checked above)


def arguments(text, at):
    """The comma-separated arguments of the call whose '(' is at text[at]."""
    depth, start, out = 0, at + 1, []
    for i in range(at, len(text)):
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                out.append(text[start:i].strip())
                return out
        elif c == "," and depth == 1:
            out.append(text[start:i].strip())
            start = i + 1
    return out


def calls(text, name, after=0, before=None):
    for m in re.finditer(r"\b(?:" + name + r")\s*\(", text[after:before]):
        at = after + m.end() - 1
        yield at, arguments(text, at)


def size_code(value):
    m = re.search(r"G_IM_SIZ_(\d+)b", value)
    return int(m.group(1)) if m else None


def fmt_code(fmt, bits):
    kind = {"G_IM_FMT_RGBA": "rgba", "G_IM_FMT_IA": "ia", "G_IM_FMT_I": "i", "G_IM_FMT_CI": "ci"}.get(fmt.strip())
    name = f"{kind}{bits}" if kind and bits else None
    return name if name in BITS else None


def palette_for(text, at, arrays):
    """The palette a display list loads (gsDPLoadTLUT...) before the texture at text[at]."""
    best = None
    for pos, args in calls(text, r"gsDPLoadTLUT_pal(?:16|256)", 0, at):
        best = args[-1]
    for pos, args in calls(text, "gsDPSetTextureImage", 0, at):
        if len(args) == 4 and re.search(r"gsDPLoadTLUT", text[pos:pos + 400]):
            best = args[3]
    return arrays.get(best) if best else None


def layout(text, name, size, arrays, base=None):
    """(format, width, height, palette) of the texture array called name, from the display lists using it."""
    for at, args in calls(text, r"gsDPLoadTextureBlock(?:_4b)?|gsDPLoadTextureTile(?:_4b)?"):
        if args and args[0] == name:
            four = text[text.rfind("gsDP", 0, at):at].rstrip().endswith("_4b")
            fmt = fmt_code(args[1], 4 if four else size_code(args[2]))
            w, h = (args[2], args[3]) if four else (args[3], args[4])
            if fmt:
                return fmt, number(w), number(h), palette_for(text, at, arrays)
    for at, args in calls(text, "gsDPSetTextureImage"):
        if len(args) == 4 and args[3] == name:
            ends = [p for p, _ in calls(text, "gsDPSetTextureImage", at + 1)]
            end = ends[0] if ends else len(text)
            sizes = list(calls(text, "gsDPSetTileSize", at, end))
            tiles = [a for p, a in calls(text, "gsDPSetTile", at, sizes[0][0] if sizes else end) if len(a) >= 2]
            if sizes and tiles and len(sizes[0][1]) == 5:
                fmt = fmt_code(tiles[-1][0], size_code(tiles[-1][1]))
                if fmt:
                    lrs, lrt = sizes[0][1][3], sizes[0][1][4]
                    return fmt, number(lrs) // 4 + 1, number(lrt) // 4 + 1, palette_for(text, at, arrays)
    fmt = format_of(base or "") or format_of(name)
    if fmt:
        side = int(round((size * 8 / BITS[fmt]) ** 0.5))
        if side * side * BITS[fmt] == size * 8:
            return fmt, side, side, None
    raise TextureError(f"no display list says how big the texture {name} is")


def raw_bytes(body, kind):
    clean = COMMENTS.sub("", body)
    if not re.fullmatch(r"[\s,0-9xXa-fA-F]*", clean):
        return None
    values = [int(v, 0) for v in NUMBER.findall(clean)]
    if kind == "u16":
        return b"".join(struct.pack(">H", v & 0xFFFF) for v in values)
    return bytes(v & 255 for v in values)


class Textures:
    """One pack's textures: rewrite() makes a source file's texture arrays into names; self.files is what goes
    into characters.zip, (png bytes or path, name in the zip)."""

    def __init__(self, root, slug, folder, sources, pack_root=None):
        self.root, self.slug, self.folder = root, slug, folder
        self.sources = sources  # every model source's text: the display lists to read sizes from
        self.pngs, self.hex = {}, {}
        # (next to the model first, then anywhere else in the pack)
        found = sorted(folder.rglob("*.png")) + sorted(set((pack_root or folder).rglob("*.png")) - set(folder.rglob("*.png")))
        for p in found:
            for key in (p.name.lower(), p.stem.lower()):  # (a .png named without its format too)
                if key in self.pngs and self.pngs[key].read_bytes() != p.read_bytes():
                    print(f"  two different {p.name} in the pack: using {self.pngs[key]}, not {p}", flush=True)
                self.pngs.setdefault(key, p)
        hexes = sorted(folder.rglob("*.inc.c")) + sorted((pack_root or folder).rglob("*.inc.c"))
        for p in hexes:
            if p.name not in ("model.inc.c", "geo.inc.c"):
                self.hex.setdefault(p.name[:-len(".inc.c")].lower(), p)
        self.files, self.made = [], {}

    def name_for(self, base):
        entry = f"characters/{self.slug}/{base}"
        return entry, "gfx/" + entry + ".png"

    def add(self, base, data):
        entry, zipped = self.name_for(base)
        if zipped not in self.made:
            self.made[zipped] = True
            self.files.append((data, zipped))
        return entry

    def pack_png(self, base):
        for key in (base.lower() + ".png", base.lower(), re.sub(r"\.(%s)$" % "|".join(FORMATS), "", base.lower())):
            if key in self.pngs:
                return self.pngs[key]
        return None

    def decoded(self, name, base, data, arrays):
        fmt, width, height, palette = layout(self.sources, name, len(data), arrays, base)
        if not format_of(base):
            base = f"{base}.{fmt}"  # (the game reads a texture's format from its name when it preloads them)
        return self.add(base, png(width, height, decode(data, fmt, width, height, palette)))

    def resolve(self, name, path, arrays):
        """The name the game loads for a texture written as a path (an include or a string)."""
        base = path.rsplit("/", 1)[-1]
        found = self.pack_png(base)
        if found:
            if not format_of(base) and format_of(found.name):
                base = found.name[:-len(".png")]
            return self.add(base, found)
        if base.lower() in self.hex:
            data = raw_bytes(self.hex[base.lower()].read_text(errors="replace"), "u8")
            if data:
                return self.decoded(name, base, data, arrays)
        if (self.root / (path + ".png")).is_file():
            return path  # (one of the game's own)
        raise TextureError(f"the texture {base}.png is neither in the pack nor one of the game's")

    def rewrite(self, text):
        """The source with every texture array holding its texture's name."""
        arrays, spans = {}, []
        for m in ARRAY.finditer(text):
            start = m.end()
            if start < len(text) and text[start] == "{":
                end = text.find("}", start)
                if end < 0:
                    continue
                body = text[start + 1:end]
                spans.append((m, start, end + 1, body))
                data = raw_bytes(body, m.group(1))
                if data:
                    arrays[m.group(2)] = data
            elif text.startswith('"', start):
                end = text.find('"', start + 1)
                spans.append((m, start, end + 1, text[start:end + 1]))
        out, last = [], 0
        for m, start, end, body in spans:
            name, value = m.group(2), None
            include = INCLUDE.search(body)
            if include and include.group(1).endswith(".inc.c"):
                path = include.group(1)[:-len(".inc.c")]
                if format_of(path.rsplit("/", 1)[-1]):
                    value = self.resolve(name, path, arrays)
            elif body.startswith('"'):
                value = self.resolve(name, body[1:-1], arrays)
            elif name in arrays and self.is_texture(name) and not self.is_palette(name):
                value = self.decoded(name, name, arrays[name], arrays)
            if value is None:
                continue
            literal = ",".join("0x%X" % b for b in value.encode() + b"\0") + ","
            out.append(text[last:start])
            out.append("{" + literal + "}" if not body.startswith('"') else '"' + value + '"')
            last = end
        out.append(text[last:])
        return "".join(out)

    def is_texture(self, name):
        """Drawn as a texture by a display list (or named like one)."""
        for _, args in calls(self.sources, r"gsDPLoadTextureBlock(?:_4b)?|gsDPLoadTextureTile(?:_4b)?"):
            if args and args[0] == name:
                return True
        for _, args in calls(self.sources, "gsDPSetTextureImage"):
            if len(args) == 4 and args[3] == name:
                return True
        return format_of(name) is not None

    def is_palette(self, name):
        """Loaded as a palette (gsDPLoadTLUT...), not drawn: left as it is (the game reads its colours itself)."""
        if re.search(r"gsDPLoadTLUT_pal(?:16|256)\s*\([^)]*\b%s\b" % re.escape(name), self.sources):
            return True
        for pos, args in calls(self.sources, "gsDPSetTextureImage"):
            if len(args) == 4 and args[3] == name and re.search(r"gsDPLoadTLUT", self.sources[pos:pos + 400]):
                return True
        return False
