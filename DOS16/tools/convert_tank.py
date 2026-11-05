"""Convert user-supplied Allied CD artwork to the optional DOS16 TANK.SPR pack.

No artwork is downloaded or embedded. Python 3.9+; encrypted MIX directories
require pycryptodome. Format algorithms and facing data derive from EA source;
see ra_formats.py and ../ASSETS.md for attribution and exact limitations.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import tempfile
import zipfile
import zlib
from ra_formats import need, mix_member, shp_decode, Slice

PALETTE = bytes.fromhex(
    '000000 0000aa 00aa00 00aaaa aa0000 aa00aa aa5500 aaaaaa '
    '555555 5555ff 55ff55 55ffff ff5555 ff55ff ffff55 ffffff')
# Exact TechnoClass::BodyShape table from CODE/TECHNO.CPP (EA, GPL-3.0+).
BODY_SHAPE = (0,31,30,29,28,27,26,25,24,23,22,21,20,19,18,17,16,15,14,13,12,11,10,9,8,7,6,5,4,3,2,1)
MAGIC = b'R16SPR1\0'


class FileSource:
    def __init__(self, stream):
        self.stream = stream
        stream.seek(0, 2)
        self.size = stream.tell()

    def read(self, offset, size):
        need(0 <= offset <= self.size and 0 <= size <= self.size - offset, 'File extent out of range')
        self.stream.seek(offset)
        data = self.stream.read(size)
        need(len(data) == size, 'Truncated file')
        return data


class DiscSource:
    """One-track ISO9660 ISO or MODE1/2352 BIN. Never mounts/executes the CD."""
    def __init__(self, source):
        self.source = source
        if source.read(16 * 2048 + 1, 5) == b'CD001':
            self.sector, self.skip = 2048, 0
        else:
            need(source.read(16 * 2352 + 16, 7) == b'\1CD001\1', 'Expected ISO or MODE1/2352 BIN')
            self.sector, self.skip = 2352, 16
        self.size = source.size // self.sector * 2048

    def read(self, offset, size):
        need(0 <= offset <= self.size and 0 <= size <= self.size - offset, 'Disc extent out of range')
        out = bytearray()
        while size:
            lba, pos = divmod(offset, 2048)
            n = min(size, 2048 - pos)
            out.extend(self.source.read(lba * self.sector + self.skip + pos, n))
            offset += n
            size -= n
        return bytes(out)

    def member(self, path):
        pvd = self.read(16 * 2048, 2048)
        need(pvd[:7] == b'\1CD001\1', 'Missing ISO primary descriptor')
        record = pvd[156:190]
        for part in path.upper().split('/'):
            lba, size = struct.unpack_from('<I', record, 2)[0], struct.unpack_from('<I', record, 10)[0]
            need(record[25] & 2 and size <= 4 * 1024 * 1024, 'Invalid ISO directory')
            data, pos, found = self.read(lba * 2048, size), 0, None
            while pos < size:
                length = data[pos]
                if not length:
                    pos = (pos // 2048 + 1) * 2048
                    continue
                need(length >= 34 and pos + length <= size, 'Invalid ISO record')
                rec = data[pos:pos + length]
                need(33 + rec[32] <= length, 'Invalid ISO name')
                name = rec[33:33 + rec[32]].decode('ascii').split(';')[0]
                if name == part:
                    found = rec
                    break
                pos += length
            need(found is not None, f'Disc member not found: {path}')
            record = found
        need(not record[25] & 2, 'Expected ISO file')
        return Slice(self, struct.unpack_from('<I', record, 2)[0] * 2048,
                     struct.unpack_from('<I', record, 10)[0])


def read_member(source, *names):
    for name in names:
        source = mix_member(source, name)
    need(source.size <= 1024 * 1024, 'Unexpectedly large sprite asset')
    return source.read(0, source.size)


def load_disc(stream):
    disc = DiscSource(FileSource(stream))
    tank = read_member(disc.member('MAIN.MIX'), 'CONQUER.MIX', '1TNK.SHP')
    red = disc.member('INSTALL/REDALERT.MIX')
    icon = read_member(red, 'LORES.MIX', '1TNKICON.SHP')
    pal = read_member(red, 'LOCAL.MIX', 'TEMPERAT.PAL')
    return tank, icon, pal


def reduce_frame(pixels, width, height, outw, outh, palette, unit=False):
    """Nearest-neighbor geometry and nearest RGB Tandy color; index 0 transparent."""
    need(len(palette) == 768 and max(palette) <= 63, 'Expected 6-bit VGA palette')
    mapping = []
    for i in range(256):
        rgb = [v * 255 // 63 for v in palette[i * 3:i * 3 + 3]]
        mapping.append(min(range(16), key=lambda c: sum(
            (rgb[k] - PALETTE[c * 3 + k]) ** 2 for k in range(3))))
    result = []
    for y in range(outh):
        sy = min(height - 1, (2 * y + 1) * height // (2 * outh))
        for x in range(outw):
            sx = min(width - 1, (2 * x + 1) * width // (2 * outw))
            index = pixels[sy * width + sx]
            # DISPLAY.CPP UShadowCols treats index 4 as a translucent shadow.
            # Omit it for units rather than drawing its bright-green palette entry.
            result.append(mapping[index] if index and not (unit and index == 4) else None)
    return result


def pack_frame(pixels):
    need(len(pixels) % 8 == 0, 'Frame must align to mask bytes')
    colors, mask = bytearray(), bytearray()
    for i in range(0, len(pixels), 2):
        colors.append(((pixels[i] or 0) << 4) | (pixels[i + 1] or 0))
    for i in range(0, len(pixels), 8):
        mask.append(sum((pixels[i + j] is not None) << (7 - j) for j in range(8)))
    return bytes(colors + mask)


def png(path, width, height, rgb):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    rows = b''.join(b'\0' + rgb[y * width * 3:(y + 1) * width * 3] for y in range(height))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>2I5B', width, height, 8, 2, 0, 0, 0)) +
                     chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


def convert(tank, icon, palette, output):
    width, height, frames = shp_decode(tank)
    iw, ih, icons = shp_decode(icon)
    need((width, height, len(frames)) == (24, 24, 64), 'Expected original 1TNK.SHP (24x24, 64 frames)')
    need((iw, ih) == (32, 24), 'Expected LORES 32x24 icon')
    originals, converted = [], []
    for facing in range(8):
        frame = BODY_SHAPE[facing * 4]
        # UNIT.CPP draws hull then turret at BodyShape[facing]+32.
        # UDATA.CPP Turret_Adjust applies no offset to the light tank.
        combined = bytes(t or b for b, t in zip(frames[frame], frames[frame + 32]))
        originals.append(combined)
        converted.append(reduce_frame(combined, width, height, 16, 16, palette, unit=True))
    converted.append(reduce_frame(icons[0], iw, ih, 32, 24, palette))
    payload = MAGIC + b''.join(pack_frame(p) for p in converted)
    need(len(payload) == 1768, 'Incorrect pack size')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'TANK.SPR').write_bytes(payload)
    # Top: original 24x24 hull+turret. Bottom: corresponding 16x16 Tandy frames.
    # Both at 4x nearest-neighbor display scale; directions clockwise N..NW.
    w, h, scale = 8 * 32, 64, 4
    canvas = bytearray(bytes((32, 40, 32)) * w * h)
    for i in range(8):
        for row, data, fw, fh in ((0, originals[i], 24, 24), (32, converted[i], 16, 16)):
            for y in range(fh):
                for x in range(fw):
                    index = data[y * fw + x]
                    if row == 0:
                        if index == 0:
                            continue
                        color = (bytes((16, 20, 16)) if index == 4 else
                                 bytes(v * 255 // 63 for v in palette[index * 3:index * 3 + 3]))
                    else:
                        if index is None:
                            continue
                        color = PALETTE[index * 3:index * 3 + 3]
                    off = ((row + y) * w + i * 32 + x) * 3
                    canvas[off:off + 3] = color
    enlarged = b''.join(bytes(canvas[(y // scale * w + x // scale) * 3:
                                     (y // scale * w + x // scale) * 3 + 3])
                        for y in range(h * scale) for x in range(w * scale))
    png(output / 'tank-comparison.png', w * scale, h * scale, enlarged)
    manifest = {
        'unit': 'Allied light tank (1TNK)', 'palette': 'TEMPERAT.PAL',
        'directions': ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'],
        'source_dimensions': [width, height], 'tank_dimensions': [16, 16],
        'icon_dimensions': [32, 24], 'pack_bytes': len(payload),
        'source_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in
                          [('1TNK.SHP', tank), ('1TNKICON.SHP', icon), ('TEMPERAT.PAL', palette)]},
        'pack_sha256': hashlib.sha256(payload).hexdigest(),
        'limitations': 'Fixed source palette colors; no dynamic team remap. Unit shadow index 4 omitted.'
    }
    (output / 'asset-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(manifest, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--disc', type=Path, help='Allied CD .bin, .iso, or ZIP containing one image')
    group.add_argument('--assets', type=Path, help='Directory with 1TNK.SHP, 1TNKICON.SHP, TEMPERAT.PAL')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.assets:
        assets = tuple((args.assets / name).read_bytes() for name in ('1TNK.SHP', '1TNKICON.SHP', 'TEMPERAT.PAL'))
    elif args.disc.suffix.lower() == '.zip':
        with zipfile.ZipFile(args.disc) as archive, tempfile.TemporaryFile() as temp:
            candidates = [i for i in archive.infolist() if Path(i.filename).suffix.lower() in ('.bin', '.iso')]
            need(len(candidates) == 1 and candidates[0].file_size <= 900 * 1024 * 1024,
                 'Expected one CD image of at most 900 MiB')
            with archive.open(candidates[0]) as source:
                shutil.copyfileobj(source, temp)
            assets = load_disc(temp)
    else:
        with args.disc.open('rb') as source:
            assets = load_disc(source)
    convert(*assets, args.output)


if __name__ == '__main__':
    main()
