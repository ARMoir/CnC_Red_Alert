"""Check the actual DOS MZ and Tandy VRAM dump; emit a portable PPM preview."""
from pathlib import Path
import struct

exe = Path("RA16.EXE").read_bytes()
assert exe[:2] == b"MZ", "Not a DOS MZ executable"
last, pages, reloc, header = struct.unpack_from("<4H", exe, 2)
assert (pages - 1) * 512 + (last or 512) == len(exe)
assert header * 16 < len(exe) < 65536
assert reloc > 0
assert Path("PASS.TXT").read_text().strip() == "DOS16 simulation, input and video smoke PASS"
raw = Path("FRAME.RAW").read_bytes()
assert len(raw) == 32768
palette = bytes.fromhex(
    "000000 0000aa 00aa00 00aaaa aa0000 aa00aa aa5500 aaaaaa "
    "555555 5555ff 55ff55 55ffff ff5555 ff55ff ffff55 ffffff"
)
pixels = []
# Independent row-bank decoder, deliberately separate from the C implementation.
for y in range(200):
    bank, row = y % 4, y // 4
    for x in range(320):
        byte = raw[bank * 0x2000 + row * 160 + x // 2]
        pixels.append((byte >> 4) if x % 2 == 0 else byte & 15)
def color(x, y):
    return pixels[y * 320 + x]
assert color(0, 0) == 2, "Terrain missing"
assert color(240, 0) == 8 and color(242, 2) == 4, "Sidebar missing"
assert color(96, 64) == 15, "Selected moved unit missing"
if Path('TANK.SPR').exists():
    pack = Path('TANK.SPR').read_bytes()
    assert pack[:8] == b'R16SPR1\0' and len(pack) == 1768
    # Compare every opaque pixel of the east-facing first tank and sidebar icon.
    for frame, left, top, width, height in [(2, 80, 80, 16, 16), (8, 264, 124, 32, 24)]:
        size = width * height
        start = 8 + frame * 160
        for i in range(size):
            if pack[start + size // 2 + i // 8] & (0x80 >> (i % 8)):
                byte = pack[start + i // 2]
                expected = byte & 15 if i % 2 else byte >> 4
                assert color(left + i % width, top + i // width) == expected, 'Sprite pixel mismatch'
else:
    assert color(84, 83) == 12, "First moved unit missing"
assert color(0, 192) == 0, "Status strip missing"
assert len(set(pixels)) >= 10, "Unexpectedly empty/monochrome output"
rgb = b"".join(palette[c * 3:c * 3 + 3] for c in pixels)
Path("frame.ppm").write_bytes(b"P6\n320 200\n255\n" + rgb)
print(f"PASS: DOS MZ {len(exe)} bytes; simulation/input/video checks; frame.ppm")
