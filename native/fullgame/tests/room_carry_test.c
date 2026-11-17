/* Headless test of Mario out in the room (unity_mr.c): no floor under him there, or a warp, puts him back in the
 * game instead of the game killing him for being out of bounds. Run by run_headless_test.sh. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <ultra64.h>
#include "sm64.h"
#include "types.h"
#include "object_fields.h"
#include "model_ids.h"
#include "behavior_data.h"
#include "game/object_list_processor.h"
#include "game/spawn_object.h"
#include "game/level_update.h"
#include "game/area.h"
#include "game/object_helpers.h"
#include "game/mario.h"
#include "pc/cliopts.h"

int sm64unity_init(const char *);
int sm64unity_tick(uint16_t, int8_t, int8_t);
int sm64unity_stage(void);
void sm64unity_cursor(int, float, float);
void sm64unity_mr_geometry(int);
int sm64unity_room_mesh(const s16 *, int);
float sm64unity_room_floor(float, float, float);
int sm64unity_render_current(void);
int sm64unity_game_hands(const s16 *, int);
int sm64unity_carry(int, float, float, float, float, float, float);
int sm64unity_carry_mode(void);

static int failures;
#define CHECK(c, ...) do { if (c) printf("  ok   " __VA_ARGS__); else { printf("  FAIL " __VA_ARGS__); failures++; } printf("\n"); } while (0)

static void tick(uint16_t b) { sm64unity_tick(b, 0, 0); sm64unity_render_current(); }
static void ticks(int n) { for (int i = 0; i < n; i++) tick(0); }

/* A flat rectangle (two floor triangles, wound up) at height y */
static int quad(s16 *t, float x0, float z0, float x1, float z1, float y) {
    s16 v[] = { x0, y, z0, x0, y, z1, x1, y, z1, x0, y, z0, x1, y, z1, x1, y, z0 };
    memcpy(t, v, sizeof(v));
    return 2;
}

/* Through the title screen and the file select into Castle Grounds */
static int into_castle_grounds(int argc, char **argv) {
    gCLIOpts.SkipIntro = 1;
    if (!sm64unity_init(argc > 1 ? argv[1] : ".")) { printf("init failed\n"); return 0; }
    sm64unity_mr_geometry(1);
    for (int i = 0; i < 2000 && sm64unity_stage() != 2; i++) tick(i % 20 < 2 ? START_BUTTON : 0);
    for (int i = 0; i < 2000 && (sm64unity_stage() != 3 || !gMarioObject || gCurrLevelNum != LEVEL_CASTLE_GROUNDS); i++) {
        sm64unity_cursor(1, 62, 77);
        tick(i % 20 < 2 ? A_BUTTON : 0);
    }
    sm64unity_cursor(0, 0, 0);
    if (!gMarioObject || gCurrLevelNum != LEVEL_CASTLE_GROUNDS) { printf("never got into Castle Grounds\n"); return 0; }
    ticks(200);
    printf("Castle Grounds, Mario at %.0f %.0f %.0f\n", gMarioObject->oPosX, gMarioObject->oPosY, gMarioObject->oPosZ);
    return 1;
}

/* The room: a floor 2 m square (600 units a metre) round the origin */
static s16 room[4 * 9];
static void load_room(void) {
    int n = quad(room, -600, -600, 600, 600, 0);
    printf("room: %d surfaces\n", sm64unity_room_mesh(room, n));
}

/* Ticks until he's back in the game, or n run out. Whether he died on the way (lost health to nothing, or a death
 * warp's action) */
static int dies_within(int n) {
    for (int i = 0; i < n; i++) {
        tick(0);
        u32 a = gMarioState->action;
        if (gMarioState->health < 0x100 || a == ACT_DEATH_EXIT || a == ACT_UNUSED_DEATH_EXIT || a == ACT_FALLING_DEATH_EXIT
            || gMarioState->hurtCounter) return 1;
    }
    return 0;
}

int main(int argc, char **argv) {
    if (!into_castle_grounds(argc, argv)) return 1;
    load_room();
    float from[3] = { gMarioState->pos[0], gMarioState->pos[1], gMarioState->pos[2] };

    printf("Put down where the room has no floor:\n");
    CHECK(sm64unity_carry(1, from[0], from[1] + 200, from[2], 0, 0, 0) == 1, "picked up");
    CHECK(sm64unity_carry(3, 5000, 100, 5000, 0, 0, 0) == 0, "not let go out there");
    CHECK(sm64unity_carry(0, from[0], from[1] + 100, from[2], 0, 0, 0) == 1, "put back in the game");
    ticks(60);

    printf("Put down on the room's floor:\n");
    from[0] = gMarioState->pos[0]; from[1] = gMarioState->pos[1]; from[2] = gMarioState->pos[2];
    CHECK(sm64unity_carry(1, from[0], from[1] + 200, from[2], 0, 0, 0) == 1, "picked up");
    CHECK(sm64unity_carry(3, 0, 100, 0, 0, 0, 0) == 1, "let go over the floor");
    ticks(30);
    CHECK(sm64unity_carry_mode() == 3 && fabsf(gMarioState->pos[1]) < 5, "standing on it (%.0f %.0f %.0f)",
          gMarioState->pos[0], gMarioState->pos[1], gMarioState->pos[2]);

    printf("Walked off the edge of the scanned room:\n");
    s16 health = gMarioState->health;
    int i;
    for (i = 0; i < 300 && sm64unity_carry_mode() == 3; i++) { gMarioState->pos[0] += 10; tick(0); } /* (shoved along) */
    CHECK(sm64unity_carry_mode() == 0, "back in the game (after %d frames)", i);
    CHECK(fabsf(gMarioState->pos[0] - from[0]) < 1 && fabsf(gMarioState->pos[2] - from[2]) < 1,
          "where he was picked up (%.0f %.0f %.0f, from %.0f %.0f %.0f)", gMarioState->pos[0], gMarioState->pos[1],
          gMarioState->pos[2], from[0], from[1], from[2]);
    CHECK(!dies_within(120) && gMarioState->health >= health, "and not killed for it");

    printf("Room forgotten under him:\n");
    from[0] = gMarioState->pos[0]; from[1] = gMarioState->pos[1]; from[2] = gMarioState->pos[2];
    sm64unity_carry(1, from[0], from[1] + 200, from[2], 0, 0, 0);
    sm64unity_carry(3, 0, 100, 0, 0, 0, 0);
    ticks(30);
    CHECK(sm64unity_carry_mode() == 3, "out in the room");
    sm64unity_room_mesh(NULL, 0);
    ticks(2);
    CHECK(sm64unity_carry_mode() == 0, "back in the game");
    CHECK(!dies_within(120), "and not killed for it");
    load_room();

    printf("A warp while out in the room:\n");
    sm64unity_carry(1, gMarioState->pos[0], gMarioState->pos[1] + 200, gMarioState->pos[2], 0, 0, 0);
    sm64unity_carry(3, 0, 100, 0, 0, 0, 0);
    ticks(30);
    CHECK(sm64unity_carry_mode() == 3, "out in the room");
    s16 level = gCurrLevelNum, area = gCurrAreaIndex;
    /* (the door warp into the castle from Castle Grounds is to another level: a same-area warp is what the level
     * check missed, so warp to this area's own entry node) */
    extern void initiate_warp(s16 destLevel, s16 destArea, s16 destWarpNode, s32 arg3);
    initiate_warp(level, area, 0x0A, 0);
    int warped = 0;
    for (i = 0; i < 200; i++) { tick(0); if (sm64unity_carry_mode() == 0) { warped = 1; break; } }
    CHECK(warped && gCurrLevelNum == level && gCurrAreaIndex == area, "the same area's warp brings him back into the game (%d frames)", i);
    ticks(120);
    CHECK(sm64unity_carry_mode() == 0 && gMarioState->health > 0x100, "and he's playing there");

    printf("%s (%d failures)\n", failures ? "FAILED" : "PASSED", failures);
    return failures != 0;
}
