/* Experimental DOS16 engine. Repository LICENSE.md applies. No original assets. */
#include <dos.h>
#include <bios.h>
#include <conio.h>
#include <stdio.h>
#include <string.h>
#include "sim.h"

static World world;
static unsigned char __far *vram;
/* Compact original 3x5 font, A-Z then 0-9. Bit 14 is top left. */
static const unsigned int font[] = {
    0x2bed,0x6bae,0x3923,0x6b6e,0x79a7,0x79a4,0x396b,
    0x5bed,0x7497,0x126a,0x5bad,0x4927,0x5fed,0x5f6d,
    0x2b6a,0x6ba4,0x2b7b,0x6bad,0x388e,0x7492,0x5b6f,
    0x5b6a,0x5bfd,0x5aad,0x5a92,0x72a7,
    0x7b6f,0x2492,0x73e7,0x73cf,0x5bc9,0x79cf,0x79ef,
    0x7249,0x7bef,0x7bcf
};
static void mode(unsigned char m)
{
    union REGS r;
    memset(&r, 0, sizeof(r)); r.h.ah = 0; r.h.al = m;
    int86(0x10, &r, &r);
}
static void pixel(int x, int y, unsigned char c)
{
    unsigned int off;
    if (x < 0 || x >= 320 || y < 0 || y >= 200) return;
    off = video_offset((unsigned int)x, (unsigned int)y);
    if (x & 1) vram[off] = (vram[off] & 0xf0) | c;
    else vram[off] = (vram[off] & 0x0f) | (c << 4);
}
/* All rectangles have even x/width; fill two pixels per write. */
static void rect(int x, int y, int width, int height, unsigned char c)
{
    int row;
    for (row = y; row < y + height; ++row)
        _fmemset(vram + video_offset(x, row), c | (c << 4), width / 2);
}
static void text(int x, int y, const char *s, unsigned char color)
{
    int n, row, col;
    unsigned int bits;
    while (*s) {
        n = (*s >= 'A' && *s <= 'Z') ? *s - 'A' :
            ((*s >= '0' && *s <= '9') ? *s - '0' + 26 : -1);
        if (n >= 0) {
            bits = font[n];
            for (row = 0; row < 5; ++row) for (col = 0; col < 3; ++col)
                if (bits & (1U << (14 - row * 3 - col))) pixel(x + col, y + row, color);
        }
        x += 4; ++s;
    }
}
static void draw(void)
{
    int x, y, sx, sy, i, terrain;
    unsigned char colors[] = {2, 1, 8, 6};
    char label[20];
    for (y = 0; y < VIEW_H; ++y) for (x = 0; x < VIEW_W; ++x) {
        terrain = world.terrain[y + world.camera_y][x + world.camera_x];
        sx = x * 16; sy = y * 16;
        rect(sx, sy, 16, 16, colors[terrain]);
        if (terrain == 0) {
            rect(sx + 2, sy + 4, 2, 2, 10); rect(sx + 10, sy + 12, 2, 1, 0);
        } else if (terrain == 1) {
            rect(sx + 2, sy + 5, 8, 1, 9); rect(sx + 6, sy + 11, 8, 1, 3);
        } else if (terrain == 2) rect(sx + 4, sy + 4, 8, 7, 7);
        else rect(sx, sy + 7, 16, 2, 14);
    }
    for (i = 0; i < UNIT_COUNT; ++i) {
        x = world.units[i].x - world.camera_x;
        y = world.units[i].y - world.camera_y;
        if (x < 0 || x >= VIEW_W || y < 0 || y >= VIEW_H) continue;
        sx = x * 16; sy = y * 16;
        if (i == world.selected) {
            rect(sx, sy, 16, 1, 15); rect(sx, sy + 15, 16, 1, 15);
            rect(sx, sy, 2, 16, 15); rect(sx + 14, sy, 2, 16, 15);
        }
        rect(sx + 2, sy + 3, 12, 10, 0);
        rect(sx + 4, sy + 3, 8, 10, 12);
        rect(sx + 6, sy + 5, 4, 5, 4);
        rect(sx + 6, sy + 1, 2, 6, 14);
    }
    rect(240, 0, 80, 200, 8); rect(242, 2, 76, 16, 4);
    text(252, 7, "RA16 DEMO", 15);
    text(248, 24, "RADAR", 7);
    for (y = 0; y < MAP_H; ++y) for (x = 0; x < MAP_W; ++x)
        pixel(248 + x, 34 + y, colors[world.terrain[y][x]]);
    for (x = 0; x < VIEW_W; ++x) {
        pixel(248 + world.camera_x + x, 34 + world.camera_y, 15);
        pixel(248 + world.camera_x + x, 34 + world.camera_y + VIEW_H - 1, 15);
    }
    for (y = 0; y < VIEW_H; ++y) {
        pixel(248 + world.camera_x, 34 + world.camera_y + y, 15);
        pixel(248 + world.camera_x + VIEW_W - 1, 34 + world.camera_y + y, 15);
    }
    for (i = 0; i < UNIT_COUNT; ++i)
        pixel(248 + world.units[i].x, 34 + world.units[i].y, 12);
    sprintf(label, "UNIT %d", world.selected + 1); text(248, 105, label, 15);
    sprintf(label, "X %02d Y %02d", world.units[world.selected].x, world.units[world.selected].y);
    text(248, 114, label, 7);
    text(248, 128, "ARROWS PAN", 15); text(248, 138, "WASD MOVE", 15);
    text(248, 148, "TAB SELECT", 15); text(248, 158, "C CENTER", 15);
    text(248, 174, "NO COMBAT", 7); text(248, 184, "ESC EXIT", 15);
    rect(0, 192, 240, 8, 0);
    text(4, 194, "DOS16 PROTOTYPE  1 2 3 SELECT UNIT", 7);
}
/* BIOS key words preserve scan codes and work with the EX keyboard. */
static int handle_key(unsigned int key)
{
    int c = key & 255;
    if (c >= 'A' && c <= 'Z') c += 'a' - 'A';
    if (c == 27) return -1;
    if (c == 0 || c == 0xe0) {
        switch (key >> 8) {
        case 72: world_scroll(&world, 0, -1); break;
        case 80: world_scroll(&world, 0, 1); break;
        case 75: world_scroll(&world, -1, 0); break;
        case 77: world_scroll(&world, 1, 0); break;
        default: return 0;
        }
    } else switch (c) {
    case 'w': world_move(&world, 0, -1); break;
    case 's': world_move(&world, 0, 1); break;
    case 'a': world_move(&world, -1, 0); break;
    case 'd': world_move(&world, 1, 0); break;
    case 9: world_select(&world, (world.selected + 1) % UNIT_COUNT); break;
    case '1': case '2': case '3': world_select(&world, c - '1'); break;
    case 'c': world_center(&world); break;
    default: return 0;
    }
    return 1;
}
int test_sim(void);
int main(int argc, char **argv)
{
    union REGS r;
    unsigned char old_mode;
    int result, smoke = argc == 2 && strcmp(argv[1], "-test") == 0;
    FILE *f;
    unsigned int i;
    if (smoke) test_sim();
    if (!smoke) {
        puts("RA16 prototype requires Tandy 320x200 16-color graphics.");
        puts("Press Y to start on Tandy hardware/emulation; any other key cancels.");
        result = getch();
        if (result != 'y' && result != 'Y') return 0;
    }
    memset(&r, 0, sizeof(r)); r.h.ah = 0x0f; int86(0x10, &r, &r);
    old_mode = r.h.al & 0x7f;
    mode(9);
    memset(&r, 0, sizeof(r)); r.h.ah = 0x0f; int86(0x10, &r, &r);
    if (r.h.al != 9) { mode(old_mode); puts("Mode 09h unavailable."); return 1; }
    vram = (unsigned char __far *)MK_FP(0xb800, 0);
    _fmemset(vram, 0, 32768U);
    world_init(&world); draw();
    if (smoke) {
        /* Exercise the same input dispatcher used interactively. */
        handle_key('d'); handle_key('2'); handle_key('w');
        handle_key(0x4d00); handle_key(0x5000); draw();
        f = fopen("FRAME.RAW", "wb");
        if (!f) { mode(old_mode); return 2; }
        for (i = 0; i < 32768U; ++i) if (fputc(vram[i], f) == EOF) {
            fclose(f); mode(old_mode); return 2;
        }
        result = fclose(f);
        mode(old_mode);
        if (result || world.selected != 1 || world.units[0].x != 6 ||
            world.units[1].y != 5 || world.camera_x != 1 || world.camera_y != 1)
            return 3;
        f = fopen("PASS.TXT", "w");
        if (!f) return 4;
        fputs("DOS16 simulation, input and video smoke PASS\n", f);
        return fclose(f) ? 4 : 0;
    }
    for (;;) {
        /* Blocking BIOS read: no idle redraw or processor-speed-dependent loop. */
        result = handle_key(_bios_keybrd(_KEYBRD_READ));
        if (result < 0) break;
        if (result) draw();
    }
    mode(old_mode);
    return 0;
}
