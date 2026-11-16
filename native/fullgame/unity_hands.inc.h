/* Your hands reaching into the game, touching its objects. Included after unity_room.inc.h (in surface_load.c), whose
 * hand triangles (sm64unity_game_hands, game coordinates) it reads: nothing new for the host to send. There is no
 * grip, only touch.
 *
 * - Touch to collect: a coin, star, key, cap or 1-up your hand touches is collected as if Mario had touched it (it is
 *   put on his list of things he collided with this frame, which the game's own interactions then handle).
 *
 * UNITY_HANDS_TOUCH turns touch-to-collect off. */
#include "game/interaction.h"
#include "engine/math_util.h"

#define UNITY_HANDS_TOUCH 1

extern int unity_mario_carried(void);

static void unity_hand_vertex(const s16 *triangles, int triangle, int corner, float out[3]) {
    const s16 *v = triangles + triangle * 9 + corner * 3;
    out[0] = v[0]; out[1] = v[1]; out[2] = v[2];
}

/* The closest point on a triangle to p (Ericson, Real-Time Collision Detection 5.1.5) */
static void unity_closest_on_triangle(const float p[3], const float a[3], const float b[3], const float c[3], float out[3]) {
    float ab[3], ac[3], ap[3], bp[3], cp[3];
    for (int i = 0; i < 3; i++) { ab[i] = b[i] - a[i]; ac[i] = c[i] - a[i]; ap[i] = p[i] - a[i]; }
#define UDOT(x, y) ((x)[0] * (y)[0] + (x)[1] * (y)[1] + (x)[2] * (y)[2])
    float d1 = UDOT(ab, ap), d2 = UDOT(ac, ap);
    if (d1 <= 0 && d2 <= 0) { vec3f_copy(out, (float *) a); return; }
    for (int i = 0; i < 3; i++) bp[i] = p[i] - b[i];
    float d3 = UDOT(ab, bp), d4 = UDOT(ac, bp);
    if (d3 >= 0 && d4 <= d3) { vec3f_copy(out, (float *) b); return; }
    float vc = d1 * d4 - d3 * d2;
    if (vc <= 0 && d1 >= 0 && d3 <= 0) {
        float t = d1 / (d1 - d3);
        for (int i = 0; i < 3; i++) out[i] = a[i] + t * ab[i];
        return;
    }
    for (int i = 0; i < 3; i++) cp[i] = p[i] - c[i];
    float d5 = UDOT(ab, cp), d6 = UDOT(ac, cp);
    if (d6 >= 0 && d5 <= d6) { vec3f_copy(out, (float *) c); return; }
    float vb = d5 * d2 - d1 * d6;
    if (vb <= 0 && d2 >= 0 && d6 <= 0) {
        float t = d2 / (d2 - d6);
        for (int i = 0; i < 3; i++) out[i] = a[i] + t * ac[i];
        return;
    }
    float va = d3 * d6 - d5 * d4;
    if (va <= 0 && (d4 - d3) >= 0 && (d5 - d6) >= 0) {
        float t = (d4 - d3) / ((d4 - d3) + (d5 - d6));
        for (int i = 0; i < 3; i++) out[i] = b[i] + t * (c[i] - b[i]);
        return;
    }
    float denom = 1.f / (va + vb + vc);
    float v = vb * denom, w = vc * denom;
    for (int i = 0; i < 3; i++) out[i] = a[i] + ab[i] * v + ac[i] * w;
#undef UDOT
}

static int unity_object_usable(struct Object *o) {
    /* (far from Mario is fine: it's out of sight unless a diorama draws it, and moves all the same) */
    return o != gMarioObject && (o->activeFlags & ACTIVE_FLAG_ACTIVE)
        && (o->header.gfx.node.flags & GRAPH_RENDER_ACTIVE) && !(o->header.gfx.node.flags & GRAPH_RENDER_INVISIBLE);
}

/* The hands' bounds this frame, to pass over objects nowhere near them */
static float unity_hand_min[3], unity_hand_max[3];
static int unity_hand_bounds(void) {
    if (unity_game_hand_count <= 0) return 0;
    for (int i = 0; i < 3; i++) { unity_hand_min[i] = 1e9f; unity_hand_max[i] = -1e9f; }
    for (int i = 0; i < unity_game_hand_count * 3; i++) {
        const s16 *v = unity_game_hand_triangles + i * 3;
        for (int j = 0; j < 3; j++) {
            if (v[j] < unity_hand_min[j]) unity_hand_min[j] = v[j];
            if (v[j] > unity_hand_max[j]) unity_hand_max[j] = v[j];
        }
    }
    return 1;
}
static int unity_near_hands(struct Object *o, float margin) {
    float bottom = o->oPosY - o->hitboxDownOffset, top = bottom + o->hitboxHeight;
    return o->oPosX + margin >= unity_hand_min[0] && o->oPosX - margin <= unity_hand_max[0]
        && o->oPosZ + margin >= unity_hand_min[2] && o->oPosZ - margin <= unity_hand_max[2]
        && top + margin >= unity_hand_min[1] && bottom - margin <= unity_hand_max[1];
}

/* ---- Touch to collect ---- */

static int unity_is_1up(struct Object *o) {
    const BehaviorScript *b = o->behavior;
    return b == segmented_to_virtual(bhv1Up) || b == segmented_to_virtual(bhv1upWalking)
        || b == segmented_to_virtual(bhv1upRunningAway) || b == segmented_to_virtual(bhv1upSliding)
        || b == segmented_to_virtual(bhv1upJumpOnApproach) || b == segmented_to_virtual(bhvHidden1up)
        || b == segmented_to_virtual(bhvHidden1upInPole);
}
static int unity_collectable(struct Object *o) {
    if (o->oIntangibleTimer != 0 || (o->oInteractStatus & INT_STATUS_INTERACTED)) return 0;
    if (o->oInteractType & (INTERACT_COIN | INTERACT_STAR_OR_KEY | INTERACT_CAP)) return 1;
    return unity_is_1up(o);
}

static int unity_hand_touches(struct Object *o) {
    float radius = o->hitboxRadius > 40.f ? o->hitboxRadius : 40.f;
    float height = o->hitboxHeight > 40.f ? o->hitboxHeight : 40.f;
    float bottom = o->oPosY - o->hitboxDownOffset, top = bottom + height;
    float centre[3] = { o->oPosX, (bottom + top) * 0.5f, o->oPosZ };
    for (int i = 0; i < unity_game_hand_count; i++) {
        float a[3], b[3], c[3], p[3];
        unity_hand_vertex(unity_game_hand_triangles, i, 0, a);
        unity_hand_vertex(unity_game_hand_triangles, i, 1, b);
        unity_hand_vertex(unity_game_hand_triangles, i, 2, c);
        unity_closest_on_triangle(centre, a, b, c, p);
        float dx = p[0] - centre[0], dz = p[2] - centre[2];
        if (dx * dx + dz * dz <= radius * radius && p[1] >= bottom - 10.f && p[1] <= top + 10.f) return 1;
    }
    return 0;
}

/* After detect_object_collisions: what your hand touches, Mario touches, so his interactions (or a 1-up's own
 * check for him) collect it this frame */
void unity_hands_touch(void) {
    if (!UNITY_HANDS_TOUCH || !gMarioObject || unity_mario_carried() || unity_room_depth) return;
    if ((gTimeStopState & TIME_STOP_ACTIVE) || !unity_hand_bounds()) return;
    static const int lists[] = { OBJ_LIST_LEVEL, OBJ_LIST_GENACTOR, OBJ_LIST_DEFAULT };
    for (int l = 0; l < (int) (sizeof(lists) / sizeof(lists[0])); l++) {
        struct ObjectNode *head = &gObjectLists[lists[l]];
        for (struct ObjectNode *node = head->next; node != head; node = node->next) {
            struct Object *o = (struct Object *) node;
            if (gMarioObject->numCollidedObjs >= 4) return;
            if (!unity_object_usable(o) || !unity_collectable(o) || !unity_near_hands(o, 80.f)) continue;
            if (obj_check_if_collided_with_object(o, gMarioObject) || o->numCollidedObjs >= 4) continue;
            if (!unity_hand_touches(o)) continue;
            gMarioObject->collidedObjs[gMarioObject->numCollidedObjs++] = o;
            o->collidedObjs[o->numCollidedObjs++] = gMarioObject;
            gMarioObject->collidedObjInteractTypes |= o->oInteractType;
            o->collidedObjInteractTypes |= gMarioObject->oInteractType;
        }
    }
}
