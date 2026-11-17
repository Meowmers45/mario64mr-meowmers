/* Your own characters (character packs, characters.py): Mario's model and voice clips swapped together, picked in
 * the options (Character) and kept for next time. Mario out in your room is the game's own Mario, so he changes
 * there too. */
#include <ultra64.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sm64.h"
#include "types.h"
#include "model_ids.h"
#include "game/area.h"
#include "game/memory.h"
#include "game/object_list_processor.h"
#include "engine/geo_layout.h"
#include "audio/internal.h"
#include "audio/heap.h"
#include "audio/load.h"
#include "pc/fs/fs.h"
#include "pc/cliopts.h"
#include "pc/unity_options.h"

#define MODEL_POOL 0x20000
#define MAX_BANKS 64

extern const int gUnityCharacterCount;
extern const char *const gUnityCharacterIds[];
extern const void *const gUnityCharacterGeos[];
extern const char *const gUnityCharacterVoices[];
extern ALSeqFile *gAlCtlHeader;
extern void unity_skip_interpolation(void);

/* The menu's choice: 0 the original Mario, then the packs in order */
unsigned int gUnityCharacter;
static int started, heard, kept;

/* ---- the model: each pack's geo layout made into a graph once, as the level script makes Mario's */
static struct GraphNode **models;

static struct GraphNode *character_model(int c) {
    if (!gUnityCharacterGeos[c]) return NULL;
    if (!models) models = calloc(gUnityCharacterCount, sizeof(*models));
    if (!models[c]) {
        u8 *memory = malloc(MODEL_POOL + 16);
        struct AllocOnlyPool *pool = malloc(sizeof(*pool));
        if (!memory || !pool) return NULL;
        pool->totalSpace = MODEL_POOL;
        pool->usedSpace = 0;
        pool->startPtr = pool->freePtr = (u8 *)(((uintptr_t) memory + 15) & ~(uintptr_t) 15);
        struct AllocOnlyPool *saved = gGraphNodePool;
        models[c] = process_geo_layout(pool, (void *) gUnityCharacterGeos[c]);
        gGraphNodePool = saved;
    }
    return models[c];
}

static int is_character_model(struct GraphNode *node) {
    for (int c = 1; models && c < gUnityCharacterCount; c++)
        if (models[c] && models[c] == node) return 1;
    return 0;
}

/* Each frame before Mario's step (unity_mr.c): his object drawn with the chosen character's model (a new Mario,
 * after a warp, starts with the original's) */
void unity_character_model(struct Object *o) {
    struct GraphNode *mario = gLoadedGraphNodes ? gLoadedGraphNodes[MODEL_MARIO] : NULL;
    if (!o || !mario || gUnityCharacterCount <= 1) return;
    struct GraphNode *want = gUnityCharacter ? character_model(gUnityCharacter) : NULL;
    if (!want) want = mario;
    struct GraphNode *now = o->header.gfx.sharedChild;
    if (now == want || (now != mario && !is_character_model(now))) return;
    o->header.gfx.sharedChild = want;
    unity_skip_interpolation();
}

/* ---- the voice: the pack's sound banks (sound_data.ctl and .tbl, in characters.zip), in place of the game's for
 * the banks they change. Banks loaded already are loaded again from them, as bank_load_immediate does; the rest
 * load from them when the game asks for them */
struct Voice { ALSeqFile *ctl, *tbl; struct AudioBank *banks[MAX_BANKS]; int tried; };
static struct Voice *voices;

static ALSeqFile *copy_header(const ALSeqFile *from) {
    size_t size = sizeof(ALSeqFile) + from->seqCount * sizeof(ALSeqData);
    ALSeqFile *copy = malloc(size);
    if (copy) memcpy(copy, from, size - sizeof(ALSeqData));
    return copy;
}

static ALSeqFile *read_header(u8 *data) {
    ALSeqFile *header = copy_header((ALSeqFile *) data);
    if (header) alSeqFileNew(header, data);
    return header;
}

static struct Voice *voice(int c) {
    if (!voices) {
        voices = calloc(gUnityCharacterCount, sizeof(*voices));
        if (!voices) return NULL;
        /* (the original's: the game's own, as it loaded them) */
        voices[0].ctl = copy_header(gAlCtlHeader);
        voices[0].tbl = copy_header(gAlTbl);
        voices[0].tried = 1;
    }
    struct Voice *v = &voices[c];
    if (!v->tried && gUnityCharacterVoices[c]) {
        char path[256];
        v->tried = 1;
        snprintf(path, sizeof(path), "%s/sound_data.ctl", gUnityCharacterVoices[c]);
        u8 *ctl = fs_load_file(path, NULL);
        snprintf(path, sizeof(path), "%s/sound_data.tbl", gUnityCharacterVoices[c]);
        u8 *tbl = fs_load_file(path, NULL);
        if (ctl && tbl) { v->ctl = read_header(ctl); v->tbl = read_header(tbl); }
        else fprintf(stderr, "characters: no sound banks in %s\n", gUnityCharacterVoices[c]);
    }
    return v->ctl && v->tbl ? v : &voices[0];
}

static int same(const ALSeqData *a, const ALSeqData *b) {
    return a->len == b->len && (a->offset == b->offset || !memcmp(a->offset, b->offset, a->len));
}

static void reload_bank(struct Voice *v, int bank) {
    ALSeqData *ctl = &v->ctl->seqArray[bank];
    u32 counts[4];
    if (ctl->len < 0x10) return;
    memcpy(counts, ctl->offset, sizeof(counts));
    if (!v->banks[bank]) {
        size_t alloc = ((ctl->len + 0xf) & ~0xf) - 0x10;
        struct AudioBank *mem = calloc(1, alloc + 0x10);
        if (!mem) return;
        memcpy(mem, ctl->offset + 0x10, ctl->len - 0x10);
        patch_audio_bank(mem, v->tbl->seqArray[bank].offset, counts[0], counts[1]);
        v->banks[bank] = mem;
    }
    gCtlEntries[bank].numInstruments = (u8) counts[0];
    gCtlEntries[bank].numDrums = (u8) counts[1];
    gCtlEntries[bank].instruments = v->banks[bank]->instruments;
    gCtlEntries[bank].drums = v->banks[bank]->drums;
}

static void hear(int c) {
    if (!gAlCtlHeader || !gAlTbl || !gCtlEntries) return;
    struct Voice *v = voice(c);
    if (!v || v->ctl->seqCount != gAlCtlHeader->seqCount || v->tbl->seqCount != gAlTbl->seqCount) return;
    for (int bank = 0; bank < gAlCtlHeader->seqCount && bank < gAlTbl->seqCount; bank++) {
        ALSeqData *ctl = &gAlCtlHeader->seqArray[bank], *tbl = &gAlTbl->seqArray[bank];
        int changed = !same(ctl, &v->ctl->seqArray[bank]) || !same(tbl, &v->tbl->seqArray[bank]);
        *ctl = v->ctl->seqArray[bank];
        *tbl = v->tbl->seqArray[bank];
        if (changed && bank < MAX_BANKS && gBankLoadStatus[bank] >= SOUND_LOAD_STATUS_COMPLETE) reload_bank(v, bank);
    }
}

/* ---- kept for next time: the pack's name, in the save folder */
static void kept_path(char *path, size_t size) { snprintf(path, size, "%s/mr_character.txt", gCLIOpts.SavePath); }

static int read_kept(void) {
    char path[SYS_MAX_PATH + 32], id[128] = "";
    kept_path(path, sizeof(path));
    FILE *f = fopen(path, "r");
    if (!f) return 0;
    if (!fgets(id, sizeof(id), f)) id[0] = 0;
    fclose(f);
    id[strcspn(id, "\r\n")] = 0;
    for (int c = 1; c < gUnityCharacterCount; c++)
        if (!strcmp(id, gUnityCharacterIds[c])) return c;
    return 0;
}

static void write_kept(int c) {
    char path[SYS_MAX_PATH + 32];
    kept_path(path, sizeof(path));
    FILE *f = fopen(path, "w");
    if (!f) return;
    fprintf(f, "%s\n", gUnityCharacterIds[c]);
    fclose(f);
}

/* Each tick, before the game's (unity_apply_options) */
void unity_characters_update(void) {
    if (gUnityCharacterCount <= 1) return;
    if (!started) {
        started = 1;
        gUnityCharacter = kept = read_kept();
    }
    if (gUnityCharacter >= (unsigned) gUnityCharacterCount) gUnityCharacter = 0;
    if ((int) gUnityCharacter != heard) {
        hear(gUnityCharacter);
        heard = gUnityCharacter;
    }
    if ((int) gUnityCharacter != kept) {
        write_kept(gUnityCharacter);
        kept = gUnityCharacter;
    }
}
