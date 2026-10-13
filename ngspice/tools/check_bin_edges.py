#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_bin_edges.py - warns if an LTspice netlist/schematic uses an L right on a bin edge
of the translated sky130A PDK (sky130A_ltspice_min).

Why it matters
--------------
The sky130 models are binned in L. When L falls EXACTLY on a bin edge
(e.g. 0.5u, 0.25u, 1u, 2u...), the model response to global process variation
(sw_polycd, which shifts the effective L) differs between LTspice and ngspice, and in ngspice it also
shows a change of slope. With L = edge + 10 nm the two simulators agree to three
decimals (measured on the 45 edges of the 6 FETs: test4_bin_edges).
Effect: only the sigma of the process variation (Monte Carlo); the nominal operating point
and the corners are NOT affected (they agree to ~1e-5).

Usage
-----
    python check_bin_edges.py circuit.cir other.net schematic.asc
    python check_bin_edges.py --tol 5e-9 circuit.cir        # tolerance (m) around the edge
Exit code: 0 without warnings, 2 if there is an L on an edge (useful in scripts).

Scope: reads lines  X... xnfet_01v8 l=0.5u w=2u  (and .asc schematics: SYMBOL + SpiceLine).
It does not evaluate {..}/.param expressions: it reports them as "note". An L that comes from .step/.param
must be checked by hand against the table.
Limit of what was measured: only L exactly on the edge and at edge + 10 nm was measured (not below).
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

# L bin edges (microns) per device, measured: (edge_um, LT/ng ratio of the sensitivity to
# sw_polycd at the edge, severity). Severity: high (>25 % or opposite sign), medium (5-25 %),
# low (<5 %: no appreciable difference at the measured edge, but it is still an edge).
BIN_EDGES = {'nfet_01v8': [(0.15, 1.0, 'low'),
               (0.18, 1.08, 'medium'),
               (0.25, 0.35, 'high'),
               (0.5, 0.69, 'high'),
               (1, 1.06, 'medium'),
               (2, 0.94, 'medium'),
               (4, 1.0, 'low'),
               (8, 1.01, 'low')],
 'nfet_01v8_lvt': [(0.15, 1.0, 'low'),
                   (0.18, 0.66, 'high'),
                   (0.25, 0.58, 'high'),
                   (0.5, 1.0, 'low'),
                   (1, 1.07, 'medium'),
                   (2, -0.58, 'high'),
                   (4, 0.84, 'medium'),
                   (8, 1.0, 'low')],
 'pfet_01v8': [(0.15, 1.0, 'low'),
               (0.18, 1.21, 'medium'),
               (0.25, 1.54, 'high'),
               (0.5, 1.36, 'high'),
               (1, 1.06, 'medium'),
               (2, 0.92, 'medium'),
               (4, 1.05, 'medium'),
               (8, 0.94, 'medium')],
 'pfet_01v8_lvt': [(0.35, 1.0, 'low'),
                   (0.5, 1.07, 'medium'),
                   (1, 1.14, 'medium'),
                   (1.5, 0.93, 'medium'),
                   (2, 0.99, 'low'),
                   (4, 1.0, 'low'),
                   (8, 0.97, 'low')],
 'nfet_g5v0d10v5': [(0.5, 1.0, 'low'),
                    (0.6, 0.91, 'medium'),
                    (0.8, 0.9, 'medium'),
                    (1, 1.03, 'low'),
                    (2, 1.02, 'low'),
                    (4, 1.01, 'low'),
                    (8, 0.99, 'low')],
 'pfet_g5v0d10v5': [(0.5, 1.0, 'low'),
                    (0.6, 0.98, 'low'),
                    (0.8, 0.84, 'medium'),
                    (1, 0.47, 'high'),
                    (2, 1.02, 'low'),
                    (4, 1.02, 'low'),
                    (8, 0.95, 'medium')]}

TOL_M = 5e-9   # warn if |L - edge| <= 5 nm
SUG_M = 10e-9  # suggestion: edge + 10 nm

_SUF = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3, "meg": 1e6, "g": 1e9}
_NUM = re.compile(r"^([-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?)(meg|[fpnumkg])?[a-z]*$", re.I)


def parse_val(s: str):
    """SPICE value -> float in SI; None if it is not a literal number."""
    m = _NUM.match(s.strip().strip("'\""))
    if not m:
        return None
    v = float(m.group(1))
    return v * _SUF[m.group(2).lower()] if m.group(2) else v


def fmt_um(m: float) -> str:
    return f"{m * 1e6:.4g}u"


def edge_hit(dev: str, l_m: float, tol: float = TOL_M):
    for e, ratio, sev in BIN_EDGES.get(dev, ()):
        if abs(l_m - e * 1e-6) <= tol:
            return e, ratio, sev
    return None


_DEV = re.compile(r"(?:sky130_fd_pr__|x)((?:n|p)fet_(?:01v8_lvt|01v8|g5v0d10v5))\b", re.I)
_L = re.compile(r"\bl\s*=\s*(\{[^}]*\}|'[^']*'|\S+)", re.I)


def _scan_line(text: str, where: str, out: list, tol: float):
    m = _DEV.search(text)
    lm = _L.search(text)
    if not m or not lm:
        return
    dev = m.group(1).lower()
    raw = lm.group(1)
    v = parse_val(raw)
    if v is None:
        out.append((where, dev, raw, None, None))
        return
    hit = edge_hit(dev, v, tol)
    if hit:
        out.append((where, dev, raw, v, hit))


def scan(path: Path, tol: float = TOL_M) -> list:
    out: list = []
    lines = path.read_text(errors="replace").splitlines()
    if path.suffix.lower() == ".asc":
        sym = None
        for i, ln in enumerate(lines, 1):
            if ln.startswith("SYMBOL "):
                sym = ln.split()[1]
            elif ln.startswith("SYMATTR SpiceLine") and sym:
                parts = ln.split(None, 2)
                if len(parts) == 3:
                    _scan_line(sym + " " + parts[2], f"{path.name}:{i}", out, tol)
        return out
    logical: list = []
    for i, ln in enumerate(lines, 1):
        s = ln.strip()
        if s.startswith("+") and logical:
            logical[-1] = (logical[-1][0], logical[-1][1] + " " + s[1:])
        elif s and not s.startswith(("*", ";")):
            logical.append((i, s))
    for i, s in logical:
        if s[0] in "xXmM":
            _scan_line(s, f"{path.name}:{i}", out, tol)
    return out


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    tol = TOL_M
    if "--tol" in argv:
        k = argv.index("--tol")
        tol = float(argv[k + 1])
        del argv[k:k + 2]
    if not argv:
        print(__doc__)
        return 1
    warn = 0
    for p in map(Path, argv):
        if not p.is_file():
            print(f"[{p}] does not exist")
            continue
        res = scan(p, tol)
        if not res:
            print(f"[{p}] OK (no L on a bin edge)")
            continue
        print(f"[{p}]")
        for where, dev, raw, v, hit in res:
            if v is None:
                print(f"  note {where}: {dev} L={raw} is an expression; check it against the edge table")
                continue
            e, ratio, sev = hit
            warn += 1
            print(f"  WARNING {where}: {dev} L={raw} is on bin edge {fmt_um(e * 1e-6)} "
                  f"(severity {sev}, LT/ng={ratio}). Use L={fmt_um(e * 1e-6 + SUG_M)} "
                  f"(edge + 10 nm) if you are going to run process Monte Carlo.")
    return 2 if warn else 0


if __name__ == "__main__":
    sys.exit(main())
