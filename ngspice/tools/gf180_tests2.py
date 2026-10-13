# -*- coding: utf-8 -*-
"""Additional LTspice tests: sf/fs corners (OP) and MC/mismatch with 03v3, 06v0 and 05v0.

test1_op_sf / test1_op_fs      : like test1 (deterministic, native ngspice reference).
test3_mc_<case>.cir            : 300 runs, 6 transistors (03v3, 06v0, 05v0; n and p).
cases: mc mcmm mm ss_mm ff_mm sf_mm fs_mm
"""
from __future__ import annotations
import shutil, tempfile
from pathlib import Path
import make_min_gf180 as g
import gf180_tests as t

MC3_GEOS = [("nfet_03v3", 0.55, 2), ("pfet_03v3", 0.55, 2),
            ("nfet_06v0", 0.75, 2), ("pfet_06v0", 0.75, 2),
            ("nfet_05v0", 0.6, 2), ("pfet_05v0", 0.6, 2)]
MC3_CASES = ("mc", "mcmm", "mm", "ss_mm", "ff_mm", "sf_mm", "fs_mm")


def _setup_geos():
    t.MC_GEOS = MC3_GEOS
    for d, _, _ in MC3_GEOS:
        vd, vg = t._bias(d)
        t.VD_MC[d], t.VG_MC[d] = vd, vg


def write_test3(dst: Path, case: str, ref):
    L = [f".title Test 3 - MC gf180mcuD LTspice ({case}) with 03v3, 06v0 and 05v0",
         "* 300 runs. ngspice reference (reduced lib, gauss->agauss, different seeds):"]
    for (d, lu, wu), (mu, s, n) in zip(MC3_GEOS, ref):
        L.append(f"*   {d} L={lu} W={wu}: mean |Id| = {mu*1e6:.2f} uA   sigma/mean = {s:.2f} %   (n={n})")
    L += ["* Compare mean and sigma/mean of id0..id5 (see the .log or File>Export). Tolerance: ~1 % on the",
          "* mean and ~10 % relative on sigma/mean (300 runs).",
          f'.lib "{g.OUT_PREFIX}{case}.lib"', ".step param run 1 300 1", "V9 x9 0 0", "R9 x9 0 1k", ".dc V9 0 1 1"]
    for k, (d, lu, wu) in enumerate(MC3_GEOS):
        L += [f"Vd{k} d{k} 0 {t.VD_MC[d]}", f"Vg{k} g{k} 0 {t.VG_MC[d]}", f"X{k} d{k} g{k} 0 0 x{d} l={lu}u w={wu}u",
              f".meas DC id{k} FIND I(Vd{k}) AT 0"]
    L.append(".end")
    (dst / f"test3_mc_{case}.cir").write_text("\n".join(L) + "\n")


def run(src: Path, dst: Path, n_ref: int = 300):
    ng = shutil.which("ngspice")
    tmp = Path(tempfile.mkdtemp(prefix="gf180t2_"))
    for case in ("sf", "fs"):
        t.write_test1(dst, case, t.ref_op(ng, src, tmp, case))
    _setup_geos()
    for case in MC3_CASES:
        ref = t.stats(t.ng_mc(ng, dst, case, tmp, n_ref))
        write_test3(dst, case, ref)
        print(case, "  ".join(f"{d[:1]}{d[5:9]}:{s:.2f}%" for (d, _, _), (_, s, _) in zip(MC3_GEOS, ref)), flush=True)


if __name__ == "__main__":
    run(Path("."), Path("final/gf180mcuD_ltspice_min"))
