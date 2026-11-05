/* DOS16 prototype; repository LICENSE.md applies. */
#ifndef RA16_SIM_H
#define RA16_SIM_H
#define MAP_W 64
#define MAP_H 64
#define VIEW_W 15
#define VIEW_H 12
#define UNIT_COUNT 3
/* Facing order follows the original compass convention: N, NE, E, ... NW. */
typedef struct { int x, y; unsigned char facing; } Unit;
typedef struct {
    unsigned char terrain[MAP_H][MAP_W];
    Unit units[UNIT_COUNT];
    int selected, camera_x, camera_y;
} World;
void world_init(World *w);
int world_move(World *w, int dx, int dy);
void world_scroll(World *w, int dx, int dy);
void world_center(World *w);
void world_select(World *w, int index);
unsigned int video_offset(unsigned int x, unsigned int y);
#endif
