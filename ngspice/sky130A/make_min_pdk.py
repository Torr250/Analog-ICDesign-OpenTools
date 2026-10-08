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


# ----------------------------------------------------------------------------
def main(argv=None) -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(
        description="Genera un PDK sky130A reducido (solo FET) para ngspice.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
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
    dst = (args.dst or here / "sky130A_min").resolve()
    devices = list(dict.fromkeys(args.devices))

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
