# plaits-bench

Measures the CPU cost of each Plaits engine, so the decision about which models
fit on the SP-1 rests on numbers rather than intuition. Re-run it after any trim
to a voice count, harmonic count or oversampling ratio.

## What it measures

`bench_ir.cc` drives a real `plaits::Voice` at `kBlockSize = 12` and is measured
under Callgrind for **retired instructions per output sample**. Because the shared
cost — LPG, internal envelope, output mixing — runs for every engine, these are
total per-engine costs, not marginal ones.

`bench_wall.cc` does the same with a wall clock. **It is kept for reference only
and should not be used for decisions.** On an out-of-order x86 core it spreads the
engines over a 43× range, because it is measuring stalls on the serially dependent
filter chains in the physical models. The Cortex-M4 is in-order at roughly 1 IPC
with mostly single-cycle single-precision VFP ops, so instruction count is the far
better proxy.

## Budget

`64 MHz ÷ 48 kHz = 1333 cycles per sample`, for everything. Reserve 10–20 % for
I²S, the ADC, LEDs and the sequencer, leaving roughly **1050–1200 cycles** for the
synth. Convert with `cycles ≈ instructions × k`, `k` between 1.0 and 1.5.

The bound on `k`: Plaits demonstrably runs all 24 engines on an STM32F373 at
72 MHz, which is 1500 cycles per sample, and the heaviest engine measures 995
instructions. If `k` were much above 1.5, Plaits itself would not work.

## ⚠️ Use `ir_fwflags.csv` for projections (M3f)

`ir.csv` was built with the flags below, which lack the firmware's `-funroll-loops
-finline-functions-called-once -fno-move-loop-invariants`. With the firmware's flags every
engine is cheaper, some a lot (Additive 995 → 677, FM 552 → 501). `ir_fwflags.csv` has
all 24 engines with the firmware's flags: upstream, and with the M3f trims (String 2, Particle
3 + diffuser skip, Modal 8, the Additive rewrite), at MORPH 0.5 and 0.2 (Particle's diffuser
only runs below MORPH centre). Add those three flags to the command below to reproduce it; the
trims need the override files from a firmware build (`build/plaits_overrides/`,
`firmware/src/plaits_ovr/`) ahead of the eurorack root on the include path.

## Running it

Needs the Plaits sources and `stmlib` (a submodule of the `eurorack` repo that
must be cloned separately):

```sh
git clone --depth 1 --filter=blob:none --sparse https://github.com/pichenettes/eurorack.git
cd eurorack
git sparse-checkout set --skip-checks plaits marbles stmlib
rmdir stmlib && git clone --depth 1 https://github.com/pichenettes/stmlib.git stmlib
```

Build from the `eurorack` root. Vectorisation is disabled deliberately: x86 SIMD
would make the batched code (the resonator SVF batches, the harmonic oscillator
batches) look artificially cheap, and that is exactly where the heavy engines live.

```sh
g++ -std=c++11 -DTEST -O2 -fno-tree-vectorize -fno-tree-slp-vectorize \
    -mfpmath=sse -msse2 -ffp-contract=off -Wno-unused-variable \
    -include cstdio -include cstdlib -I. -o bench_ir bench_ir.cc \
    plaits/dsp/voice.cc plaits/dsp/engine/*.cc plaits/dsp/engine2/*.cc \
    plaits/dsp/chords/*.cc plaits/dsp/fm/*.cc plaits/dsp/physical_modelling/*.cc \
    plaits/dsp/speech/*.cc plaits/resources.cc \
    stmlib/dsp/atan.cc stmlib/dsp/units.cc stmlib/utils/random.cc -lm
```

Then, per engine, subtract two runs of different length so init and warm-up cancel:

```sh
for e in $(seq 0 23); do
  a=$(valgrind --tool=callgrind --callgrind-out-file=/dev/null ./bench_ir $e 200 2>&1 \
      | grep refs: | tr -d ' ,' | sed 's/.*refs://')
  b=$(valgrind --tool=callgrind --callgrind-out-file=/dev/null ./bench_ir $e 2200 2>&1 \
      | grep refs: | tr -d ' ,' | sed 's/.*refs://')
  echo "$e $(python3 -c "print(f'{($b-$a)/(2000*12):.1f}')")"
done
```

`bench_ir <engine> <blocks> [note] [harmonics] [timbre] [morph]`

## Results as of 2026-09-14

`ir.csv` and `sweep.csv` hold the raw output. Cost turned out to be essentially
parameter-independent: 22 of 24 engines varied under 5 % across three very
different parameter settings. Only Speech (it switches between naive/SAM/LPC models
on morph) and Wave terrain move at all.

Headline: **20 of 24 engines fit with room to spare.** Additive (995) and Modal
(858) are the two that need trimming — `kNumHarmonics` 36→24 and `kMaxNumModes`
24→16 each cut about a third for the loss of only the highest partials.
