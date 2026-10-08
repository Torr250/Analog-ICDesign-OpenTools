#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_min_pdk.py - genera una versión reducida del PDK sky130A para ngspice.

Objetivo
--------
ngspice tarda ~4 s en leer los modelos del PDK completo aunque el circuito use
solo un par de transistores. Esta herramienta construye un PDK que contiene
únicamente los transistores NMOS/PMOS elegidos (por defecto 1.8 V, 1.8 V LVT y
5 V), manteniendo TODAS las secciones de esquina (tt, ss_ll, tt_mm, mc, ...) con
los mismos nombres, de modo que los netlists existentes solo cambian la ruta raíz.

Qué produce (un subconjunto exacto del árbol original)
------------------------------------------------------
    <dst>/libs.tech/combined/
        sky130.lib.spice               MODIFICADO: includes podados
        continuous/models_fet.spice    MODIFICADO: solo los dispositivos elegidos
        continuous/models_global.spice           copia idéntica
        continuous/parameters_{fet,res,cap}_*.spice   copias idénticas
        continuous/models_fet/sky130_fd_pr__<dispositivo>.spice   copias idénticas
    <dst>/MANIFEST.txt                 hashes sha256 y estado de cada archivo
    <dst>/libs.tech/combined/sections/ (solo con --split-sections)
        sky130_<sección>.lib.spice     una lib por sección (49), p. ej. sky130_tt.lib.spice

Qué se descarta: modelos de BJT, diodos, resistencias y capacitores, corners/*,
rescap/*, SONOS, RF, y parameters/{critical,montecarlo,invariant}.spice (estos
solo sirven a modelos discretos legacy; los FET continuos no los usan).

Uso
---
    python make_min_pdk.py                         # ./sky130A -> ./sky130A_min
    python make_min_pdk.py --src RUTA --dst RUTA --force
    python make_min_pdk.py --split-sections        # además, una lib por sección
    python make_min_pdk.py --check-netlist CMOS_Inverter.cir otro.cir
    python make_min_pdk.py --smoke-test            # compara resultados (requiere ngspice)

Notas
-----
* Las comprobaciones de integridad (todos los includes existen, secciones
  idénticas, copias byte a byte, opción scale presente) se ejecutan siempre.
* --smoke-test compara corrientes DC del PDK completo y del reducido en las
  esquinas deterministas (deben coincidir) y verifica que tt_mm y mc corran.
  Si existen las libs por sección, las valida igual y compara tiempos.

Destino LTspice (--target ltspice)
----------------------------------
    python make_min_pdk.py --target ltspice --src sky130A --dst sky130A_ltspice_min --force [--smoke-test]

Traduce los 6 FET continuos (nueva estructura del PDK) a LTspice, sin depender de ngspice:
  * geometria en METROS (sin .option scale): l w ad as pd ps nrd nrs sa sb sd en unidades SI,
    nf, mult (-> m= en la linea M);  nrd/nrs = -1 usa el valor por defecto del PDK (0.14/w[um]);
  * mismatch por instancia: el delvto del PDK se conserva; AGAUSS(0,1,1) -> .param gauss(1) dentro
    del subcircuito (LTspice sortea un valor por instancia);
  * proceso global: .param con gauss(sigma) a nivel global (un valor por paso de .step);
  * wrappers xnfet_*/xpfet_* con ad/as/pd/ps/nrd/nrs automaticos (misma interfaz que la lib actual);
  * secciones TT SS FF SF FS (deterministas), MC (proceso), MM (mismatch), MCMM (ambos), en
    sky130A_ltspice.lib y como archivos planos sky130A_ltspice_<seccion>.lib (macOS).
Monte Carlo en LTspice:   .lib "sky130A_ltspice_mcmm.lib"   +   .step param run 1 300 1
--smoke-test compara en ngspice (gauss -> 0) PDK completo vs traduccion: Id y Cgg, 5 esquinas.
AVISO: L exactamente en un borde de bin da otra sigma de proceso que ngspice; usa L = borde + 10 nm
(se genera README_ltspice.md con la tabla y check_bin_edges.py avisa; --check-netlist tambien).
Nota: LTspice no admite mulu0, asi que el mismatch de k (mis_k, solo gf180) no se modela.

Libs por sección (--split-sections)
-----------------------------------
ngspice tarda mucho más con el archivo multi-sección que con una lib de una sola
sección (en un inversor: ~2.5 s vs ~0.6 s con el PDK reducido; ~4.9 s vs ~0.7 s
con el completo). Cada archivo sections/sky130_<sec>.lib.spice contiene SOLO la
sección <sec>, con el mismo nombre de sección, así que en un netlist basta cambiar:
    .lib /ruta/libs.tech/combined/sky130.lib.spice tt
por
    .lib /ruta/libs.tech/combined/sections/sky130_tt.lib.spice tt
Los includes se reescriben con prefijo ../ (relativos a sections/); el resto del
contenido es idéntico al de la sección original (se verifica línea por línea).
Con --split-sections sobre un PDK reducido ya existente no hace falta --force:
solo se regeneran las libs por sección.
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
# Includes de la lib que se conservan (todo lo demás se descarta).
KEEP_RE = re.compile(
    r"^continuous/(?:models_global\.spice|models_fet\.spice|"
    r"parameters_(?:fet|res|cap)_\w+\.spice)$"
)
SCALE_RE = re.compile(r"^\s*\.options?\s+.*\bscale\s*=", re.I | re.M)
MODEL_RE = re.compile(r"sky130_fd_pr__(\w+)", re.I)

MODELS_FET_REL = "continuous/models_fet.spice"
HEADER = "* Versión reducida generada por make_min_pdk.py ({date}).\n" \
         "* Dispositivos FET incluidos: {devices}\n" \
         "* Ver MANIFEST.txt en la raíz para el detalle de archivos.\n*\n"


# ----------------------------------------------------------------------------
# utilidades
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
SPLIT_MARK = "libs derivadas por sección"


def lib_section_lines(text: str) -> dict[str, list[str]]:
    """{sección: líneas internas (sin .lib/.endl)} en el orden del archivo."""
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
    """Recorre recursivamente los .include a partir de `entry`.

    Devuelve (archivos_alcanzados, [(ruta_faltante, archivo_que_la_incluye)]).
    Las rutas relativas se resuelven respecto al directorio del archivo que
    contiene el include (igual que hace ngspice).
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
# construcción
# ----------------------------------------------------------------------------
README_NG = """# sky130A_min (ngspice)

PDK sky130A reducido para ngspice: conserva solo los 6 FET continuos (1.8 V, 1.8 V LVT y 5 V) y las
49 secciones de esquina del original, con los mismos nombres. Sirve para que ngspice lea el modelo
mucho mas rapido. Generado por make_min_pdk.py; MANIFEST.txt lista cada archivo con su sha256.

## Dispositivos
nfet_01v8  pfet_01v8  nfet_01v8_lvt  pfet_01v8_lvt  nfet_g5v0d10v5  pfet_g5v0d10v5
Mismos nombres de subcircuito que el PDK original (sky130_fd_pr__nfet_01v8, etc.).
NO incluye: BJT, diodos, resistencias, capacitores, SONOS, RF ni celdas digitales. Si un netlist los
usa, ngspice dara "unknown subckt". Para otros FET: --devices en el generador.

## Estructura
    libs.tech/combined/
        sky130.lib.spice                    lib completa (49 secciones), includes podados
        sections/sky130_<seccion>.lib.spice una lib por seccion (49 archivos)  <- recomendada
        continuous/                         modelos y parametros (copias identicas al original)
    MANIFEST.txt

## Uso
En el netlist, solo cambia la ruta de la lib:

    .lib /ruta/sky130A_min/libs.tech/combined/sky130.lib.spice tt           (lib completa)
    .lib /ruta/sky130A_min/libs.tech/combined/sections/sky130_tt.lib.spice tt   (una seccion, mas rapido)

El nombre de seccion al final (tt) se repite a proposito: es la seccion .lib dentro del archivo, y
es la misma que tiene el original, asi que los netlists existentes no cambian. Secciones:
tt ss ff sf fs; ll hl lh hh (res/cap, no afectan a los FET); combinadas ss_ll ... ff_hh; todas con
sufijo _mm (mismatch por instancia); y mc (proceso global, para .step/.control con semillas).

## Velocidad (inversor, referencia)
    PDK completo, sky130.lib.spice      ~4.9 s      PDK reducido, sky130.lib.spice      ~2.5 s
    PDK completo, una seccion           ~0.7 s      PDK reducido, una seccion           ~0.6 s
El mayor ahorro viene de usar la lib de una sola seccion; reducir dispositivos ayuda sobre todo
con la lib multi-seccion. Los tiempos dependen de la maquina.

## Que cambia respecto al original
* sky130.lib.spice: solo se podan los .include de modelos descartados.
* continuous/models_fet.spice: lista solo los 6 dispositivos.
* sections/*: contenido de la seccion identico (verificado linea a linea); los includes llevan
  prefijo ../ porque la lib vive un nivel mas abajo.
* Todo lo demas son copias byte a byte (estado "identico" en MANIFEST.txt).

## Validacion (--smoke-test, requiere ngspice)
Compara Id en DC entre el PDK completo y el reducido en las esquinas deterministas (deben coincidir)
y comprueba que tt_mm y mc corran. Ademas, la verificacion de integridad corre siempre: todos los
includes existen, las secciones son identicas al original y la opcion scale esta presente.

## Regenerar
    python make_min_pdk.py --src RUTA/sky130A --dst sky130A_min --split-sections --force
    python make_min_pdk.py --check-netlist mi_circuito.cir     (avisa de dispositivos o secciones faltantes)

## Relacionado
sky130A_ltspice_min es otra cosa: traduccion a LTspice (--target ltspice), con su propio README_ltspice.md.
"""

def build(src: Path, dst: Path, devices, force: bool = False, split: bool = False,
          log=print):
    comb_src = src / "libs.tech" / "combined"
    lib_src = comb_src / "sky130.lib.spice"
    if not lib_src.is_file():
        sys.exit(f"ERROR: no encuentro {lib_src}\n"
                 f"       --src debe apuntar al directorio sky130A "
                 f"(el que contiene libs.tech/).")

    models_src = comb_src / "continuous" / "models_fet"
    for d in devices:
        if not (models_src / f"sky130_fd_pr__{d}.spice").is_file():
            sys.exit(f"ERROR: no existe el modelo del dispositivo '{d}' en {models_src}")

    if dst.exists():
        if not force:
            sys.exit(f"ERROR: {dst} ya existe (use --force para regenerarlo).")
        shutil.rmtree(dst)

    comb_dst = dst / "libs.tech" / "combined"
    (comb_dst / "continuous" / "models_fet").mkdir(parents=True)

    # 1) sky130.lib.spice podado --------------------------------------------
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
        sys.exit("ERROR: la lib original no incluye continuous/models_fet.spice; "
                 "estructura de PDK no reconocida.")
    (comb_dst / "sky130.lib.spice").write_text("".join(out))

    # 2) archivos copiados sin cambios ----------------------------------------
    verbatim: list[str] = []
    for rel in sorted(kept - {MODELS_FET_REL}):
        s = comb_src / rel
        if not s.is_file():
            sys.exit(f"ERROR: la lib incluye {rel} pero no existe en el origen.")
        shutil.copyfile(s, comb_dst / rel)
        verbatim.append(rel)

    # 3) continuous/models_fet.spice nuevo ---------------------------------------
    mf = ["* Modelos FET continuos - versión reducida (make_min_pdk.py)\n"]
    for d in sorted(devices):
        mf.append(f'.include "models_fet/sky130_fd_pr__{d}.spice"\n')
    (comb_dst / MODELS_FET_REL).write_text("".join(mf))

    # 4) modelos de los dispositivos ---------------------------------------------
    for d in sorted(devices):
        rel = f"continuous/models_fet/sky130_fd_pr__{d}.spice"
        shutil.copyfile(comb_src / rel, comb_dst / rel)
        verbatim.append(rel)

    # 5) verificación de integridad -------------------------------------------
    problems = verify(src, dst, devices, verbatim)

    # 5b) libs por sección (opcional) ---------------------------------------------
    split_files: list[Path] = []
    if split:
        split_files, sp = split_sections(dst)
        problems += sp

    (dst / "README_sky130A_min.md").write_text(README_NG)

    # 6) manifiesto -----------------------------------------------------------------
    write_manifest(src, dst, devices, verbatim, dropped, problems)
    if split_files:
        update_manifest_split(dst, split_files)

    # 7) resumen ----------------------------------------------------------------------
    files = [p for p in dst.rglob("*") if p.is_file()]
    size_kb = sum(p.stat().st_size for p in files) / 1024
    secs = lib_sections((comb_dst / "sky130.lib.spice").read_text())
    log(f"PDK reducido: {dst}")
    log(f"  archivos: {len(files)} (incluye MANIFEST.txt)   tamaño: {size_kb:.0f} KB")
    log(f"  secciones de esquina conservadas: {len(secs)}")
    log(f"  includes descartados (distintos): {len(dropped)}")
    if split_files:
        log(f"  libs por sección: {len(split_files)} archivos en libs.tech/combined/{SECTIONS_DIR}/")
    if problems:
        log("\nPROBLEMAS DETECTADOS:")
        for p in problems:
            log(f"  - {p}")
    else:
        log("  verificación de integridad: OK")
    return problems


def verify(src: Path, dst: Path, devices, verbatim) -> list[str]:
    problems: list[str] = []
    comb_src = src / "libs.tech" / "combined"
    comb_dst = dst / "libs.tech" / "combined"
    lib_dst = comb_dst / "sky130.lib.spice"

    seen, missing = walk_includes(lib_dst)
    for path, who in missing:
        problems.append(f"include faltante: {path} (referenciado desde {who})")

    s_src = lib_sections((comb_src / "sky130.lib.spice").read_text(errors="replace"))
    s_dst = lib_sections(lib_dst.read_text())
    if s_src != s_dst:
        problems.append("las secciones de la lib reducida no coinciden con las originales: "
                        f"{sorted(set(s_src) ^ set(s_dst))}")

    for rel in verbatim:
        if sha256(comb_src / rel) != sha256(comb_dst / rel):
            problems.append(f"copia no idéntica: {rel}")

    scale_found = any(SCALE_RE.search(f.read_text(errors="replace")) for f in seen)
    if not scale_found:
        problems.append("no se encontró '.option scale=...' en los archivos conservados; "
                        "W y L en micras no serían interpretados correctamente")

    for d in devices:
        f = (comb_dst / f"continuous/models_fet/sky130_fd_pr__{d}.spice").resolve()
        if f not in seen:
            problems.append(f"el dispositivo {d} no es alcanzable desde la lib")
    return problems


def write_manifest(src, dst, devices, verbatim, dropped, problems):
    comb_src = src / "libs.tech" / "combined"
    comb_dst = dst / "libs.tech" / "combined"
    lines = [
        "MANIFEST - PDK sky130A reducido",
        f"generado: {_dt.datetime.now().isoformat(timespec='seconds')}",
        f"origen:   {src.resolve()}",
        f"origen sha256 sky130.lib.spice: {sha256(comb_src / 'sky130.lib.spice')}",
        f"dispositivos: {', '.join(devices)}",
        "",
        "estado     sha256                                                            bytes  ruta",
    ]
    for rel in ["sky130.lib.spice", MODELS_FET_REL] + verbatim:
        f = comb_dst / rel
        status = "MODIFICADO" if rel in ("sky130.lib.spice", MODELS_FET_REL) else "identico  "
        lines.append(f"{status} {sha256(f)}  {f.stat().st_size:>8}  libs.tech/combined/{rel}")
    lines += ["", f"includes descartados de la lib original ({len(dropped)} distintos):"]
    for p, c in sorted(dropped.items()):
        lines.append(f"  {c:3d} x {p}")
    lines += ["", "verificación: " + ("OK" if not problems else "CON PROBLEMAS")]
    lines += [f"  - {p}" for p in problems]
    (dst / "MANIFEST.txt").write_text("\n".join(lines) + "\n")


# ----------------------------------------------------------------------------
# --split-sections
# ----------------------------------------------------------------------------
def split_sections(dst: Path):
    """Escribe una lib por sección en <dst>/libs.tech/combined/sections/.

    Devuelve (lista_de_archivos, problemas).
    """
    comb = dst / "libs.tech" / "combined"
    lib = comb / "sky130.lib.spice"
    if not lib.is_file():
        sys.exit(f"ERROR: no encuentro {lib}; genere primero el PDK reducido.")
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
            if m:  # rutas relativas a combined/ -> relativas a combined/sections/
                line = line.replace(m.group(1), "../" + m.group(1), 1)
            body.append(line)
        text = (f"* Sección '{name}' extraída de ../sky130.lib.spice "
                f"(make_min_pdk.py --split-sections)\n"
                f".lib {name}\n" + "\n".join(body) + f"\n.endl {name}\n")
        f = out_dir / f"sky130_{name}.lib.spice"
        f.write_text(text)
        files.append(f)
    return files, verify_split(dst)


def verify_split(dst: Path) -> list[str]:
    """Cada lib por sección debe reproducir la sección original y sus includes existir."""
    comb = dst / "libs.tech" / "combined"
    orig = lib_section_lines((comb / "sky130.lib.spice").read_text(errors="replace"))
    problems: list[str] = []
    for name, lines in orig.items():
        f = comb / SECTIONS_DIR / f"sky130_{name}.lib.spice"
        if not f.is_file():
            problems.append(f"falta {f.relative_to(dst)}")
            continue
        got = lib_section_lines(f.read_text(errors="replace"))
        if list(got) != [name]:
            problems.append(f"{f.name}: debe contener exactamente la sección '{name}', "
                            f"contiene {list(got)}")
            continue
        restored = []
        for line in got[name]:
            m = INCLUDE_RE.match(line)
            if m:
                p = m.group(1)
                if not p.startswith("../"):
                    problems.append(f"{f.name}: include sin prefijo ../ -> {p}")
                elif not (f.parent / p).is_file():
                    problems.append(f"{f.name}: include inexistente -> {p}")
                line = line.replace(p, p[3:], 1) if p.startswith("../") else line
            restored.append(line)
        if restored != lines:
            problems.append(f"{f.name}: el contenido difiere de la sección original")
    return problems


def update_manifest_split(dst: Path, files) -> None:
    """Añade (o reemplaza) el bloque de libs por sección en MANIFEST.txt."""
    mf = dst / "MANIFEST.txt"
    text = mf.read_text() if mf.is_file() else "MANIFEST - PDK sky130A reducido\n"
    cut = text.find("\n" + SPLIT_MARK)
    if cut != -1:
        text = text[:cut].rstrip("\n") + "\n"
    lines = ["", f"{SPLIT_MARK} ({len(files)} archivos en libs.tech/combined/{SECTIONS_DIR}/):"]
    for f in files:
        lines.append(f"derivado   {sha256(f)}  {f.stat().st_size:>8}  "
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
            print(f"[{p}] no existe")
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
            status.append("dispositivos NO incluidos en el PDK reducido: " +
                          ", ".join(f"{k} (x{v})" for k, v in sorted(bad.items())))
        for s in secs:
            if sections and s not in sections:
                ok = False
                status.append(f"sección '{s}' no existe en la lib reducida")
        if not secs:
            status.append("aviso: no encontré una línea '.lib ...sky130.lib.spice <sección>'")
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
        print("smoke-test: ngspice no está en el PATH; omitido.")
        return True
    lib_full = (src / "libs.tech" / "combined" / "sky130.lib.spice").resolve()
    lib_min = (dst / "libs.tech" / "combined" / "sky130.lib.spice").resolve()
    ok = True
    with tempfile.TemporaryDirectory(prefix="smoke_") as t:
        tmp = Path(t)
        print(f"{'sección':8} {'máx dif. relativa completo vs reducido':>40}")
        for sec in ("tt", "ss", "ff", "sf", "fs"):
            a, _ = _smoke_run(ng, lib_full, sec, devices, tmp)
            b, _ = _smoke_run(ng, lib_min, sec, devices, tmp)
            if len(a) != len(devices) or len(b) != len(devices):
                print(f"{sec:8} FALLO: sin resultados (completo={len(a)}, reducido={len(b)})")
                ok = False
                continue
            diff = max(abs(a[k] - b[k]) / max(abs(a[k]), 1e-30) for k in a)
            flag = "OK" if diff <= 1e-9 else "DIFIERE"
            ok &= diff <= 1e-9
            print(f"{sec:8} {diff:>40.2e}  {flag}")
        for sec in ("tt_mm", "mc"):
            b, _ = _smoke_run(ng, lib_min, sec, devices, tmp)
            good = len(b) == len(devices)
            ok &= good
            print(f"{sec:8} {'corre en el reducido' if good else 'FALLO':>40}  "
                  f"{'OK' if good else 'FALLO'}")

        sect = dst / "libs.tech" / "combined" / SECTIONS_DIR
        if sect.is_dir():
            print("\nlibs por sección (reducido) vs lib original del PDK completo:")
            for sec in ("tt", "ss", "ff", "sf", "fs"):
                a, _ = _smoke_run(ng, lib_full, sec, devices, tmp)
                b, _ = _smoke_run(ng, (sect / f"sky130_{sec}.lib.spice").resolve(),
                                  sec, devices, tmp)
                good = len(a) == len(devices) == len(b)
                diff = max(abs(a[k] - b[k]) / max(abs(a[k]), 1e-30) for k in a) if good else 1.0
                ok &= good and diff <= 1e-9
                print(f"{sec:8} {diff:>40.2e}  {'OK' if good and diff <= 1e-9 else 'DIFIERE'}")
            for sec in ("tt_mm", "mc"):
                b, _ = _smoke_run(ng, (sect / f"sky130_{sec}.lib.spice").resolve(),
                                  sec, devices, tmp)
                good = len(b) == len(devices)
                ok &= good
                print(f"{sec:8} {'corre desde su lib por sección' if good else 'FALLO':>40}  "
                      f"{'OK' if good else 'FALLO'}")
            print("\ntiempo total de ngspice, esquina tt (mejor de 2 corridas; orden de magnitud):")
            for label, lib in (("PDK completo, lib multi-sección", lib_full),
                               ("PDK reducido, lib multi-sección", lib_min),
                               ("PDK reducido, lib por sección", (sect / "sky130_tt.lib.spice").resolve())):
                t = min(_smoke_run(ng, lib, "tt", devices, tmp)[1] for _ in range(2))
                print(f"  {label:34} {t:6.2f} s")
    return ok


# ============================================================================
# Destino LTspice (--target ltspice)
# ============================================================================
LT_CORNERS = ("tt", "ss", "ff", "sf", "fs")
# (nombre de sección, corner de parámetros, MC_PR_SWITCH, MC_MM_SWITCH)
LT_SECTIONS = (
    ("TT", "tt", 0, 0), ("SS", "ss", 0, 0), ("FF", "ff", 0, 0),
    ("SF", "sf", 0, 0), ("FS", "fs", 0, 0),
    ("MC", "tt", 1, 0), ("MM", "tt", 0, 1), ("MCMM", "tt", 1, 1),
)
LT_DIR = "sky130A_ltspice"
LT_SECTIONS = list(LT_SECTIONS)


def lt_extra_sections(src_lib: Path) -> list[tuple[str, str, int, int]]:
    """Secciones del sky130.lib.spice original (49) que aun no estan en LT_SECTIONS, como
    (nombre, corner_fet, MC_PR_SWITCH, MC_MM_SWITCH). Se leen del original (no se asumen):
    corner = parameters_fet_<c>.spice incluido, switches = los .param de la seccion.
    Los corners de res/cap (ll hl lh hh) no cambian los 6 FET (verificado), pero se generan
    para que los netlists puedan usar los mismos nombres de seccion que en ngspice."""
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
            raise SystemExit(f"seccion '{name}' del PDK original no interpretable")
        out.append((name, mc.group(1), int(pr.group(1)), int(mm.group(1))))
    return out

# parámetros de instancia visibles (en METROS) y su valor por defecto
INST_DEFAULTS = (("l", "1u"), ("w", "1u"), ("nf", "1"), ("ad", "0"), ("as", "0"),
                 ("pd", "0"), ("ps", "0"), ("nrd", "-1"), ("nrs", "-1"),
                 ("sa", "0"), ("sb", "0"), ("sd", "0"))

# geometría por defecto de los wrappers xnfet_/xpfet_ (igual que sky130A_ltspice.lib)
WRAP_DEFAULT_L = {"nfet_01v8": "0.15u", "pfet_01v8": "0.15u", "nfet_01v8_lvt": "0.15u",
                  "pfet_01v8_lvt": "0.35u", "nfet_g5v0d10v5": "0.5u", "pfet_g5v0d10v5": "0.5u"}


# ----------------------------------------------------------------------------
# utilidades de expresiones
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
    """Primera llamada name(...) desde start -> (i0, i1, args) o None (paréntesis balanceados)."""
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

    Semántica de ngspice: agauss = nom + abs/sig*N(0,1);  gauss = nom + nom*rel/sig*N(0,1).
    En LTspice gauss(x) = N(0, sigma=x).  Si `hoist` es una lista, cada llamada se reemplaza por un
    nombre (prefix1, prefix2, ...) y la definición se agrega a la lista (para `.param` por instancia).
    """
    while True:
        a, g = _find_call(expr, "agauss"), None
        if a is None:
            g = _find_call(expr, "gauss")
            if g is None:
                break
        i0, i1, args = a or g
        if len(args) != 3:
            raise ValueError(f"gauss con {len(args)} argumentos: {expr[i0:i1]}")
        nom, spread, sig = args
        if a:
            body = f"Qgauss(({spread})/({sig}))"
            full = body if _is_zero(nom) else f"({nom}+{body})"
        else:  # GAUSS: sigma = |nom*rel/sig|; con nom=0 es exactamente 0
            full = "0" if _is_zero(nom) else f"({nom}+Qgauss(abs(({nom})*({spread})/({sig}))))"
        if hoist is not None and full != "0":
            name = f"{prefix}{len(hoist) + 1}"
            g_full = full.replace("Qgauss", "gauss")
            hoist.append(f"{name} = {{{g_full}}}")
            full = name
        expr = expr[:i0] + full + expr[i1:]
    return expr.replace("Qgauss", "gauss")


def rename_lw(expr: str) -> str:
    """l,w (µm en el PDK) -> lu,wu (variables internas en µm)."""
    expr = re.sub(r"(?<![\w.])l(?![\w.])", "lu", expr)
    return re.sub(r"(?<![\w.])w(?![\w.])", "wu", expr)


# ----------------------------------------------------------------------------
# .param globales (models_global.spice, parameters_fet_*.spice)
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
    """'a = 1 b = {x+1} + y ...' -> [(a,'1'),(b,'{x+1} + y')].  El valor termina en el siguiente 'nombre ='."""
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
    """Devuelve ([líneas .param LTspice], [nombres definidos])."""
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
# dispositivos
# ----------------------------------------------------------------------------
def parse_device(text: str) -> dict:
    """Separa subckt, .param de cabecera, línea M y bines de un archivo models_fet/*.spice."""
    m = re.search(r"^\.subckt\s+(\S+)\s+(.*)$", text, re.I | re.M)
    name = m.group(1)
    ports = [p for p in m.group(2).split() if "=" not in p]
    first_model = re.search(r"^\.model\b", text, re.I | re.M)
    head = text[m.start():first_model.start()]
    ends = re.search(r"^\.ends\b.*$", text, re.I | re.M)
    models = text[first_model.start():ends.start()]
    lines = _logical_lines(head)[1:]            # sin la línea .subckt
    params: dict[str, str] = {}
    mline = None
    for ln in lines:
        if re.match(r"\.param\b", ln, re.I):
            for k, v in _assignments(ln[len(".param"):]):
                params[k.lower()] = _value_expr(v)
        elif re.match(r"m\w*\s", ln, re.I):
            mline = ln
    # el .param de cabecera a veces viene sin '=' pegado al bloque (+ ...): ya unido por _logical_lines
    if mline is None:
        raise ValueError(f"{name}: no se encontró la línea M")
    mt = mline.split()
    mname, nodes, model = mt[0], mt[1:5], mt[5]
    rest = " ".join(mt[6:])
    mp = {k.lower(): v for k, v in _assignments(rest)}
    return dict(name=name, ports=ports, params=params, mname=mname, nodes=nodes,
                model=model, mparams=mp, models=models.rstrip() + "\n")



BIN_TOL = 1e-9   # tolerancia relativa en los bordes de bin (LTspice: 0.42u -> 4.1999999999999995e-07 < wmin)


def widen_bins(models: str, tol: float = BIN_TOL) -> str:
    """Desplaza lmin/lmax/wmin/wmax de todos los bines un factor (1-tol) hacia abajo.
    Los bordes siguen siendo contiguos, pero un valor nominal como W=0.42u (que en doble precision
    queda 1 ulp por debajo de wmin=4.2e-7) cae en el bin correcto en vez de en ninguno."""
    def fix(m):
        return f"{m.group(1)} = {float(m.group(2)) * (1.0 - tol):.12g}"
    return re.sub(r"\b(lmin|lmax|wmin|wmax)\s*=\s*([-+]?\d[\d.]*(?:[eE][-+]?\d+)?)", fix, models)


def build_core(dev: dict) -> str:
    """Subcircuito núcleo en METROS para LTspice (bines sin cambios)."""
    p, mp = dev["params"], dev["mparams"]
    hoist: list[str] = []
    internal: list[str] = []
    # derivados internos en micras
    nrd_default = rename_lw(_value_expr(p.get("nrd", "0.14/w")))
    nrs_default = rename_lw(_value_expr(p.get("nrs", "0.14/w")))
    inst = {k for k, _ in INST_DEFAULTS}
    for k, v in p.items():                       # swx_* y demás derivados
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
    """xnfet_*/xpfet_*: calcula ad/as/pd/ps/nrd/nrs en metros (misma interfaz que el wrapper actual)."""
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


HEADER = ("* sky130A -> LTspice (generado por make_min_pdk.py --target ltspice)\n"
          "* Geometria en METROS (el PDK original usa micras). Parametros: l w nf ad as pd ps nrd nrs sa sb sd mult\n")


def build_ltspice(src: Path, dst: Path, devices: list[str]) -> list[str]:
    """Genera el PDK LTspice en dst.  src = directorio sky130A original."""
    cont = src / "libs.tech" / "combined" / "continuous"
    problems: list[str] = []
    out = dst / LT_DIR
    out.mkdir(parents=True, exist_ok=True)
    LT_SECTIONS.extend(lt_extra_sections(src / "libs.tech" / "combined" / "sky130.lib.spice"))

    # modelos y wrappers (primero, para saber qué parámetros globales se necesitan)
    models, wraps = [HEADER], [HEADER]
    for d in devices:
        dev = parse_device((cont / "models_fet" / f"sky130_fd_pr__{d}.spice").read_text())
        models.append(build_core(dev))
        wraps.append(build_wrapper(d))
    models_txt = "\n".join(models)
    (out / "models_fet.inc").write_text(models_txt)
    (out / "wrappers.inc").write_text("\n".join(wraps))

    # parámetros globales: solo los que alcanzan los modelos (cierre transitivo)
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
    (out / "globals.inc").write_text(HEADER + "\n".join(keep(g_lines, g_names)) + "\n")
    for c in LT_CORNERS:
        (out / f"params_{c}.inc").write_text(HEADER + "\n".join(keep(*corner_defs[c])) + "\n")

    # libs: una sección por caso en sky130A_ltspice.lib + un archivo plano por caso
    main = [HEADER, "* Uso: .lib \"sky130A_ltspice.lib\" TT   (secciones: ver MANIFEST_ltspice.txt; mismos nombres que sky130.lib.spice + MM MCMM)",
            "* Archivo plano (p. ej. macOS): .lib \"sky130A_ltspice_tt.lib\"\n"]
    for sec, corner, pr, mm in LT_SECTIONS:
        def body(sep):
            return [f".param MC_PR_SWITCH={pr} MC_MM_SWITCH={mm}",
                    ".param corner_factor=1 process_mc_factor=1 mismatch_factor=1",
                    f'.inc "{LT_DIR}{sep}params_{corner}.inc"',
                    f'.inc "{LT_DIR}{sep}globals.inc"',
                    f'.inc "{LT_DIR}{sep}models_fet.inc"',
                    f'.inc "{LT_DIR}{sep}wrappers.inc"']
        main += [f".LIB {sec}"] + body("\\") + [f".ENDL {sec}\n"]
        (dst / f"sky130A_ltspice_{sec.lower()}.lib").write_text(HEADER + "\n".join(body("/")) + "\n")
    (dst / "sky130A_ltspice.lib").write_text("\n".join(main))
    return problems


# ----------------------------------------------------------------------------
# verificación estática del PDK LTspice
# ----------------------------------------------------------------------------
_FUNCS = {"sqrt", "if", "gauss", "exp", "abs", "int", "min", "max", "pwr", "ln", "log", "log10", "sin", "cos"}


def verify_ltspice(dst: Path) -> list[str]:
    """Comprobaciones sin simulador: includes existentes, símbolos definidos, sin restos de ngspice."""
    problems: list[str] = []
    out = dst / LT_DIR
    texts = {p: p.read_text() for p in list(out.glob("*.inc")) + list(dst.glob("sky130A_ltspice*.lib"))}
    # 1) includes
    for p, t in texts.items():
        if p.suffix != ".lib":
            continue
        for m in re.finditer(r'^\.inc\s+"([^"]+)"', t, re.M | re.I):
            if not (dst / m.group(1).replace("\\", "/")).exists():
                problems.append(f"{p.name}: include inexistente {m.group(1)}")
    # 2) restos de ngspice
    for p, t in texts.items():
        for pat, why in ((r"agauss", "AGAUSS sin convertir"), (r"^\s*\.options?\s+.*scale", "opción scale")):
            if re.search(pat, t, re.I | re.M):
                problems.append(f"{p.name}: {why}")
    # 3) .subckt/.ends balanceados
    mt = texts[out / "models_fet.inc"]
    if len(re.findall(r"^\.subckt", mt, re.M | re.I)) != len(re.findall(r"^\.ends", mt, re.M | re.I)):
        problems.append("models_fet.inc: .subckt/.ends desbalanceados")
    # 4) símbolos indefinidos en expresiones {...} de cada sección
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
                        problems.append(f"sección {sec}: símbolo no definido '{name}' en {fn}.inc: {s[:70]}")
                if mp:
                    scope |= {x.lower() for x in re.findall(r"([A-Za-z_]\w*)\s*=", s[len(".param"):])}
            if len(problems) > 20:
                return problems
    return problems


def write_manifest_ltspice(dst: Path, devices, problems) -> None:
    out = dst / LT_DIR
    lines = [f"# sky130A -> LTspice  ({_dt.datetime.now():%Y-%m-%d %H:%M})",
             f"dispositivos: {' '.join(devices)}",
             f"secciones: {' '.join(s[0] for s in LT_SECTIONS)}",
             f"verificación estática: {'OK' if not problems else 'CON PROBLEMAS'}"]
    lines += [f"  - {p}" for p in problems]
    lines += ["", "# archivos (sha256, tamaño)"]
    for p in sorted(list(out.glob("*")) + list(dst.glob("sky130A_ltspice*.lib"))):
        lines.append(f"{sha256(p)}  {p.stat().st_size:>9}  {p.relative_to(dst).as_posix()}")
    lines += ["", "# AVISO: L en borde de bin (ver README_ltspice.md y check_bin_edges.py)"]
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
        return ["  (check_bin_edges.py no encontrado junto al generador: sin tabla)"]
    out = ["  dispositivo        L_borde(um)  LT/ng(sens. sw_polycd)  severidad"]
    for d, rows in cbe.BIN_EDGES.items():
        for e, r, sev in rows:
            out.append(f"  {d:<17} {e:>10g}  {r:>22.2f}  {sev}")
    return out


README_LT = """# sky130A para LTspice (sky130A_ltspice_min)

Uso rapido
    .lib "sky130A_ltspice_tt.lib"        (tt ss ff sf fs: deterministas)
    .lib "sky130A_ltspice_mc.lib"        + .step param run 1 300 1   (proceso global)
    .lib "sky130A_ltspice_mm.lib"        (mismatch por instancia)
    .lib "sky130A_ltspice_mcmm.lib"      (ambos)
Secciones: las mismas 49 de sky130.lib.spice (tt ss ff sf fs, ll hl lh hh, ss_ll ... ff_hh, todas las
_mm y mc) + MM y MCMM (mismatch solo / proceso+mismatch con parametros tt). Se usan igual:
    .lib "sky130A_ltspice.lib" ss_hl      o el archivo plano   .lib "sky130A_ltspice_ss_hl.lib"
Los sufijos de res/cap (ll hl lh hh) solo cambian resistencias/capacitores, que no se traducen: para
estos 6 FET dan EXACTAMENTE lo mismo que su corner base (ss_hl == ss). Existen para que un netlist
pueda cambiar de seccion sin editar nombres. sufijo _mm = mismatch por instancia activo; mc = proceso
global (usar con .step param run 1 N 1). Nota: el original no define sf_lh ni sf_lh_mm; tampoco aqui.
Dispositivos (subcircuitos con parametros l w nf mult ad as pd ps nrd nrs):
    xnfet_01v8 xpfet_01v8 xnfet_01v8_lvt xpfet_01v8_lvt xnfet_g5v0d10v5 xpfet_g5v0d10v5

## Validacion
* Las 24 secciones deterministas (tt..ff_hh): Id y Cgg de 23 geometrias contra el PDK completo en
  ngspice, diferencia 0 (--smoke-test). Las secciones _mm y mc: solo verificacion estatica; MC y
  mismatch validados con las corridas de LTspice descritas abajo (secciones mc, mm, mcmm).
* OP determinista (tt) en LTspice: 23 geometrias, incluidas nf=2/m=2 y bordes de W, diferencia maxima
  vs ngspice 0.0005 %.
* Monte Carlo de proceso global (L=0.55u, 300 pasos): sigma/mu nfet 0.59 %, pfet 0.74 %
  (ngspice, sensibilidades: 0.61 % / 0.76 %). Pares identicos: corr = 1.
* Mismatch con nf/m distintos de 1: NO validado en LTspice (la formula de area es la del PDK).

## AVISO: no uses L exactamente en un borde de bin
Los modelos estan binneados en L. Con L exactamente igual a un borde, la respuesta a la variacion
global de proceso (sw_polycd) difiere entre LTspice y ngspice (en ngspice ademas hay un cambio de
pendiente cerca del borde). Con L = borde + 10 nm coinciden a tres decimales en los 45 bordes
medidos. Afecta SOLO la sigma del Monte Carlo de proceso; el punto de operacion nominal y las
esquinas coinciden a ~1e-5 tambien en el borde.

Recomendacion: usa L >= borde + 10 nm (0.51u en lugar de 0.5u, 1.01u en lugar de 1u, ...).
Si necesitas L exactamente en el borde, compara con ngspice antes de confiar en la sigma.

Bordes de L (um) y razon LT/ng de la sensibilidad a sw_polycd medida EN el borde
(alta: >25 % o signo opuesto; media: 5-25 %; baja: <5 %):

@@TABLE@@

Bordes de W (um), sin medir en MC: 0.42, 0.55 (segun dispositivo), 0.75 (5 V), 1, 3, 5, 7, 15, 20.

Detalle: medido solo en L = borde y L = borde + 10 nm (no por debajo del borde), con W = 2u,
barriendo sw_polycd = -3, 0, +3 nm (test4_bordes_bin).

Aviso automatico:
    python check_bin_edges.py mi_circuito.cir otro.net esquema.asc
Revisa lineas  X.. xnfet_01v8 l=0.5u ..  (y .asc con SYMBOL/SpiceLine); tolerancia 5 nm; codigo de
salida 2 si hay L en borde. Las L dadas por .param/expresiones salen como "nota": revisalas a mano.
Con el generador: python make_min_pdk.py --target ltspice ... --check-netlist mi_circuito.cir
"""


def write_readme_lt(dst: Path) -> None:
    cbe = _load_edges()
    table = "\n".join("    " + l.strip() if l.strip() else l for l in _edge_table_lines())
    (dst / "README_ltspice.md").write_text(README_LT.replace("@@TABLE@@", table))
    if cbe is not None:
        shutil.copy2(Path(cbe.__file__), dst / "check_bin_edges.py")


# ----------------------------------------------------------------------------
# smoke test del PDK LTspice (usa ngspice como sustituto: no se necesita LTspice)
# ----------------------------------------------------------------------------
_SMOKE_GEOS = {  # dispositivo: (tipo, Vdd, [(L_um, W_um, nf, mult)])
    "nfet_01v8": ("n", 1.8, [(0.15, 1, 1, 1), (0.5, 2, 2, 2), (1, 5, 1, 1), (0.18, 0.42, 1, 1), (0.15, 0.42, 1, 1), (0.5, 0.55, 1, 1)]),
    "pfet_01v8": ("p", 1.8, [(0.15, 1, 1, 1), (0.5, 2, 2, 2), (1, 5, 1, 1), (0.15, 0.55, 1, 1), (0.18, 0.55, 1, 1)]),
    "nfet_01v8_lvt": ("n", 1.8, [(0.15, 1, 1, 1), (0.5, 2, 2, 2), (1, 5, 1, 1)]),
    "pfet_01v8_lvt": ("p", 1.8, [(0.35, 1, 1, 1), (0.5, 2, 2, 2), (1, 5, 1, 1)]),
    "nfet_g5v0d10v5": ("n", 5.0, [(0.5, 1, 1, 1), (1, 2, 2, 2), (2, 5, 1, 1)]),
    "pfet_g5v0d10v5": ("p", 5.0, [(0.5, 1, 1, 1), (1, 2, 2, 2), (2, 5, 1, 1)]),
}


def _ng_version(text: str, mode: str) -> str:
    """Convierte sintaxis LTspice -> ngspice para probar con ngspice.
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
    """mode: full | core | wrap.  Devuelve netlist con .op y .ac (Cgg) de cada dispositivo."""
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
    """Compara en ngspice el PDK completo con la traducción (núcleo y wrapper) en tt/ss/ff/sf/fs:
    corriente DC y Cgg de varias geometrías (bines, nf, mult). Con gauss -> 0 deben coincidir."""
    ng = shutil.which("ngspice")
    if not ng:
        print("smoke-test LTspice: ngspice no encontrado")
        return False
    devs = [d for d in devices if d in _SMOKE_GEOS]
    full = (src / "libs.tech" / "combined" / "sky130.lib.spice").resolve()
    ok, worst = True, 0.0
    print("\nsmoke-test LTspice (equivalencia numérica en ngspice, gauss -> 0):")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        ngdet = _ng_copy(dst, tmp, "det")

        def run(net: str, tag: str):
            p = tmp / f"{tag}.cir"
            p.write_text(net)
            r = subprocess.run([ng, "-b", str(p)], capture_output=True, text=True, timeout=900)
            return _smoke_parse(r.stdout + r.stderr)

        for c in [x[0].lower() for x in LT_SECTIONS if x[2] == 0 and x[3] == 0]:  # solo deterministas
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
            print(f"  {c}: {n} geometrías, max diferencia relativa (Id y Cgg, núcleo y wrapper) = {w_c:.2e}")
    ok &= worst < 1e-5
    print("  resultado: " + ("OK" if ok else "FALLO"))
    return ok


# ----------------------------------------------------------------------------
def main(argv=None) -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(
        description="Genera un PDK sky130A reducido (solo FET) para ngspice.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--target", choices=("ngspice", "ltspice"), default="ngspice",
                    help="ngspice: PDK reducido (por defecto). ltspice: PDK traducido a LTspice "
                         "(metros, delvto con gauss, wrappers xnfet_/xpfet_, MC por .step)")
    ap.add_argument("--src", type=Path, default=here / "sky130A",
                    help="directorio sky130A original (contiene libs.tech/). "
                         "Por defecto: <carpeta del script>/sky130A")
    ap.add_argument("--dst", type=Path, default=None,
                    help="directorio de salida. Por defecto: <carpeta del script>/sky130A_min")
    ap.add_argument("--devices", nargs="+", default=list(DEFAULT_DEVICES),
                    help="dispositivos a conservar, sin el prefijo sky130_fd_pr__ "
                         f"(por defecto: {' '.join(DEFAULT_DEVICES)})")
    ap.add_argument("--force", action="store_true", help="sobrescribir --dst si existe")
    ap.add_argument("--split-sections", action="store_true",
                    help="además genera una lib por sección en libs.tech/combined/sections/ "
                         "(mucho más rápida de cargar que el archivo multi-sección)")
    ap.add_argument("--check-netlist", nargs="+", metavar="NETLIST",
                    help="revisar si los netlists solo usan dispositivos del PDK reducido")
    ap.add_argument("--smoke-test", action="store_true",
                    help="comparar corrientes DC completo vs reducido (requiere ngspice)")
    args = ap.parse_args(argv)

    src = args.src.resolve()
    dst = (args.dst or here / ("sky130A_ltspice_min" if args.target == "ltspice" else "sky130A_min")).resolve()
    devices = list(dict.fromkeys(args.devices))

    if args.target == "ltspice":
        if dst.exists() and not args.force:
            print(f"{dst} ya existe; usa --force para sobrescribir", file=sys.stderr)
            return 1
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir(parents=True)
        build_ltspice(src, dst, devices)
        problems = verify_ltspice(dst)
        write_manifest_ltspice(dst, devices, problems)
        write_readme_lt(dst)
        n_files = sum(1 for _ in dst.rglob("*") if _.is_file())
        print(f"PDK LTspice: {dst}  ({n_files} archivos)")
        print("  verificación estática: " + ("OK" if not problems else "CON PROBLEMAS"))
        for pr in problems:
            print(f"  - {pr}")
        ok = not problems
        if args.check_netlist:
            cbe = _load_edges()
            if cbe is None:
                print("check_bin_edges.py no encontrado junto al generador")
            else:
                print()
                if cbe.main(list(args.check_netlist)):
                    print("  (hay L en borde de bin: ver README_ltspice.md)")
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
        print(f"libs por sección regeneradas: {len(files)} archivos en "
              f"{dst / 'libs.tech' / 'combined' / SECTIONS_DIR}")
        print("  verificación: " + ("OK" if not problems else "CON PROBLEMAS"))
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
