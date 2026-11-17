// Halo Mario: an example character pack (Mario 64 MR).
// The pack's mario_geo is the one the game draws him with. This one keeps Mario's own body (the game's
// mario_geo_load_body and mario_geo_render_body: a pack can use any of the game's parts it doesn't replace) and
// adds the halo from model.inc.c, floating above his head.
const GeoLayout mario_geo[] = {
   GEO_SHADOW(SHADOW_CIRCLE_PLAYER, 0xB4, 100),
   GEO_OPEN_NODE(),
      GEO_TRANSLATE_NODE_WITH_DL(LAYER_ALPHA, 0, 195, 0, example_halo_dl),
      GEO_SCALE(0x00, 16384),
      GEO_OPEN_NODE(),
         GEO_ASM(0, geo_mirror_mario_backface_culling),
         GEO_ASM(0, geo_mirror_mario_set_alpha),
         GEO_SWITCH_CASE(0, geo_switch_mario_stand_run),
         GEO_OPEN_NODE(),
            GEO_BRANCH(1, mario_geo_load_body),
            GEO_BRANCH(1, mario_geo_render_body),
         GEO_CLOSE_NODE(),
         GEO_ASM(1, geo_mirror_mario_backface_culling),
      GEO_CLOSE_NODE(),
   GEO_CLOSE_NODE(),
   GEO_END(),
};
