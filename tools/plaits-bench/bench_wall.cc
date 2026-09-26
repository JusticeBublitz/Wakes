// Per-engine CPU cost benchmark for Plaits, driven through Voice::Render.
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <cmath>
#include <ctime>
#include <algorithm>
#include <vector>
#include <string>

#include "plaits/dsp/dsp.h"
#include "plaits/dsp/voice.h"
#include "stmlib/utils/buffer_allocator.h"

using namespace plaits;
using namespace stmlib;

static char ram_block[16 * 1024];

static const char* kNames[24] = {
  "VA VCF (virtual analog + VCF)",
  "Phase distortion",
  "6-op FM: bank A",
  "6-op FM: bank B",
  "6-op FM: bank C",
  "Wave terrain",
  "String machine",
  "Chiptune",
  "Virtual analog (classic)",
  "Waveshaping",
  "2-op FM (classic)",
  "Grain / formant",
  "Additive harmonics",
  "Wavetable",
  "Chord",
  "Speech / vowel",
  "Swarm",
  "Noise (filtered/clocked)",
  "Particle",
  "String (inharmonic)",
  "Modal resonator",
  "Bass drum",
  "Snare drum",
  "Hi-hat",
};

static inline double now_s() {
  struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
  return ts.tv_sec + ts.tv_nsec * 1e-9;
}

struct Result { int idx; double ns_per_sample; };

int main(int argc, char** argv) {
  const int kReps = argc > 1 ? atoi(argv[1]) : 6;
  // Number of 12-sample blocks per measurement = 4 seconds of audio.
  const int kBlocks = 48000 * 4 / kBlockSize;

  static Voice voice;
  BufferAllocator allocator(ram_block, sizeof(ram_block));
  voice.Init(&allocator);

  Voice::Frame out[kMaxBlockSize];
  std::vector<Result> results;

  for (int e = 0; e < 24; ++e) {
    double best = 1e30;
    for (int rep = 0; rep < kReps; ++rep) {
      Patch patch; Modulations mod;
      memset(&patch, 0, sizeof(patch));
      memset(&mod, 0, sizeof(mod));
      // Representative "worked hard" settings: mid-scale params, audible pitch,
      // sustained (long decay), no CV patched -> internal envelope + LPG active.
      patch.note = 48.0f;
      patch.harmonics = 0.5f;
      patch.timbre = 0.5f;
      patch.morph = 0.5f;
      patch.frequency_modulation_amount = 0.0f;
      patch.timbre_modulation_amount = 0.0f;
      patch.morph_modulation_amount = 0.0f;
      patch.engine = e;
      patch.decay = 0.8f;
      patch.lpg_colour = 0.5f;
      mod.engine = 0.0f; mod.note = 0.0f; mod.frequency = 0.0f;
      mod.harmonics = 0.0f; mod.timbre = 0.0f; mod.morph = 0.0f;
      mod.trigger = 0.0f; mod.level = 0.0f;
      mod.frequency_patched = false; mod.timbre_patched = false;
      mod.morph_patched = false; mod.trigger_patched = true; mod.level_patched = false;

      // Warm-up + force engine switch to settle (engine change is smoothed).
      for (int i = 0; i < 200; ++i) {
        mod.trigger = (i % 64 == 0) ? 1.0f : 0.0f;
        voice.Render(patch, mod, out, kBlockSize);
      }
      if (voice.active_engine() != e) {
        fprintf(stderr, "warn: engine %d did not activate (got %d)\n", e, voice.active_engine());
      }

      double t0 = now_s();
      for (int i = 0; i < kBlocks; ++i) {
        // Retrigger every ~0.25 s so envelopes/transients stay alive.
        mod.trigger = (i % 1000 == 0) ? 1.0f : 0.0f;
        voice.Render(patch, mod, out, kBlockSize);
      }
      double t1 = now_s();
      double ns = (t1 - t0) * 1e9 / (double)(kBlocks * kBlockSize);
      if (ns < best) best = ns;
    }
    results.push_back({e, best});
    fprintf(stderr, "engine %2d  %-32s  %8.2f ns/sample\n", e, kNames[e], best);
  }

  // Normalise against the cheapest engine.
  double lo = 1e30;
  for (auto& r : results) lo = std::min(lo, r.ns_per_sample);

  printf("idx,name,ns_per_sample,relative_to_cheapest\n");
  for (auto& r : results) {
    printf("%d,\"%s\",%.3f,%.2f\n", r.idx, kNames[r.idx], r.ns_per_sample,
           r.ns_per_sample / lo);
  }
  return 0;
}
