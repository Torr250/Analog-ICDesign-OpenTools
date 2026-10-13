# -*- coding: utf-8 -*-
"""Generate test netlists for LTspice with reference values computed in ngspice.

test1_op_<case>.cir : deterministic Id (native PDK in ngspice) -> LTspice must match (<0.1 %).
test2_mc_<case>.cir : 300 MC runs; reference sigma/mean of Id computed in ngspice
                      (reduced lib with gauss(x)->agauss(0,x,1), different seeds).
"""
from __future__ import annotations

import re
import shutil
import statistics as st
import subprocess
import tempfile
from pathlib import Path

import make_min_gf180 as g
import make_min_pdk as mp
import gf180_smoke as sm

T1_GEOS = [  # (device, L_um, W_um, nf, m)
    ("nfet_03v3", 0.28, 1, 1, 1), ("nfet_03v3", 0.5, 2, 2, 2), ("nfet_03v3", 1.2, 5, 1, 1), ("nfet_03v3", 0.55, 2, 1, 1),
    ("pfet_03v3", 0.28, 1, 1, 1), ("pfet_03v3", 0.5, 2, 2, 2), ("pfet_03v3", 1.2, 5, 1, 1), ("pfet_03v3", 0.55, 2, 1, 1),
    ("nfet_06v0", 0.75, 2, 1, 1), ("pfet_06v0", 0.55, 2, 1, 1), ("nfet_05v0", 0.6, 2, 1, 1), ("pfet_05v0", 0.5, 2, 1, 1),
]
MC_GEOS = [("nfet_03v3", 0.5, 2), ("nfet_03v3", 0.55, 2), ("pfet_03v3", 0.5, 2), ("pfet_03v3", 0.55, 2)]
VG_MC = {"nfet_03v3": 1.5, "pfet_03v3": -1.5}
VD_MC = {"nfet_03v3": 1.65, "pfet_03v3": -1.65}


def _vdd(dev: str) -> float:
    return sm.VDD[dev[5:9]]


def _bias(dev):
    s = 1 if dev.startswith("nfet") else -1
    return round(s * 0.5 * _vdd(dev), 6), round(s * 0.75 * _vdd(dev), 6)


def gauss_to_agauss(text: str) -> str:
    while True:
        r = mp._find_call(text, "gauss")
        if r is None:
            return text
        i0, i1, args = r
        text = text[:i0] + f"agauss(0,({args[0]}),1)" + text[i1:]


def ref_op(ng, src, tmp, case):
    """Reference Id (native PDK, deterministic) for T1_GEOS."""
    sec, sg, smm = g.CASES[case]
    nat = tmp / "sm141064.ngspice"
    nat.write_text("\n".join(sm._rhs_const(g.read_native(src / g.SRC_NAME), sm.NAT_PAT, 0.0)))
    des = sm.design_copy(src / "design.ngspice", tmp, sg, smm)
    L = ["ref", f".include {des.name}", f".lib {nat.name} {sec}"]
    for k, (d, lu, wu, nf, m) in enumerate(T1_GEOS):
        vd, vg = _bias(d)
        ad, as_, pd, ps, nr = sm.geom(nf, wu)
        L += [f"Vd{k} d{k} 0 {vd}", f"Vg{k} g{k} 0 {vg}",
              f"X{k} d{k} g{k} 0 0 {d} w={wu}u l={lu}u nf={nf} m={m} ad={ad:.6e} as={as_:.6e} pd={pd:.6e} ps={ps:.6e} nrd={nr:.6e} nrs={nr:.6e}"]
    L += [".control", "op"] + [f"print i(vd{k})" for k in range(len(T1_GEOS))] + [".endc", ".end"]
    f = tmp / f"ref_{case}.cir"
    f.write_text("\n".join(L) + "\n")
    out = subprocess.run([ng, "-b", str(f)], capture_output=True, text=True, cwd=tmp).stdout
    vals = {int(a): float(b) for a, b in re.findall(r"i\(vd(\d+)\)\s*=\s*(\S+)", out, re.I)}
    return [vals[k] for k in range(len(T1_GEOS))]


def write_test1(dst: Path, case: str, refs):
    L = [f".title Test 1 - deterministic OP, gf180mcuD LTspice ({case.upper()})",
         f"* Compare each Id with the ngspice reference (native PDK, {case}). Expected: difference < 0.1 %.",
         "* The nf=2 m=2 lines check that LTspice applies nf and m. L=0.5u and 1.2u are bin edges; avoid L exactly on an internal bin edge (e.g. 0.7u in 06v0): LTspice and ngspice differ by ~1.7 % there.",
         f'.lib "{g.OUT_PREFIX}{case}.lib"', "V9 x9 0 0", "R9 x9 0 1k", ".dc V9 0 1 1", ""]
    for k, ((d, lu, wu, nf, m), r) in enumerate(zip(T1_GEOS, refs)):
        vd, vg = _bias(d)
        L += [f"Vd{k} d{k} 0 {vd}", f"Vg{k} g{k} 0 {vg}",
              f"X{k} d{k} g{k} 0 0 x{d} l={lu}u w={wu}u nf={nf} m={m}",
              f".meas DC id{k} FIND I(Vd{k}) AT 0   ; ref ngspice = {r:.6e}  ({d} L={lu} W={wu} nf={nf} m={m})"]
    L.append(".end")
    (dst / f"test1_op_{case}.cir").write_text("\n".join(L) + "\n")


def mc_netlist(libfile: str, n_runs: int, seeded: str | None = None):
    """ngspice (seeded) or LTspice (seeded=None) netlist for MC with 4 transistors."""
    L = [f"mc", f"{'.include ' if seeded else '.lib '}{libfile if seeded else chr(34) + libfile + chr(34)}"]
    for k, (d, lu, wu) in enumerate(MC_GEOS):
        L += [f"Vd{k} d{k} 0 {VD_MC[d]}", f"Vg{k} g{k} 0 {VG_MC[d]}",
              f"X{k} d{k} g{k} 0 0 x{d} l={lu}u w={wu}u"]
    return L


def ng_mc(ng, dst: Path, case: str, tmp: Path, n: int, keep_mulu0=False):
    """Sample n runs in ngspice with the reduced lib (gauss -> agauss)."""
    lib = (dst / f"{g.OUT_PREFIX}{case}.lib").read_text()
    f = tmp / f"ngmc_{case}.lib"
    f.write_text(gauss_to_agauss(lib))
    cols = [[] for _ in MC_GEOS]
    for seed in range(1, n + 1):
        L = mc_netlist(f.name, n, seeded=True)
        L.insert(1, f".option seed={seed}")
        L += [".control", "op"] + [f"print i(vd{k})" for k in range(len(MC_GEOS))] + [".endc", ".end"]
        c = tmp / f"mc_{case}.cir"
        c.write_text("\n".join(L) + "\n")
        out = subprocess.run([ng, "-b", str(c)], capture_output=True, text=True, cwd=tmp).stdout
        v = re.findall(r"i\(vd(\d+)\)\s*=\s*(\S+)", out, re.I)
        if len(v) != len(MC_GEOS):
            continue
        for k, x in v:
            cols[int(k)].append(abs(float(x)))
    return cols


def stats(cols):
    return [(st.mean(c), st.pstdev(c) / st.mean(c) * 100, len(c)) for c in cols]


def write_test2(dst: Path, case: str, ref):
    sec, sg, smm = g.CASES[case]
    what = {"mc": "global process variation", "mm": "per-instance mismatch", "mcmm": "process + mismatch"}[case]
    L = [f".title Test 2 - MC gf180mcuD LTspice ({what})",
         "* 300 runs. Four transistors: nfet/pfet with L=0.5u (bin edge) and L=0.55u (not an edge), W=2u.",
         "* ngspice reference (reduced lib, same models, different seeds; n = reference samples):"]
    for (d, lu, wu), (mu, sg_, n) in zip(MC_GEOS, ref):
        L.append(f"*   {d} L={lu} W={wu}: mean |Id| = {mu*1e6:.2f} uA   sigma/mean = {sg_:.2f} %   (n={n})")
    L += ["* With 300 runs sigma has ~4 % relative uncertainty; if L=0.5u differs a lot from L=0.55u",
          "* in LTspice but not in the reference, there is a bin-edge effect (see README).",
          f'.lib "{g.OUT_PREFIX}{case}.lib"', ".step param run 1 300 1", "V9 x9 0 0", "R9 x9 0 1k", ".dc V9 0 1 1"]
    for k, (d, lu, wu) in enumerate(MC_GEOS):
        L += [f"Vd{k} d{k} 0 {VD_MC[d]}", f"Vg{k} g{k} 0 {VG_MC[d]}", f"X{k} d{k} g{k} 0 0 x{d} l={lu}u w={wu}u",
              f".meas DC id{k} FIND I(Vd{k}) AT 0"]
    L.append(".end")
    (dst / f"test2_mc_{case}.cir").write_text("\n".join(L) + "\n")


def write_test0(dst: Path):
    L = [".title Test 0 - sigma of gauss() in LTspice (1000 steps)",
         "* a1 = gauss(1/3)       -> expected sigma 0.333 if gauss(x) is N(0,sigma=x)  (what these libs use)",
         "* a2 = (1/3)*gauss(3)   -> sigma 1.0 if gauss(x) is N(0,sigma=x); 0.333 if gauss(x) were N(0,1)*",
         "* Compute the standard deviation of v1 and v2 from the .log (v1/v2 columns of .meas).",
         ".param a1={gauss(1/3)} a2={(1/3)*gauss(3)}",
         ".step param run 1 1000 1",
         "V1 n1 0 {a1}", "V2 n2 0 {a2}", "R1 n1 0 1k", "R2 n2 0 1k",
         "V9 x9 0 0", "R9 x9 0 1k", ".dc V9 0 1 1",
         ".meas DC v1 FIND V(n1) AT 0", ".meas DC v2 FIND V(n2) AT 0", ".end"]
    (dst / "test0_gauss_sigma.cir").write_text("\n".join(L) + "\n")


def run(src: Path, dst: Path, n_ref: int = 400) -> bool:
    ng = shutil.which("ngspice")
    if not ng:
        print("ngspice not found: tests are not generated")
        return False
    tmp = Path(tempfile.mkdtemp(prefix="gf180tests_"))
    for case in ("tt", "ss", "ff"):
        write_test1(dst, case, ref_op(ng, src, tmp, case))
    summary = {}
    for case in ("mc", "mm", "mcmm"):
        ref = stats(ng_mc(ng, dst, case, tmp, n_ref))
        write_test2(dst, case, ref)
        summary[case] = ref
        print(f"  ref MC {case}: " + "  ".join(f"{d[:1]}{lu}: {s:.2f}%" for (d, lu, _), (_, s, _) in zip(MC_GEOS, ref)))
    return True
