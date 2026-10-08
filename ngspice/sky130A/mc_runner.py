#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mc_runner.py - Monte Carlo para sky130 en ngspice con variación GLOBAL de proceso.

Problema que resuelve
---------------------
En la sección `mc` del PDK, los parámetros de proceso se definen como
`.param sw_polycd = {nominal} + process_mc_factor*MC_PR_SWITCH*AGAUSS(0,sigma,1)`.
ngspice vuelve a evaluar AGAUSS cada vez que se usa el parámetro, de modo que
cada instancia recibe su propio sorteo: dos transistores idénticos tienen
correlación ~0 y la "variación de proceso" se comporta como mismatch extra.

Qué hace este wrapper (process="global")
----------------------------------------
Por cada muestra:
  1. Sortea en Python UN valor por parámetro de proceso, con las mismas sigmas
     del PDK y la misma semántica de ngspice (ver `Spec.value`).
  2. Reescribe `parameters_fet_<esquina>.spice` sustituyendo cada término
     `process_mc_factor*MC_PR_SWITCH*AGAUSS(...)` por el valor ya sorteado.
  3. Genera una lib de la esquina elegida con MC_PR_SWITCH=0 que apunta a ese
     archivo, y reescribe la línea `.lib .../sky130.lib.spice <sección>` del netlist.
  4. Ejecuta ngspice una vez y recoge las medidas (.meas / print).
Resultado: el proceso es común a todos los dispositivos de la corrida; el
mismatch (MC_MM_SWITCH) sigue siendo independiente por instancia, como debe ser.

Reproducibilidad
----------------
* `seed` fija los sorteos de proceso (hechos en Python).
* El mismatch lo sortea ngspice; el wrapper inserta `.option seed=<N>` en cada
  netlist (N derivado de `seed`), con lo que también es reproducible.
  (`set rndseed` dentro de .control NO funciona para esto; `.option seed=` sí.)

Modos de proceso
----------------
  global    (por defecto) un sorteo por corrida, común a todos los dispositivos
  instance  comportamiento original del PDK (MC_PR_SWITCH=1, sorteo por instancia)
  off       sin variación de proceso (MC_PR_SWITCH=0)

Uso desde Python
----------------
    from mc_runner import run_mc
    df = run_mc("CMOS_Inverter.cir", "sky130A_min", n=200, corner="tt",
                process="global", mismatch=False, seed=1, jobs=4)
    df[["tphl", "tplh"]].describe()

Uso desde la línea de comandos
------------------------------
    python mc_runner.py sky130A/CMOS_Inverter.cir --pdk sky130A_min -n 200 \\
        --corner tt --process global --no-mismatch --seed 1 --jobs 4 --out mc.csv

Corner / mismatch (si no se indican se infieren de la línea `.lib` del netlist)
    tt      -> corner tt, mismatch False
    tt_mm   -> corner tt, mismatch True
    mc      -> corner tt, mismatch False
  `corner` debe ser una esquina base (tt, ss, ff, sf, fs, ll, ss_hl, ...).
  Para mismatch use mismatch=True, no una sección *_mm.

Rendimiento (medido con CMOS_Inverter.cir; ngspice 42, un solo núcleo)
----------------------------------------------------------------------
  `.lib sky130.lib.spice tt` (lib original, 49 secciones)   PDK completo ~4.9 s   reducido ~2.5 s
  lib de UNA sección (la que genera este wrapper)           PDK completo ~0.73 s  reducido ~0.63 s
La lib de una sola sección evita el costo de ngspice con el archivo multi-sección
(en las pruebas, un include roto en la sección `mc` producía error al correr `tt`,
lo que sugiere que los includes de secciones no seleccionadas también se procesan).
Por eso este wrapper ya es rápido incluso apuntando al PDK completo.

Columnas del resultado
----------------------
  run, ok, seconds        número de corrida, éxito y duración
  p_<parámetro>           valor sorteado del término de proceso (se SUMA al nominal de la
                          esquina). Solo aparecen los que varían; hay parámetros que no
                          alcanzan a los FET (p. ej. sw_nw_rs_mult) y se registran igual.
  <medidas>               cada .meas del netlist y cada `nombre = valor` de `print`
                          (en minúsculas, como los imprime ngspice); NaN si la medida falló
  error                   primer mensaje de error de ngspice, si lo hubo
  df.attrs                corner, mismatch, process, master_seed, n, netlist, pdk

Limitaciones
------------
* Los modelos de proceso solo se reescriben en parameters_fet_*.spice (variación
  de los FET). Los parámetros de res/cap no se sortean (no afectan a los FET).
* En ngspice, GAUSS(0, rel, n) vale exactamente 0 (su sigma es nominal*rel);
  el wrapper replica esa semántica, por lo que esos parámetros no varían.
* Rutas relativas de .include/.lib/.inc del netlist se convierten a absolutas
  respecto al directorio del netlist. `source`/`load` dentro de .control no.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import math
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

try:  # pandas es opcional
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None

# ----------------------------------------------------------------------------
# expresiones regulares
# ----------------------------------------------------------------------------
SAMPLED_RE = re.compile(
    r"process_mc_factor\*MC_PR_SWITCH\*(?:(?P<exp>EXP)\()?(?P<fn>A?GAUSS)\("
    r"(?P<mu>[^,()]+),(?P<sig>[^,()]+),(?P<n>[^,()]+)\)(?(exp)\))", re.I)
PARAM_RE = re.compile(r"^\s*\.param\s+(\w+)\s*=", re.I)
PRE_RE = re.compile(r"=\s*\{([^}]*)\}\s*\+\s*$")
INCLUDE_RE = re.compile(r"""^\s*\.(?:include|inc)\s+["']?([^"'\s]+)["']?""", re.I)
LIB_OPEN_RE = re.compile(r"^\s*\.lib\s+(\w+)\s*$", re.I)
LIB_END_RE = re.compile(r"^\s*\.endl\b", re.I)
NETLIST_LIB_RE = re.compile(
    r"""^(?P<pre>\s*\.lib\s+)(?P<q>["']?)(?P<path>[^"'\s]*sky130[^"'\s]*\.lib\.spice)(?P=q)"""
    r"""\s+(?P<sec>\w+)(?P<rest>.*)$""", re.I | re.M)
NETLIST_INC_RE = re.compile(
    r"""^(?P<pre>\s*\.(?:include|inc|lib)\s+)(?P<q>["']?)(?P<path>[^"'\s]+)(?P=q)(?P<rest>.*)$""",
    re.I | re.M)
MEAS_DEF_RE = re.compile(r"^\s*\.meas(?:ure)?\s+\w+\s+(\w+)", re.I | re.M)
MEAS_OUT_RE = re.compile(
    r"^\s*([A-Za-z_][\w.()#:\[\]/]*)\s*=\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)"
    r"(?=\s|$)(?!\s*k?bytes)")
# nombres que ngspice imprime como informe de recursos, no como medidas
NOISE_NAMES = {"stack", "library", "shared", "text", "data", "resident", "dynamic"}

SECTION_NAME = "mc_run"


# ----------------------------------------------------------------------------
# parámetros sorteados
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Spec:
    """Un parámetro de proceso sorteado: `nominal + factor*switch*FN(mu,sig,n)`."""
    name: str
    fn: str          # "AGAUSS" o "GAUSS"
    mu: float
    sig: float
    n: float
    is_exp: bool

    def value(self, z: float) -> float:
        """Valor para una normal estándar `z`, con la semántica de ngspice:

        agauss(mu, abs, n): media mu, desviación abs/n
        gauss (mu, rel, n): media mu, desviación |mu|*rel/n   (=0 si mu=0)
        EXP(...) envuelve el resultado.
        """
        if self.fn == "AGAUSS":
            v = self.mu + self.sig / self.n * z
        else:
            v = self.mu + abs(self.mu * self.sig) / self.n * z
        return math.exp(v) if self.is_exp else v


def parse_specs(params_text: str) -> list[Spec]:
    specs: list[Spec] = []
    for line in params_text.splitlines():
        m = PARAM_RE.match(line)
        if not m or line.lstrip().startswith("*"):
            continue
        terms = list(SAMPLED_RE.finditer(line))
        if not terms:
            continue
        if len(terms) > 1:
            raise ValueError(f"forma no soportada (varios términos sorteados en una línea): {line!r}")
        t = terms[0]
        specs.append(Spec(m.group(1), t.group("fn").upper(), float(t.group("mu")),
                          float(t.group("sig")), float(t.group("n")), bool(t.group("exp"))))
    return specs


def rewrite_params(params_text: str, values: dict[str, float]) -> str:
    """Sustituye cada término sorteado por su valor numérico."""
    out = []
    for line in params_text.splitlines():
        m = PARAM_RE.match(line)
        t = SAMPLED_RE.search(line) if (m and not line.lstrip().startswith("*")) else None
        if t:
            pm = PRE_RE.search(line[:t.start()])
            if not pm:
                raise ValueError(f"forma no soportada (se esperaba '= {{...}} + término'): {line!r}")
            v = values[m.group(1)]
            line = (line[:t.start()][:pm.start()] + f"= {{{pm.group(1)}+({v:.12e})}}"
                    + line[t.end():])
        out.append(line)
    text = "\n".join(out) + "\n"
    leftover = [l for l in text.splitlines()
                if "MC_PR_SWITCH" in l and not l.lstrip().startswith("*")]
    if leftover:
        raise ValueError(f"quedaron términos sin reescribir: {leftover[:2]}")
    return text


# ----------------------------------------------------------------------------
# PDK
# ----------------------------------------------------------------------------
class PdkLib:
    """Lee `sky130.lib.spice` de un PDK (completo o reducido) por secciones."""

    def __init__(self, pdk):
        root = Path(pdk).resolve()
        comb = root / "libs.tech" / "combined" if (root / "libs.tech").is_dir() else root
        self.lib_path = comb / "sky130.lib.spice"
        if not self.lib_path.is_file():
            raise FileNotFoundError(f"no encuentro {self.lib_path} (revise el argumento pdk)")
        self.comb = comb
        self.sections: dict[str, list[str]] = {}
        cur = None
        for line in self.lib_path.read_text(errors="replace").splitlines():
            if (m := LIB_OPEN_RE.match(line)):
                cur = m.group(1)
                self.sections[cur] = []
            elif LIB_END_RE.match(line):
                cur = None
            elif cur is not None:
                self.sections[cur].append(line)

    def fet_params_rel(self, corner: str) -> str:
        for line in self.sections[corner]:
            m = INCLUDE_RE.match(line)
            if m and re.match(r"continuous/parameters_fet_\w+\.spice$", m.group(1)):
                return m.group(1)
        raise ValueError(f"la sección '{corner}' no incluye continuous/parameters_fet_*.spice")

    def run_lib_text(self, corner: str, *, mismatch: bool, pr_switch: int,
                     fet_params: Path | None) -> str:
        """Texto de una lib de una sola sección basada en `corner`."""
        out = [f".lib {SECTION_NAME}"]
        have_mm = have_pr = False
        for line in self.sections[corner]:
            if re.match(r"^\s*\.param\s+MC_MM_SWITCH\s*=", line, re.I):
                out.append(f".param MC_MM_SWITCH={1 if mismatch else 0}")
                have_mm = True
            elif re.match(r"^\s*\.param\s+MC_PR_SWITCH\s*=", line, re.I):
                out.append(f".param MC_PR_SWITCH={pr_switch}")
                have_pr = True
            elif (m := INCLUDE_RE.match(line)):
                rel = m.group(1)
                if fet_params is not None and re.match(
                        r"continuous/parameters_fet_\w+\.spice$", rel):
                    path = fet_params
                else:
                    path = self.comb / rel
                out.append(f'.include "{Path(path).as_posix()}"')
            else:
                out.append(line)
        if not have_mm:
            out.insert(1, f".param MC_MM_SWITCH={1 if mismatch else 0}")
        if not have_pr:
            out.insert(1, f".param MC_PR_SWITCH={pr_switch}")
        out.append(f".endl {SECTION_NAME}")
        return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------
# netlist
# ----------------------------------------------------------------------------
def infer_corner(section: str):
    """(corner_base, mismatch_inferido) a partir del nombre de sección del netlist."""
    if section == "mc":
        return "tt", False
    if section.endswith("_mm"):
        return section[:-3], True
    return section, False


def prepare_netlist(text: str, netlist_dir: Path, lib_file: Path, *,
                    seed_line: str | None) -> str:
    """Apunta la línea .lib del PDK a la lib por corrida y absolutiza rutas relativas."""
    def fix_lib(m):
        return f'{m.group("pre")}"{lib_file.as_posix()}" {SECTION_NAME}{m.group("rest")}'
    text = NETLIST_LIB_RE.sub(fix_lib, text)

    def fix_inc(m):
        p = m.group("path")
        if p.startswith(SECTION_NAME) or str(lib_file.as_posix()) in p:
            return m.group(0)
        if Path(p).is_absolute() or p.startswith("$"):
            return m.group(0)
        absp = (netlist_dir / p).resolve()
        return f'{m.group("pre")}"{absp.as_posix()}"{m.group("rest")}'
    lines = []
    for ln in text.splitlines():
        if ln.lstrip().startswith("*") or not NETLIST_INC_RE.match(ln):
            lines.append(ln)
        else:
            lines.append(NETLIST_INC_RE.sub(fix_inc, ln))
    if seed_line and lines:
        lines.insert(1, seed_line)  # la línea 0 es el título del netlist
    return "\n".join(lines) + "\n"


def parse_log(log_text: str, meas_names: list[str]) -> dict[str, float]:
    vals: dict[str, float] = {}
    for line in log_text.splitlines():
        m = MEAS_OUT_RE.match(line)
        if m and m.group(1).lower() not in NOISE_NAMES:
            vals[m.group(1).lower()] = float(m.group(2))   # la última aparición gana
    for n in meas_names:
        vals.setdefault(n.lower(), float("nan"))
    return vals


# ----------------------------------------------------------------------------
# ejecución
# ----------------------------------------------------------------------------
def run_mc(netlist, pdk, *, n: int = 100, corner: str | None = None,
           process: str = "global", mismatch: bool | None = None,
           seed: int | None = None, jobs: int = 1, workdir=None,
           keep_runs: bool = False, ngspice: str = "ngspice", timeout: float = 600,
           post=None, out=None, keep_zero_params: bool = False, progress: bool = True):
    """Ejecuta `n` corridas Monte Carlo y devuelve un DataFrame (o lista de dicts).

    Parámetros
    ----------
    netlist : ruta del netlist; debe contener `.lib <...>/sky130.lib.spice <sección>`.
    pdk     : directorio sky130A o sky130A_min (el que contiene libs.tech/).
    corner  : esquina base (tt, ss, ff_ll, ...). None -> se infiere del netlist.
    process : "global" | "instance" | "off" (ver docstring del módulo).
    mismatch: True activa MC_MM_SWITCH (mismatch por instancia). None -> se infiere.
    seed    : semilla maestra (sorteos de proceso y semilla de ngspice por corrida).
    jobs    : corridas de ngspice en paralelo.
    post    : función opcional `post(run_dir: Path) -> dict` para leer archivos
              (p. ej. .raw) antes de borrar el directorio de la corrida.
    out     : ruta de CSV opcional.
    """
    if process not in ("global", "instance", "off"):
        raise ValueError("process debe ser 'global', 'instance' u 'off'")
    if shutil.which(ngspice) is None:
        raise FileNotFoundError(f"no encuentro el ejecutable '{ngspice}' en el PATH")

    netlist = Path(netlist).resolve()
    nl_text = netlist.read_text(errors="replace")
    libs = {(m.group("path"), m.group("sec")) for m in NETLIST_LIB_RE.finditer(nl_text)}
    if not libs:
        raise ValueError("el netlist no tiene una línea '.lib <...>sky130...lib.spice <sección>'")
    sections = {s for _, s in libs}
    if len(sections) > 1:
        raise ValueError(f"el netlist usa varias secciones del PDK {sorted(sections)}; "
                         "no soportado")
    net_section = sections.pop()
    inf_corner, inf_mm = infer_corner(net_section)
    corner = corner or inf_corner
    mismatch = inf_mm if mismatch is None else bool(mismatch)
    if corner == "mc" or corner.endswith("_mm"):
        raise ValueError("`corner` debe ser una esquina base (tt, ss, ...); "
                         "use mismatch=True en lugar de una sección *_mm")

    pdk_lib = PdkLib(pdk)
    if corner not in pdk_lib.sections:
        raise ValueError(f"la esquina '{corner}' no existe en {pdk_lib.lib_path}")

    # --- sorteos (todos por adelantado: el resultado no depende de `jobs`) -------
    specs: list[Spec] = []
    params_src_text = ""
    if process == "global":
        params_src = pdk_lib.comb / pdk_lib.fet_params_rel(corner)
        params_src_text = params_src.read_text(errors="replace")
        specs = parse_specs(params_src_text)
        if not specs:
            raise ValueError(f"no encontré parámetros sorteados en {params_src}")
    master = np.random.SeedSequence(seed)
    master_seed = int(master.entropy) if seed is None else int(seed)
    rng = np.random.default_rng(master)
    Z = rng.standard_normal((n, len(specs)))
    NG_SEEDS = rng.integers(1, 2**31 - 1, size=n)

    base = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="mc_runner_"))
    base.mkdir(parents=True, exist_ok=True)
    meas_names = MEAS_DEF_RE.findall(nl_text)
    pr_switch = {"global": 0, "off": 0, "instance": 1}[process]
    uses_ngspice_rng = mismatch or process == "instance"

    def one(i: int) -> dict:
        t0 = time.time()
        rd = base / f"run_{i:05d}"
        rd.mkdir(parents=True, exist_ok=True)
        draws = {}
        fet_params = None
        if process == "global":
            draws = {s.name: s.value(float(Z[i, k])) for k, s in enumerate(specs)}
            fet_params = rd / "parameters_fet.spice"
            fet_params.write_text(rewrite_params(params_src_text, draws))
        lib_file = rd / "lib.spice"
        lib_file.write_text(pdk_lib.run_lib_text(corner, mismatch=mismatch,
                                                 pr_switch=pr_switch, fet_params=fet_params))
        seed_line = f".option seed={int(NG_SEEDS[i])}" if uses_ngspice_rng else None
        cir = rd / "netlist.cir"
        cir.write_text(prepare_netlist(nl_text, netlist.parent, lib_file, seed_line=seed_line))
        log = rd / "ngspice.log"
        error = ""
        try:
            proc = subprocess.run([ngspice, "-b", "-o", str(log), str(cir)], cwd=rd,
                                  capture_output=True, text=True, timeout=timeout)
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            rc, error = -1, f"timeout ({timeout}s)"
        log_text = log.read_text(errors="replace") if log.exists() else ""
        vals = parse_log(log_text, meas_names)
        if rc != 0 and not error:
            error = next((l.strip() for l in log_text.splitlines() if "error" in l.lower()),
                         f"ngspice terminó con código {rc}")
        ok = rc == 0 and (not meas_names or any(not math.isnan(vals.get(m.lower(), float("nan")))
                                                for m in meas_names))
        if post is not None:
            try:
                vals.update(post(rd) or {})
            except Exception as exc:  # noqa: BLE001
                error = error or f"post(): {exc}"
                ok = False
        if not keep_runs:
            shutil.rmtree(rd, ignore_errors=True)
        row = {"run": i, "ok": ok, "seconds": round(time.time() - t0, 3)}
        row.update({f"p_{k}": v for k, v in draws.items()})
        row.update(vals)
        row["error"] = error
        return row

    rows: list[dict] = []
    done = 0
    t_start = time.time()
    with cf.ThreadPoolExecutor(max_workers=max(1, int(jobs))) as ex:
        for row in ex.map(one, range(n)):
            rows.append(row)
            done += 1
            if progress and (done % max(1, n // 10) == 0 or done == n):
                print(f"  [{done}/{n}] {time.time() - t_start:6.1f} s", file=sys.stderr)
    if not keep_runs and not workdir:
        shutil.rmtree(base, ignore_errors=True)

    meta = {"corner": corner, "mismatch": mismatch, "process": process,
            "master_seed": master_seed, "n": n, "netlist": str(netlist), "pdk": str(pdk_lib.comb)}
    if pd is None:
        return rows
    df = pd.DataFrame(rows)
    if not keep_zero_params:
        zero = [c for c in df.columns if c.startswith("p_") and (df[c] == 0).all()]
        df = df.drop(columns=zero)
    df.attrs.update(meta)
    if out:
        df.to_csv(out, index=False)
    return df


# ----------------------------------------------------------------------------
def main(argv=None) -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(
        description="Monte Carlo con variación global de proceso para sky130 en ngspice.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("netlist", type=Path)
    ap.add_argument("--pdk", type=Path, default=here / "sky130A_min",
                    help="directorio sky130A o sky130A_min (por defecto: ./sky130A_min)")
    ap.add_argument("-n", type=int, default=100, help="número de corridas")
    ap.add_argument("--corner", default=None, help="esquina base (por defecto: del netlist)")
    ap.add_argument("--process", choices=["global", "instance", "off"], default="global")
    ap.add_argument("--mismatch", action=argparse.BooleanOptionalAction, default=None,
                    help="activar/desactivar mismatch (por defecto: según la sección del netlist)")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--out", type=Path, default=None, help="CSV de salida")
    ap.add_argument("--workdir", type=Path, default=None)
    ap.add_argument("--keep-runs", action="store_true")
    ap.add_argument("--ngspice", default="ngspice")
    args = ap.parse_args(argv)

    df = run_mc(args.netlist, args.pdk, n=args.n, corner=args.corner, process=args.process,
                mismatch=args.mismatch, seed=args.seed, jobs=args.jobs, workdir=args.workdir,
                keep_runs=args.keep_runs, ngspice=args.ngspice, out=args.out)
    if pd is None:
        print(f"{len(df)} corridas (instale pandas para el resumen)")
        return 0
    a = df.attrs
    print(f"\ncorner={a['corner']} mismatch={a['mismatch']} process={a['process']} "
          f"semilla={a['master_seed']}  corridas ok: {int(df['ok'].sum())}/{len(df)}")
    num = [c for c in df.columns if c not in ("run", "ok", "seconds", "error")
           and not c.startswith("p_") and df[c].dtype.kind == "f"]
    if num:
        print(df[num].describe().T[["mean", "std", "min", "max"]].to_string())
    bad = df[~df["ok"]]
    if len(bad):
        print(f"\n{len(bad)} corridas con problemas; primer error: {bad['error'].iloc[0]}")
    if args.out:
        print(f"\nCSV: {args.out}")
    return 0 if len(bad) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
