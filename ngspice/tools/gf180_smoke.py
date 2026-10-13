# -*- coding: utf-8 -*-
"""Smoke test: compare in ngspice the native PDK against the generated LTspice libs.

So that ngspice can evaluate them, the random draws are replaced by DETERMINISTIC constants
(the same constant per parameter name on both sides).  Id (several biases) and Cgg are compared
for every device/geometry/case.  They must agree to ~1e-9 (same BSIM4 models).
"""
from __future__ import annotations

import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import make_min_gf180 as g

VDD = {"03v3": 3.3, "05v0": 5.0, "06v0": 6.0}
GEOS = {  # device: [(L_um, W_um, nf, m)]
    "03v3": [(0.28, 1, 1, 1), (0.5, 2, 2, 2), (1.2, 5, 1, 1), (0.6, 10, 4, 1), (0.3, 0.5, 1, 1), (11, 3, 1, 1)],
    "05v0": [(0.6, 2, 1, 1), (1.0, 5, 2, 2)],
    "06v0": [(0.7, 2, 1, 1), (1.0, 5, 2, 2), (2.0, 10, 1, 3)],
    "nvt": [(1.8, 10, 1, 1)],
}


def cval(name: str, k_const: float) -> str:
    n = name.lower()
    if n == "mis_vth":
        return "5e-3"
    if n == "mis_k":
        return repr(k_const)
    if n.startswith("mc_rsh"):
        return "0"
    return repr(((sum(map(ord, n)) % 9) - 4) * 0.1)


def _rhs_const(lines, pat, k_const):
    out = []
    for ln in lines:
        m = pat.match(ln)
        out.append(f"{m.group(1)}{m.group(2)}{m.group(3)}{cval(m.group(2), k_const)}" if m else ln)
    return out


NAT_PAT = re.compile(r"^(\s*\+?\s*)(\w+)(\s*=\s*)agauss\(.*\)\s*$", re.I)
LT_PAT = re.compile(r"^(\s*(?:\+|\.param)\s*)(\w+)(\s*=\s*)\{gauss\(.*\)\}\s*$", re.I)


def dev_list(devs):
    out = []
    for d in devs:
        out.append((d, d[5:9] if "nvt" not in d else "nvt"))
        if d in g.ALIAS_05V0:
            out.append((g.ALIAS_05V0[d], "05v0"))
    return out


def geom(nf, w_um):
    W = w_um * 1e-6
    ad = int((nf + 1) / 2) * W / nf * 0.18e-6
    as_ = int((nf + 2) / 2) * W / nf * 0.18e-6
    pd = 2 * int((nf + 1) / 2) * (W / nf + 0.18e-6)
    ps = 2 * int((nf + 2) / 2) * (W / nf + 0.18e-6)
    return ad, as_, pd, ps, 0.18e-6 / W


def netlist(kind: str, devs, libline: str, legacy=False) -> tuple[str, list[str]]:
    """kind 'nat' (native subckt with explicit geometry) or 'lt' (x* wrapper)."""
    L, keys = ["smoke", libline], []
    k = 0
    for d, v in dev_list(devs):
        n = d.startswith("nfet")
        vdd = VDD[v] if v != "nvt" else 6.0
        for (lu, wu, nf, m) in GEOS[v]:
            if v == "nvt" and kind == "lt" and not n:
                continue
            sg = 1 if n else -1
            vgs = sg * 0.75 * vdd
            vds = sg * 0.5 * vdd
            vg2 = sg * 0.45 * vdd
            L.append(f"Vd{k} d{k} 0 {vds}")
            L.append(f"Vg{k} g{k} 0 {vgs} ac 1")
            L.append(f"Vh{k} h{k} 0 {vds}")
            L.append(f"Vi{k} i{k} 0 {vg2}")
            if kind == "nat":
                ad, as_, pd, ps, nr = geom(nf, wu)
                prm = f"w={wu}u l={lu}u nf={nf} m={m} ad={ad:.6e} as={as_:.6e} pd={pd:.6e} ps={ps:.6e} nrd={nr:.6e} nrs={nr:.6e}"
                L.append(f"X{k} d{k} g{k} 0 0 {d} {prm}")
                L.append(f"Xb{k} h{k} i{k} 0 0 {d} {prm}")
            else:
                prm = f"w={wu}u l={lu}u nf={nf} m={m}"
                L.append(f"X{k} d{k} g{k} 0 0 x{d} {prm}")
                L.append(f"Xb{k} h{k} i{k} 0 0 x{d} {prm}")
            keys.append(f"{d} L={lu} W={wu} nf={nf} m={m}")
            k += 1
    L += [".control", "op", "ac lin 1 1meg 1meg"]
    L += ["echo OPDATA"] + [f"print i(vd{j}) i(vh{j})" for j in range(k)]
    L += ["echo ACDATA"] + [f"print imag(i(vg{j}))" for j in range(k)]
    L += [".endc", ".end"]
    return "\n".join(L) + "\n", keys


def run_ng(ng: str, net: str, tmp: Path, name: str):
    f = tmp / f"{name}.cir"
    f.write_text(net)
    r = subprocess.run([ng, "-b", str(f)], capture_output=True, text=True, cwd=tmp, timeout=600)
    out = r.stdout + r.stderr
    op = re.findall(r"i\(vd(\d+)\)\s*=\s*(\S+)", out, re.I)
    ih = re.findall(r"i\(vh(\d+)\)\s*=\s*(\S+)", out, re.I)
    ac = re.findall(r"imag\(i\(vg(\d+)\)\)\s*=\s*(\S+)", out, re.I)
    if not op or not ac:
        raise RuntimeError(f"{name}: no results.\n" + out[-1500:])
    fl = lambda x: float(x.split(",")[0])
    return ({int(a): fl(b) for a, b in op}, {int(a): fl(b) for a, b in ih},
            {int(a): fl(b) for a, b in ac})


def build_native_copy(src: Path, tmp: Path, k_const: float) -> Path:
    lines = src.read_text().replace("\r", "").split("\n")
    lines = g.read_native.__wrapped__(lines) if hasattr(g.read_native, "__wrapped__") else lines
    f = tmp / "native_ng.ngspice"
    f.write_text("\n".join(_rhs_const(lines, NAT_PAT, k_const)))
    return f


def design_copy(src_design: Path, tmp: Path, sg: int, smm: int) -> Path:
    t = src_design.read_text().replace("\r", "")
    t = re.sub(r"sw_stat_global\s*=\s*\d", f"sw_stat_global = {sg}", t)
    t = re.sub(r"sw_stat_mismatch\s*=\s*\d", f"sw_stat_mismatch = {smm}", t)
    f = tmp / "design_ng.ngspice"
    f.write_text(t)
    return f


def run(src: Path, dst: Path, devs, k_const: float = 0.0, verbose=True) -> bool:
    ng = shutil.which("ngspice")
    if not ng:
        print("ngspice not found: smoke test skipped")
        return True
    tmp = Path(tempfile.mkdtemp(prefix="gf180smoke_"))
    nat_src = src / g.SRC_NAME
    # native copy with draws -> constants (and normalization of the hand-edited version)
    text_lines = g.read_native(nat_src)
    nat = tmp / "sm141064.ngspice"
    nat.write_text("\n".join(_rhs_const(text_lines, NAT_PAT, k_const)))
    allok = True
    worst = 0.0
    for case, (sec, sg, smm) in g.CASES.items():
        if case == "mm":
            continue
        des = design_copy(src / "design.ngspice", tmp, sg, smm)
        nat_net, keys = netlist("nat", devs, f".include {des.name}\n.lib {nat.name} {sec}", False)
        lt_lines = (dst / f"{g.OUT_PREFIX}{case}.lib").read_text().split("\n")
        ltf = tmp / f"lt_{case}.lib"
        ltf.write_text("\n".join(_rhs_const(lt_lines, LT_PAT, k_const)))
        lt_net, _ = netlist("lt", devs, f".include {ltf.name}", False)
        a = run_ng(ng, nat_net, tmp, f"nat_{case}")
        b = run_ng(ng, lt_net, tmp, f"lt_{case}")
        diffs = []
        for idx in range(len(keys)):
            for q in range(3):
                x, y = a[q].get(idx), b[q].get(idx)
                if x is None or y is None:
                    diffs.append((9.9, keys[idx], "missing"))
                    continue
                d = abs(x - y) / (abs(x) + 1e-18)
                diffs.append((d, keys[idx], ("Id", "Id2", "Cgg")[q]))
        mx = max(diffs)
        worst = max(worst, mx[0])
        ok = mx[0] < 1e-6
        allok &= ok
        if verbose:
            print(f"  {case:6s} {len(keys)} devices x 3 measurements   max |dif| rel = {mx[0]:.2e}  [{mx[2]} {mx[1]}]  {'OK' if ok else 'FAIL'}")
    print(f"smoke-test: worst relative difference {worst:.2e}  ->  {'OK' if allok else 'FAIL'}")
    return allok
