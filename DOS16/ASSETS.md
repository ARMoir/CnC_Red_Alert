# Original light-tank artwork: optional local asset pack

The prototype can now display the original Allied light tank, reduced from
24x24 to 16x16 pixels, in eight directions, and its original 32x24 low-resolution
sidebar icon. `R` rotates the selected tank clockwise by 45 degrees for inspection;
successful WASD movement sets its facing. The turret is composited with the hull
offline and follows the hull; independent aiming is not implemented.

The repository and CI contain **no extracted or converted game artwork**. Supply
your own Allied CD image or extracted files to generate `TANK.SPR` locally.
Without this file, the executable uses the original prototype's geometric tanks.
An existing but malformed pack is rejected before entering graphics mode.

## Convert on a modern computer

From `DOS16`, using Python 3.9 or later:

```sh
python -m pip install -r tools/requirements-assets.txt
python tools/convert_tank.py --disc /path/to/redalert-allied.zip --output converted
```

`--disc` accepts the original Allied CD's single-track MODE1/2352 `.bin`, a plain
ISO9660 `.iso`, or a ZIP containing exactly one such image. No mount or installer
is run. ZIP extraction uses a temporary file rather than archive-controlled paths.
Other disc editions, multitrack images, and other SHP variants are not supported
by this first converter. The original archive is read without modification.

Alternatively, put `1TNK.SHP`, the **LORES** `1TNKICON.SHP`, and `TEMPERAT.PAL` in
a directory and run:

```sh
python tools/convert_tank.py --assets /path/to/extracted --output converted
```

This alternative uses only Python's standard library. Files are found on the
Allied disc at:

| Asset | Container chain |
| --- | --- |
| `1TNK.SHP` | `MAIN.MIX` -> `CONQUER.MIX` |
| `1TNKICON.SHP` | `INSTALL/REDALERT.MIX` -> `LORES.MIX` |
| `TEMPERAT.PAL` | `INSTALL/REDALERT.MIX` -> `LOCAL.MIX` |

Copy `converted/TANK.SPR` into the current DOS working directory with `RA16.EXE`.
Run `RA16`, press Y, move with WASD and rotate with R. The pack is independent of
the executable, so changing artwork does not require rebuilding. All three demo
tanks currently use this same light-tank sprite and fixed palette colors.

Outputs:

- `TANK.SPR`: 1,768-byte runtime pack.
- `tank-comparison.png`: top row original 24x24 hull/turret compositions; bottom
  row converted 16x16 frames. Each row is displayed at 4x pixel scale, clockwise
  from north. The reference row approximates index-4 shadows on its background.
- `asset-manifest.json`: source hashes, output hash, dimensions and limitations.

Keep source game data and generated artwork local. The source-code license does
not itself grant rights to redistribute the commercial game's artwork.

## What is reused from the original source

These are narrow adaptations, not a linked copy of the original engine:

- `CODE/2KEYFRAM.CPP`: SHP header and keyframe/key-delta/delta-chain semantics.
- `CODE/LCWUNCMP.CPP`: LCW decompression operations, ported to bounded Python.
- `WWFLAT32/WSA/XORDELTA.ASM`: XOR delta operations, ported to bounded Python.
- `CODE/TECHNO.CPP`: exact `TechnoClass::BodyShape` facing lookup table.
- `CODE/UNIT.CPP`: hull frame plus turret frame at `BodyShape[facing] + 32`.
- `CODE/UDATA.CPP`: light-tank asset name and no special turret offset.
- `CODE/DISPLAY.CPP`: index-4 unit shadow interpretation.
- `CODE/{MIXFILE,CRC,PK,CONST}.CPP`: MIX directory, filename hash and public-key
  setup conventions. PyCryptodome performs Blowfish directory decoding.

The modern converter does expensive archive decoding, compositing and palette
conversion once. The V20 only loads a small fixed-size pack and draws masked
4-bit pixels. The original engine's 32-bit graphics assembly is not executed.
Derived format code retains attribution and the repository license applies.

## Palette and detail limits

Nearest-neighbor resizing preserves crisp pixel edges. Nearest RGB color matching
maps the 6-bit original palette to Tandy's fixed 16 RGBI colors, with a separate
transparency mask so opaque black pixels remain opaque. Gold tones can become
gray or yellow under this simple mapping. Dynamic team-color remapping and
artist-tuned/dithered color conversion are future improvements. Unit shadow index
4 is omitted instead of appearing bright green; no translucent shadows yet.
Icons use the ordinary palette mapping. The pack keeps eight of the original
32 facings; there are no firing, damage, death or track animations.

## Pack format, version 1

All sizes are fixed; the loader checks both the signature and exact file length.

| Offset | Contents |
| --- | --- |
| 0 | Eight-byte signature `R16SPR1` followed by a zero byte |
| 8 | Eight 160-byte 16x16 frames, compass order N, NE, E, SE, S, SW, W, NW |
| 1288 | One 480-byte 32x24 icon |

Each frame stores row-major 4-bit colors (even pixel in high nibble), followed by
a one-bit-per-pixel opacity mask (first pixel in bit 7). A tank frame uses 128
color bytes plus 32 mask bytes; the icon uses 384 plus 96. No pointers, allocation,
compression or variable dimensions are present in the DOS file format.

## Validation

`python tools/test_assets.py` runs synthetic LCW, XOR, SHP delta-chain, MIX,
sector-read, transparency and facing tests. CI needs no game files or Python
packages for those tests. It runs DOSBox smoke tests both without a pack and
with a synthetic pack, compares every opaque pixel of a moved tank and the icon
against the loaded pack, and verifies that a malformed pack cannot report success.

Local validation on November 5, 2026 also decoded the supplied Allied CD archive,
all 64 light-tank SHP frames and the LORES icon, generated the actual pack, built
with Open Watcom's 8086 target and passed the DOSBox Tandy framebuffer check with
that pack loaded. The captured battlefield and source/conversion preview were
visually reviewed. This is not yet a test on physical EX/V20 hardware.

For local game-art smoke testing, copy the converted pack beside the EXE, remove
old `PASS.TXT` and `FRAME.RAW`, run `RA16 -test` in a known Tandy configuration,
then run `python check_smoke.py` on the host. The checker automatically detects
the optional pack. Do not publish the resulting game-art dumps as CI fixtures.
