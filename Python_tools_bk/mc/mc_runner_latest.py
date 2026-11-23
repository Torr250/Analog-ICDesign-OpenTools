#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mc_runner.py - Monte Carlo for sky130 in ngspice with GLOBAL process variation.

Problem it solves
-----------------
In the `mc` section of the PDK, the process parameters are defined as
`.param sw_polycd = {nominal} + process_mc_factor*MC_PR_SWITCH*AGAUSS(0,sigma,1)`.
ngspice re-evaluates AGAUSS every time the parameter is used, so
each instance gets its own draw: two identical transistors have
correlation ~0 and the "process variation" behaves like extra mismatch.

What this wrapper does (process="global")
-----------------------------------------
For each sample:
  1. Draws in Python ONE value per process parameter, with the same sigmas
     as the PDK and the same ngspice semantics (see `Spec.value`).
  2. Rewrites `parameters_fet_<corner>.spice`, replacing every term
     `process_mc_factor*MC_PR_SWITCH*AGAUSS(...)` with the value already drawn.
  3. Generates a lib of the chosen corner with MC_PR_SWITCH=0 that points to that
     file, and rewrites the `.lib .../sky130.lib.spice <section>` line of the netlist.
  4. Runs ngspice once and collects the measurements (.meas / print).
Result: the process is common to all the devices of the run; the
mismatch (MC_MM_SWITCH) is still independent per instance, as it should be.

Reproducibility
---------------
* `seed` fixes the process draws (done in Python).
* The mismatch is drawn by ngspice; the wrapper inserts `.option seed=<N>` in every
  netlist (N derived from `seed`), so it is reproducible too.
  (`set rndseed` inside .control does NOT work for this; `.option seed=` does.)

Process modes
-------------
  global    (default) one draw per run, common to all the devices
  instance  original PDK behavior (MC_PR_SWITCH=1, one draw per instance)
  off       no process variation (MC_PR_SWITCH=0)

Use from Python
---------------
    from mc_runner import run_mc
    df = run_mc("CMOS_Inverter.cir", "sky130A_min", n=200, corner="tt",
                process="global", mismatch=False, seed=1, jobs=4)
    df[["tphl", "tplh"]].describe()

Use from the command line
-------------------------
    python mc_runner.py sky130A/CMOS_Inverter.cir --pdk sky130A_min -n 200 \\
        --corner tt --process global --no-mismatch --seed 1 --jobs 4 --out mc.csv

Corner / mismatch (if not given they are inferred from the `.lib` line of the netlist)
    tt      -> corner tt, mismatch False
    tt_mm   -> corner tt, mismatch True
    mc      -> corner tt, mismatch False
  `corner` must be a base corner (tt, ss, ff, sf, fs, ll, ss_hl, ...).
  For mismatch use mismatch=True, not a *_mm section.

Performance (measured with CMOS_Inverter.cir; ngspice 42, a single core)
------------------------------------------------------------------------
  `.lib sky130.lib.spice tt` (original lib, 49 sections)    full PDK ~4.9 s   reduced ~2.5 s
  ONE-section lib (the one this wrapper generates)          full PDK ~0.73 s  reduced ~0.63 s
The single-section lib avoids the cost of ngspice with the multi-section file
(in the tests, a broken include in the `mc` section produced an error when running `tt`,
which suggests that the includes of unselected sections are also processed).
That is why this wrapper is fast even when pointing to the full PDK.

Result columns
--------------
  run, ok, seconds        run number, success and duration
  p_<parameter>           drawn value of the process term (it is ADDED to the corner nominal).
                          Only those that vary appear; some parameters do not
                          reach the FETs (e.g. sw_nw_rs_mult) and are recorded anyway.
  <measurements>          every .meas of the netlist and every `name = value` of `print`
                          (in lowercase, as ngspice prints them); NaN if the measurement failed
  error                   first ngspice error message, if any
  df.attrs                corner, mismatch, process, master_seed, n, netlist, pdk

Limitations
-----------
* The process models are only rewritten in parameters_fet_*.spice (FET
  variation). The res/cap parameters are not drawn (they do not affect the FETs).
* In ngspice, GAUSS(0, rel, n) is exactly 0 (its sigma is nominal*rel);
  the wrapper replicates that semantics, so those parameters do not vary.
* Relative paths of .include/.lib/.inc in the netlist are converted to absolute
  with respect to the netlist directory. `source`/`load` inside .control are not.
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

try:  # pandas is optional
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None

# ----------------------------------------------------------------------------
# regular expressions
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
# names that ngspice prints as a resource report, not as measurements
NOISE_NAMES = {"stack", "library", "shared", "text", "data", "resident", "dynamic"}

SECTION_NAME = "mc_run"


# ----------------------------------------------------------------------------
# drawn parameters
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Spec:
    """A drawn process parameter: `nominal + factor*switch*FN(mu,sig,n)`."""
    name: str
    fn: str          # "AGAUSS" or "GAUSS"
    mu: float
    sig: float
    n: float
    is_exp: bool

    def value(self, z: float) -> float:
        """Value for a standard normal `z`, with ngspice semantics:

        agauss(mu, abs, n): mean mu, deviation abs/n
        gauss (mu, rel, n): mean mu, deviation |mu|*rel/n   (=0 if mu=0)
        EXP(...) wraps the result.
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
            raise ValueError(f"unsupported form (several drawn terms in one line): {line!r}")
        t = terms[0]
        specs.append(Spec(m.group(1), t.group("fn").upper(), float(t.group("mu")),
                          float(t.group("sig")), float(t.group("n")), bool(t.group("exp"))))
    return specs


def rewrite_params(params_text: str, values: dict[str, float]) -> str:
    """Replace each drawn term with its numeric value."""
    out = []
    for line in params_text.splitlines():
        m = PARAM_RE.match(line)
        t = SAMPLED_RE.search(line) if (m and not line.lstrip().startswith("*")) else None
        if t:
            pm = PRE_RE.search(line[:t.start()])
            if not pm:
                raise ValueError(f"unsupported form (expected '= {{...}} + term'): {line!r}")
            v = values[m.group(1)]
            line = (line[:t.start()][:pm.start()] + f"= {{{pm.group(1)}+({v:.12e})}}"
                    + line[t.end():])
        out.append(line)
    text = "\n".join(out) + "\n"
    leftover = [l for l in text.splitlines()
                if "MC_PR_SWITCH" in l and not l.lstrip().startswith("*")]
    if leftover:
        raise ValueError(f"terms left unrewritten: {leftover[:2]}")
    return text


# ----------------------------------------------------------------------------
# PDK
# ----------------------------------------------------------------------------
class PdkLib:
    """Read `sky130.lib.spice` of a PDK (full or reduced) by sections."""

    def __init__(self, pdk):
        root = Path(pdk).resolve()
        comb = root / "libs.tech" / "combined" if (root / "libs.tech").is_dir() else root
        self.lib_path = comb / "sky130.lib.spice"
        if not self.lib_path.is_file():
            raise FileNotFoundError(f"cannot find {self.lib_path} (check the pdk argument)")
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
        raise ValueError(f"section '{corner}' does not include continuous/parameters_fet_*.spice")

    def run_lib_text(self, corner: str, *, mismatch: bool, pr_switch: int,
                     fet_params: Path | None) -> str:
        """Text of a single-section lib based on `corner`."""
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
    """(base_corner, inferred_mismatch) from the section name in the netlist."""
    if section == "mc":
        return "tt", False
    if section.endswith("_mm"):
        return section[:-3], True
    return section, False


def prepare_netlist(text: str, netlist_dir: Path, lib_file: Path, *,
                    seed_line: str | None) -> str:
    """Point the PDK .lib line to the per-run lib and make relative paths absolute."""
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
        lines.insert(1, seed_line)  # line 0 is the netlist title
    return "\n".join(lines) + "\n"


def parse_log(log_text: str, meas_names: list[str]) -> dict[str, float]:
    vals: dict[str, float] = {}
    for line in log_text.splitlines():
        m = MEAS_OUT_RE.match(line)
        if m and m.group(1).lower() not in NOISE_NAMES:
            vals[m.group(1).lower()] = float(m.group(2))   # the last occurrence wins
    for n in meas_names:
        vals.setdefault(n.lower(), float("nan"))
    return vals


# ----------------------------------------------------------------------------
# execution
# ----------------------------------------------------------------------------
def run_mc(netlist, pdk, *, n: int = 100, corner: str | None = None,
           process: str = "global", mismatch: bool | None = None,
           seed: int | None = None, jobs: int = 1, workdir=None,
           keep_runs: bool = False, ngspice: str = "ngspice", timeout: float = 600,
           post=None, out=None, keep_zero_params: bool = False, progress: bool = True):
    """Run `n` Monte Carlo runs and return a DataFrame (or a list of dicts).

    Parameters
    ----------
    netlist : netlist path; must contain `.lib <...>/sky130.lib.spice <section>`.
    pdk     : sky130A or sky130A_min directory (the one that contains libs.tech/).
    corner  : base corner (tt, ss, ff_ll, ...). None -> inferred from the netlist.
    process : "global" | "instance" | "off" (see the module docstring).
    mismatch: True enables MC_MM_SWITCH (per-instance mismatch). None -> inferred.
    seed    : master seed (process draws and per-run ngspice seed).
    jobs    : parallel ngspice runs.
    post    : optional function `post(run_dir: Path) -> dict` to read files
              (e.g. .raw) before deleting the run directory.
    out     : optional CSV path.
    """
    if process not in ("global", "instance", "off"):
        raise ValueError("process must be 'global', 'instance' or 'off'")
    if shutil.which(ngspice) is None:
        raise FileNotFoundError(f"cannot find the executable '{ngspice}' in the PATH")

    netlist = Path(netlist).resolve()
    nl_text = netlist.read_text(errors="replace")
    libs = {(m.group("path"), m.group("sec")) for m in NETLIST_LIB_RE.finditer(nl_text)}
    if not libs:
        raise ValueError("the netlist has no '.lib <...>sky130...lib.spice <section>' line")
    sections = {s for _, s in libs}
    if len(sections) > 1:
        raise ValueError(f"the netlist uses several PDK sections {sorted(sections)}; "
                         "not supported")
    net_section = sections.pop()
    inf_corner, inf_mm = infer_corner(net_section)
    corner = corner or inf_corner
    mismatch = inf_mm if mismatch is None else bool(mismatch)
    if corner == "mc" or corner.endswith("_mm"):
        raise ValueError("`corner` must be a base corner (tt, ss, ...); "
                         "use mismatch=True instead of a *_mm section")

    pdk_lib = PdkLib(pdk)
    if corner not in pdk_lib.sections:
        raise ValueError(f"corner '{corner}' does not exist in {pdk_lib.lib_path}")

    # --- draws (all up front: the result does not depend on `jobs`) -------
    specs: list[Spec] = []
    params_src_text = ""
    if process == "global":
        params_src = pdk_lib.comb / pdk_lib.fet_params_rel(corner)
        params_src_text = params_src.read_text(errors="replace")
        specs = parse_specs(params_src_text)
        if not specs:
            raise ValueError(f"no drawn parameters found in {params_src}")
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
                         f"ngspice finished with code {rc}")
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
        description="Monte Carlo with global process variation for sky130 in ngspice.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("netlist", type=Path)
    ap.add_argument("--pdk", type=Path, default=here / "sky130A_min",
                    help="sky130A or sky130A_min directory (default: ./sky130A_min)")
    ap.add_argument("-n", type=int, default=100, help="number of runs")
    ap.add_argument("--corner", default=None, help="base corner (default: from the netlist)")
    ap.add_argument("--process", choices=["global", "instance", "off"], default="global")
    ap.add_argument("--mismatch", action=argparse.BooleanOptionalAction, default=None,
                    help="enable/disable mismatch (default: according to the netlist section)")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--out", type=Path, default=None, help="output CSV")
    ap.add_argument("--workdir", type=Path, default=None)
    ap.add_argument("--keep-runs", action="store_true")
    ap.add_argument("--ngspice", default="ngspice")
    args = ap.parse_args(argv)

    df = run_mc(args.netlist, args.pdk, n=args.n, corner=args.corner, process=args.process,
                mismatch=args.mismatch, seed=args.seed, jobs=args.jobs, workdir=args.workdir,
                keep_runs=args.keep_runs, ngspice=args.ngspice, out=args.out)
    if pd is None:
        print(f"{len(df)} runs (install pandas for the summary)")
        return 0
    a = df.attrs
    print(f"\ncorner={a['corner']} mismatch={a['mismatch']} process={a['process']} "
          f"seed={a['master_seed']}  runs ok: {int(df['ok'].sum())}/{len(df)}")
    num = [c for c in df.columns if c not in ("run", "ok", "seconds", "error")
           and not c.startswith("p_") and df[c].dtype.kind == "f"]
    if num:
        print(df[num].describe().T[["mean", "std", "min", "max"]].to_string())
    bad = df[~df["ok"]]
    if len(bad):
        print(f"\n{len(bad)} runs with problems; first error: {bad['error'].iloc[0]}")
    if args.out:
        print(f"\nCSV: {args.out}")
    return 0 if len(bad) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
