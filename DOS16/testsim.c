/* Runs unchanged as a native host test and inside the 16-bit DOS executable. */
#include <assert.h>
#include <string.h>
#include "sim.h"
int test_sim(void)
{
    static World w;
    static unsigned char seen[32768];
    unsigned int x, y, off;
    int i;
    world_init(&w);
    assert(w.selected == 0 && w.units[0].x == 5);
    memset(w.terrain, 0, sizeof(w.terrain));
    assert(world_move(&w, 1, 0));
    assert(!world_move(&w, 1, 0)); /* unit at 7,6 */
    w.terrain[7][6] = 1;
    assert(!world_move(&w, 0, 1));
    w.terrain[7][6] = 2;
    assert(!world_move(&w, 0, 1));
    w.terrain[7][6] = 3;
    assert(world_move(&w, 0, 1));
    assert(!world_move(&w, 1, 1));
    w.units[0].x = w.units[0].y = 0;
    assert(!world_move(&w, -1, 0) && !world_move(&w, 0, -1));
    w.units[0].x = w.units[0].y = 63;
    assert(!world_move(&w, 1, 0) && !world_move(&w, 0, 1));
    world_center(&w);
    assert(w.camera_x == 49 && w.camera_y == 52);
    for (i = 0; i < 100; ++i) world_scroll(&w, -1, -1);
    assert(w.camera_x == 0 && w.camera_y == 0);
    for (i = 0; i < 100; ++i) world_scroll(&w, 1, 1);
    assert(w.camera_x == 49 && w.camera_y == 52);
    world_select(&w, 2); world_select(&w, 3);
    assert(w.selected == 2);
    /* All 32000 visible bytes must map uniquely within the 32 KiB aperture. */
    memset(seen, 0, sizeof(seen));
    for (y = 0; y < 200; ++y) for (x = 0; x < 320; x += 2) {
        off = video_offset(x, y);
        assert(off < 32768U && !seen[off]);
        seen[off] = 1;
        assert(video_offset(x + 1, y) == off);
    }
    assert(video_offset(318, 199) == 32575U);
    return 0;
}
#ifdef HOST_TEST
int main(void) { return test_sim(); }
#endif
