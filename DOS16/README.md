# RA16: Tandy DOS16 prototype, milestone 1

This is a small experimental engine, **not a recompiled or playable
Red Alert port**. It does not link the original engine. An optional offline
converter now adapts original format/facing code and loads converted light-tank
artwork from user-supplied game data; see [ASSETS.md](ASSETS.md). All original source and build files remain unchanged. Repository
[LICENSE.md](../LICENSE.md) applies, including its additional terms.

## Implemented

- Real-mode DOS MZ `RA16.EXE`, Open Watcom small model, 8086 instruction target
  (also suitable for the NEC V20; no DOS extender, x87, EMS or XMS required).
- BIOS mode 09h: 320x200 Tandy 16-color graphics, packed pixels in four 8 KiB
  banks through B800:0000. The BIOS sets up the video page; no VGA fallback.
- A deterministic 64x64 tile world, river, two crossing roads, rocks and three tanks.
- A 240x192 battlefield, 80-pixel sidebar with radar/viewport outline, selection
  and coordinates, and an 8-pixel status strip. Tiles are 16x16 pixels.
- Keyboard-driven, tile-step movement with terrain/occupancy checks and bounded
  tile-step camera scrolling. No autonomous movement or real-time simulation yet.
- DOS smoke mode, native simulation tests, CI cross-build and emulator check.
- Optional `TANK.SPR` pack: eight converted original light-tank facings and its
  sidebar icon. Without the pack, generated geometric tanks remain available.

| Key | Action |
| --- | --- |
| Y at startup | Confirm Tandy hardware/emulation and enter graphics |
| Arrow keys | Pan camera one tile (use Num Lock off on a numeric keypad) |
| W A S D | Move selected tank one tile; water, rocks and other tanks block it |
| Tab / 1 2 3 | Cycle / select tank |
| C | Center camera on selection |
| R | Rotate selection 45 degrees (visible with the optional sprite pack) |
| Esc | Restore previous BIOS video mode and exit |

Selection and movement do not automatically move the camera; press C if a tank
is off screen. The program redraws on recognized keys and blocks in the BIOS
keyboard service while idle. Key repeat uses the keyboard's typematic settings.
Previous screen contents/cursor state are not saved, only the video mode.

## Build

Use [Open Watcom V2](https://github.com/open-watcom/open-watcom-v2/releases/tag/2026-11-01-Build).
CI pins the November 1, 2026 snapshot and verifies SHA-256:
`89e90b7544cf3ea4a38124ec4c104a5027f31101405d7115c3f833daa465bb48`.

After extracting `ow-snapshot.tar.xz` into a directory of your choice, on Linux:

```sh
export WATCOM=/absolute/path/to/watcom
export PATH="$WATCOM/binl64:$PATH"
export INCLUDE="$WATCOM/h"
cd DOS16
wmake
```

On Windows PowerShell:

```powershell
$env:WATCOM = 'C:\watcom'
$env:PATH = "$env:WATCOM\binnt64;$env:PATH"
$env:INCLUDE = "$env:WATCOM\h"
cd DOS16
wmake
```

Or use an existing Open Watcom DOS installation's environment and run `wmake`
from this directory. The native compiler itself need not run on the Tandy: copy
the resulting EXE to the target. The build uses `wcl -bt=dos -ms -0 -os`, with
warnings treated as errors. `wcl386` is not a substitute. No original game
libraries, assembler, asset files or proprietary SDKs are needed for the default demo.
To use the original tank artwork, follow the separate [conversion instructions](ASSETS.md).

## Run and validate

In DOS on the Tandy, run `RA16`, then Y. Start with at least 128 KiB of free
conventional DOS memory; this is a conservative test recommendation, not a
measured minimum machine RAM requirement. Video memory is shared system RAM on
the EX. DOS, drivers and video reservation also consume memory.

From this directory, with DOSBox installed:

```sh
dosbox -conf dosbox.conf -c 'mount c .' -c 'c:' -c 'ra16'
```

The supplied configuration explicitly selects `machine=tandy`. Fixed 800 DOSBox
cycles are a deliberately slow test setting, **not a calibrated V20 speed**.
DOSBox 0.74 does not model the V20 instruction set/timing exactly; compiler `-0`
selects the compatible instruction baseline. Real EX/V20 validation is pending.

Automated tests on a Linux host:

```sh
cc -std=c89 -pedantic -Wall -Wextra -Werror -DHOST_TEST sim.c testsim.c -o host-test
./host-test
rm -f PASS.TXT FRAME.RAW
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy timeout 60s \
  dosbox -conf dosbox.conf -c 'mount c .' -c 'c:' -c 'ra16 -test' -c exit
python3 check_smoke.py
```

`-test` is for a known Tandy emulator/hardware configuration: it bypasses the
startup prompt. It runs simulation assertions, enters mode 09h, sends scripted
inputs through the real input dispatcher, renders, saves 32 KiB of video memory
to `FRAME.RAW`, restores the video mode and writes `PASS.TXT` only on success.
Always remove stale output first. The Python check validates the MZ header,
success marker and selected framebuffer pixels and creates `frame.ppm`.
The dump validates memory contents; visual emulator inspection is a separate
check of what the display actually shows. CI publishes the EXE, linker map,
frame dump/preview, test marker, configuration, instructions and license.

## Validation and limits

Initial local validation (November 5, 2026): Open Watcom 2026-11-01 Windows x64
cross-build passed with warnings as errors; DOSBox 0.74-3 Tandy smoke test passed;
MZ, input state and decoded video checks passed. EXE: 17,632 bytes. Linker memory
size: 60,928 bytes, including a 2,048-byte stack (not total machine RAM usage).
Tests are included in the EXE for repeatable target-side checks; their 32 KiB
address-coverage array can be separated later when optimizing memory.

After adding the optional sprite loader: EXE 20,190 bytes; linker memory size
65,520 bytes including the same stack. The actual converted Allied CD tank pack
passed the DOSBox smoke/framebuffer test. These sizes describe the Windows-host
cross-build; library/build differences may change the exact byte counts.

Full redraws write directly to VRAM without retrace synchronization or a back
buffer. Scrolling may visibly paint/tear and feel slow on an EX. This milestone
prioritizes verified layout and controls; no frame-rate or hardware-performance
claim is made. A successful BIOS mode query is not reliable hardware detection;
the startup prompt is intentional. Do not select Y on a non-Tandy adapter.

Before claiming hardware support: test startup/exit, all four scroll limits,
each selected tank, river/rock/unit blocking, bridge traversal, off-screen units,
Num Lock behavior, DOS free memory and redraw latency on the actual EX/V20.

## Next milestones (not implemented)

1. Measure EX/V20 redraw latency and memory; add dirty-tile rendering, optimized
   row blits and a bounded simulation tick before expanding gameplay.
2. Movement orders and pathfinding with explicit node/memory budgets.
3. Minimal combat/health, then economy and production with small fixed pools.
4. Expand the initial tank conversion and narrowly scoped original-source reuse
   into map/rules logic. No promise of original campaigns,
   save compatibility, networking, audio, mouse input or full game parity.

## Technical references

- Original repository [README](../README.md), [DOS/4GW loader](../CODE/CWSTUB.C)
  and `WWFLAT32`: context for why a separate real-mode engine is necessary.
- [Tandy 1000 technical reference, graphics memory](https://www.manualslib.com/manual/887518/Tandy-1000.html?page=53):
  banked graphics layout. EX-specific behavior remains a hardware test item.
- [Open Watcom source and releases](https://github.com/open-watcom/open-watcom-v2).
