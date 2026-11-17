// Halo Mario: an example character pack (Mario 64 MR). Everything here is made for this example.
// A golden halo with a texture of its own (example_halo.rgba16.png, next to this file), drawn over Mario's own
// body (see geo.inc.c). A pack with a whole new model has its own display lists for every part of Mario instead.

ALIGNED8 static const u8 example_halo_texture[] = {
#include "actors/mario/example_halo.rgba16.inc.c"
};

// a flat ring, 8 sides, in game units (it hangs above Mario's head, outside his model's scale)
static const Vtx example_halo_vertices[16] = {
    {{{   40, 0,    0 }, 0, {    0,    0 }, { 0xFF, 0xFF, 0xFF, 0xFF }}},
    {{{   28, 0,   28 }, 0, {  128,    0 }, { 0xFF, 0xFF, 0xFF, 0xFF }}},
    {{{    0, 0,   40 }, 0, {  256,    0 }, { 0xFF, 0xFF, 0xFF, 0xFF }}},
    {{{  -28, 0,   28 }, 0, {  384,    0 }, { 0xFF, 0xFF, 0xFF, 0xFF }}},
    {{{  -40, 0,    0 }, 0, {  512,    0 }, { 0xFF, 0xFF, 0xFF, 0xFF }}},
    {{{  -28, 0,  -28 }, 0, {  640,    0 }, { 0xFF, 0xFF, 0xFF, 0xFF }}},
    {{{    0, 0,  -40 }, 0, {  768,    0 }, { 0xFF, 0xFF, 0xFF, 0xFF }}},
    {{{   28, 0,  -28 }, 0, {  896,    0 }, { 0xFF, 0xFF, 0xFF, 0xFF }}},
    {{{   28, 0,    0 }, 0, {    0,  992 }, { 0xFF, 0xFF, 0xFF, 0xFF }}},
    {{{   20, 0,   20 }, 0, {  128,  992 }, { 0xFF, 0xFF, 0xFF, 0xFF }}},
    {{{    0, 0,   28 }, 0, {  256,  992 }, { 0xFF, 0xFF, 0xFF, 0xFF }}},
    {{{  -20, 0,   20 }, 0, {  384,  992 }, { 0xFF, 0xFF, 0xFF, 0xFF }}},
    {{{  -28, 0,    0 }, 0, {  512,  992 }, { 0xFF, 0xFF, 0xFF, 0xFF }}},
    {{{  -20, 0,  -20 }, 0, {  640,  992 }, { 0xFF, 0xFF, 0xFF, 0xFF }}},
    {{{    0, 0,  -28 }, 0, {  768,  992 }, { 0xFF, 0xFF, 0xFF, 0xFF }}},
    {{{   20, 0,  -20 }, 0, {  896,  992 }, { 0xFF, 0xFF, 0xFF, 0xFF }}},
};

const Gfx example_halo_dl[] = {
    gsDPPipeSync(),
    gsSPClearGeometryMode(G_LIGHTING | G_CULL_BACK),
    gsDPSetCombineMode(G_CC_MODULATERGBA, G_CC_MODULATERGBA),
    gsSPTexture(0xFFFF, 0xFFFF, 0, G_TX_RENDERTILE, G_ON),
    gsDPLoadTextureBlock(example_halo_texture, G_IM_FMT_RGBA, G_IM_SIZ_16b, 32, 32, 0,
                         G_TX_WRAP | G_TX_NOMIRROR, G_TX_WRAP | G_TX_NOMIRROR, 5, 5, G_TX_NOLOD, G_TX_NOLOD),
    gsSPVertex(example_halo_vertices, 16, 0),
    gsSP2Triangles( 0,  1,  9, 0x0,  0,  9,  8, 0x0),
    gsSP2Triangles( 1,  2, 10, 0x0,  1, 10,  9, 0x0),
    gsSP2Triangles( 2,  3, 11, 0x0,  2, 11, 10, 0x0),
    gsSP2Triangles( 3,  4, 12, 0x0,  3, 12, 11, 0x0),
    gsSP2Triangles( 4,  5, 13, 0x0,  4, 13, 12, 0x0),
    gsSP2Triangles( 5,  6, 14, 0x0,  5, 14, 13, 0x0),
    gsSP2Triangles( 6,  7, 15, 0x0,  6, 15, 14, 0x0),
    gsSP2Triangles( 7,  0,  8, 0x0,  7,  8, 15, 0x0),
    gsSPTexture(0xFFFF, 0xFFFF, 0, G_TX_RENDERTILE, G_OFF),
    gsDPPipeSync(),
    gsSPSetGeometryMode(G_LIGHTING | G_CULL_BACK),
    gsDPSetCombineMode(G_CC_SHADE, G_CC_SHADE),
    gsSPEndDisplayList(),
};
