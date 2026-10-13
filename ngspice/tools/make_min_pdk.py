#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_min_pdk.py - generates a reduced version of the sky130A PDK for ngspice.

Goal
----
ngspice takes ~4 s to read the models of the full PDK even if the circuit uses
only a couple of transistors. This tool builds a PDK that contains only the
chosen NMOS/PMOS transistors (by default 1.8 V, 1.8 V LVT and 5 V), keeping ALL the
corner sections (tt, ss_ll, tt_mm, mc, ...) with the same names, so that existing
netlists only change the root path.

What it produces (an exact subset of the original tree)
-------------------------------------------------------
    <dst>/libs.tech/combined/
        sky130.lib.spice               MODIFIED: pruned includes
        continuous/models_fet.spice    MODIFIED: only the chosen devices
        continuous/models_global.spice           identical copy
        continuous/parameters_{fet,res,cap}_*.spice   identical copies
        continuous/models_fet/sky130_fd_pr__<device>.spice   identical copies
    <dst>/MANIFEST.txt                 sha256 hashes and status of every file
    <dst>/libs.tech/combined/sections/ (only with --split-sections)
        sky130_<section>.lib.spice     one lib per section (49), e.g. sky130_tt.lib.spice

What is discarded: BJT, diode, resistor and capacitor models, corners/*,
rescap/*, SONOS, RF, and parameters/{critical,montecarlo,invariant}.spice (these
only serve legacy discrete models; the continuous FETs do not use them).

Usage
-----
    python make_min_pdk.py                         # ./sky130A -> ./sky130A_min
    python make_min_pdk.py --src PATH --dst PATH --force
    python make_min_pdk.py --split-sections        # additionally, one lib per section
    python make_min_pdk.py --check-netlist CMOS_Inverter.cir other.cir
    python make_min_pdk.py --smoke-test            # compare results (requires ngspice)

Notes
-----
* The integrity checks (all includes exist, identical sections,
  byte-for-byte copies, scale option present) always run.
* --smoke-test compares DC currents of the full and the reduced PDK in the
  deterministic corners (they must match) and checks that tt_mm and mc run.
  If the per-section libs exist, it validates them the same way and compares times.

LTspice target (--target ltspice)
---------------------------------
    python make_min_pdk.py --target ltspice --src sky130A --dst sky130A_ltspice_min --force [--smoke-test]

Translates the 6 continuous FETs (new PDK structure) to LTspice, without depending on ngspice:
  * geometry in METERS (no .option scale): l w ad as pd ps nrd nrs sa sb sd in SI units,
    nf, mult (-> m= on the M line);  nrd/nrs = -1 uses the PDK default value (0.14/w[um]);
  * per-instance mismatch: the PDK delvto is kept; AGAUSS(0,1,1) -> .param gauss(1) inside
    the subcircuit (LTspice draws one value per instance);
  * global process: .param with gauss(sigma) at global level (one value per .step step);
  * xnfet_*/xpfet_* wrappers with automatic ad/as/pd/ps/nrd/nrs (same interface as the current lib);
  * sections TT SS FF SF FS (deterministic), MC (process), MM (mismatch), MCMM (both), in
    sky130A_ltspice.lib and as flat files sky130A_ltspice_<section>.lib (macOS).
Monte Carlo in LTspice:   .lib "sky130A_ltspice_mcmm.lib"   +   .step param run 1 300 1
--smoke-test compares in ngspice (gauss -> 0) full PDK vs translation: Id and Cgg, 5 corners.
WARNING: L exactly on a bin edge gives a different process sigma than ngspice; use L = edge + 10 nm
(README_ltspice.md is generated with the table and check_bin_edges.py warns; --check-netlist too).
Note: LTspice does not support mulu0, so the k mismatch (mis_k, gf180 only) is not modeled.

Per-section libs (--split-sections)
-----------------------------------
ngspice takes much longer with the multi-section file than with a single-section lib
(on an inverter: ~2.5 s vs ~0.6 s with the reduced PDK; ~4.9 s vs ~0.7 s
with the full one). Each file sections/sky130_<sec>.lib.spice contains ONLY the
section <sec>, with the same section name, so in a netlist it is enough to change:
    .lib /path/libs.tech/combined/sky130.lib.spice tt
to
    .lib /path/libs.tech/combined/sections/sky130_tt.lib.spice tt
The includes are rewritten with a ../ prefix (relative to sections/); the rest of the
content is identical to that of the original section (verified line by line).
With --split-sections on an already existing reduced PDK, --force is not needed:
only the per-section libs are regenerated.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

DEFAULT_DEVICES = (
    "nfet_01v8", "nfet_01v8_lvt", "nfet_g5v0d10v5",
    "pfet_01v8", "pfet_01v8_lvt", "pfet_g5v0d10v5",
)

INCLUDE_RE = re.compile(r"""^\s*\.(?:include|inc)\s+["']?([^"'\s]+)["']?""", re.I)
LIB_OPEN_RE = re.compile(r"^\s*\.lib\s+(\w+)\s*$", re.I)
# Lib includes that are kept (everything else is discarded).
KEEP_RE = re.compile(
    r"^continuous/(?:models_global\.spice|models_fet\.spice|"
    r"parameters_(?:fet|res|cap)_\w+\.spice)$"
)
SCALE_RE = re.compile(r"^\s*\.options?\s+.*\bscale\s*=", re.I | re.M)
MODEL_RE = re.compile(r"sky130_fd_pr__(\w+)", re.I)

MODELS_FET_REL = "continuous/models_fet.spice"
HEADER = "* Reduced version generated by make_min_pdk.py ({date}).\n" \
         "* FET devices included: {devices}\n" \
         "* See MANIFEST.txt in the root for the file details.\n*\n"


# ----------------------------------------------------------------------------
# utilities
# ----------------------------------------------------------------------------
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def lib_sections(text: str) -> list[str]:
    return [m.group(1) for line in text.splitlines()
            if (m := LIB_OPEN_RE.match(line))]


LIB_END_RE = re.compile(r"^\s*\.endl\b", re.I)
SECTIONS_DIR = "sections"
SPLIT_MARK = "per-section derived libs"


def lib_section_lines(text: str) -> dict[str, list[str]]:
    """{section: inner lines (without .lib/.endl)} in file order."""
    out: dict[str, list[str]] = {}
    cur = None
    for line in text.splitlines():
        if (m := LIB_OPEN_RE.match(line)):
            cur = m.group(1)
            out[cur] = []
        elif LIB_END_RE.match(line):
            cur = None
        elif cur is not None:
            out[cur].append(line)
    return out


def walk_includes(entry: Path):
    """Recursively walk the .include statements starting from `entry`.

    Returns (reached_files, [(missing_path, file_that_includes_it)]).
    Relative paths are resolved with respect to the directory of the file that
    contains the include (as ngspice does).
    """
    seen: set[Path] = set()
    missing: list[tuple[str, str]] = []
    stack = [entry]
    while stack:
        f = stack.pop().resolve()
        if f in seen:
            continue
        seen.add(f)
        for line in f.read_text(errors="replace").splitlines():
            m = INCLUDE_RE.match(line)
            if not m:
                continue
            target = f.parent / m.group(1)
            if target.is_file():
                stack.append(target)
            else:
                missing.append((str(target), f.name))
    return seen, missing


# ----------------------------------------------------------------------------
# build
# ----------------------------------------------------------------------------
README_NG = """# sky130A_min (ngspice): reduced and segmented sky130A PDK

## The problem

ngspice parses the whole sky130A model library every time it starts, even if the circuit
uses two transistors. The standard entry point `sky130.lib.spice` contains 49 corner
sections, and ngspice also processes the includes of the sections you did NOT select. For a
small inverter, loading the library takes far longer than the simulation itself
(almost all of a 6 s run: the same run takes 0.12 s when only one section is loaded). When you run corners, parameter sweeps or Monte Carlo with
hundreds of runs, that fixed cost dominates everything.

This package attacks the problem in two independent ways:

1. **Reduced PDK ("min")**: keeps only the 6 continuous FETs
   (`nfet_01v8`, `pfet_01v8`, `nfet_01v8_lvt`, `pfet_01v8_lvt`, `nfet_g5v0d10v5`, `pfet_g5v0d10v5`)
   and drops everything else (BJTs, diodes, resistors, capacitors, SONOS, RF, digital cells).
   All 49 corner sections keep their original names, so existing netlists only change the path.
2. **Segmented libs**: one file per corner section (`sections/sky130_<section>.lib.spice`),
   so ngspice only reads the section you ask for.

Generated by `make_min_pdk.py`. `MANIFEST.txt` lists every file with its sha256 and whether it is an
identical copy of the original, a modified file or a derived file.

## Speed comparison

Same CMOS inverter (netlist below), `.tran 10p 6n`, section `tt`, wall time of the whole
`ngspice -b` run, median of 7 runs. Machine: 2 vCPU Intel Xeon 2.8 GHz, ngspice-42.
Times depend on the machine; the ratios are what matters.

| Library | File passed to `.lib` | Time (median) | Speed-up |
|---|---|---|---|
| Original (full PDK, 49 sections) | `sky130A/libs.tech/combined/sky130.lib.spice` | 6.00 s | 1x |
| Reduced ("min"), 49 sections | `sky130A_min/libs.tech/combined/sky130.lib.spice` | 2.74 s | 2.2x |
| Original PDK, segmented | `.../sections/sky130_tt.lib.spice` | 0.14 s | 43x |
| Reduced + segmented (recommended) | `sky130A_min/libs.tech/combined/sections/sky130_tt.lib.spice` | 0.12 s | 50x |

Take-aways:

* **Segmenting gives almost all of the gain.** Reducing the devices alone helps (2.2x) when you keep the
  multi-section file, but once you load a single section the full and the reduced PDK are within
  a few tens of milliseconds of each other.
* All four variants give the identical result (`tpHL = 3.7137e-11 s`, `tpLH = 4.5643e-11 s`).
* The ranges across the 7 runs were 5.50-6.30 s, 2.59-2.92 s, 0.14-0.17 s and 0.11-0.13 s.

Inverter used for the measurement:

    * CMOS inverter - sky130A (ngspice)
    .lib /path/sky130A_min/libs.tech/combined/sections/sky130_tt.lib.spice tt
    Xp out in vdd vdd sky130_fd_pr__pfet_01v8 L=0.15 W=2
    Xn out in 0 0     sky130_fd_pr__nfet_01v8 L=0.15 W=1
    Vdd vdd 0 1.8
    Vin in 0 pulse(0 1.8 0.2n 50p 50p 1n 2n)
    Cl out 0 10f
    .tran 10p 6n
    .meas tran tpHL TRIG V(in) VAL=0.9 RISE=1 TARG V(out) VAL=0.9 FALL=1
    .meas tran tpLH TRIG V(in) VAL=0.9 FALL=1 TARG V(out) VAL=0.9 RISE=1
    .end

## Contents

    sky130A_min/
        README_sky130A_min.md
        MANIFEST.txt
        libs.tech/combined/
            sky130.lib.spice                      full lib (49 sections), unused includes pruned
            sections/sky130_<section>.lib.spice   one lib per section (49 files)   <- recommended
            continuous/                           models and parameters (identical copies of the original)

The files in `sections/` are small (they are lists of includes, with the section's parameters) and point
to `../continuous/`. **Keep the folder structure**: they are not self-contained.

## How to use it

Only the path of the `.lib` line changes; the section name at the end (here `tt`) stays, because it is the
`.lib` section inside the file and it is the same as in the original PDK.

    * original
    .lib /path/sky130A/libs.tech/combined/sky130.lib.spice tt

    * reduced PDK, multi-section file (same names, 2.2x faster)
    .lib /path/sky130A_min/libs.tech/combined/sky130.lib.spice tt

    * reduced PDK, one section (recommended)
    .lib /path/sky130A_min/libs.tech/combined/sections/sky130_tt.lib.spice tt

Sections available in both forms: `tt ss ff sf fs`; `ll hl lh hh` (res/cap corners, they do not affect the FETs);
combined `ss_ll ... ff_hh`; each of them with the `_mm` suffix (per-instance mismatch); and `mc` (global process
variation, see the note below).

Device names are the original ones (`sky130_fd_pr__nfet_01v8`, ...), W and L in micrometers (the library
sets `.option scale=1e-6`). In sky130 the area and perimeter parameters `ad as pd ps` default to 0 and
`nrd = nrs = 0.14/w` unless you pass them on the instance.

Check a netlist before running it (it reports devices or sections that the reduced PDK does not have):

    python make_min_pdk.py --check-netlist my_circuit.cir

### Note on Monte Carlo (`mc`) in ngspice

In the original `mc` section the process parameters are drawn with `AGAUSS`, and ngspice evaluates it again for
every instance. Two identical transistors therefore receive different "process" values, so the process
variation behaves like additional mismatch. If you want one process draw shared by all devices in a run,
use `mc_runner.py` (see the overview README, `README_min_libs.md`). It works with this reduced PDK.

## What changes with respect to the original

* `sky130.lib.spice`: only the `.include` lines of discarded models are pruned.
* `continuous/models_fet.spice`: lists only the 6 devices.
* `sections/*`: the content of each section is identical to the original (verified line by line); the
  includes carry a `../` prefix because the file lives one level below.
* Everything else is a byte-for-byte copy (status `identical` in `MANIFEST.txt`).

## Validation

* **Integrity checks (always run by the generator):** every include exists, the sections are the same as the
  original, copies are byte for byte, the `scale` option is present.
* **`--smoke-test` (needs ngspice):** DC currents of the full and the reduced PDK in `tt ss ff sf fs` for the 6
  devices: relative difference 0.00e+00. The sections `tt_mm` and `mc` also run, from the multi-section file and
  from their per-section libs. Every per-section lib reproduces the original section.

## Limitations

* Only the 6 FETs above. A netlist that uses anything else fails with `unknown subckt`; regenerate with
  `--devices` to keep other FETs.
* No resistors, capacitors, BJTs, diodes, SONOS, RF or digital cells.
* Timings are for one inverter on one machine; the absolute values change with the circuit and the machine.

## Regenerate

Requires Python 3.9+ and, for `--smoke-test`, ngspice. The input is a complete `sky130A` directory (the
one that contains `libs.tech/`, as installed by open_pdks / volare).

    python make_min_pdk.py --src PATH/sky130A --dst sky130A_min --split-sections --force
    python make_min_pdk.py --src PATH/sky130A --dst sky130A_min --split-sections --force --smoke-test
    python make_min_pdk.py --split-sections --dst sky130A_min      # only rebuild the per-section libs

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `unknown subckt sky130_fd_pr__...` | The device is not one of the 6 kept. Regenerate with `--devices`. |
| `Could not find include file .../continuous/...` | A file from `sections/` was moved. Keep `sections/` and `continuous/` together. |
| Section not found | Use the exact section name, as in the original (`tt`, `ss_ll_mm`, ...); they are the `.lib <name>` lines of `sky130.lib.spice`. |
| Two identical transistors differ in `mc` | Expected in ngspice (see the Monte Carlo note). Use `mc_runner.py`. |

## Related

`sky130A_ltspice_min` is something else: a translation of the same PDK to LTspice (`--target ltspice`),
with its own `README_ltspice.md`. The overview of all packages is in `README_min_libs.md`.

## License

The contents are derived from the SkyWater sky130 PDK (Apache License 2.0, Copyright The SkyWater PDK
Authors); the license headers of the original files are kept. The tools are provided as they are, with no warranty.
"""

def build(src: Path, dst: Path, devices, force: bool = False, split: bool = False,
          log=print):
    comb_src = src / "libs.tech" / "combined"
    lib_src = comb_src / "sky130.lib.spice"
    if not lib_src.is_file():
        sys.exit(f"ERROR: cannot find {lib_src}\n"
                 f"       --src must point to the sky130A directory "
                 f"(the one that contains libs.tech/).")

    models_src = comb_src / "continuous" / "models_fet"
    for d in devices:
        if not (models_src / f"sky130_fd_pr__{d}.spice").is_file():
            sys.exit(f"ERROR: the model of device '{d}' does not exist in {models_src}")

    if dst.exists():
        if not force:
            sys.exit(f"ERROR: {dst} already exists (use --force to regenerate it).")
        shutil.rmtree(dst)

    comb_dst = dst / "libs.tech" / "combined"
    (comb_dst / "continuous" / "models_fet").mkdir(parents=True)

    # 1) pruned sky130.lib.spice --------------------------------------------
    kept: set[str] = set()
    dropped: dict[str, int] = {}
    out: list[str] = [HEADER.format(date=_dt.date.today().isoformat(),
                                    devices=", ".join(devices))]
    for line in lib_src.read_text(errors="replace").splitlines(keepends=True):
        m = INCLUDE_RE.match(line)
        if m:
            p = m.group(1)
            if KEEP_RE.match(p):
                kept.add(p)
                out.append(line)
            else:
                dropped[p] = dropped.get(p, 0) + 1
            continue
        out.append(line)
    if MODELS_FET_REL not in kept:
        sys.exit("ERROR: the original lib does not include continuous/models_fet.spice; "
                 "PDK structure not recognized.")
    (comb_dst / "sky130.lib.spice").write_text("".join(out))

    # 2) files copied unchanged ----------------------------------------
    verbatim: list[str] = []
    for rel in sorted(kept - {MODELS_FET_REL}):
        s = comb_src / rel
        if not s.is_file():
            sys.exit(f"ERROR: the lib includes {rel} but it does not exist in the source.")
        shutil.copyfile(s, comb_dst / rel)
        verbatim.append(rel)

    # 3) new continuous/models_fet.spice ---------------------------------------
    mf = ["* Continuous FET models - reduced version (make_min_pdk.py)\n"]
    for d in sorted(devices):
        mf.append(f'.include "models_fet/sky130_fd_pr__{d}.spice"\n')
    (comb_dst / MODELS_FET_REL).write_text("".join(mf))

    # 4) device models ---------------------------------------------
    for d in sorted(devices):
        rel = f"continuous/models_fet/sky130_fd_pr__{d}.spice"
        shutil.copyfile(comb_src / rel, comb_dst / rel)
        verbatim.append(rel)

    # 5) integrity check -------------------------------------------
    problems = verify(src, dst, devices, verbatim)

    # 5b) per-section libs (optional) ---------------------------------------------
    split_files: list[Path] = []
    if split:
        split_files, sp = split_sections(dst)
        problems += sp

    (dst / "README_sky130A_min.md").write_text(README_NG)

    # 6) manifest -----------------------------------------------------------------
    write_manifest(src, dst, devices, verbatim, dropped, problems)
    if split_files:
        update_manifest_split(dst, split_files)

    # 7) summary ----------------------------------------------------------------------
    files = [p for p in dst.rglob("*") if p.is_file()]
    size_kb = sum(p.stat().st_size for p in files) / 1024
    secs = lib_sections((comb_dst / "sky130.lib.spice").read_text())
    log(f"Reduced PDK: {dst}")
    log(f"  files: {len(files)} (includes MANIFEST.txt)   size: {size_kb:.0f} KB")
    log(f"  corner sections kept: {len(secs)}")
    log(f"  discarded includes (distinct): {len(dropped)}")
    if split_files:
        log(f"  per-section libs: {len(split_files)} files in libs.tech/combined/{SECTIONS_DIR}/")
    if problems:
        log("\nPROBLEMS DETECTED:")
        for p in problems:
            log(f"  - {p}")
    else:
        log("  integrity check: OK")
    return problems


def verify(src: Path, dst: Path, devices, verbatim) -> list[str]:
    problems: list[str] = []
    comb_src = src / "libs.tech" / "combined"
    comb_dst = dst / "libs.tech" / "combined"
    lib_dst = comb_dst / "sky130.lib.spice"

    seen, missing = walk_includes(lib_dst)
    for path, who in missing:
        problems.append(f"missing include: {path} (referenced from {who})")

    s_src = lib_sections((comb_src / "sky130.lib.spice").read_text(errors="replace"))
    s_dst = lib_sections(lib_dst.read_text())
    if s_src != s_dst:
        problems.append("the sections of the reduced lib do not match the original ones: "
                        f"{sorted(set(s_src) ^ set(s_dst))}")

    for rel in verbatim:
        if sha256(comb_src / rel) != sha256(comb_dst / rel):
            problems.append(f"non-identical copy: {rel}")

    scale_found = any(SCALE_RE.search(f.read_text(errors="replace")) for f in seen)
    if not scale_found:
        problems.append("'.option scale=...' not found in the kept files; "
                        "W and L in microns would not be interpreted correctly")

    for d in devices:
        f = (comb_dst / f"continuous/models_fet/sky130_fd_pr__{d}.spice").resolve()
        if f not in seen:
            problems.append(f"device {d} is not reachable from the lib")
    return problems


def write_manifest(src, dst, devices, verbatim, dropped, problems):
    comb_src = src / "libs.tech" / "combined"
    comb_dst = dst / "libs.tech" / "combined"
    lines = [
        "MANIFEST - reduced sky130A PDK",
        f"generated: {_dt.datetime.now().isoformat(timespec='seconds')}",
        f"source:    {src.resolve()}",
        f"source sha256 sky130.lib.spice: {sha256(comb_src / 'sky130.lib.spice')}",
        f"devices: {', '.join(devices)}",
        "",
        "status     sha256                                                            bytes  path",
    ]
    for rel in ["sky130.lib.spice", MODELS_FET_REL] + verbatim:
        f = comb_dst / rel
        status = "MODIFIED  " if rel in ("sky130.lib.spice", MODELS_FET_REL) else "identical "
        lines.append(f"{status} {sha256(f)}  {f.stat().st_size:>8}  libs.tech/combined/{rel}")
    lines += ["", f"includes discarded from the original lib ({len(dropped)} distinct):"]
    for p, c in sorted(dropped.items()):
        lines.append(f"  {c:3d} x {p}")
    lines += ["", "verification: " + ("OK" if not problems else "WITH PROBLEMS")]
    lines += [f"  - {p}" for p in problems]
    (dst / "MANIFEST.txt").write_text("\n".join(lines) + "\n")


# ----------------------------------------------------------------------------
# --split-sections
# ----------------------------------------------------------------------------
def split_sections(dst: Path):
    """Write one lib per section in <dst>/libs.tech/combined/sections/.

    Returns (list_of_files, problems).
    """
    comb = dst / "libs.tech" / "combined"
    lib = comb / "sky130.lib.spice"
    if not lib.is_file():
        sys.exit(f"ERROR: cannot find {lib}; generate the reduced PDK first.")
    secs = lib_section_lines(lib.read_text(errors="replace"))
    out_dir = comb / SECTIONS_DIR
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir()
    files: list[Path] = []
    for name, lines in secs.items():
        body = []
        for line in lines:
            m = INCLUDE_RE.match(line)
            if m:  # paths relative to combined/ -> relative to combined/sections/
                line = line.replace(m.group(1), "../" + m.group(1), 1)
            body.append(line)
        text = (f"* Section '{name}' extracted from ../sky130.lib.spice "
                f"(make_min_pdk.py --split-sections)\n"
                f".lib {name}\n" + "\n".join(body) + f"\n.endl {name}\n")
        f = out_dir / f"sky130_{name}.lib.spice"
        f.write_text(text)
        files.append(f)
    return files, verify_split(dst)


def verify_split(dst: Path) -> list[str]:
    """Each per-section lib must reproduce the original section and its includes must exist."""
    comb = dst / "libs.tech" / "combined"
    orig = lib_section_lines((comb / "sky130.lib.spice").read_text(errors="replace"))
    problems: list[str] = []
    for name, lines in orig.items():
        f = comb / SECTIONS_DIR / f"sky130_{name}.lib.spice"
        if not f.is_file():
            problems.append(f"missing {f.relative_to(dst)}")
            continue
        got = lib_section_lines(f.read_text(errors="replace"))
        if list(got) != [name]:
            problems.append(f"{f.name}: must contain exactly the section '{name}', "
                            f"contains {list(got)}")
            continue
        restored = []
        for line in got[name]:
            m = INCLUDE_RE.match(line)
            if m:
                p = m.group(1)
                if not p.startswith("../"):
                    problems.append(f"{f.name}: include without ../ prefix -> {p}")
                elif not (f.parent / p).is_file():
                    problems.append(f"{f.name}: nonexistent include -> {p}")
                line = line.replace(p, p[3:], 1) if p.startswith("../") else line
            restored.append(line)
        if restored != lines:
            problems.append(f"{f.name}: content differs from the original section")
    return problems


def update_manifest_split(dst: Path, files) -> None:
    """Add (or replace) the per-section libs block in MANIFEST.txt."""
    mf = dst / "MANIFEST.txt"
    text = mf.read_text() if mf.is_file() else "MANIFEST - reduced sky130A PDK\n"
    cut = text.find("\n" + SPLIT_MARK)
    if cut != -1:
        text = text[:cut].rstrip("\n") + "\n"
    lines = ["", f"{SPLIT_MARK} ({len(files)} files in libs.tech/combined/{SECTIONS_DIR}/):"]
    for f in files:
        lines.append(f"derived    {sha256(f)}  {f.stat().st_size:>8}  "
                     f"libs.tech/combined/{SECTIONS_DIR}/{f.name}")
    mf.write_text(text + "\n".join(lines) + "\n")


# ----------------------------------------------------------------------------
# --check-netlist
# ----------------------------------------------------------------------------
def check_netlists(paths, dst: Path, devices) -> bool:
    lib_dst = dst / "libs.tech" / "combined" / "sky130.lib.spice"
    sections = set(lib_sections(lib_dst.read_text())) if lib_dst.is_file() else set()
    ok = True
    allowed = set(devices)
    for p in map(Path, paths):
        if not p.is_file():
            print(f"[{p}] does not exist")
            ok = False
            continue
        bad: dict[str, int] = {}
        secs: list[str] = []
        for line in p.read_text(errors="replace").splitlines():
            if line.lstrip().startswith("*"):
                continue
            for m in MODEL_RE.finditer(line):
                name = m.group(1)
                if name not in allowed:
                    bad[name] = bad.get(name, 0) + 1
            lm = re.match(r"^\s*\.lib\s+[\"']?\S*sky130\S*\.lib\.spice[\"']?\s+(\w+)", line, re.I)
            if lm:
                secs.append(lm.group(1))
        status = []
        if bad:
            ok = False
            status.append("devices NOT included in the reduced PDK: " +
                          ", ".join(f"{k} (x{v})" for k, v in sorted(bad.items())))
        for s in secs:
            if sections and s not in sections:
                ok = False
                status.append(f"section '{s}' does not exist in the reduced lib")
        if not secs:
            status.append("warning: no '.lib ...sky130.lib.spice <section>' line found")
        print(f"[{p}] " + ("OK" if not status else "\n    ".join([""] + status).strip()))
    return ok


# ----------------------------------------------------------------------------
# --smoke-test
# ----------------------------------------------------------------------------
_SMOKE_L = {"01v8": 0.15, "01v8_lvt": 0.35, "g5v0d10v5": 0.5}


def _smoke_netlist(lib: Path, section: str, devices) -> str:
    L = [f"smoke test {section}", f".lib {lib.as_posix()} {section}",
         "Vdd vdd 0 1.8", "Vhv vhv 0 5.0"]
    meas = []
    for i, d in enumerate(devices):
        kind, rest = d.split("_", 1)
        high = "g5v0" in rest or "05v0" in rest
        bias = 2.5 if high else (1.65 if "03v3" in rest else 0.9)
        length = _SMOKE_L.get(rest, 1.0)
        rail = "vhv" if high else "vdd"
        n = f"d{i}"
        L += [f"Vg{n} g{n} 0 {bias}", f"Vd{n} d{n} 0 {bias}"]
        if kind == "nfet":
            L.append(f"X{n} d{n} g{n} 0 0 sky130_fd_pr__{d} L={length} W=1")
        else:
            L.append(f"X{n} d{n} g{n} {rail} {rail} sky130_fd_pr__{d} L={length} W=1")
        meas.append(f"i(vd{n})")
    L += [".control", "op", "print " + " ".join(meas), ".endc", ".end"]
    return "\n".join(L) + "\n"


def _smoke_run(ngspice: str, lib: Path, section: str, devices, tmp: Path):
    cir = tmp / "smoke.cir"
    log = tmp / "smoke.log"
    cir.write_text(_smoke_netlist(lib, section, devices))
    t0 = time.perf_counter()
    subprocess.run([ngspice, "-b", "-o", str(log), str(cir)], cwd=tmp,
                   capture_output=True, timeout=300)
    elapsed = time.perf_counter() - t0
    vals = {}
    for line in log.read_text(errors="replace").splitlines():
        m = re.match(r"^\s*(i\(vd\w+\))\s*=\s*(\S+)", line)
        if m:
            vals[m.group(1)] = float(m.group(2))
    return vals, elapsed


def smoke_test(src: Path, dst: Path, devices) -> bool:
    ng = shutil.which("ngspice")
    if not ng:
        print("smoke-test: ngspice is not in the PATH; skipped.")
        return True
    lib_full = (src / "libs.tech" / "combined" / "sky130.lib.spice").resolve()
    lib_min = (dst / "libs.tech" / "combined" / "sky130.lib.spice").resolve()
    ok = True
    with tempfile.TemporaryDirectory(prefix="smoke_") as t:
        tmp = Path(t)
        print(f"{'section':8} {'max rel. diff full vs reduced':>40}")
        for sec in ("tt", "ss", "ff", "sf", "fs"):
            a, _ = _smoke_run(ng, lib_full, sec, devices, tmp)
            b, _ = _smoke_run(ng, lib_min, sec, devices, tmp)
            if len(a) != len(devices) or len(b) != len(devices):
                print(f"{sec:8} FAILED: no results (full={len(a)}, reduced={len(b)})")
                ok = False
                continue
            diff = max(abs(a[k] - b[k]) / max(abs(a[k]), 1e-30) for k in a)
            flag = "OK" if diff <= 1e-9 else "DIFFERS"
            ok &= diff <= 1e-9
            print(f"{sec:8} {diff:>40.2e}  {flag}")
        for sec in ("tt_mm", "mc"):
            b, _ = _smoke_run(ng, lib_min, sec, devices, tmp)
            good = len(b) == len(devices)
            ok &= good
            print(f"{sec:8} {'runs in the reduced one' if good else 'FAILED':>40}  "
                  f"{'OK' if good else 'FAILED'}")

        sect = dst / "libs.tech" / "combined" / SECTIONS_DIR
        if sect.is_dir():
            print("\nper-section libs (reduced) vs original lib of the full PDK:")
            for sec in ("tt", "ss", "ff", "sf", "fs"):
                a, _ = _smoke_run(ng, lib_full, sec, devices, tmp)
                b, _ = _smoke_run(ng, (sect / f"sky130_{sec}.lib.spice").resolve(),
                                  sec, devices, tmp)
                good = len(a) == len(devices) == len(b)
                diff = max(abs(a[k] - b[k]) / max(abs(a[k]), 1e-30) for k in a) if good else 1.0
                ok &= good and diff <= 1e-9
                print(f"{sec:8} {diff:>40.2e}  {'OK' if good and diff <= 1e-9 else 'DIFFERS'}")
            for sec in ("tt_mm", "mc"):
                b, _ = _smoke_run(ng, (sect / f"sky130_{sec}.lib.spice").resolve(),
                                  sec, devices, tmp)
                good = len(b) == len(devices)
                ok &= good
                print(f"{sec:8} {'runs from its per-section lib' if good else 'FAILED':>40}  "
                      f"{'OK' if good else 'FAILED'}")
            print("\ntotal ngspice time, tt corner (best of 2 runs; order of magnitude):")
            for label, lib in (("Full PDK, multi-section lib", lib_full),
                               ("Reduced PDK, multi-section lib", lib_min),
                               ("Reduced PDK, per-section lib", (sect / "sky130_tt.lib.spice").resolve())):
                t = min(_smoke_run(ng, lib, "tt", devices, tmp)[1] for _ in range(2))
                print(f"  {label:34} {t:6.2f} s")
    return ok


# ============================================================================
# LTspice target (--target ltspice)
# ============================================================================
LT_CORNERS = ("tt", "ss", "ff", "sf", "fs")
# (section name, parameter corner, MC_PR_SWITCH, MC_MM_SWITCH)
LT_SECTIONS = (
    ("TT", "tt", 0, 0), ("SS", "ss", 0, 0), ("FF", "ff", 0, 0),
    ("SF", "sf", 0, 0), ("FS", "fs", 0, 0),
    ("MC", "tt", 1, 0), ("MM", "tt", 0, 1), ("MCMM", "tt", 1, 1),
)
LT_DIR = "sky130A_ltspice"
LT_SECTIONS = list(LT_SECTIONS)


def lt_extra_sections(src_lib: Path) -> list[tuple[str, str, int, int]]:
    """Sections of the original sky130.lib.spice (49) that are not yet in LT_SECTIONS, as
    (name, fet_corner, MC_PR_SWITCH, MC_MM_SWITCH). They are read from the original (not assumed):
    corner = included parameters_fet_<c>.spice, switches = the .param of the section.
    The res/cap corners (ll hl lh hh) do not change the 6 FETs (verified), but they are generated
    so that netlists can use the same section names as in ngspice."""
    have = {s[0].lower() for s in LT_SECTIONS}
    out = []
    for name, lines in lib_section_lines(src_lib.read_text()).items():
        if name.lower() in have:
            continue
        txt = "\n".join(lines)
        mc = re.search(r"parameters_fet_(\w+)\.spice", txt)
        pr = re.search(r"MC_PR_SWITCH\s*=\s*(\d)", txt)
        mm = re.search(r"MC_MM_SWITCH\s*=\s*(\d)", txt)
        if not (mc and pr and mm) or mc.group(1) not in LT_CORNERS:
            raise SystemExit(f"section '{name}' of the original PDK could not be interpreted")
        out.append((name, mc.group(1), int(pr.group(1)), int(mm.group(1))))
    return out

# visible instance parameters (in METERS) and their default value
INST_DEFAULTS = (("l", "1u"), ("w", "1u"), ("nf", "1"), ("ad", "0"), ("as", "0"),
                 ("pd", "0"), ("ps", "0"), ("nrd", "-1"), ("nrs", "-1"),
                 ("sa", "0"), ("sb", "0"), ("sd", "0"))

# default geometry of the xnfet_/xpfet_ wrappers (same as sky130A_ltspice.lib)
WRAP_DEFAULT_L = {"nfet_01v8": "0.15u", "pfet_01v8": "0.15u", "nfet_01v8_lvt": "0.15u",
                  "pfet_01v8_lvt": "0.35u", "nfet_g5v0d10v5": "0.5u", "pfet_g5v0d10v5": "0.5u"}


# ----------------------------------------------------------------------------
# expression utilities
# ----------------------------------------------------------------------------
def _split_args(s: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip()); cur = ""
        else:
            cur += ch
    out.append(cur.strip())
    return out


def _find_call(s: str, name: str, start: int = 0):
    """First call name(...) from start -> (i0, i1, args) or None (balanced parentheses)."""
    m = re.compile(r"(?<![\w.])" + name + r"\s*\(", re.I).search(s, start)
    if not m:
        return None
    depth, i = 1, m.end()
    while i < len(s) and depth:
        depth += (s[i] == "(") - (s[i] == ")")
        i += 1
    return m.start(), i, _split_args(s[m.end():i - 1])


def _is_zero(x: str) -> bool:
    try:
        return float(x) == 0.0
    except ValueError:
        return False


def convert_gauss(expr: str, hoist: list[str] | None = None, prefix: str = "mmz") -> str:
    """AGAUSS(nom,abs,sig) -> (nom+gauss(abs/sig));  GAUSS(nom,rel,sig) -> nom (+gauss(|nom*rel/sig|)).

    ngspice semantics: agauss = nom + abs/sig*N(0,1);  gauss = nom + nom*rel/sig*N(0,1).
    In LTspice gauss(x) = N(0, sigma=x).  If `hoist` is a list, each call is replaced by a
    name (prefix1, prefix2, ...) and the definition is appended to the list (for per-instance `.param`).
    """
    while True:
        a, g = _find_call(expr, "agauss"), None
        if a is None:
            g = _find_call(expr, "gauss")
            if g is None:
                break
        i0, i1, args = a or g
        if len(args) != 3:
            raise ValueError(f"gauss with {len(args)} arguments: {expr[i0:i1]}")
        nom, spread, sig = args
        if a:
            body = f"Qgauss(({spread})/({sig}))"
            full = body if _is_zero(nom) else f"({nom}+{body})"
        else:  # GAUSS: sigma = |nom*rel/sig|; with nom=0 it is exactly 0
            full = "0" if _is_zero(nom) else f"({nom}+Qgauss(abs(({nom})*({spread})/({sig}))))"
        if hoist is not None and full != "0":
            name = f"{prefix}{len(hoist) + 1}"
            g_full = full.replace("Qgauss", "gauss")
            hoist.append(f"{name} = {{{g_full}}}")
            full = name
        expr = expr[:i0] + full + expr[i1:]
    return expr.replace("Qgauss", "gauss")


def rename_lw(expr: str) -> str:
    """l,w (um in the PDK) -> lu,wu (internal variables in um)."""
    expr = re.sub(r"(?<![\w.])l(?![\w.])", "lu", expr)
    return re.sub(r"(?<![\w.])w(?![\w.])", "wu", expr)


# ----------------------------------------------------------------------------
# global .param (models_global.spice, parameters_fet_*.spice)
# ----------------------------------------------------------------------------
def _logical_lines(text: str) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        ln = raw.split(";")[0].rstrip() if not raw.lstrip().startswith("*") else ""
        if not ln.strip():
            continue
        if ln.lstrip().startswith("+") and out:
            out[-1] += " " + ln.lstrip()[1:]
        else:
            out.append(ln.strip())
    return out


def _assignments(s: str) -> list[tuple[str, str]]:
    """'a = 1 b = {x+1} + y ...' -> [(a,'1'),(b,'{x+1} + y')].  The value ends at the next 'name ='."""
    toks = list(re.finditer(r"(?<![\w.])([A-Za-z_]\w*)\s*=(?!=)", s))
    res = []
    for k, m in enumerate(toks):
        end = toks[k + 1].start() if k + 1 < len(toks) else len(s)
        res.append((m.group(1), s[m.end():end].strip()))
    return res


def _value_expr(v: str) -> str:
    """'{A} + B' -> 'A + B' ; '{A}' -> 'A' ; 'A' -> 'A'."""
    v = v.strip()
    if v.startswith("{"):
        depth = 0
        for i, ch in enumerate(v):
            depth += (ch == "{") - (ch == "}")
            if depth == 0:
                return v[1:i] + v[i + 1:]
    return v.strip("'\"")


def translate_params(text: str) -> tuple[list[str], list[str]]:
    """Returns ([LTspice .param lines], [defined names])."""
    lines, names = [], []
    for ln in _logical_lines(text):
        if not re.match(r"\.param\b", ln, re.I):
            continue
        for name, val in _assignments(ln[len(".param"):]):
            e = convert_gauss(_value_expr(val))
            lines.append(f".param {name} = {{{e}}}")
            names.append(name)
    return lines, names


# ----------------------------------------------------------------------------
# devices
# ----------------------------------------------------------------------------
def parse_device(text: str) -> dict:
    """Split subckt, header .param, M line and bins of a models_fet/*.spice file."""
    m = re.search(r"^\.subckt\s+(\S+)\s+(.*)$", text, re.I | re.M)
    name = m.group(1)
    ports = [p for p in m.group(2).split() if "=" not in p]
    first_model = re.search(r"^\.model\b", text, re.I | re.M)
    head = text[m.start():first_model.start()]
    ends = re.search(r"^\.ends\b.*$", text, re.I | re.M)
    models = text[first_model.start():ends.start()]
    lines = _logical_lines(head)[1:]            # without the .subckt line
    params: dict[str, str] = {}
    mline = None
    for ln in lines:
        if re.match(r"\.param\b", ln, re.I):
            for k, v in _assignments(ln[len(".param"):]):
                params[k.lower()] = _value_expr(v)
        elif re.match(r"m\w*\s", ln, re.I):
            mline = ln
    # the header .param sometimes comes without '=' attached to the block (+ ...): already joined by _logical_lines
    if mline is None:
        raise ValueError(f"{name}: M line not found")
    mt = mline.split()
    mname, nodes, model = mt[0], mt[1:5], mt[5]
    rest = " ".join(mt[6:])
    mp = {k.lower(): v for k, v in _assignments(rest)}
    return dict(name=name, ports=ports, params=params, mname=mname, nodes=nodes,
                model=model, mparams=mp, models=models.rstrip() + "\n")



BIN_TOL = 1e-9   # relative tolerance at the bin edges (LTspice: 0.42u -> 4.1999999999999995e-07 < wmin)


def widen_bins(models: str, tol: float = BIN_TOL) -> str:
    """Shift lmin/lmax/wmin/wmax of all bins down by a factor (1-tol).
    The edges remain contiguous, but a nominal value such as W=0.42u (which in double precision
    ends up 1 ulp below wmin=4.2e-7) falls in the right bin instead of in none."""
    def fix(m):
        return f"{m.group(1)} = {float(m.group(2)) * (1.0 - tol):.12g}"
    return re.sub(r"\b(lmin|lmax|wmin|wmax)\s*=\s*([-+]?\d[\d.]*(?:[eE][-+]?\d+)?)", fix, models)


def build_core(dev: dict) -> str:
    """Core subcircuit in METERS for LTspice (bins unchanged)."""
    p, mp = dev["params"], dev["mparams"]
    hoist: list[str] = []
    internal: list[str] = []
    # internal derived values in microns
    nrd_default = rename_lw(_value_expr(p.get("nrd", "0.14/w")))
    nrs_default = rename_lw(_value_expr(p.get("nrs", "0.14/w")))
    inst = {k for k, _ in INST_DEFAULTS}
    for k, v in p.items():                       # swx_* and other derived values
        if k in inst:
            continue
        internal.append((k, rename_lw(convert_gauss(_value_expr(v), hoist))))
    delvto = rename_lw(convert_gauss(_value_expr(mp.get("delvto", "0")), hoist))
    hdr = " ".join(f"{k}={d}" for k, d in INST_DEFAULTS)
    out = [f".subckt {dev['name']} {' '.join(dev['ports'])} mult=1 {hdr}",
           ".param lu = {l*1e6}", ".param wu = {w*1e6}",
           f".param nrd_i = {{if(nrd<0, {nrd_default}, nrd)}}",
           f".param nrs_i = {{if(nrs<0, {nrs_default}, nrs)}}"]
    out += [f".param {h}" for h in hoist]
    out += [f".param {k} = {{{v}}}" for k, v in internal]
    d = dev["nodes"]
    out.append(
        f"{dev['mname']} {' '.join(d)} {dev['model']} l={{l}} w={{w}} ad={{ad}} as={{as}} pd={{pd}} ps={{ps}} "
        f"nrd={{nrd_i}} nrs={{nrs_i}} sa={{sa}} sb={{sb}} sd={{sd}} nf={{nf}} m={{mult}} delvto={{{delvto}}}")
    out.append(widen_bins(dev["models"]).rstrip())
    out.append(f".ends {dev['name']}\n")
    return "\n".join(out)


def build_wrapper(dev: str) -> str:
    """xnfet_*/xpfet_*: computes ad/as/pd/ps/nrd/nrs in meters (same interface as the current wrapper)."""
    kind = "n" if dev.startswith("nfet") else "p"
    short = dev.split("_", 1)[1]
    l = WRAP_DEFAULT_L.get(dev, "0.15u")
    return "\n".join([
        f".subckt x{kind}fet_{short} D G S B",
        f".param l={l} w=1u m=1 nf=1",
        ".param ad = {int((nf+1)/2) * W/nf * 0.29u}",
        ".param as = {int((nf+2)/2) * W/nf * 0.29u}",
        ".param ps = {2*int((nf+2)/2) * (W/nf + 0.29u)}",
        ".param pd = {2*int((nf+1)/2) * (W/nf + 0.29u)}",
        ".param nrd = {0.29u / W}",
        ".param nrs = {0.29u / W}",
        f"X1 D G S B sky130_fd_pr__{dev} l=l w=w nf=nf ad=ad as=as pd=pd ps=ps nrd=nrd nrs=nrs mult=m",
        ".ends\n"])


HEADER_LT = ("* sky130A -> LTspice (generated by make_min_pdk.py --target ltspice)\n"
          "* Geometry in METERS (the original PDK uses microns). Parameters: l w nf ad as pd ps nrd nrs sa sb sd mult\n")


def build_ltspice(src: Path, dst: Path, devices: list[str]) -> list[str]:
    """Generate the LTspice PDK in dst.  src = original sky130A directory."""
    cont = src / "libs.tech" / "combined" / "continuous"
    problems: list[str] = []
    out = dst / LT_DIR
    out.mkdir(parents=True, exist_ok=True)
    LT_SECTIONS.extend(lt_extra_sections(src / "libs.tech" / "combined" / "sky130.lib.spice"))

    # models and wrappers (first, to know which global parameters are needed)
    models, wraps = [HEADER_LT], [HEADER_LT]
    for d in devices:
        dev = parse_device((cont / "models_fet" / f"sky130_fd_pr__{d}.spice").read_text())
        models.append(build_core(dev))
        wraps.append(build_wrapper(d))
    models_txt = "\n".join(models)
    (out / "models_fet.inc").write_text(models_txt)
    (out / "wrappers.inc").write_text("\n".join(wraps))

    # global parameters: only those reached by the models (transitive closure)
    g_lines, g_names = translate_params((cont / "models_global.spice").read_text())
    corner_defs = {}
    for c in LT_CORNERS:
        corner_defs[c] = translate_params((cont / f"parameters_fet_{c}.spice").read_text())
    defs: dict[str, str] = {}
    for ln, nm in zip(g_lines, g_names):
        defs.setdefault(nm.lower(), ln)
    for c in LT_CORNERS:
        for ln, nm in zip(*corner_defs[c]):
            defs.setdefault(nm.lower(), ln)
    ident = lambda s: set(x.lower() for x in re.findall(r"(?<![\w.])[A-Za-z_]\w*", s))
    need, todo = set(), list(ident(models_txt))
    while todo:
        n = todo.pop()
        if n in need or n not in defs:
            continue
        need.add(n)
        todo += list(ident(defs[n].split("=", 1)[1]))
    keep = lambda lines, names: [ln for ln, nm in zip(lines, names) if nm.lower() in need]
    (out / "globals.inc").write_text(HEADER_LT + "\n".join(keep(g_lines, g_names)) + "\n")
    for c in LT_CORNERS:
        (out / f"params_{c}.inc").write_text(HEADER_LT + "\n".join(keep(*corner_defs[c])) + "\n")

    # libs: one section per case in sky130A_ltspice.lib + one flat file per case
    main = [HEADER_LT, "* Usage: .lib \"sky130A_ltspice.lib\" TT   (sections: see MANIFEST_ltspice.txt; same names as sky130.lib.spice + MM MCMM)",
            "* Flat file (e.g. macOS): .lib \"sky130A_ltspice_tt.lib\"\n"]
    for sec, corner, pr, mm in LT_SECTIONS:
        def body(sep):
            return [f".param MC_PR_SWITCH={pr} MC_MM_SWITCH={mm}",
                    ".param corner_factor=1 process_mc_factor=1 mismatch_factor=1",
                    f'.inc "{LT_DIR}{sep}params_{corner}.inc"',
                    f'.inc "{LT_DIR}{sep}globals.inc"',
                    f'.inc "{LT_DIR}{sep}models_fet.inc"',
                    f'.inc "{LT_DIR}{sep}wrappers.inc"']
        main += [f".LIB {sec}"] + body("\\") + [f".ENDL {sec}\n"]
        (dst / f"sky130A_ltspice_{sec.lower()}.lib").write_text(HEADER_LT + "\n".join(body("/")) + "\n")
    (dst / "sky130A_ltspice.lib").write_text("\n".join(main))
    return problems


# ----------------------------------------------------------------------------
# static verification of the LTspice PDK
# ----------------------------------------------------------------------------
_FUNCS = {"sqrt", "if", "gauss", "exp", "abs", "int", "min", "max", "pwr", "ln", "log", "log10", "sin", "cos"}


def verify_ltspice(dst: Path) -> list[str]:
    """Checks without a simulator: existing includes, defined symbols, no ngspice leftovers."""
    problems: list[str] = []
    out = dst / LT_DIR
    texts = {p: p.read_text() for p in list(out.glob("*.inc")) + list(dst.glob("sky130A_ltspice*.lib"))}
    # 1) includes
    for p, t in texts.items():
        if p.suffix != ".lib":
            continue
        for m in re.finditer(r'^\.inc\s+"([^"]+)"', t, re.M | re.I):
            if not (dst / m.group(1).replace("\\", "/")).exists():
                problems.append(f"{p.name}: nonexistent include {m.group(1)}")
    # 2) ngspice leftovers
    for p, t in texts.items():
        for pat, why in ((r"agauss", "unconverted AGAUSS"), (r"^\s*\.options?\s+.*scale", "scale option")):
            if re.search(pat, t, re.I | re.M):
                problems.append(f"{p.name}: {why}")
    # 3) balanced .subckt/.ends
    mt = texts[out / "models_fet.inc"]
    if len(re.findall(r"^\.subckt", mt, re.M | re.I)) != len(re.findall(r"^\.ends", mt, re.M | re.I)):
        problems.append("models_fet.inc: unbalanced .subckt/.ends")
    # 4) undefined symbols in {...} expressions of each section
    for sec, corner, pr, mm in LT_SECTIONS:
        defined = {"mc_pr_switch", "mc_mm_switch", "corner_factor", "process_mc_factor", "mismatch_factor"}
        for fn in ("globals", f"params_{corner}"):
            defined |= {m.group(1).lower() for m in re.finditer(r"^\.param\s+(\w+)\s*=", texts[out / f"{fn}.inc"], re.M | re.I)}
        for fn in ("models_fet", "wrappers"):
            t = texts[out / f"{fn}.inc"]
            scope: set[str] = set()
            for ln in t.splitlines():
                s = ln.strip()
                if s.lower().startswith(".subckt"):
                    scope = {x.split("=")[0].lower() for x in s.split()[2:]} | {"d", "g", "s", "b"}
                    continue
                mp = re.match(r"\.param\s+(\w+)\s*=", s, re.I)
                if not (mp or s[:1] in "Mm" or s.lower().startswith("x1")):
                    continue
                for e in re.findall(r"\{([^}]*)\}", s):
                    for name in re.findall(r"(?<![\w.])[A-Za-z_]\w*", e):
                        n = name.lower()
                        if n in _FUNCS or n in defined or n in scope:
                            continue
                        problems.append(f"section {sec}: undefined symbol '{name}' in {fn}.inc: {s[:70]}")
                if mp:
                    scope |= {x.lower() for x in re.findall(r"([A-Za-z_]\w*)\s*=", s[len(".param"):])}
            if len(problems) > 20:
                return problems
    return problems


def write_manifest_ltspice(dst: Path, devices, problems) -> None:
    out = dst / LT_DIR
    lines = [f"# sky130A -> LTspice  ({_dt.datetime.now():%Y-%m-%d %H:%M})",
             f"devices: {' '.join(devices)}",
             f"sections: {' '.join(s[0] for s in LT_SECTIONS)}",
             f"static verification: {'OK' if not problems else 'WITH PROBLEMS'}"]
    lines += [f"  - {p}" for p in problems]
    lines += ["", "# files (sha256, size)"]
    for p in sorted(list(out.glob("*")) + list(dst.glob("sky130A_ltspice*.lib"))):
        lines.append(f"{sha256(p)}  {p.stat().st_size:>9}  {p.relative_to(dst).as_posix()}")
    lines += ["", "# WARNING: L on a bin edge (see README_ltspice.md and check_bin_edges.py)"]
    lines += _edge_table_lines()
    (dst / "MANIFEST_ltspice.txt").write_text("\n".join(lines) + "\n")


def _load_edges():
    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    try:
        import check_bin_edges as cbe
        return cbe
    except ImportError:
        return None


def _edge_table_lines() -> list[str]:
    cbe = _load_edges()
    if cbe is None:
        return ["  (check_bin_edges.py not found next to the generator: no table)"]
    out = ["  device             L_edge(um)   LT/ng(sens. sw_polycd)  severity"]
    for d, rows in cbe.BIN_EDGES.items():
        for e, r, sev in rows:
            out.append(f"  {d:<17} {e:>10g}  {r:>22.2f}  {sev}")
    return out


README_LT = """# sky130A for LTspice (sky130A_ltspice_min)

## What it is and why it exists

The sky130A PDK is written for ngspice: geometry in micrometers through `.option scale`, random draws with
`AGAUSS`, a `.model` per bin inside the subcircuits and a different structure of corner sections. LTspice
cannot read it. `make_min_pdk.py --target ltspice` translates the 6 continuous FETs
(`nfet_01v8`, `pfet_01v8`, `nfet_01v8_lvt`, `pfet_01v8_lvt`, `nfet_g5v0d10v5`, `pfet_g5v0d10v5`) to LTspice
without needing ngspice or the original LTspice-edited files:

* geometry in METERS (`l=0.15u`, no `.option scale`), parameters `l w nf mult ad as pd ps nrd nrs sa sb sd`;
* per-instance mismatch: the PDK `delvto` is kept and `AGAUSS(0,1,1)` becomes `gauss(1)` in a `.param` inside the
  subcircuit (LTspice draws one value per instance);
* global process variation: `.param` with `gauss(sigma)` at global level (one draw per `.step`);
* `xnfet_*` / `xpfet_*` wrappers that compute `ad/as/pd/ps/nrd/nrs` from `w` and `nf`;
* the same 49 corner sections as `sky130.lib.spice` plus `MM` and `MCMM`, as one flat file per section
  (macOS friendly) and as a single `sky130A_ltspice.lib` with sections.

## Quick use

Put the `.lib` files and the `sky130A_ltspice/` folder together (next to your `.asc` / `.cir`), or give the
absolute path in quotes.

    .lib "sky130A_ltspice_tt.lib"        (tt ss ff sf fs: deterministic)
    .lib "sky130A_ltspice_mc.lib"        + .step param run 1 300 1   (global process variation)
    .lib "sky130A_ltspice_mm.lib"        (per-instance mismatch)
    .lib "sky130A_ltspice_mcmm.lib"      (both)

Sections: the same 49 of `sky130.lib.spice` (tt ss ff sf fs, ll hl lh hh, ss_ll ... ff_hh, all the `_mm` ones and
`mc`) plus `MM` and `MCMM` (mismatch only / process + mismatch with tt parameters). They are used the same way:

    .lib "sky130A_ltspice.lib" ss_hl      or the flat file   .lib "sky130A_ltspice_ss_hl.lib"

The res/cap suffixes (ll hl lh hh) only change resistors and capacitors, which are not translated: for these 6 FETs
they give EXACTLY the same as their base corner (`ss_hl == ss`). They exist so that a netlist can change section
without editing names. The `_mm` suffix means per-instance mismatch is on; `mc` is global process variation (use it
with `.step param run 1 N 1`). The original does not define `sf_lh` or `sf_lh_mm`; neither does this one.

## How to instantiate the transistors

Use the wrappers. Subcircuit parameters: `l w nf m` (default `l` depends on the device, `w=1u`, `nf=1`, `m=1`).
`ad as pd ps nrd nrs` are computed from `w` and `nf`. Units are SI: write `l=0.15u w=2u`.

    X1 d g s b xnfet_01v8 l=0.15u w=1u nf=1 m=1
    X2 d g s b xpfet_01v8 l=0.15u w=2u

| Wrapper | Device |
|---|---|
| `xnfet_01v8`, `xpfet_01v8` | 1.8 V |
| `xnfet_01v8_lvt`, `xpfet_01v8_lvt` | 1.8 V low-Vt |
| `xnfet_g5v0d10v5`, `xpfet_g5v0d10v5` | 5 V |

The core subcircuits `sky130_fd_pr__nfet_01v8`, ... are also available (they take `mult` instead of `m`, and
`ad as pd ps nrd nrs` must be given by you; `nrd = nrs = -1` means "PDK default").

In a schematic use the `xnch` / `xpch` symbols of the repository (`LTspice/sky130A/xnch.asy`, `xpch.asy`): set
`SpiceModel` to the wrapper name (for example `xnfet_01v8`), `Value` to `w=1u` and `Value2` to `l=0.15u`.

### Example: CMOS inverter

    * CMOS inverter - sky130A (LTspice)
    .lib "sky130A_ltspice_tt.lib"
    Xp out in vdd vdd xpfet_01v8 l=0.15u w=2u
    Xn out in 0 0     xnfet_01v8 l=0.15u w=1u
    Vdd vdd 0 1.8
    Vin in 0 pulse(0 1.8 0.2n 50p 50p 1n 2n)
    Cl out 0 10f
    .tran 10p 6n
    .meas tran tpHL TRIG V(in) VAL=0.9 RISE=1 TARG V(out) VAL=0.9 FALL=1
    .meas tran tpLH TRIG V(in) VAL=0.9 FALL=1 TARG V(out) VAL=0.9 RISE=1
    .end

Reference values from ngspice with the original PDK and the same geometry and the same `ad/as/pd/ps/nrd/nrs`
that the wrapper computes: `tpHL = 40.55 ps`, `tpLH = 50.88 ps` (the same values come out of the translated
libs run in ngspice). The LTspice transient of this exact circuit has not been compared; for DC the agreement is
shown in the next section.

### Example: Monte Carlo (300 runs)

    .lib "sky130A_ltspice_mcmm.lib"
    .step param run 1 300 1
    * circuit as above, plus a measurement of interest, e.g. .meas tran tpHL ...

To measure DC quantities under `.step`, use a dummy sweep and `.meas DC`; `.meas OP` fails with `.step`:

    V9 x9 0 0
    R9 x9 0 1k
    .dc V9 0 1 1
    .meas DC id1 FIND I(Vd1) AT 0

## ngspice vs LTspice comparison

| Check | Result |
|---|---|
| Translated libs vs full PDK, both in ngspice (`--smoke-test`): 24 deterministic sections, Id and Cgg of 23 geometries (bins, `nf`, `mult`), core and wrapper | difference 0 |
| Deterministic OP in LTspice (`test1_op_tt.cir`), 23 geometries incl. `nf=2 m=2` and W bin edges | max 0.0005 % vs ngspice |
| `gauss(x)` in LTspice | N(0, sigma = x) (checked in LTspice with gf180 `test0`, sigma 0.326 for `gauss(1/3)` and 0.972 for `(1/3)*gauss(3)`) |

Monte Carlo, sigma/mean of Id (LTspice measured / ngspice reference), W = 2u, nfet and pfet:

| Case | Runs | nfet | pfet | Notes |
|---|---|---|---|---|
| `mc`, L = 0.55u (inside a bin) | 300 | 0.59 % / 0.61 % | 0.74 % / 0.76 % | identical pairs: correlation 1.000 |
| `mc`, L = 0.5u (bin edge) | 1000 | 0.60 % / 0.70 % | 0.84 % / 0.76 % | edge effect, see below |
| `mm`, L = 0.5u | 300 | 1.67 % / 1.65 % | 2.01 % / 2.06 % | correlation 0.05, sd(di)/sd(i) = 1.38 (1.41 expected) |
| `mcmm`, L = 0.5u | 300 | 1.80 % / 1.94 % | 2.11 % / 2.23 % | correlation 0.18, sd(di)/sd(i) = 1.27 |

With 300 runs the sigma has about 4 % relative uncertainty on each side. The `mismatch` with `nf` or `m`
different from 1 has NOT been validated in LTspice (the area formula is the one from the PDK).

## WARNING: do not use L exactly on a bin edge

The models are binned in L. With L exactly equal to an edge, the response to global process variation
(`sw_polycd`) differs between LTspice and ngspice (in ngspice there is also a change of slope near the edge). With
L = edge + 10 nm they agree to three decimals on the 45 edges measured. It affects ONLY the sigma of the process
Monte Carlo; the nominal operating point and the corners agree to ~1e-5 on the edge as well.

Recommendation: use L >= edge + 10 nm (0.51u instead of 0.5u, 1.01u instead of 1u, ...). If you need L exactly on
the edge, compare with ngspice before trusting the sigma.

L edges (um) and LT/ng ratio of the sensitivity to `sw_polycd` measured AT the edge
(high: >25 % or opposite sign; medium: 5-25 %; low: <5 %):

@@TABLE@@

W edges (um), not measured in MC: 0.42, 0.55 (depending on the device), 0.75 (5 V), 1, 3, 5, 7, 15, 20.

Detail: measured only at L = edge and L = edge + 10 nm (not below the edge), with W = 2u, sweeping
`sw_polycd` = -3, 0, +3 nm (`test4_bin_edges.cir`).

Automatic warning:

    python check_bin_edges.py my_circuit.cir other.net schematic.asc

It checks lines `X.. xnfet_01v8 l=0.5u ..` (and `.asc` files with SYMBOL / SpiceLine); tolerance 5 nm; exit code 2 if
there is an L on an edge. L values given by `.param` or expressions appear as "note": check them by hand. With the
generator: `python make_min_pdk.py --target ltspice ... --check-netlist my_circuit.cir`.

## Limitations

* Only the 6 FETs. No resistors, capacitors, BJTs or diodes.
* `ll hl lh hh` do not change anything for these FETs (see above).
* Mismatch with `nf`/`m` different from 1: not validated in LTspice.
* Validated in LTspice 26.0.1 for Windows. It is built to work in LTspice for macOS (flat files, no relative
  includes beyond the `sky130A_ltspice/` folder) but it has not been run there.
* The random sequence of LTspice is reproducible: different netlists with the same structure show almost the same
  sampling deviation, so do not treat different cases as independent samples.

## Files

    sky130A_ltspice_<section>.lib     flat file per section (+ sky130A_ltspice.lib with all of them)
    sky130A_ltspice/                  models_fet.inc, wrappers.inc, globals.inc, params_<corner>.inc
    check_bin_edges.py                bin-edge warning
    test1_op_tt.cir                   deterministic OP vs ngspice
    test2_mc_*.cir                    Monte Carlo (mc, mm, mcmm, L = 0.5u and 0.55u, 1000 runs)
    test3_polycd_diag.cir, test4_bin_edges.cir, sky130A_ltspice_diag.lib   bin-edge diagnostics
    MANIFEST_ltspice.txt              sha256 of every generated file

## Regenerate

Requires Python 3.9+ (ngspice only for `--smoke-test`). Input: a complete `sky130A` directory.

    python make_min_pdk.py --target ltspice --src PATH/sky130A --dst sky130A_ltspice_min --force [--smoke-test]

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Unknown subcircuit called in: xnfet_01v8` | The library was not found or not loaded. Check the `.lib` path (absolute path in quotes) and that `sky130A_ltspice/` is next to the `.lib`. |
| `.meas OP` FAILS with `.step` | Use the dummy `.dc V9 0 1 1` and `.meas DC ... AT 0`. |
| Sigma of an MC run differs from ngspice by tens of % | Check L for a bin edge (`check_bin_edges.py`). |

## License

Derived from the SkyWater sky130 PDK (Apache License 2.0, Copyright The SkyWater PDK Authors). The
tools are provided as they are, with no warranty.
"""


def write_readme_lt(dst: Path) -> None:
    cbe = _load_edges()
    table = "\n".join("    " + l.strip() if l.strip() else l for l in _edge_table_lines())
    (dst / "README_ltspice.md").write_text(README_LT.replace("@@TABLE@@", table))
    if cbe is not None:
        shutil.copy2(Path(cbe.__file__), dst / "check_bin_edges.py")


# ----------------------------------------------------------------------------
# smoke test of the LTspice PDK (uses ngspice as a stand-in: LTspice is not needed)
# ----------------------------------------------------------------------------
_SMOKE_GEOS = {  # device: (type, Vdd, [(L_um, W_um, nf, mult)])
    "nfet_01v8": ("n", 1.8, [(0.15, 1, 1, 1), (0.5, 2, 2, 2), (1, 5, 1, 1), (0.18, 0.42, 1, 1), (0.15, 0.42, 1, 1), (0.5, 0.55, 1, 1)]),
    "pfet_01v8": ("p", 1.8, [(0.15, 1, 1, 1), (0.5, 2, 2, 2), (1, 5, 1, 1), (0.15, 0.55, 1, 1), (0.18, 0.55, 1, 1)]),
    "nfet_01v8_lvt": ("n", 1.8, [(0.15, 1, 1, 1), (0.5, 2, 2, 2), (1, 5, 1, 1)]),
    "pfet_01v8_lvt": ("p", 1.8, [(0.35, 1, 1, 1), (0.5, 2, 2, 2), (1, 5, 1, 1)]),
    "nfet_g5v0d10v5": ("n", 5.0, [(0.5, 1, 1, 1), (1, 2, 2, 2), (2, 5, 1, 1)]),
    "pfet_g5v0d10v5": ("p", 5.0, [(0.5, 1, 1, 1), (1, 2, 2, 2), (2, 5, 1, 1)]),
}


def _ng_version(text: str, mode: str) -> str:
    """Convert LTspice syntax -> ngspice so it can be tested with ngspice.
    mode='det': gauss(x) -> 0 ;  mode='mc': gauss(x) -> agauss(0,x,1)."""
    while True:
        r = _find_call(text, "gauss")
        if not r:
            break
        rep = "0" if mode == "det" else f"agauss(0,{r[2][0]},1)"
        text = text[:r[0]] + rep + text[r[1]:]
    while True:
        r = _find_call(text, "if")
        if not r:
            break
        a = r[2]
        text = text[:r[0]] + f"ternary_fcn({a[0]},{a[1]},{a[2]})" + text[r[1]:]
    return text


def _ng_copy(dst: Path, tmp: Path, mode: str) -> Path:
    ng = tmp / f"ng_{mode}"
    shutil.copytree(dst, ng)
    for f in (ng / LT_DIR).glob("*.inc"):
        f.write_text(_ng_version(f.read_text(), mode))
    return ng


def _smoke_net_lt(libline: str, mode: str, devices, corner_sec: str) -> str:
    """mode: full | core | wrap.  Returns a netlist with .op and .ac (Cgg) of every device."""
    body, k = "", 0
    for dev in devices:
        ty, vdd, geos = _SMOKE_GEOS[dev]
        for (l, w, nf, m) in geos:
            k += 1
            sg = 1 if ty == "n" else -1
            body += (f"Vd{k} d{k} 0 {0.5 * vdd * sg}\nVg{k} g{k} 0 dc {0.6 * vdd * sg} ac 1\n"
                     f"Vs{k} s{k} 0 0\nVb{k} b{k} 0 0\n")
            ad = int((nf + 1) / 2) * w / nf * 0.29
            as_ = int((nf + 2) / 2) * w / nf * 0.29
            ps = 2 * int((nf + 2) / 2) * (w / nf + 0.29)
            pd = 2 * int((nf + 1) / 2) * (w / nf + 0.29)
            nm = f"sky130_fd_pr__{dev}"
            n = f"d{k} g{k} s{k} b{k}"
            if mode == "full":
                body += (f"X{k} {n} {nm} L={l} W={w} nf={nf} ad={ad} as={as_} pd={pd} ps={ps} "
                         f"nrd={0.29 / w} nrs={0.29 / w} m={m} mult={m}\n")
            elif mode == "core":
                body += (f"X{k} {n} {nm} l={l * 1e-6} w={w * 1e-6} nf={nf} ad={ad * 1e-12} as={as_ * 1e-12} "
                         f"pd={pd * 1e-6} ps={ps * 1e-6} nrd={0.29 / w} nrs={0.29 / w} mult={m}\n")
            else:
                body += f"X{k} {n} x{ty}fet_{dev.split('_', 1)[1]} l={l * 1e-6} w={w * 1e-6} nf={nf} m={m}\n"
    scale = ".option scale=1u\n" if mode == "full" else ""
    ctl = (".control\nop\n" + "".join(f"print i(vd{j})\n" for j in range(1, k + 1))
           + "ac lin 1 1meg 1meg\n" + "".join(f"print i(vg{j})\n" for j in range(1, k + 1)) + ".endc\n")
    return f"* smoke {mode}\n{libline}\n{scale}{body}{ctl}.end\n"


def _smoke_parse(out: str):
    ids, cgs = [], []
    for ln in out.splitlines():
        m = re.match(r"^i\((v[dg])(\d+)\)\s*=\s*(.*)$", ln.strip())
        if not m:
            continue
        v = [float(x) for x in re.findall(r"[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?", m.group(3))]
        (ids if m.group(1) == "vd" else cgs).append(v[0] if m.group(1) == "vd" else v[-1])
    return ids, cgs


def smoke_test_ltspice(src: Path, dst: Path, devices) -> bool:
    """Compare in ngspice the full PDK with the translation (core and wrapper) in tt/ss/ff/sf/fs:
    DC current and Cgg of several geometries (bins, nf, mult). With gauss -> 0 they must match."""
    ng = shutil.which("ngspice")
    if not ng:
        print("LTspice smoke-test: ngspice not found")
        return False
    devs = [d for d in devices if d in _SMOKE_GEOS]
    full = (src / "libs.tech" / "combined" / "sky130.lib.spice").resolve()
    ok, worst = True, 0.0
    print("\nLTspice smoke-test (numerical equivalence in ngspice, gauss -> 0):")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        ngdet = _ng_copy(dst, tmp, "det")

        def run(net: str, tag: str):
            p = tmp / f"{tag}.cir"
            p.write_text(net)
            r = subprocess.run([ng, "-b", str(p)], capture_output=True, text=True, timeout=900)
            return _smoke_parse(r.stdout + r.stderr)

        for c in [x[0].lower() for x in LT_SECTIONS if x[2] == 0 and x[3] == 0]:  # deterministic only
            res = {"full": run(_smoke_net_lt(f".lib {full} {c}", "full", devs, c), f"{c}_full")}
            for mode in ("core", "wrap"):
                res[mode] = run(_smoke_net_lt(f".include {ngdet}/sky130A_ltspice_{c}.lib", mode, devs, c),
                                f"{c}_{mode}")
            n = len(res["full"][0])
            w_c = 0.0
            for mode in ("core", "wrap"):
                for kind in (0, 1):
                    a, b = res["full"][kind], res[mode][kind]
                    if n == 0 or len(a) != len(b):
                        ok = False
                        w_c = float("inf")
                        continue
                    w_c = max(w_c, max(abs(x - y) / max(abs(x), 1e-30) for x, y in zip(a, b)))
            worst = max(worst, w_c)
            print(f"  {c}: {n} geometries, max relative difference (Id and Cgg, core and wrapper) = {w_c:.2e}")
    ok &= worst < 1e-5
    print("  result: " + ("OK" if ok else "FAILED"))
    return ok


# ----------------------------------------------------------------------------
def main(argv=None) -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(
        description="Generate a reduced sky130A PDK (FETs only) for ngspice.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--target", choices=("ngspice", "ltspice"), default="ngspice",
                    help="ngspice: reduced PDK (default). ltspice: PDK translated to LTspice "
                         "(meters, delvto with gauss, xnfet_/xpfet_ wrappers, MC via .step)")
    ap.add_argument("--src", type=Path, default=here / "sky130A",
                    help="original sky130A directory (contains libs.tech/). "
                         "Default: <script folder>/sky130A")
    ap.add_argument("--dst", type=Path, default=None,
                    help="output directory. Default: <script folder>/sky130A_min")
    ap.add_argument("--devices", nargs="+", default=list(DEFAULT_DEVICES),
                    help="devices to keep, without the sky130_fd_pr__ prefix "
                         f"(default: {' '.join(DEFAULT_DEVICES)})")
    ap.add_argument("--force", action="store_true", help="overwrite --dst if it exists")
    ap.add_argument("--split-sections", action="store_true",
                    help="additionally generate one lib per section in libs.tech/combined/sections/ "
                         "(much faster to load than the multi-section file)")
    ap.add_argument("--check-netlist", nargs="+", metavar="NETLIST",
                    help="check whether the netlists only use devices of the reduced PDK")
    ap.add_argument("--smoke-test", action="store_true",
                    help="compare DC currents full vs reduced (requires ngspice)")
    args = ap.parse_args(argv)

    src = args.src.resolve()
    dst = (args.dst or here / ("sky130A_ltspice_min" if args.target == "ltspice" else "sky130A_min")).resolve()
    devices = list(dict.fromkeys(args.devices))

    if args.target == "ltspice":
        if dst.exists() and not args.force:
            print(f"{dst} already exists; use --force to overwrite", file=sys.stderr)
            return 1
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir(parents=True)
        build_ltspice(src, dst, devices)
        problems = verify_ltspice(dst)
        write_manifest_ltspice(dst, devices, problems)
        write_readme_lt(dst)
        n_files = sum(1 for _ in dst.rglob("*") if _.is_file())
        print(f"LTspice PDK: {dst}  ({n_files} files)")
        print("  static verification: " + ("OK" if not problems else "WITH PROBLEMS"))
        for pr in problems:
            print(f"  - {pr}")
        ok = not problems
        if args.check_netlist:
            cbe = _load_edges()
            if cbe is None:
                print("check_bin_edges.py not found next to the generator")
            else:
                print()
                if cbe.main(list(args.check_netlist)):
                    print("  (there is an L on a bin edge: see README_ltspice.md)")
        if args.smoke_test:
            ok &= smoke_test_ltspice(src, dst, devices)
        return 0 if ok else 1

    only_checks = ((args.check_netlist or args.smoke_test or args.split_sections)
                   and dst.exists() and not args.force)
    problems: list[str] = []
    if not only_checks:
        problems = build(src, dst, devices, force=args.force, split=args.split_sections)
    elif args.split_sections:
        files, problems = split_sections(dst)
        update_manifest_split(dst, files)
        print(f"per-section libs regenerated: {len(files)} files in "
              f"{dst / 'libs.tech' / 'combined' / SECTIONS_DIR}")
        print("  verification: " + ("OK" if not problems else "WITH PROBLEMS"))
        for pr in problems:
            print(f"  - {pr}")

    ok = not problems
    if args.check_netlist:
        print()
        ok &= check_netlists(args.check_netlist, dst, devices)
    if args.smoke_test:
        print()
        ok &= smoke_test(src, dst, devices)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
