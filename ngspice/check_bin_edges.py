#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_bin_edges.py - avisa si un netlist/esquematico de LTspice usa una L justo en un borde de bin
del PDK sky130A traducido (sky130A_ltspice_min).

Por que importa
---------------
Los modelos sky130 estan "binneados" en L. Cuando L cae EXACTAMENTE en el borde de un bin
(p. ej. 0.5u, 0.25u, 1u, 2u...), la respuesta del modelo a la variacion global de proceso
(sw_polycd, que desplaza la L efectiva) difiere entre LTspice y ngspice, y en ngspice tambien
muestra un cambio de pendiente. Con L = borde + 10 nm los dos simuladores coinciden a tres
decimales (medido en los 45 bordes de los 6 FET: test4_bordes_bin).
Efecto: solo la sigma de la variacion de proceso (Monte Carlo); el punto de operacion nominal
y las esquinas NO se ven afectados (coinciden a ~1e-5).

Uso
---
    python check_bin_edges.py circuito.cir otro.net esquema.asc
    python check_bin_edges.py --tol 5e-9 circuito.cir        # tolerancia (m) alrededor del borde
Codigo de salida: 0 sin avisos, 2 si hay L en borde (util en scripts).

Alcance: lee lineas  X... xnfet_01v8 l=0.5u w=2u  (y los esquematicos .asc: SYMBOL + SpiceLine).
No evalua expresiones {..}/.param: las reporta como "nota". Una L que viene de .step/.param
hay que revisarla a mano contra la tabla.
Limite de lo medido: solo se midio L exactamente en el borde y en borde + 10 nm (no por debajo).
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

# bordes de L (micras) por dispositivo, medidos: (borde_um, razon LT/ng de la sensibilidad a
# sw_polycd en el borde, severidad). Severidad: alta (>25 % o signo opuesto), media (5-25 %),
# baja (<5 %: sin diferencia apreciable en el borde medido, pero sigue siendo un borde).
BIN_EDGES = {'nfet_01v8': [(0.15, 1.0, 'baja'),
               (0.18, 1.08, 'media'),
               (0.25, 0.35, 'alta'),
               (0.5, 0.69, 'alta'),
               (1, 1.06, 'media'),
               (2, 0.94, 'media'),
               (4, 1.0, 'baja'),
               (8, 1.01, 'baja')],
 'nfet_01v8_lvt': [(0.15, 1.0, 'baja'),
                   (0.18, 0.66, 'alta'),
                   (0.25, 0.58, 'alta'),
                   (0.5, 1.0, 'baja'),
                   (1, 1.07, 'media'),
                   (2, -0.58, 'alta'),
                   (4, 0.84, 'media'),
                   (8, 1.0, 'baja')],
 'pfet_01v8': [(0.15, 1.0, 'baja'),
               (0.18, 1.21, 'media'),
               (0.25, 1.54, 'alta'),
               (0.5, 1.36, 'alta'),
               (1, 1.06, 'media'),
               (2, 0.92, 'media'),
               (4, 1.05, 'media'),
               (8, 0.94, 'media')],
 'pfet_01v8_lvt': [(0.35, 1.0, 'baja'),
                   (0.5, 1.07, 'media'),
                   (1, 1.14, 'media'),
                   (1.5, 0.93, 'media'),
                   (2, 0.99, 'baja'),
                   (4, 1.0, 'baja'),
                   (8, 0.97, 'baja')],
 'nfet_g5v0d10v5': [(0.5, 1.0, 'baja'),
                    (0.6, 0.91, 'media'),
                    (0.8, 0.9, 'media'),
                    (1, 1.03, 'baja'),
                    (2, 1.02, 'baja'),
                    (4, 1.01, 'baja'),
                    (8, 0.99, 'baja')],
 'pfet_g5v0d10v5': [(0.5, 1.0, 'baja'),
                    (0.6, 0.98, 'baja'),
                    (0.8, 0.84, 'media'),
                    (1, 0.47, 'alta'),
                    (2, 1.02, 'baja'),
                    (4, 1.02, 'baja'),
                    (8, 0.95, 'media')]}

TOL_M = 5e-9   # se avisa si |L - borde| <= 5 nm
SUG_M = 10e-9  # sugerencia: borde + 10 nm

_SUF = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3, "meg": 1e6, "g": 1e9}
_NUM = re.compile(r"^([-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?)(meg|[fpnumkg])?[a-z]*$", re.I)


def parse_val(s: str):
    """valor SPICE -> float en SI; None si no es un numero literal."""
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
            print(f"[{p}] no existe")
            continue
        res = scan(p, tol)
        if not res:
            print(f"[{p}] OK (ninguna L en borde de bin)")
            continue
        print(f"[{p}]")
        for where, dev, raw, v, hit in res:
            if v is None:
                print(f"  nota {where}: {dev} L={raw} es una expresion; revisala contra la tabla de bordes")
                continue
            e, ratio, sev = hit
            warn += 1
            print(f"  AVISO {where}: {dev} L={raw} esta en el borde de bin {fmt_um(e * 1e-6)} "
                  f"(severidad {sev}, LT/ng={ratio}). Usa L={fmt_um(e * 1e-6 + SUG_M)} "
                  f"(borde + 10 nm) si vas a hacer Monte Carlo de proceso.")
    return 2 if warn else 0


if __name__ == "__main__":
    sys.exit(main())
