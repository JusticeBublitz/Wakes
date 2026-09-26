#!/usr/bin/env python3
"""wakes-sp1 -- generate the firmware's engine table from docs/PLAITS-ENGINES.md.

    gen_engines.py <PLAITS-ENGINES.md> <out.h>     build step (CMake runs this)
    gen_engines.py --fix [<PLAITS-ENGINES.md>]     renumber the Slot column to match
                                                   the row order

The markdown table under "## The engines" is the single source of truth for engine
order, LED pattern, enabled flag and centre detents. Row position = slot.

The LED column is FREE-FORM (Adara, M3c): four symbols, T1 first, each one of
    U+25CB  off   (0 %)
    U+25D0  half
    U+25CF  full
and every pattern must be unique, so each engine is recognisable on its own.

Standard library only. The file is read and written as UTF-8 explicitly: Windows'
default code page would mangle the LED symbols.
"""
import os
import sys

OFF, HALF, FULL = "○", "◐", "●"
LED_LEVEL = {OFF: 0, HALF: 1, FULL: 2}
DETENT_BITS = {"F4": 0x1, "F2": 0x2, "F3": 0x4}   # HARMONICS, TIMBRE, MORPH
MAX_SLOTS = 24
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MD = os.path.join(HERE, "..", "docs", "PLAITS-ENGINES.md")


def fail(msg):
    sys.stderr.write("\n*** docs/PLAITS-ENGINES.md: %s\n\n" % msg)
    sys.exit(1)


def led_levels(led, where):
    """Four symbols -> [0|1|2] * 4, or fail with a readable message."""
    syms = [ch for ch in led if not ch.isspace()]
    if len(syms) != 4 or any(ch not in LED_LEVEL for ch in syms):
        fail("%s: LED must be exactly four of %s %s %s (off, half, full), T1 first "
             "-- got `%s`" % (where, OFF, HALF, FULL, led))
    return [LED_LEVEL[ch] for ch in syms]


def table_rows(lines, heading="## the engines"):
    """(line index, cells) for each data row of the table under `heading`."""
    start = None
    for i, l in enumerate(lines):
        if l.strip().lower().startswith(heading):
            start = i
            break
    if start is None:
        fail("no '%s' section" % heading)
    rows, header_seen = [], False
    for i in range(start + 1, len(lines)):
        l = lines[i].strip()
        if l.startswith("## "):
            break
        if not l.startswith("|"):
            if rows:
                break
            continue
        cells = [c.strip() for c in l.strip("|").split("|")]
        if not header_seen:
            header_seen = True           # header row
            continue
        if set("".join(cells)) <= set("-: "):
            continue                     # separator row
        rows.append((i, cells))
    if not rows:
        fail("the engine table is empty")
    return rows


def parse(md_path):
    with open(md_path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    rows = table_rows(lines)
    if len(rows) > MAX_SLOTS:
        fail("%d rows; at most %d engines" % (len(rows), MAX_SLOTS))
    engines, seen = [], {}
    for lineno, c in rows:
        if len(c) < 6:
            fail("line %d: expected at least 6 columns, got %d" % (lineno + 1, len(c)))
        slot, led, name, pidx, on, det = c[:6]
        where = "line %d (%s)" % (lineno + 1, name)
        try:
            p = int(pidx)
        except ValueError:
            fail("%s: 'Plaits #' must be a number 0-23, got %r" % (where, pidx))
        if not 0 <= p <= 23:
            fail("%s: 'Plaits #' %d is outside 0-23" % (where, p))
        if p in seen:
            fail("%s: Plaits # %d is also used by %s" % (where, p, seen[p]))
        seen[p] = name
        if on.lower() not in ("yes", "no"):
            fail("%s: 'On' must be yes or no, got %r" % (where, on))
        bits = 0
        if det.strip() not in ("-", ""):
            for t in det.replace(",", " ").split():
                t = t.upper()
                if t not in DETENT_BITS:
                    fail("%s: detent %r -- use F2, F3, F4 or -" % (where, t))
                bits |= DETENT_BITS[t]
        ledtxt = led.strip("` ")
        engines.append(dict(slot=slot, led=ledtxt, levels=led_levels(ledtxt, where),
                            name=name, plaits=p, on=on.lower() == "yes", centre=bits,
                            line=lineno))
    if not any(e["on"] for e in engines):
        fail("every engine is disabled")
    return lines, engines


def check_parameter_table(lines, engines):
    """The "What each fader does, per engine" table is documentation, not build input,
    but it is useless if it drifts out of step with the engine list -- so its Engine
    column has to name the same engines in the same order (M4a). Its Slot column may
    merge rows ("22-24"), so only the names are compared."""
    try:
        rows = table_rows(lines, "## what each fader does")
    except SystemExit:
        return                        # section removed on purpose: nothing to check
    doc = []
    for lineno, cells in rows:
        if len(cells) < 2:
            fail("line %d: the parameter table needs a Slot and an Engine column"
                 % (lineno + 1))
        # "22-24 | 6-op FM A/B/C" stands for three engines whose names share a stem.
        doc.append((lineno, cells[1]))
    i = 0
    for lineno, name in doc:
        if name.endswith("A/B/C"):
            stem = name[:-5].strip()
            n = 0
            while i < len(engines) and engines[i]["name"].startswith(stem):
                i += 1
                n += 1
            if n == 0:
                fail("line %d: parameter table says %r, but no engine is named that"
                     % (lineno + 1, name))
            continue
        if i >= len(engines):
            fail("line %d: parameter table has more rows than the engine table"
                 % (lineno + 1))
        if engines[i]["name"] != name:
            fail("line %d: the parameter table says %r where the engine table's row %d "
                 "is %r.\n    The two tables must list the same engines in the same "
                 "order." % (lineno + 1, name, i + 1, engines[i]["name"]))
        i += 1
    if i != len(engines):
        fail("the parameter table stops at engine %d of %d (%r is missing)"
             % (i, len(engines), engines[i]["name"]))


def check(engines):
    seen = {}
    for n, e in enumerate(engines):
        where = "line %d (%s)" % (e["line"] + 1, e["name"])
        if e["slot"] != str(n + 1):
            fail("%s is row %d, so its Slot must be %d (it says %s).\n"
                 "    Run: python tools/gen_engines.py --fix"
                 % (where, n + 1, n + 1, e["slot"]))
        key = tuple(e["levels"])
        if key in seen:
            fail("%s: LED `%s` is the same as %s's -- every pattern must be unique"
                 % (where, e["led"], seen[key]))
        seen[key] = e["name"]


def c_str(s):
    s = s.encode("ascii", "replace").decode("ascii")[:24]
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def generate(md_path, out_path):
    lines, engines = parse(md_path)
    check(engines)
    check_parameter_table(lines, engines)
    # M4 (Adara): the device starts on the FIRST enabled row of the table.
    default = next(n for n, e in enumerate(engines) if e["on"])
    out = [
        "/* GENERATED from docs/PLAITS-ENGINES.md by tools/gen_engines.py.",
        " * Do not edit: edit the markdown table and rebuild. */",
        "#ifndef SP1_ENGINES_GEN_H",
        "#define SP1_ENGINES_GEN_H",
        "",
        "#include <stdint.h>",
        "",
        "#define SP1_ENGINE_SLOTS        %d" % len(engines),
        "#define SP1_ENGINE_DEFAULT_SLOT %d   /* the first enabled row */"
        % default,
        "",
        "/* centre: 0x1 = F4 HARMONICS, 0x2 = F2 TIMBRE, 0x4 = F3 MORPH",
        " * led:    T1..T4, 0 = off, 1 = half, 2 = full */",
        "static const struct {",
        "\tuint8_t plaits;     /* index in plaits/dsp/voice.cc */",
        "\tuint8_t on;",
        "\tuint8_t centre;",
        "\tuint8_t led[4];",
        "\tconst char *name;",
        "} SP1_ENGINE_TABLE[SP1_ENGINE_SLOTS] = {",
    ]
    for n, e in enumerate(engines):
        out.append("\t{ %2d, %d, 0x%x, { %d, %d, %d, %d }, %s },   /* slot %2d */"
                   % ((e["plaits"], int(e["on"]), e["centre"]) + tuple(e["levels"])
                      + (c_str(e["name"]), n + 1)))
    out += ["};", "", "#endif /* SP1_ENGINES_GEN_H */", ""]
    text = "\n".join(out)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    try:
        with open(out_path, encoding="utf-8") as f:
            if f.read() == text:
                return                     # unchanged: don't force a recompile
    except OSError:
        pass
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def fix(md_path):
    with open(md_path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    changed = 0
    for n, (lineno, cells) in enumerate(table_rows(lines)):
        l = lines[lineno]
        lead = l[: len(l) - len(l.lstrip())]
        nl = lead + "| " + " | ".join([str(n + 1)] + cells[1:]) + " |"
        if nl != l:
            lines[lineno] = nl
            changed += 1
    with open(md_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    print("PLAITS-ENGINES.md: %d row(s) renumbered" % changed)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--fix":
        fix(a[1] if len(a) > 1 else DEFAULT_MD)
    elif len(a) == 2:
        generate(a[0], a[1])
    else:
        sys.stderr.write(__doc__)
        sys.exit(2)
