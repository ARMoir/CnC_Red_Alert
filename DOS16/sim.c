/* DOS16 prototype; repository LICENSE.md applies. */
#include "sim.h"
static int clamp(int n, int max) { return n < 0 ? 0 : (n > max ? max : n); }
void world_init(World *w)
{
    int x, y, i;
    for (y = 0; y < MAP_H; ++y)
        for (x = 0; x < MAP_W; ++x) {
            /* River with two bridges; sparse rocks, all deterministic. */
            w->terrain[y][x] = (unsigned char)
                ((x >= 22 && x <= 24 && y != 10 && y != 40) ? 1 :
                 ((x * 7 + y * 11) % 37 == 0 ? 2 : 0));
            if (y == 10 || y == 40) w->terrain[y][x] = 3;
        }
    for (i = 0; i < UNIT_COUNT; ++i) {
        w->units[i].x = 5 + i * 2; w->units[i].y = 6;
        w->units[i].facing = 0;
        w->terrain[6][5 + i * 2] = 0;
    }
    w->selected = w->camera_x = w->camera_y = 0;
}
int world_move(World *w, int dx, int dy)
{
    int i, x, y;
    Unit *u = &w->units[w->selected];
    if (!((dx == 0 && (dy == -1 || dy == 1)) ||
          (dy == 0 && (dx == -1 || dx == 1)))) return 0;
    x = u->x + dx; y = u->y + dy;
    if (x < 0 || x >= MAP_W || y < 0 || y >= MAP_H) return 0;
    if (w->terrain[y][x] == 1 || w->terrain[y][x] == 2) return 0;
    for (i = 0; i < UNIT_COUNT; ++i)
        if (w->units[i].x == x && w->units[i].y == y) return 0;
    u->x = x; u->y = y;
    u->facing = (unsigned char)(dy < 0 ? 0 : (dx > 0 ? 2 : (dy > 0 ? 4 : 6)));
    return 1;
}
void world_scroll(World *w, int dx, int dy)
{
    w->camera_x = clamp(w->camera_x + dx, MAP_W - VIEW_W);
    w->camera_y = clamp(w->camera_y + dy, MAP_H - VIEW_H);
}
void world_center(World *w)
{
    w->camera_x = clamp(w->units[w->selected].x - VIEW_W / 2, MAP_W - VIEW_W);
    w->camera_y = clamp(w->units[w->selected].y - VIEW_H / 2, MAP_H - VIEW_H);
}
void world_select(World *w, int index)
{
    if (index >= 0 && index < UNIT_COUNT) w->selected = index;
}
unsigned int video_offset(unsigned int x, unsigned int y)
{
    /* Mode 09h: four 8 KiB banks, 160 bytes/scanline, even pixel high nibble. */
    return (y & 3U) * 8192U + (y >> 2) * 160U + (x >> 1);
}
