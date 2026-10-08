#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_min_gf180.py - libs LTspice segmentadas (planas y autocontenidas) del PDK gf180mcuD.

Entrada : sm141064.ngspice NATIVO del PDK (el que trae open_pdks / gf180mcu-pdk).
Salida  : un archivo por esquina/caso, p. ej. gf180mcuD_ltspice_tt.lib, SIN `.lib` anidados,
          SIN rutas relativas y SIN depender de design.ngspice ni de gf180mcuD_ltspice.lib:
              .include "gf180mcuD_ltspice_tt.lib"
          y listo (modelos + parametros + subcircuitos xnfet_*/xpfet_* con ad/as/pd/ps/nrd/nrs).
Pensado para macOS (LTspice para Mac): un solo archivo por caso, ASCII, saltos de linea LF,
sin includes relativos, sin el archivo de 1.3 MB / 47 000 lineas.

Que hace
  * Reduce: solo los dispositivos pedidos (por defecto nfet/pfet 3.3 V y 6 V; los 05v0 salen
    de los 06v0) y solo los parametros globales que esos modelos necesitan.
  * Resuelve la anidacion `.lib 'sm141064.ngspice' X` de cada seccion nativa (typical, ss, ff, sf,
    fs, statistical) y la deja plana.
  * Traduce a LTspice: AGAUSS(nom,abs,sig) -> gauss(abs/sig) (en LTspice gauss(x) = N(0,sigma=x));
    un parametro global se sortea una vez por paso de .step; el mismatch (mis_vth) se sortea por
    instancia (esta dentro del subcircuito).  mulu0 no existe en LTspice: el mismatch de k (mis_k)
    NO se modela (ver README).  Se omiten los subcircuitos *_dss (SAB, usan el operador ?:).
  * Casos (nombres como en la version sky130):
        tt ss ff sf fs                    deterministas (design.ngspice por defecto: sin MC)
        tt_mm ss_mm ff_mm sf_mm fs_mm     mismatch por instancia sobre esa esquina (mm = tt_mm)
        mc                                variacion de proceso global (lib statistical)
        mcmm                              proceso + mismatch

Uso
    python make_min_gf180.py --src gf180mcuD --dst gf180mcuD_ltspice_min --force
    python make_min_gf180.py ... --devices nfet_03v3 pfet_03v3          (solo 3.3 V)
    python make_min_gf180.py ... --smoke-test                           (compara con el nativo en ngspice)
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

# caso: (seccion nativa, sw_stat_global, sw_stat_mismatch)
CASES = {
    "tt": ("typical", 0, 0), "ss": ("ss", 0, 0), "ff": ("ff", 0, 0),
    "sf": ("sf", 0, 0), "fs": ("fs", 0, 0),
    "tt_mm": ("typical", 0, 1), "ss_mm": ("ss", 0, 1), "ff_mm": ("ff", 0, 1),
    "sf_mm": ("sf", 0, 1), "fs_mm": ("fs", 0, 1),
    "mm": ("typical", 0, 1),
    "mc": ("statistical", 1, 0), "mcmm": ("statistical", 1, 1),
}
# parametros que en el nativo vienen de design.ngspice (aqui se fijan por caso)
PRELUDE_NAMES = {"sw_stat_global", "sw_stat_mismatch", "mc_skew", "res_mc_skew", "cap_mc_skew", "fnoicor"}
MODEL_LIB = re.compile(r"^(?P<dev>[np]fet_\d\dv\d(?:_nvt)?)_(?P<c>t|f|s|fs|sf|stat)$", re.I)
# geometria por defecto de los wrappers: (L, W)
WRAP_DEFAULT = {
    "nfet_03v3": ("0.28u", "2u"), "pfet_03v3": ("0.28u", "2u"),
    "nfet_05v0": ("0.6u", "2u"), "pfet_05v0": ("0.5u", "2u"),
    "nfet_06v0": ("0.7u", "2u"), "pfet_06v0": ("0.55u", "2u"),
    "nfet_06v0_nvt": ("1.8u", "2u"),
}

README_GF = """# gf180mcuD para LTspice (macOS y Windows) - libs segmentadas

Generado por `make_min_gf180.py` a partir del `sm141064.ngspice` NATIVO del PDK.
Cada archivo `gf180mcuD_ltspice_<caso>.lib` es plano y autocontenido (~160 KB en vez de 1.3 MB):
no hay `.lib` anidados, ni rutas relativas, ni `design.ngspice`, ni `gf180mcuD_ltspice.lib`.

## Uso (una sola linea en el netlist/esquematico)

    .lib "gf180mcuD_ltspice_tt.lib"

* Pon los `.lib` en la misma carpeta que tu `.asc`/`.cir` o usa la ruta absoluta entre comillas.
* Instancias:  `X1 d g s b xnfet_03v3 l=0.28u w=2u nf=1 m=1`  (igual para xpfet_03v3, xnfet_06v0,
  xpfet_06v0, xnfet_05v0, xpfet_05v0). ad/as/pd/ps/nrd/nrs se calculan solos.
* En un esquematico, SpiceModel = `xnfet_03v3`, etc. (los simbolos xnch/xpch de tu repo sirven).

## Casos

| archivo (`gf180mcuD_ltspice_...lib`) | seccion nativa | sw_stat_global | sw_stat_mismatch |
|---|---|---|---|
| tt, ss, ff, sf, fs | typical, ss, ff, sf, fs | 0 | 0 |
| tt_mm, ss_mm, ff_mm, sf_mm, fs_mm (mm = tt_mm) | idem | 0 | 1 |
| mc | statistical | 1 | 0 |
| mcmm | statistical | 1 | 1 |

Monte Carlo: `.lib "gf180mcuD_ltspice_mcmm.lib"` + `.step param run 1 300 1`.
Un parametro global se sortea una vez por paso; el mismatch se sortea por instancia.
`mc_skew`, `res_mc_skew`, `cap_mc_skew` = 3 y `fnoicor` = 0 (valores de design.ngspice) estan al inicio de cada archivo.

## Que cambia respecto al PDK nativo / a tu sm141064 editado

1. **Sorteos**: `agauss(0,1,3)` -> `gauss((1)/(3))`. En LTspice `gauss(x)` es N(0, sigma=x), asi que
   sigma = 1/3, igual que ngspice. (`{(1/3)*gauss(3)}` daria sigma = 1, tres veces mayor;
   `test0_gauss_sigma.cir` lo comprueba en tu LTspice.)
2. **Mismatch**: `delvto='mis_vth*sw_stat_mismatch'` se conserva y se sortea por instancia.
   **`mulu0` se omite** (LTspice no lo admite): el mismatch de movilidad `mis_k` no se modela. En ngspice,
   con y sin `mulu0` la sigma de Id es indistinguible (1.29 % vs 1.33 %, 500 muestras).
3. **pd/ps**: los wrappers usan el perimetro `2*int((nf+1)/2)*(W/nf+0.18u)` (convencion de los simbolos
   xschem de gf180mcu). En `gf180mcuD_ltspice.lib` pd/ps eran como ad/as (un area, no un perimetro), lo
   que anulaba las capacidades de pared lateral de las uniones: Cdd cambia ~20-30 % (p. ej. nfet
   L=0.28u W=2u: 1.93 fF -> 2.30 fF a Vds=0); Id y Cgg no cambian. `--legacy-wrapper` reproduce el anterior.
4. **Se omiten** los subcircuitos `*_dss` (SAB; usan el operador `?:` que LTspice no tiene) y las
   resistencias/capacitores/BJT/diodos. `--keep-dss` los conserva (con `?:` -> `if()`).
5. **nf**: el wrapper original no pasaba `nf` al modelo (siempre nf=1, aunque ad/as/pd/ps si usaban nf); aqui si.
   Efecto en Id (nfet L=0.6u): nf=2 W=4u +2.3 %, nf=4 W=10u +0.6 %, nf=8 W=20u +0.7 % (se reduce Id al aplicar nf).
6. Solo se conservan los parametros globales que usan los modelos elegidos.

## Verificacion (ngspice, PDK nativo vs estas libs)

`--smoke-test`: con los sorteos sustituidos por constantes, Id (2 sesgos) y Cgg de 22 dispositivos/geometrias
(nf, m, L y W de varios bins) en los 12 casos: diferencia relativa maxima 0 (identicos).
Esto valida corners, nf/m, mismatch (delvto) y el cableado de parametros estadisticos.
NO valida el motor de LTspice: para eso estan los tests.

## Pruebas para correr en LTspice

* `test0_gauss_sigma.cir` - sigma de gauss(1/3) y (1/3)*gauss(3) (1000 pasos).
* `test1_op_{tt,ss,ff}.cir` - Id contra ngspice nativo (<0.1 %). Incluye nf=2 m=2 y bordes de bin L=0.5u, 1.2u.
* `test2_mc_{mc,mm,mcmm}.cir` - 300 corridas, sigma/media de Id contra ngspice. Compara L=0.5u (borde de
  bin) con L=0.55u: en ngspice el gf180 es suave en los bordes (salto de Id <= 0.08 %); en sky130 LTspice
  difirio en el borde, aqui se comprueba.

## Regenerar

    python make_min_gf180.py --src CARPETA_CON_sm141064.ngspice --dst gf180mcuD_ltspice_min --force --smoke-test --write-tests
    python make_min_gf180.py ... --devices nfet_03v3 pfet_03v3     # solo 3.3 V
    python make_min_gf180.py ... --devices nfet_03v3 pfet_03v3 nfet_06v0 pfet_06v0 nfet_06v0_nvt
"""

HEADER = ("* gf180mcuD -> LTspice (generado por make_min_gf180.py a partir de sm141064.ngspice nativo)\n"
          "* Archivo plano y autocontenido: no necesita design.ngspice, gf180mcuD_ltspice.lib ni includes.\n")


# ----------------------------------------------------------------------------
# lectura y parseo del PDK nativo
# ----------------------------------------------------------------------------
_TRAIL = re.compile(r"^(?P<head>.*?=)\s*\{[^;]*\}\s*;\s*\+?\s*(?:\w+\s*=\s*)?(?P<ag>agauss\(.*\))\s*$", re.I)


def read_native(path: Path) -> list[str]:
    """Lee el PDK; admite la version nativa y la editada a mano para LTspice ({..};agauss(..))."""
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
    """-> lista de ('text', [lineas]) o ('subckt', nombre, [lineas])."""
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
    """nombres de subcircuitos instanciados por lineas X..."""
    names = set()
    for ln in lines:
        if re.match(r"^\s*x", ln, re.I):
            toks = [t for t in re.sub(r"'[^']*'", "''", ln).split() if "=" not in t]
            if len(toks) >= 2:
                names.add(toks[-1].lower())
    return names


def fix_ternary(s: str) -> str:
    """'(a==0) ? x : y' -> 'if(a==0,x,y)' (LTspice no tiene ?:)."""
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
    """Una linea 'name = ...gauss(...)...' dentro de un .param de subcircuito -> '{expr LTspice}'."""
    if "gauss(" not in ln.lower():
        return ln
    m = re.match(r"^(\s*\+?\s*(?:\.param\s+)?\w+\s*=\s*)(.*)$", ln, re.I)
    if not m:
        raise ValueError("linea con gauss no reconocida: " + ln)
    return f"{m.group(1)}{{{mp.convert_gauss(mp._value_expr(m.group(2).strip()))}}}"


def mm_subckts(lines: list[str], names: set[str], keep_mulu0: bool) -> list[str]:
    """Subcircuitos de fets_mm de los dispositivos elegidos, traducidos."""
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
# construccion de un caso
# ----------------------------------------------------------------------------
def _ident(s: str) -> set[str]:
    return {x.lower() for x in re.findall(r"(?<![\w.])[A-Za-z_]\w*", s)}


def expand_section(libs, sec: str, devs: set[str], _acc=None):
    """Recorre la seccion nativa (y sus refs) -> (texto de params, [nombres lib de modelo], usa_mm)."""
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
        # res, efuse, bjt_mc, ...: no hacen falta para los FET
    return acc


def build_case(libs, case: str, devs: list[str], keep_dss=False, keep_mulu0=False, legacy_wrapper=False):
    sec, sg, smm = CASES[case]
    devset = set(devs)
    allnames = devset | {ALIAS_05V0[d] for d in devs if d in ALIAS_05V0}
    acc = expand_section(libs, sec, devset)
    # parametros de seccion (traducidos, la ultima definicion de cada nombre gana)
    lines, names = mp.translate_params("\n".join(acc["params"]))
    defs: dict[str, str] = {}
    for ln, nm in zip(lines, names):
        defs.pop(nm.lower(), None)
        defs[nm.lower()] = ln
    # bloques de modelos
    body: list[str] = []
    for t in acc["models"]:
        body += [f"* ---- {t} (nativo: .lib {t}) ----"] + clean_model_lib(libs[t], keep_dss) + [""]
    if acc["mm"]:
        body += ["* ---- subcircuitos con mismatch (nativo: .lib fets_mm) ----"]
        body += mm_subckts(libs["fets_mm"], allnames, keep_mulu0)
    # nvt no tiene subcircuito mm: el propio bloque ya define nfet_06v0_nvt
    wraps = []
    for d in devs:
        for dd in [d] + ([ALIAS_05V0[d]] if d in ALIAS_05V0 else []):
            wraps += wrapper_lines(dd, legacy_wrapper)
    body_txt = "\n".join(body + wraps)
    # cierre transitivo de parametros necesarios
    need, todo = set(), list(_ident(body_txt))
    while todo:
        n = todo.pop()
        if n in need or n not in defs:
            continue
        need.add(n)
        todo += list(_ident(defs[n].split("=", 1)[1]))
    kept = [defs[n] for n in defs if n in need]
    # parametros usados pero no definidos (aparte de los de design.ngspice)
    used = set()
    for ln in kept:
        used |= _ident(ln.split("=", 1)[1])
    unresolved = sorted(u for u in used if u not in defs and u not in PRELUDE_NAMES
                        and u not in {"gauss", "int", "if", "abs", "sqrt", "exp", "min", "max"})
    prelude = [
        f".param sw_stat_global={sg} sw_stat_mismatch={smm}",
        ".param mc_skew=3 res_mc_skew=3 cap_mc_skew=3 fnoicor=0",
    ]
    txt = (HEADER + f"* caso: {case.upper()}  (seccion nativa: {sec}; sw_stat_global={sg}, sw_stat_mismatch={smm})\n"
           + f"* dispositivos: {', '.join(sorted(allnames))}\n"
           + "\n".join(prelude + [""] + kept + [""]) + "\n" + body_txt + "\n")
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt, unresolved


# ----------------------------------------------------------------------------
# verificacion estatica
# ----------------------------------------------------------------------------
def verify_text(txt: str, devs: list[str]) -> list[str]:
    p = []
    low = txt.lower()
    if "\r" in txt:
        p.append("contiene CR")
    if any(ord(c) > 126 for c in txt):
        p.append("caracteres no ASCII")
    if "\t" in txt:
        p.append("contiene tabuladores")
    if re.search(r"agauss\s*\(", low):
        p.append("queda agauss()")
    if re.search(r"^\s*\.lib\b", low, re.M):
        p.append("queda una linea .lib")
    if re.search(r"^[^*\n]*\?[^\n]*:", txt, re.M):
        p.append("queda un operador ?:")
    defined = {m.lower() for m in re.findall(r"^\s*\.subckt\s+(\S+)", txt, re.M | re.I)}
    for ref in _refs_in(txt.split("\n")):
        if ref not in defined and not ref.startswith("$"):
            p.append(f"subcircuito sin definir: {ref}")
    for d in devs:
        if d not in defined:
            p.append(f"falta el subcircuito {d}")
        if f"x{d}" not in defined:
            p.append(f"falta el wrapper x{d}")
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
            problems.append(f"{case}: parametro sin definir: {u}")
        for q in verify_text(txt, devs):
            problems.append(f"{case}: {q}")
        f = dst / f"{OUT_PREFIX}{case}.lib"
        f.write_text(txt)
        manifest.append((f.name, f.stat().st_size, txt.count("\n"), hashlib.sha256(txt.encode()).hexdigest()[:12]))
    lines = ["MANIFEST gf180mcuD LTspice", f"fuente: {SRC_NAME} sha256={hashlib.sha256(src.read_bytes()).hexdigest()[:16]}",
             f"dispositivos: {' '.join(devs)}", "", f"{'archivo':44s} {'bytes':>9s} {'lineas':>7s}  sha256[:12]"]
    lines += [f"{n:44s} {b:9d} {l:7d}  {h}" for n, b, l, h in manifest]
    lines += ["", "problemas: " + (str(len(problems)) if problems else "ninguno")] + problems
    (dst / "MANIFEST_gf180_ltspice.txt").write_text("\n".join(lines) + "\n")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, default=Path("."), help="carpeta con sm141064.ngspice nativo")
    ap.add_argument("--dst", type=Path, default=Path("gf180mcuD_ltspice_min"))
    ap.add_argument("--devices", nargs="+", default=DEFAULT_DEVICES, choices=KNOWN_DEVICES)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--keep-dss", action="store_true", help="conservar los subcircuitos *_dss (SAB)")
    ap.add_argument("--keep-mulu0", action="store_true", help="dejar mulu0 en las instancias (LTspice lo rechaza)")
    ap.add_argument("--legacy-wrapper", action="store_true",
                    help="pd/ps como en gf180mcuD_ltspice.lib original (sin perimetro)")
    ap.add_argument("--smoke-test", action="store_true")
    ap.add_argument("--write-tests", action="store_true",
                    help="escribe test0/test1/test2 para LTspice con referencias calculadas en ngspice")
    a = ap.parse_args(argv)
    src = a.src / SRC_NAME
    if not src.exists():
        print(f"no existe {src}", file=sys.stderr)
        return 1
    if a.dst.exists() and any(a.dst.iterdir()):
        if not a.force:
            print(f"{a.dst} existe; usa --force", file=sys.stderr)
            return 1
        shutil.rmtree(a.dst)
    libs = parse_libs(read_native(src))
    probs = write_all(libs, src, a.dst, a.devices, a)
    print(f"{len(CASES)} libs en {a.dst}; problemas estaticos: {len(probs)}")
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
