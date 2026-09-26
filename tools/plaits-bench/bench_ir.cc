// Instruction-count benchmark: argv[1]=engine index, argv[2]=blocks to render.
// Run twice with different block counts and subtract to cancel init/warm-up.
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include "plaits/dsp/dsp.h"
#include "plaits/dsp/voice.h"
#include "stmlib/utils/buffer_allocator.h"
using namespace plaits; using namespace stmlib;
static char ram_block[16 * 1024];
int main(int argc, char** argv) {
  const int e = atoi(argv[1]);
  const int blocks = atoi(argv[2]);
  static Voice voice;
  BufferAllocator allocator(ram_block, sizeof(ram_block));
  voice.Init(&allocator);
  Voice::Frame out[kMaxBlockSize];
  Patch patch; Modulations mod;
  memset(&patch, 0, sizeof(patch)); memset(&mod, 0, sizeof(mod));
  const float note  = argc > 3 ? atof(argv[3]) : 48.0f;
  const float harm  = argc > 4 ? atof(argv[4]) : 0.5f;
  const float timb  = argc > 5 ? atof(argv[5]) : 0.5f;
  const float morp  = argc > 6 ? atof(argv[6]) : 0.5f;
  patch.note = note; patch.harmonics = harm; patch.timbre = timb;
  patch.morph = morp; patch.engine = e; patch.decay = 0.8f; patch.lpg_colour = 0.5f;
  mod.trigger_patched = true;
  // Fixed warm-up, identical for every run -> cancels on subtraction.
  for (int i = 0; i < 300; ++i) {
    mod.trigger = (i % 64 == 0) ? 1.0f : 0.0f;
    voice.Render(patch, mod, out, kBlockSize);
  }
  if (voice.active_engine() != e) fprintf(stderr, "warn e=%d got %d\n", e, voice.active_engine());
  for (int i = 0; i < blocks; ++i) {
    mod.trigger = (i % 1000 == 0) ? 1.0f : 0.0f;
    voice.Render(patch, mod, out, kBlockSize);
  }
  volatile float sink = out[0].out; (void)sink;
  return 0;
}
