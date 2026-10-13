#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_min_gf180.py - segmented (flat, self-contained) LTspice libs of the gf180mcuD PDK.

Input  : the NATIVE sm141064.ngspice of the PDK (the one shipped by open_pdks / gf180mcu-pdk).
Output : one file per corner/case, e.g. gf180mcuD_ltspice_tt.lib, WITHOUT nested `.lib`,
         WITHOUT relative paths and WITHOUT depending on design.ngspice or gf180mcuD_ltspice.lib:
             .include "gf180mcuD_ltspice_tt.lib"
         and that is it (models + parameters + xnfet_*/xpfet_* subcircuits with ad/as/pd/ps/nrd/nrs).
Designed for macOS (LTspice for Mac): a single file per case, ASCII, LF line endings,
no relative includes, without the 1.3 MB / 47 000-line file.

What it does
  * Reduces: only the requested devices (by default 3.3 V and 6 V nfet/pfet; the 05v0 ones are
    taken from the 06v0) and only the global parameters those models need.
  * Resolves the nesting `.lib 'sm141064.ngspice' X` of every native section (typical, ss, ff, sf,
    fs, statistical) and flattens it.
  * Translates to LTspice: AGAUSS(nom,abs,sig) -> gauss(abs/sig) (in LTspice gauss(x) = N(0,sigma=x));
    a global parameter is drawn once per .step; mismatch (mis_vth) is drawn per
    instance (it lives inside the subcircuit).  mulu0 does not exist in LTspice: the k mismatch
    (mis_k) is NOT modeled (see README).  The *_dss subcircuits (SAB, which use the ?: operator) are omitted.
  * Cases (names as in the sky130 version):
        tt ss ff sf fs                    deterministic (default design.ngspice: no MC)
        tt_mm ss_mm ff_mm sf_mm fs_mm     per-instance mismatch on that corner (mm = tt_mm)
        mc                                global process variation (statistical lib)
        mcmm                              process + mismatch

Usage
    python make_min_gf180.py --src DIR_with_sm141064 --dst gf180mcuD_ltspice_min --force
    python make_min_gf180.py ... --devices nfet_03v3 pfet_03v3          (3.3 V only)
    python make_min_gf180.py ... --smoke-test                           (compare with native in ngspice)
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_min_pdk as mp  # noqa: E402  (convert_gauss, translate_params)

SRC_NAME = "sm141064.ngspice"
DEFAULT_DEVICES = ["nfet_03v3", "pfet_03v3", "nfet_06v0", "pfet_06v0"]
KNOWN_DEVICES = DEFAULT_DEVICES + ["nfet_06v0_nvt"]
ALIAS_05V0 = {"nfet_06v0": "nfet_05v0", "pfet_06v0": "pfet_05v0"}
OUT_PREFIX = "gf180mcuD_ltspice_"

# case: (native section, sw_stat_global, sw_stat_mismatch)
CASES = {
    "tt": ("typical", 0, 0), "ss": ("ss", 0, 0), "ff": ("ff", 0, 0),
    "sf": ("sf", 0, 0), "fs": ("fs", 0, 0),
    "tt_mm": ("typical", 0, 1), "ss_mm": ("ss", 0, 1), "ff_mm": ("ff", 0, 1),
    "sf_mm": ("sf", 0, 1), "fs_mm": ("fs", 0, 1),
    "mm": ("typical", 0, 1),
    "mc": ("statistical", 1, 0), "mcmm": ("statistical", 1, 1),
}
# parameters that in the native PDK come from design.ngspice (set per case here)
PRELUDE_NAMES = {"sw_stat_global", "sw_stat_mismatch", "mc_skew", "res_mc_skew", "cap_mc_skew", "fnoicor"}
MODEL_LIB = re.compile(r"^(?P<dev>[np]fet_\d\dv\d(?:_nvt)?)_(?P<c>t|f|s|fs|sf|stat)$", re.I)
# default wrapper geometry: (L, W)
WRAP_DEFAULT = {
    "nfet_03v3": ("0.28u", "2u"), "pfet_03v3": ("0.28u", "2u"),
    "nfet_05v0": ("0.6u", "2u"), "pfet_05v0": ("0.5u", "2u"),
    "nfet_06v0": ("0.7u", "2u"), "pfet_06v0": ("0.55u", "2u"),
    "nfet_06v0_nvt": ("1.8u", "2u"),
}

README_GF = """# gf180mcuD for LTspice (macOS and Windows): flat, segmented libraries

## What it is and why it exists

The native gf180mcuD model file (`sm141064.ngspice`, 47 764 lines, 1.3 MB) is written for ngspice: nested
`.lib 'sm141064.ngspice' <section>` calls, parameters that come from a separate `design.ngspice`, random draws
with `AGAUSS`, the `?:` operator in the SAB subcircuits and the instance parameter `mulu0` for the k mismatch.
LTspice cannot read it as it is, and editing the file by hand every time the PDK changes is error prone.

`make_min_gf180.py` generates, from the NATIVE file, one library per case:

* **flat and self-contained** (about 160 KB, 7 700 lines instead of 47 764): no nested `.lib`, no relative paths,
  no dependence on `design.ngspice`;
* **segmented**: one file per corner / Monte Carlo case, so LTspice only reads what the simulation needs;
* **reduced**: only the requested devices (by default the 3.3 V and 6 V nfet/pfet, with the 5 V ones taken from the
  6 V models) and only the global parameters those models use;
* **translated to LTspice**: `AGAUSS(nom,abs,sig)` becomes `gauss(abs/sig)`; a global parameter is drawn once
  per `.step`; mismatch is drawn per instance;
* **ASCII, LF line endings, one file per case**: it works the same on macOS and Windows.

## Cases (files `gf180mcuD_ltspice_<case>.lib`)

| Case | Native section | sw_stat_global | sw_stat_mismatch | Use |
|---|---|---|---|---|
| `tt`, `ss`, `ff`, `sf`, `fs` | typical, ss, ff, sf, fs | 0 | 0 | deterministic corners |
| `tt_mm`, `ss_mm`, `ff_mm`, `sf_mm`, `fs_mm` (`mm` = `tt_mm`) | same | 0 | 1 | per-instance mismatch on that corner |
| `mc` | statistical | 1 | 0 | global process variation |
| `mcmm` | statistical | 1 | 1 | process + mismatch |

`mc_skew`, `res_mc_skew`, `cap_mc_skew` = 3 and `fnoicor` = 0 (values from `design.ngspice`) are at the top of each file.

## How to use it

One line in the netlist or in the schematic (the lib has no sections, so `.lib "file"` works):

    .lib "gf180mcuD_ltspice_tt.lib"

* Put the `.lib` files in the same folder as your `.asc` / `.cir`, or use the absolute path in quotes
  (for example `.lib "gf180mcuD_PDK/gf180mcuD_ltspice_tt.lib"`).
* Switching case is a change of file name: `..._ss.lib`, `..._mcmm.lib`, ...
* Monte Carlo: `.lib "gf180mcuD_ltspice_mcmm.lib"` and `.step param run 1 300 1`.

### Instantiating the transistors

Wrappers `xnfet_03v3`, `xpfet_03v3`, `xnfet_06v0`, `xpfet_06v0`, `xnfet_05v0`, `xpfet_05v0`
(and `xnfet_06v0_nvt` if generated with it). Parameters: `l w nf m`. `ad as pd ps nrd nrs` are computed from `w` and `nf`.
Units are SI (`l=0.28u w=2u`).

    X1 d g s b xnfet_03v3 l=0.28u w=2u nf=1 m=1

Default `l` / `w` of the wrappers: 03v3: 0.28u / 2u; 05v0: nfet 0.6u, pfet 0.5u / 2u; 06v0: nfet 0.7u, pfet 0.55u / 2u.

In a schematic use the `xnch` / `xpch` symbols of the repository (`LTspice/gf180mcuD/xnch.asy`, `xpch.asy`):
`SpiceModel` = `xnfet_03v3`, `Value` = `w=2u`, `Value2` = `l=0.28u`. See `DC_Sweep_03V3.asc`.

### Example: CMOS inverter

    * CMOS inverter - gf180mcuD (LTspice)
    .lib "gf180mcuD_ltspice_tt.lib"
    Xp out in vdd vdd xpfet_03v3 l=0.28u w=4u
    Xn out in 0 0     xnfet_03v3 l=0.28u w=2u
    Vdd vdd 0 3.3
    Vin in 0 pulse(0 3.3 0.2n 100p 100p 1n 2n)
    Cl out 0 20f
    .tran 10p 6n
    .meas tran tpHL TRIG V(in) VAL=1.65 RISE=1 TARG V(out) VAL=1.65 FALL=1
    .meas tran tpLH TRIG V(in) VAL=1.65 FALL=1 TARG V(out) VAL=1.65 RISE=1
    .end

Reference from ngspice with the native PDK (`design.ngspice` + `sm141064.ngspice`, section `typical`) and the same
geometry and `ad/as/pd/ps/nrd/nrs`: `tpHL = 63.73 ps`, `tpLH = 69.53 ps` (the generated library run in ngspice gives
exactly the same). The LTspice transient of this circuit has not been compared; the DC comparisons are below.

To measure DC quantities under `.step`, use a dummy sweep and `.meas DC` (`.meas OP` fails with `.step`):

    V9 x9 0 0
    R9 x9 0 1k
    .dc V9 0 1 1
    .meas DC id0 FIND I(Vd0) AT 0

## What changes with respect to the native PDK / to a hand-edited sm141064

1. **Random draws:** `agauss(0,1,3)` -> `gauss((1)/(3))`. In LTspice `gauss(x)` is N(0, sigma = x), so sigma = 1/3, the
   same as ngspice (`{(1/3)*gauss(3)}` would give sigma = 1; `test0_gauss_sigma.cir` checks it).
2. **Mismatch:** `delvto='mis_vth*sw_stat_mismatch'` is kept and drawn per instance. **`mulu0` is omitted**
   (LTspice does not support it), so the mobility mismatch `mis_k` is not modelled. In ngspice, with and without
   `mulu0`, the sigma of Id is practically the same (1.29 % vs 1.33 %, 500 samples).
3. **pd / ps:** the wrappers use the perimeter `2*int((nf+1)/2)*(W/nf+0.18u)` (convention of the gf180mcu xschem
   symbols). In the old `gf180mcuD_ltspice.lib`, pd/ps were like ad/as (an area, not a perimeter), which cancelled the
   sidewall capacitances of the junctions: Cdd changes by ~20-30 % (nfet L = 0.28u W = 2u: 1.93 fF -> 2.30 fF at
   Vds = 0); Id and Cgg do not change. `--legacy-wrapper` reproduces the old behaviour.
4. **Omitted:** the `*_dss` subcircuits (SAB, they use the `?:` operator) and the resistors, capacitors, BJTs and
   diodes. `--keep-dss` keeps the SAB ones (with `?:` -> `if()`).
5. **nf:** the old wrapper did not pass `nf` to the model (always `nf=1`, although ad/as/pd/ps did use it); now it does.
   Effect on Id (nfet L = 0.6u): nf = 2, W = 4u: +2.3 %; nf = 4, W = 10u: +0.6 %; nf = 8, W = 20u: +0.7 %.
6. Only the global parameters used by the selected models are kept.

## ngspice vs LTspice comparison

**Libraries vs native PDK, both in ngspice (`--smoke-test`):** with the random draws replaced by constants, Id (2
biases) and Cgg of 22 devices / geometries (several bins, `nf`, `m`, L and W) in the 12 deterministic and mismatch
cases: maximum relative difference 0 (identical). It validates corners, `nf`/`m`, mismatch (`delvto`) and the wiring of
the statistical parameters. It does not validate the LTspice engine; that is what the tests below do.

**Deterministic OP in LTspice 26.0.1 (`test1_op_<case>.cir`)**, Id of 12 devices / geometries (including `nf=2 m=2`)
against ngspice with the native PDK:

| Case | tt | ss | ff | sf | fs |
|---|---|---|---|---|---|
| Max difference | 0.023 % | 0.032 % | 0.016 % | 0.023 % | 0.028 % |

**Random draws:** `test0_gauss_sigma.cir`, 1000 steps: `gauss(1/3)` -> sigma 0.326, `(1/3)*gauss(3)` -> sigma 0.972, so
`gauss(x)` = N(0, sigma = x).

**Monte Carlo and mismatch in LTspice (`test3_mc_<case>.cir`)**: 300 runs, six transistors
(nfet / pfet 03v3 L = 0.55u, 06v0 L = 0.75u, 05v0 L = 0.6u, all W = 2u), against ngspice (the same libs with
`gauss` -> `agauss`, different seeds).

| Case | Mean of Id | sigma/mean |
|---|---|---|
| `mc` | within 0.45 % | -8 % ... +3 % |
| `mcmm` | within 0.45 % | -8 % ... +3 % |
| `mm`, `ss_mm`, `ff_mm`, `sf_mm`, `fs_mm` | within 0.13 % | 06v0 / 05v0: -5 % ... +7 %; 03v3: -9 % ... -13 % (see below) |
| `mm`, 1000 runs (`test3_mc_mm_1000.cir`), ngspice 3000 runs | within 0.02 % | all six devices: -7 % ... +4 % |
| `mm`, `pfet_03v3` only, 3000 runs (`test3_mc_mm_pfet03v3_3000.cir`), ngspice 6000 runs | mean 130.76 uA vs 130.72 uA (+0.03 %) | -4.4 % (0.603 % vs 0.631 %) |

With 300 runs the sigma has about 4 % relative uncertainty in LTspice and in ngspice. The apparent bias of -10 %
to -13 % in the 03v3 mismatch with 300 runs was sampling noise: with 1000 runs it is -2 % (nfet) and -7 % (pfet,
about 3 combined sigmas, the only value that stays a bit high). A dedicated 3000-run test of pfet_03v3 gives -4.4 %
(about 2.7 combined sigmas): a small residual, probably real, difference in the pfet_03v3 mismatch of at most a few
percent of sigma (0.03 pp of absolute sigma/mean); the mean current agrees within 0.03 %, so it has no practical impact. In LTspice the random sequence seems reproducible per
run index, so the five `*_mm` cases show almost the same deviation: they are not five independent samples.
Correlations behave as expected (instance mismatch ~0; global MC: n-n 0.66-0.97, n-p 0.42).

**Bin edges (`test2_mc_<case>.cir`):** nfet / pfet 03v3 at L = 0.5u (edge) and 0.55u (not an edge) are compared with
ngspice; see Known limitations for the rule.

## Known limitations

* **Bin edges:** BSIM4 level 54 is binned (`lmin/lmax/wmin/wmax`). When L is *exactly* on an internal bin edge (for
  example nfet_06v0 L = 0.7u, where bins .0 and .1 share `lmax = lmin = 0.7e-6`) LTspice deviates by ~1.7 % from ngspice,
  which is continuous there. Avoid L exactly on an edge (rule used for sky130: edge + 10 nm). Away from the edges
  the difference is < 0.04 %. That is why `test1` uses L = 0.75u for the nfet_06v0.
* **`mis_k` (`mulu0`) mismatch is not modelled.**
* Only FETs: no resistors, capacitors, BJTs, diodes or SAB (`*_dss`) variants unless `--keep-dss`.
* Validated in LTspice 26.0.1 for Windows. The files are made for LTspice for macOS (flat, ASCII, LF, no relative
  includes) but they have not been run there.

## Files

    gf180mcuD_ltspice_<case>.lib      13 libraries (tt ss ff sf fs, *_mm, mm, mc, mcmm)
    test0_gauss_sigma.cir             sigma of gauss()
    test1_op_<case>.cir               deterministic OP vs ngspice (tt ss ff sf fs)
    test2_mc_{mc,mm,mcmm}.cir         MC, 300 runs, L = 0.5u vs 0.55u
    test3_mc_<case>.cir               MC / mismatch with 03v3, 06v0 and 05v0 (7 cases)
    test3_mc_mm_1000.cir              mismatch with 1000 runs
    test3_mc_mm_pfet03v3_3000.cir     mismatch of pfet_03v3 only, 3000 runs
    MANIFEST_gf180_ltspice.txt        sha256 of every library
    tools/                            generator and test scripts

## Regenerate

Requires Python 3.9+; ngspice for `--smoke-test` and `--write-tests`. Input: the folder with the native
`sm141064.ngspice` (and `design.ngspice` for the tests), as distributed by open_pdks / gf180mcu-pdk.

    python make_min_gf180.py --src FOLDER_WITH_sm141064.ngspice --dst gf180mcuD_ltspice_min --force --smoke-test --write-tests
    python make_min_gf180.py ... --devices nfet_03v3 pfet_03v3     # 3.3 V only
    python make_min_gf180.py ... --devices nfet_03v3 pfet_03v3 nfet_06v0 pfet_06v0 nfet_06v0_nvt

`make_min_gf180.py` imports `make_min_pdk.py` (expression translation); keep both scripts together.
The additional tests (`test1` sf / fs and `test3`) come from `gf180_tests2.py`, `test3_mc_mm_1000.cir` from `gf180_tests3.py` and `test3_mc_mm_pfet03v3_3000.cir` from `gf180_tests4.py`.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Unknown subcircuit called in: xnfet_03v3` | The library was not found. Use the absolute path in quotes or put it next to the netlist. |
| `.meas OP` FAILS with `.step` | Use the dummy `.dc V9 0 1 1` and `.meas DC ... AT 0`. |
| ~1.7 % difference in Id at some L | L exactly on a bin edge (see Known limitations). Move L by 10 nm. |
| MC sigma off by a few % from ngspice | Normal with 300 runs (~4 % uncertainty per side). Use more runs. |
| LTspice rejects `mulu0` | Do not use `--keep-mulu0`; LTspice does not support it. |

## License

Derived from the GlobalFoundries gf180mcu PDK (Apache License 2.0, Copyright GlobalFoundries PDK Authors);
see the license header of the original `sm141064.ngspice`. The tools are provided as they are, with no warranty.
"""

HEADER = ("* gf180mcuD -> LTspice (generated by make_min_gf180.py from the native sm141064.ngspice)\n"
          "* Flat, self-contained file: needs no design.ngspice, gf180mcuD_ltspice.lib or includes.\n")


# ----------------------------------------------------------------------------
# reading and parsing the native PDK
# ----------------------------------------------------------------------------
_TRAIL = re.compile(r"^(?P<head>.*?=)\s*\{[^;]*\}\s*;\s*\+?\s*(?:\w+\s*=\s*)?(?P<ag>agauss\(.*\))\s*$", re.I)


def read_native(path: Path) -> list[str]:
    """Read the PDK; accepts the native version and the hand-edited LTspice one ({..};agauss(..))."""
    text = path.read_text(errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    out = []
    for ln in text.split("\n"):
        m = _TRAIL.match(ln)
        if m:
            ln = m.group("head") + " " + m.group("ag")
        out.append(ln.expandtabs(4).rstrip())
    return out


_REF = re.compile(r"^\s*\.lib\s+['\"]?[^'\"\s]+['\"]?\s+(\S+)\s*$", re.I)
_DEF = re.compile(r"^\s*\.lib\s+(\S+)\s*$", re.I)
_END = re.compile(r"^\s*\.endl\b", re.I)


def parse_libs(lines: list[str]) -> dict[str, list[str]]:
    libs: dict[str, list[str]] = {}
    cur = None
    for ln in lines:
        if cur is None:
            m = _DEF.match(ln)
            if m:
                cur = m.group(1).lower()
                libs[cur] = []
        elif _END.match(ln):
            cur = None
        else:
            libs[cur].append(ln)
    return libs


def split_subckts(lines: list[str]):
    """-> list of ('text', [lines]) or ('subckt', name, [lines])."""
    items, cur, name = [], [], None
    buf: list[str] = []
    for ln in lines:
        m = re.match(r"^\s*\.subckt\s+(\S+)", ln, re.I)
        if name is None and m:
            if buf:
                items.append(("text", buf))
                buf = []
            name, cur = m.group(1), [ln]
        elif name is not None:
            cur.append(ln)
            if re.match(r"^\s*\.ends\b", ln, re.I):
                items.append(("subckt", name, cur))
                name, cur = None, []
        else:
            buf.append(ln)
    if buf:
        items.append(("text", buf))
    return items


def _refs_in(lines: list[str]) -> set[str]:
    """names of subcircuits instantiated by X... lines"""
    names = set()
    for ln in lines:
        if re.match(r"^\s*x", ln, re.I):
            toks = [t for t in re.sub(r"'[^']*'", "''", ln).split() if "=" not in t]
            if len(toks) >= 2:
                names.add(toks[-1].lower())
    return names


def fix_ternary(s: str) -> str:
    """'(a==0) ? x : y' -> 'if(a==0,x,y)' (LTspice has no ?:)."""
    return re.sub(r"\(([^()?]+)\)\s*\?\s*([^:'\"]+?)\s*:\s*([^'\"]+?)(?=['\"\s]|$)", r"if(\1,\2,\3)", s)


def clean_model_lib(lines: list[str], keep_dss: bool) -> list[str]:
    items = split_subckts(lines)
    if not keep_dss:
        dss = [it for it in items if it[0] == "subckt" and it[1].lower().endswith("_dss")]
        helpers = set()
        for it in dss:
            helpers |= _refs_in(it[2])
        items = [it for it in items if not (it[0] == "subckt" and it[1].lower().endswith("_dss"))]
        still = set()
        for it in items:
            still |= _refs_in(it[2] if it[0] == "subckt" else it[1])
        for h in helpers - still:
            items = [it for it in items if not (it[0] == "subckt" and it[1].lower() == h)]
    out = []
    for it in items:
        out += it[2] if it[0] == "subckt" else it[1]
    if keep_dss:
        out = [fix_ternary(x) for x in out]
    return out


def fix_gauss_line(ln: str) -> str:
    """A line 'name = ...gauss(...)...' inside a subcircuit .param -> '{LTspice expr}'."""
    if "gauss(" not in ln.lower():
        return ln
    m = re.match(r"^(\s*\+?\s*(?:\.param\s+)?\w+\s*=\s*)(.*)$", ln, re.I)
    if not m:
        raise ValueError("unrecognized line with gauss: " + ln)
    return f"{m.group(1)}{{{mp.convert_gauss(mp._value_expr(m.group(2).strip()))}}}"


def mm_subckts(lines: list[str], names: set[str], keep_mulu0: bool) -> list[str]:
    """Translated fets_mm subcircuits of the selected devices."""
    out: list[str] = []
    for it in split_subckts(lines):
        if it[0] != "subckt" or it[1].lower() not in names:
            continue
        body, i = [], 0
        src = it[2]
        while i < len(src):
            ln = src[i]
            if re.match(r"^\s*m0\b", ln, re.I):
                stmt = ln
                while i + 1 < len(src) and src[i + 1].lstrip().startswith("+"):
                    i += 1
                    stmt += " " + src[i].lstrip()[1:]
                toks = stmt.split()
                model = toks[5]
                geo = "w='w' l='l' as='as' ad='ad' ps='ps' pd='pd' nrd='nrd' nrs='nrs' sa='sa' sb='sb' nf='nf' sd='sd' m='m'"
                extra = "delvto='mis_vth*sw_stat_mismatch'"
                if keep_mulu0:
                    extra += " mulu0='1-mis_k*sw_stat_mismatch'"
                body.append(f"m0 {toks[1]} {toks[2]} {toks[3]} {toks[4]} {model} {geo}")
                body.append(f"+{extra}")
            else:
                body.append(fix_gauss_line(ln))
            i += 1
        out += body + [""]
    return out


def wrapper_lines(dev: str, legacy: bool) -> list[str]:
    l, w = WRAP_DEFAULT[dev]
    if legacy:
        pd, ps = "'int((nf+1)/2) * W/nf * 0.18u'", "'int((nf+2)/2) * W/nf * 0.18u'"
    else:
        pd, ps = "'2*int((nf+1)/2) * (W/nf + 0.18u)'", "'2*int((nf+2)/2) * (W/nf + 0.18u)'"
    pre = "x" + dev
    return [
        f".subckt {pre} D G S B",
        f".param l={l} w={w} m=1 nf=1",
        ".param ad='int((nf+1)/2) * W/nf * 0.18u'",
        f".param pd={pd}",
        ".param as='int((nf+2)/2) * W/nf * 0.18u'",
        f".param ps={ps}",
        ".param nrd='0.18u / W' nrs='0.18u / W'",
        f"X1 D G S B {dev} l='l' w='w' ad='ad' as='as' pd='pd' ps='ps' m='m' nrd='nrd' nrs='nrs' nf='nf'",
        ".ends", "",
    ]


# ----------------------------------------------------------------------------
# building one case
# ----------------------------------------------------------------------------
def _ident(s: str) -> set[str]:
    return {x.lower() for x in re.findall(r"(?<![\w.])[A-Za-z_]\w*", s)}


def expand_section(libs, sec: str, devs: set[str], _acc=None):
    """Walk the native section (and its refs) -> (params text, [model lib names], uses_mm)."""
    acc = _acc if _acc is not None else {"params": [], "models": [], "mm": False}
    for ln in libs[sec.lower()]:
        m = _REF.match(ln)
        if not m:
            acc["params"].append(ln)
            continue
        t = m.group(1).lower()
        mm = MODEL_LIB.match(t)
        if mm:
            if mm.group("dev").lower() in devs and t not in acc["models"]:
                acc["models"].append(t)
        elif t == "fets_mm":
            acc["mm"] = True
        elif t == "noise_corner":
            expand_section(libs, t, devs, acc)
        # res, efuse, bjt_mc, ...: not needed for the FETs
    return acc


def build_case(libs, case: str, devs: list[str], keep_dss=False, keep_mulu0=False, legacy_wrapper=False):
    sec, sg, smm = CASES[case]
    devset = set(devs)
    allnames = devset | {ALIAS_05V0[d] for d in devs if d in ALIAS_05V0}
    acc = expand_section(libs, sec, devset)
    # section parameters (translated; the last definition of each name wins)
    lines, names = mp.translate_params("\n".join(acc["params"]))
    defs: dict[str, str] = {}
    for ln, nm in zip(lines, names):
        defs.pop(nm.lower(), None)
        defs[nm.lower()] = ln
    # model blocks
    body: list[str] = []
    for t in acc["models"]:
        body += [f"* ---- {t} (native: .lib {t}) ----"] + clean_model_lib(libs[t], keep_dss) + [""]
    if acc["mm"]:
        body += ["* ---- subcircuits with mismatch (native: .lib fets_mm) ----"]
        body += mm_subckts(libs["fets_mm"], allnames, keep_mulu0)
    # nvt has no mm subcircuit: its own block already defines nfet_06v0_nvt
    wraps = []
    for d in devs:
        for dd in [d] + ([ALIAS_05V0[d]] if d in ALIAS_05V0 else []):
            wraps += wrapper_lines(dd, legacy_wrapper)
    body_txt = "\n".join(body + wraps)
    # transitive closure of the needed parameters
    need, todo = set(), list(_ident(body_txt))
    while todo:
        n = todo.pop()
        if n in need or n not in defs:
            continue
        need.add(n)
        todo += list(_ident(defs[n].split("=", 1)[1]))
    kept = [defs[n] for n in defs if n in need]
    # parameters used but not defined (besides those of design.ngspice)
    used = set()
    for ln in kept:
        used |= _ident(ln.split("=", 1)[1])
    unresolved = sorted(u for u in used if u not in defs and u not in PRELUDE_NAMES
                        and u not in {"gauss", "int", "if", "abs", "sqrt", "exp", "min", "max"})
    prelude = [
        f".param sw_stat_global={sg} sw_stat_mismatch={smm}",
        ".param mc_skew=3 res_mc_skew=3 cap_mc_skew=3 fnoicor=0",
    ]
    txt = (HEADER + f"* case: {case.upper()}  (native section: {sec}; sw_stat_global={sg}, sw_stat_mismatch={smm})\n"
           + f"* devices: {', '.join(sorted(allnames))}\n"
           + "\n".join(prelude + [""] + kept + [""]) + "\n" + body_txt + "\n")
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt, unresolved


# ----------------------------------------------------------------------------
# static verification
# ----------------------------------------------------------------------------
def verify_text(txt: str, devs: list[str]) -> list[str]:
    p = []
    low = txt.lower()
    if "\r" in txt:
        p.append("contains CR")
    if any(ord(c) > 126 for c in txt):
        p.append("non-ASCII characters")
    if "\t" in txt:
        p.append("contains tabs")
    if re.search(r"agauss\s*\(", low):
        p.append("agauss() left over")
    if re.search(r"^\s*\.lib\b", low, re.M):
        p.append("a .lib line is left over")
    if re.search(r"^[^*\n]*\?[^\n]*:", txt, re.M):
        p.append("a ?: operator is left over")
    defined = {m.lower() for m in re.findall(r"^\s*\.subckt\s+(\S+)", txt, re.M | re.I)}
    for ref in _refs_in(txt.split("\n")):
        if ref not in defined and not ref.startswith("$"):
            p.append(f"undefined subcircuit: {ref}")
    for d in devs:
        if d not in defined:
            p.append(f"missing subcircuit {d}")
        if f"x{d}" not in defined:
            p.append(f"missing wrapper x{d}")
    for m in re.findall(r"^\s*\.param\s+(\w+)\s*=\s*\{([^}]*)\}", txt, re.M):
        pass
    return p


def write_all(libs, src: Path, dst: Path, devs, args) -> list[str]:
    problems: list[str] = []
    dst.mkdir(parents=True, exist_ok=True)
    manifest = []
    for case in CASES:
        txt, unres = build_case(libs, case, devs, args.keep_dss, args.keep_mulu0, args.legacy_wrapper)
        for u in unres:
            problems.append(f"{case}: undefined parameter: {u}")
        for q in verify_text(txt, devs):
            problems.append(f"{case}: {q}")
        f = dst / f"{OUT_PREFIX}{case}.lib"
        f.write_text(txt)
        manifest.append((f.name, f.stat().st_size, txt.count("\n"), hashlib.sha256(txt.encode()).hexdigest()[:12]))
    lines = ["MANIFEST gf180mcuD LTspice", f"source: {SRC_NAME} sha256={hashlib.sha256(src.read_bytes()).hexdigest()[:16]}",
             f"devices: {' '.join(devs)}", "", f"{'file':44s} {'bytes':>9s} {'lines':>7s}  sha256[:12]"]
    lines += [f"{n:44s} {b:9d} {l:7d}  {h}" for n, b, l, h in manifest]
    lines += ["", "problems: " + (str(len(problems)) if problems else "none")] + problems
    (dst / "MANIFEST_gf180_ltspice.txt").write_text("\n".join(lines) + "\n")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, default=Path("."), help="folder with the native sm141064.ngspice")
    ap.add_argument("--dst", type=Path, default=Path("gf180mcuD_ltspice_min"))
    ap.add_argument("--devices", nargs="+", default=DEFAULT_DEVICES, choices=KNOWN_DEVICES)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--keep-dss", action="store_true", help="keep the *_dss subcircuits (SAB)")
    ap.add_argument("--keep-mulu0", action="store_true", help="leave mulu0 on the instances (LTspice rejects it)")
    ap.add_argument("--legacy-wrapper", action="store_true",
                    help="pd/ps as in the original gf180mcuD_ltspice.lib (no perimeter)")
    ap.add_argument("--smoke-test", action="store_true")
    ap.add_argument("--write-tests", action="store_true",
                    help="write test0/test1/test2 for LTspice with references computed in ngspice")
    a = ap.parse_args(argv)
    src = a.src / SRC_NAME
    if not src.exists():
        print(f"{src} does not exist", file=sys.stderr)
        return 1
    if a.dst.exists() and any(a.dst.iterdir()):
        if not a.force:
            print(f"{a.dst} exists; use --force", file=sys.stderr)
            return 1
        shutil.rmtree(a.dst)
    libs = parse_libs(read_native(src))
    probs = write_all(libs, src, a.dst, a.devices, a)
    print(f"{len(CASES)} libs in {a.dst}; static problems: {len(probs)}")
    for q in probs:
        print("  -", q)
    ok = not probs
    (a.dst / "README_gf180_ltspice.md").write_text(README_GF.lstrip("\n"))
    if a.smoke_test:
        import gf180_smoke
        ok = gf180_smoke.run(a.src, a.dst, a.devices) and ok
    if a.write_tests:
        import gf180_tests
        gf180_tests.write_test0(a.dst)
        ok = gf180_tests.run(a.src, a.dst) and ok
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
