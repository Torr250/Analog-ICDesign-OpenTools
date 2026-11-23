r"""
isfpn.py - Oscillator phase noise with the ISF method (Hajimiri) in ngspice, driven by a JSON config
=============================================================================================================

WHAT IT DOES
    Given the oscillator core netlist (without .lib or .control), a phase reference node and the list of
    special blocks, it computes L(Δf) = thermal + flicker (dBc/Hz) without PSS+PNOISE:
      1. baseline   unperturbed transient; T0, f0, waveforms of all nodes.
      2. lin        (optional) ΔQ linearity test at one node and phase.
      3. isf        Γ_raw_k(x) [rad/fC] by injecting a charge pulse at each node k (one sweep per node).
      4. noise      noise PSD (1 Hz..1e10 Hz) of each transistor, at its instantaneous bias, at N_PHASE phases.
      5. blocks     noise-current PSD of special blocks (e.g. current mirror) into a node.
       In the block netlist, the lib line is written  .lib {LIB}  (replaced by lib + section from the config).
      6. combine    Γ_dev = Γ_D - Γ_S;  L(Δf) = [Σ<Γ²S_th> + Σ<Γ√K>²/Δf^EF] / (2(2πΔf)²);  tables and validity.
      7. compare    (optional) difference against a reference table (Spectre or other).

HOW TO RUN  (from the case directory; the config and netlists live there)
    python3 isfpn.py CONFIG.json all            # everything, serially (parallel ngspice hangs in the sandbox)
    python3 isfpn.py CONFIG.json baseline|lin NODE|isf|noise|blocks|combine|compare|plots|export_template
    The lib path can be changed without touching the config:  ISFPN_LIB=/path/sky130_tt.lib.spice   (or ISFPN_PDK=/path/gf180mcuD with 'pdk')
    All netlists are generated with the line  .lib {LIB}  and the program replaces it by '<lib> <section>' at run time
    (ngspice does not expand environment variables in .lib). 'export_template' writes templates/base.spice with {LIB} visible.

CONFIG (JSON)  keys
    core        core netlist (relative to the case). Must contain the supplies and the capacitors.
    lib         the .lib file;   section  section (e.g. "tt");   temp [°C];   vdd [V]
    pdk         alternative to lib/section for PDKs that need several lines (e.g. gf180mcuD):
                {"root":"/path/gf180mcuD","preamble":[".include {PDK}/design.ngspice",".lib {PDK}/sm141064.ngspice typical"],
                 "models":"{PDK}/sm141064.ngspice"}   root can be overridden with ISFPN_PDK; "models" is the file scanned for FET names.
                In every netlist the line  .lib {LIB}  is replaced by the PDK preamble (lib+section or the pdk lines).
    vdd         supply [V]: sets .param VDD, the VDD rail, the bias clipping limit and {VDD} in block netlists (one place only)
    params      extra .param, e.g. {"TEMP":60}  (VDD is added automatically from 'vdd');   extra  list of SPICE lines (".ic v(n1)=0.2", ...)
    rails       ideal rail nodes (Γ=0 and fixed voltage); default {"0":0.0,"VDD":<vdd>}, only needed for other rails
    ref         {"vec":"v(n13)","level":0.0,"edge":"rise"}   crossing that defines the phase (x=0)
    threads      OpenMP threads per ngspice process (default 1; 0 = leave ngspice's own setting). Injected as 'set num_threads=N' in every .control
                 because a num_threads in ~/.spiceinit or spinit (e.g. IIC-OSIC-TOOLS) overrides OMP_NUM_THREADS and oversubscribes the CPU.
    sweep       {"values":["250u","500u","1m"], "line_prefix":"I0", "template":"I0 VBP 0 {v}"}  or  {"values":[...], "param":"IBIAS"}
                'python3 isfpn.py cfg.json sweep' runs 'all' for each value (control = bias current, ...) in sweep/<control>/ and writes
                sweep/sweep.csv (f0, Kvco, L at "offsets", validity, checks) and sweep.png. With line_prefix/template the element line is
                rewritten in the core AND in every block (copies; your netlists are not edited). With param, '.param IBIAS' is set and the
                netlists use 'IBIAS' (core) / {IBIAS} (blocks). Resumable (finished points are skipped; ISFPN_FORCE=1 repeats them).
    --set NAME=value   (after the command, repeatable) overrides a scalar key of the config (tstop, temp, vdd, ...) or, if it is not one,
                sets .param NAME (e.g. --set IBIAS=300u with a netlist using 'IBIAS' / {IBIAS}); the JSON is not modified. Not applied to the sweep points.
    timing.json  written by 'all': time per stage and total, with jobs/threads (to document speed-ups); single stages print '[stage: N s]'.
    ISFPN_THREADS=N / ISFPN_OMP_WAIT=auto|passive|active|none   override 'threads' / the OpenMP wait policy used when jobs > 1 (auto = passive only if threads=0, otherwise untouched).
    jobs         parallel ngspice processes in lin/isf/noise/blocks (1 = serial); also ISFPN_JOBS=N. Try 2-4 on a multi-core PC.
    run_timeout  maximum seconds per ngspice run (300); on timeout the netlist r_<tag>.spice is kept to run by hand.
    ISFPN_VERBOSE=1 prints every ISF point with its time (slow points >20 s are always printed).
    tstop, tstep, settle   transient [s], step ("1p"), time after which steady state holds
    nper        periods between the pulse and the measurement (20);  dq_fc  pulse charge (1.0);  n_phase  (30)
    nodes       list of nodes to perturb; "auto" = all D/S of the FETs that are not rails
    skip_devices  devices NOT treated as core (they go in a block); exact names or regular expressions (full match)
    RESULTS FOLDER  'all' writes in runs/<process>_<T>C_<VDD>V[_<--set NAME-value>][_tag-<--tag>]/ ; 'sweep' in runs/sweep_<variable>_<nominal|Ncorners>/ ;
                  '--here' = current directory (old behaviour); '--tag NAME' extra text for the folder name
    local         output-buffer analysis: {"nodes":[...],"devices":"auto","n_phase":40,"window":0.3,"cross":3,"nlate":3}; stage 'local' (included in 'all')
                  computes the non-accumulating buffer jitter (local ISF) and adds its floor to L: phase_noise_out.csv
    blocks      [{"name":"MIRROR","node":"VCS","file":"mirror_noise.spice","out":"mirror_noise.txt","th_freq":1e8}]
                The block netlist may use {VNODE} (mean node voltage), {VDD} and {TEMP} (the config's vdd and temp) and any
                key of "params" as {NAME}, all substituted before running, and must write the onoise_spectrum
                spectrum with wrdata to 'out' (short-circuit current into a noiseless 1 Ω resistor).
    df_list     offsets for the table (Hz);   compare_file  reference table f[Hz] dBc/Hz

OUTPUTS (in the case directory)
    base_ref.json  T0, f0, crossings;  wave_base.txt;  lin.json;  isf_<NODE>.json;  noise_dev.json;  blocks.json
    summary.json   L(Δf), contribution per device, validity, checks;   report.txt   readable tables
    phase_noise.csv   L(Δf) thermal/flicker/total, Sφ=2L [rad²/Hz] and 'valid' flag (for the PLL model);
    contributions.csv, isf.csv;   figs/fig1..fig7_*.png   one figure per stage (the 'plots' command regenerates them)
    Extra config keys:  csv_grid {"fmin","fmax","ppd"};  compare_file is optional (without it nothing is compared; the automatic
    checks cover stable period, ISF cycle closure, ΔQ linearity and validity).

NOTES
    - Units: Γ_raw in rad/fC; for L it is scaled ×1e15 (rad/C). Convention: positive Γ = injecting positive charge advances the phase.
    - Thermal: S_th = PSD at 1e10 Hz (flat, residual flicker <10%); Flicker: K = S(1 Hz)-S_th if S(1 Hz)>5 S_th, EF fitted
      from 1 to 10 Hz. Same rule validated with the ring and the CS (0.4-0.6 dB from Spectre).
    - The ISF of a device between D and S is Γ_D - Γ_S (verified by direct injection).
    - Valid for σφ(Δf..∞) < 0.3 rad (the minimum Δf is reported).
"""
import json, os, re, subprocess, sys, time
import numpy as np

_trapz = getattr(np, "trapezoid", None) or np.trapz
ENV = dict(os.environ, OMP_NUM_THREADS="1")   # OMP_WAIT_POLICY=passive is added only for parallel sweeps (jobs > 1), see Case.isf


# ---------------------------------------------------------------- ngspice utilities
def sh(args, timeout=900):
    return subprocess.run(args, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=timeout, env=ENV)


def crossings(t, v, level, edge="rise"):
    """Times (linearly interpolated) at which v crosses 'level' on edge ('rise'|'fall')."""
    a, b = v[:-1] - level, v[1:] - level
    idx = np.where((a < 0) & (b >= 0))[0] if edge == "rise" else np.where((a > 0) & (b <= 0))[0]
    return t[idx] + (level - v[idx]) * (t[idx + 1] - t[idx]) / (v[idx + 1] - v[idx])


def lib_models(libfile, _seen=None):
    """Names of .subckt/.model in a lib, following relative .include/.lib (works for both the full and the fast PDK).
    Returns the set of lowercase names, e.g. {'sky130_fd_pr__nfet_01v8', ...}."""
    _seen = _seen if _seen is not None else set(); out = set()
    libfile = os.path.abspath(libfile)
    if libfile in _seen or not os.path.exists(libfile): return out
    _seen.add(libfile); base = os.path.dirname(libfile)
    for ln in open(libfile, errors="ignore"):
        m = re.match(r"\s*\.(subckt|model)\s+(\S+)", ln, re.I)
        if m: out.add(m.group(2).lower())
        m = re.match(r"\s*\.(include|lib)\s+[\"']?([^\s\"']+)[\"']?", ln, re.I)
        if m and "/" in m.group(2) or (m and m.group(2).endswith((".spice", ".lib", ".ngspice"))):
            out |= lib_models(os.path.join(base, m.group(2)), _seen)
    return out


def vmax_model(model, vdd):
    """Maximum reasonable terminal voltage used to clip a model's bias (per sky130 family)."""
    m = model.lower()
    for key, v in (("g5v0d16", 17.0), ("g5v0", 5.5), ("06v0", 6.6), ("05v0", 5.5), ("03v3", 3.6), ("20v0", 21.0)):
        if key in m: return v
    return vdd


_SUF = {"t": 1e12, "g": 1e9, "meg": 1e6, "k": 1e3, "m": 1e-3, "u": 1e-6, "n": 1e-9, "p": 1e-12, "f": 1e-15}


def spice_number(x):
    """'250u' -> 2.5e-4; 'meg', 'k', ... and plain numbers are accepted (SPICE suffixes, case-insensitive)."""
    if isinstance(x, (int, float)): return float(x)
    m = re.fullmatch(r"\s*([-+]?[\d.]+(?:[eE][-+]?\d+)?)\s*(meg|[tgkmunpf])?[a-zA-Z]*\s*", str(x), re.I)
    if not m: raise ValueError(f"cannot read '{x}' as a SPICE number")
    return float(m.group(1)) * (_SUF[m.group(2).lower()] if m.group(2) else 1.0)


def apply_patch(text, p, what, required=True):
    """Replaces the element line starting with p['line_prefix'] (and its '+' continuation lines) by p['template'] with {v} -> p['value'].
    Same idea as the sweep of osc_characterization.py: the netlist file is never edited, the copy is. Exactly one match is required
    (none is allowed in optional files, e.g. a block that does not contain the element)."""
    rx = re.compile(rf"(?im)^[ \t]*{re.escape(p['line_prefix'])}[ \t]+[^\n]*(?:\n\+[^\n]*)*")
    n = len(rx.findall(text))
    if n == 0:
        if required: raise SystemExit(f"patch: no line starting with '{p['line_prefix']}' found in {what}")
        print(f"patch: note, no line starting with '{p['line_prefix']}' in {what} (left unchanged)"); return text
    if n > 1: raise SystemExit(f"patch: {n} lines start with '{p['line_prefix']}' in {what}; the prefix must be unique")
    return rx.sub(lambda m: p["template"].replace("{v}", str(p["value"])), text, count=1)


SETS = []     # filled by __main__ from '--set NAME=value'
SCALARS = {"jobs", "threads", "tstop", "tstep", "settle", "nper", "dq_fc", "n_phase", "temp", "vdd", "reltol", "run_timeout", "section"}   # config keys that --set may set even if absent from the JSON
TAG = [None]  # '--tag NAME': extra text for the name of the run/sweep folder


def _fmt_temp(t): return f"{t:g}".replace("-", "m")                      # -40 -> m40
def _fmt_vdd(v): return (f"{v:g}" if "." in f"{v:g}" else f"{v:g}.0").replace(".", "p")    # 3.3 -> 3p3, 3 -> 3p0
def _clean(x): return re.sub(r"[^A-Za-z0-9.+-]", "_", str(x))


def corner_label(proc, temp, vdd): return f"{proc}_{_fmt_temp(float(temp))}C_{_fmt_vdd(float(vdd))}V"


def cfg_process(cfg):
    """Process section of a config: the section of the '.lib <file> <section>' line of the pdk preamble, or 'section'."""
    if cfg.get("pdk"):
        for l in cfg["pdk"]["preamble"]:
            m = re.match(r"(?i)^\s*\.lib\s+\S+\s+(\S+)\s*$", l)
            if m: return m.group(1)
        return "pdk"
    return cfg.get("section", "tt")


def run_in_folder(cfgpath):
    """'all' without --here: the results go to runs/<process>_<temp>C_<vdd>V[_<NAME>-<value>...][_tag-<TAG>]/ (next to the case files, which
    are never written). The folder gets a self-contained config.json (absolute netlist paths, --set values applied) and all.log, and the flow
    runs inside it. The same name = the same folder (it is overwritten)."""
    raw = json.load(open(cfgpath)); suf = []
    for kv in SETS:                       # same rule as Case.__init__: scalar key of the config, otherwise a .param
        k, _, v = kv.partition("=")
        try: v = spice_number(v)
        except ValueError: pass
        if (k in raw or k in SCALARS) and not isinstance(raw.get(k), (dict, list)): raw[k] = int(v) if (isinstance(raw.get(k), int) or k in ("jobs", "threads", "nper", "n_phase")) and float(v).is_integer() else v
        else: raw.setdefault("params", {})[k] = v
        if k not in ("jobs", "threads", "temp", "vdd", "section"): suf.append(f"{_clean(k)}-{_clean(kv.partition('=')[2])}")      # jobs/threads do not change the result
    name = corner_label(cfg_process(raw), raw.get("temp", 60), raw.get("vdd", 1.8)) + "".join("_" + x for x in suf) + (f"_tag-{_clean(TAG[0])}" if TAG[0] else "")
    d = os.path.abspath(os.path.join("runs", name)); os.makedirs(d, exist_ok=True)
    for kk in ("core", "compare_file"):
        if kk in raw: raw[kk] = os.path.abspath(raw[kk])
    for b in raw.get("blocks", []): b["file"] = os.path.abspath(b["file"])
    json.dump(raw, open(os.path.join(d, "config.json"), "w"), indent=1)
    print(f"results in {os.path.relpath(d)}/", flush=True)
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    with open(os.path.join(d, "all.log"), "w") as lg:
        p = subprocess.Popen([sys.executable, os.path.abspath(__file__), "config.json", "all", "--here"], cwd=d, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for ln in p.stdout: sys.stdout.write(ln); lg.write(ln); lg.flush()
        rc = p.wait()
    print(f"results in {os.path.relpath(d)}/ (config.json, all.log, report.txt, phase_noise.csv, figs/)", flush=True)
    return rc



class Case:
    """A case = directory with CONFIG.json, core netlist and blocks."""

    def __init__(self, cfgpath):
        self.cfgpath = cfgpath
        self.cfg = c = json.load(open(cfgpath))
        c.setdefault("section", "tt"); c.setdefault("temp", 60); c.setdefault("vdd", 1.8)
        for kv in SETS:       # --set NAME=value from the command line: an existing scalar key of the config, otherwise a .param
            k, _, v = kv.partition("=")
            try: v = spice_number(v)
            except ValueError: pass          # not a number: keep the text
            if (k in c or k in SCALARS) and not isinstance(c.get(k), (dict, list)): c[k] = int(v) if (isinstance(c.get(k), int) or k in ("jobs", "threads", "nper", "n_phase")) and float(v).is_integer() else v
            else: c.setdefault("params", {})[k] = v
        c.setdefault("params", {}); c.setdefault("extra", []); c.setdefault("rails", {"0": 0.0, "VDD": c["vdd"]})
        c["params"].setdefault("VDD", c["vdd"])       # .param VDD follows 'vdd' unless set explicitly
        c.setdefault("tstop", 70e-9); c.setdefault("tstep", "1p"); c.setdefault("settle", 25e-9)
        c.setdefault("nper", 20); c.setdefault("dq_fc", 1.0); c.setdefault("n_phase", 30)
        c.setdefault("run_timeout", 300); c.setdefault("threads", 1); c.setdefault("jobs", 1); c.setdefault("nodes", "auto"); c.setdefault("skip_devices", []); c.setdefault("blocks", [])
        c.setdefault("df_list", [1e4, 1e5, 3e5, 1e6, 3e6, 1e7, 3e7, 1e8]); c.setdefault("reltol", 1e-5)
        c["threads"] = int(os.environ.get("ISFPN_THREADS", c["threads"]))   # env wins (used by tools/bench_jobs.py)
        c.setdefault("lib", None); c.setdefault("pdk", None)
        if c["pdk"]:                                  # multi-line PDK preamble (e.g. gf180mcuD)
            c["pdk"]["root"] = os.environ.get("ISFPN_PDK", c["pdk"].get("root", ""))
        else:                                         # legacy: single .lib file + section (sky130)
            c["lib"] = os.environ.get("ISFPN_LIB", c["lib"])
        self.rails = {k.upper(): v for k, v in c["rails"].items()}
        c.setdefault("patch", None); c.setdefault("local", None)
        if c["local"]:
            for k, v in (("n_phase", 40), ("window", 0.3), ("nlate", 3), ("cross", 3), ("devices", "auto")): c["local"].setdefault(k, v)
        if c["patch"]:     # written by 'sweep' (line_prefix mode): patched copy of the core, used by every run of this point
            open("core_patched.cir", "w").write(apply_patch(open(c["core"]).read(), c["patch"], f"core '{c['core']}'"))
            c["core"] = "core_patched.cir"
        self.devs = self.parse_devices()
        if c["nodes"] == "auto":
            ns = set()
            for d in self.devs.values():
                for n in (d["d"], d["s"]):
                    if n.upper() not in self.rails: ns.add(n.upper())
            c["nodes"] = sorted(ns)
        c["nodes"] = [n.upper() for n in c["nodes"]]
        for b in c["blocks"]:
            if b["node"].upper() not in c["nodes"]: c["nodes"].append(b["node"].upper())

    # ---- core netlist parsing
    def parse_devices(self, all_=False):
        """Core FETs: X... instances whose model is declared in the lib (or, if the lib cannot be read, whose
        name contains 'fet'). Returns {name: {d,g,s,b,model,kind,params}}. Warns about unsupported X instances
        (resistors, capacitors, diodes, BJTs...: their noise is NOT included)."""
        known = {m for m in lib_models(self.models_file()) if "fet" in m}
        self.known_models = known
        text = re.sub(r"\n\+", " ", open(self.cfg["core"]).read())
        devs, skip = {}, [x for x in self.cfg["skip_devices"]]     # exact names or regular expressions (full match, case-insensitive)
        for ln in text.splitlines():
            tk = ln.split()
            if len(tk) < 3 or not tk[0].upper().startswith("X"): continue
            pre = [t for t in (tk[:next((j for j, t in enumerate(tk) if "=" in t), len(tk))])]
            model = pre[-1]                      # last token before the name=value parameters
            ml = (model or "").lower()
            isfet = (ml in known) if known else ("fet" in ml)
            nm = tk[0].upper()
            if not isfet:
                print(f"WARNING: {nm} uses model '{model}', not recognized as a FET in the lib: its noise is NOT included")
                continue
            if not all_ and any(re.fullmatch(p, nm, re.I) for p in skip): continue
            i = tk.index(model)
            devs[nm] = {"d": tk[1], "g": tk[2], "s": tk[3], "b": tk[4], "model": model,
                        "kind": "p" if "pfet" in ml else "n", "params": " ".join(tk[i + 1:])}
        if not known: print("WARNING: could not read the lib; the model name ('fet') was used to detect FETs")
        return devs

    # ---- common netlist
    def netlist(self, pert=None, wr="v(n1)", wfile="w.txt", extra_control="", tstop=None):
        c = self.cfg
        L = [f".include {c['core']}"]
        if pert: L.append(f"Ipert {pert[0]} PULSE(0 {pert[1]} {pert[2]} 1p 1p 1p 1)")
        L += c["extra"]
        L += [f".param {k}={v}" for k, v in c["params"].items()]
        L += [f".temp {c['temp']}", f".options reltol={c['reltol']}",
              ".lib {LIB}", ".GLOBAL VDD", ".control", f" tran {c['tstep']} {tstop if tstop else c['tstop']} uic",
              " option remzerovec", f" wrdata {wfile} {wr}", ".endc", ".end"]
        return "\n".join(L)

    def preamble(self):
        """Lines that load the PDK. Either {"pdk": {"root", "preamble": [...{PDK}...], "models"}} or the legacy lib+section."""
        c = self.cfg
        if c["pdk"]:
            return "\n".join(l.replace("{PDK}", c["pdk"]["root"]) for l in c["pdk"]["preamble"])
        return f".lib {c['lib']} {c['section']}"

    def models_file(self):
        """File scanned to recognize the FET models (declared FET names)."""
        c = self.cfg
        if c["pdk"]:
            return c["pdk"].get("models", "{PDK}/").replace("{PDK}", c["pdk"]["root"])
        return c["lib"]

    def render(self, text):
        """Replaces the line '.lib {LIB}' by the PDK preamble: '.lib <lib> <section>' (config 'lib'/'section' or ISFPN_LIB), or
        the lines of config 'pdk' (root from ISFPN_PDK). ngspice does not expand environment variables in .lib/.include,
        so the substitution is done here."""
        if self.cfg["threads"]:   # force ngspice's OpenMP threads: a 'set num_threads=N' in .spiceinit/spinit overrides OMP_NUM_THREADS
            text = re.sub(r"(?im)^([ \t]*\.control[ \t]*)$", lambda m: m.group(1) + f"\n set num_threads={self.cfg['threads']}", text)
        text = re.sub(r"(?im)^[ \t]*\.lib[ \t]+\{LIB\}[ \t]*$", lambda m: self.preamble(), text)   # whole line -> PDK preamble
        if not self.cfg["pdk"]: text = text.replace("{LIB}", f"{self.cfg['lib']} {self.cfg['section']}")
        return text

    def export_template(self, name="base"):
        """Writes templates/<name>.spice with .lib {LIB} (template without a fixed path) to inspect or edit by hand."""
        os.makedirs("templates", exist_ok=True)
        open(f"templates/{name}.spice", "w").write(self.netlist(None, self.cfg["ref"]["vec"], "w_base.txt"))
        print(f"template written to templates/{name}.spice (line: .lib {{LIB}})")

    def run(self, tag, pert=None, wr=None, tstop=None):
        wr = wr or self.cfg["ref"]["vec"]
        fn, wf = f"r_{tag}.spice", f"w_{tag}.txt"
        open(fn, "w").write(self.render(self.netlist(pert, wr, wf, tstop=tstop)))
        T = self.cfg["run_timeout"]
        try: r = sh(["ngspice", "-b", fn], timeout=T)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"ngspice exceeded run_timeout={T} s on {fn} (kept). Run  ngspice -b {fn}  by hand to see where it stalls; "
                               f"a pulse at a bad phase can make the timestep collapse (try a larger reltol, a larger tstep or another dq_fc)")
        if not os.path.exists(wf):
            raise RuntimeError(f"ngspice did not produce {wf}; {fn} is kept. Output:\n" + (r.stdout + r.stderr)[-800:])
        d = np.loadtxt(wf); os.remove(wf); os.remove(fn)
        return d

    # ---- 1. baseline
    def baseline(self):
        c = self.cfg
        nodes = c["nodes"] + [n.upper() for d in self.devs.values() for n in (d["g"], d["b"]) if n.upper() not in self.rails]
        if c["local"]:                                    # terminals of the devices of the local (buffer) analysis
            for d in self.local_devs().values(): nodes += [n.upper() for n in (d["d"], d["g"], d["s"], d["b"]) if n.upper() not in self.rails]
        nodes = sorted(set(nodes))
        vecs = [c["ref"]["vec"]] + [f"v({n.lower()})" for n in nodes]
        d = self.run("base", wr=" ".join(vecs))
        t = d[:, 0]; V = {v: d[:, 1 + 2 * i] for i, v in enumerate(vecs)}
        cr = crossings(t, V[vecs[0]], c["ref"]["level"], c["ref"]["edge"]); cr = cr[cr > c["settle"]]
        T0 = float(np.mean(np.diff(cr)))
        np.savetxt("wave_base.txt", np.column_stack([t] + [V[v] for v in vecs]), header=" ".join(["t", "REF"] + nodes))
        json.dump({"T0": T0, "f0": 1 / T0, "c": cr.tolist(), "nodes": nodes, "jitter_T0": float(np.std(np.diff(cr)))},
                  open("base_ref.json", "w"))
        print(f"baseline: f0={1e-6/T0:.3f} MHz  T0={T0:.6e} s  std(T0)={np.std(np.diff(cr)):.2e} s  n_crossings={len(cr)}")
        self.plot_baseline()

    def base(self):
        return json.load(open("base_ref.json"))

    # ---- 2/3. ISF by pulse
    def point(self, node, dq_fc, x, tag):
        c = self.cfg; B = self.base(); T0 = B["T0"]; cr = np.array(B["c"])
        t0 = cr[0] + x * T0; iamp = dq_fc * 1e-15 / 2e-12
        pn = node if " " in node else f"{node} 0"          # "A B": extracts from A and injects into B
        # the perturbed run only needs to reach the measured crossing (+3 periods), not the full tstop: same result, less time
        tend = min(c["tstop"], cr[0] + (c["nper"] + 3) * T0)
        d = self.run(tag, (pn, iamp, t0), tstop=tend); t, v = d[:, 0], d[:, 1]
        cc = crossings(t, v, c["ref"]["level"], c["ref"]["edge"])
        tgt = cr[0] + c["nper"] * T0
        dt = cc[np.argmin(abs(cc - tgt))] - cr[np.argmin(abs(cr - tgt))]
        return float(2 * np.pi * dt / T0 / dq_fc)                         # Γ_raw rad/fC

    def pmap(self, fn, items):
        """map(fn, items) with up to 'jobs' independent ngspice processes at once (config 'jobs' or ISFPN_JOBS; 1 = serial).
        Results keep the order of 'items'. Parallel runs: OMP_WAIT_POLICY 'auto' (see README); serial keeps the default."""
        items = list(items); jobs = min(int(os.environ.get("ISFPN_JOBS", self.cfg["jobs"])), len(items))
        if jobs <= 1:
            ENV.pop("OMP_WAIT_POLICY", None)              # serial: the default policy is much faster
            return [fn(i) for i in items]
        from concurrent.futures import ThreadPoolExecutor
        pol = os.environ.get("ISFPN_OMP_WAIT", "auto")      # auto | passive | active | none (leave ngspice/libgomp default)
        if pol == "auto":   # passive only if ngspice picks its own thread count or the cores are oversubscribed (busy-waiting threads would stall);
            ncpu = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else (os.cpu_count() or 1)   # with threads>=1 and enough cores it is useless (1) or harmful (>=2)
            pol = "passive" if (self.cfg["threads"] == 0 or jobs * self.cfg["threads"] > ncpu) else "none"
        Case.omp_used = pol
        if pol in ("passive", "active"): ENV["OMP_WAIT_POLICY"] = pol   # passive: threads sleep instead of busy-waiting, avoids stalls with several ngspice at once
        try:
            with ThreadPoolExecutor(jobs) as ex: return list(ex.map(fn, items))
        finally: ENV.pop("OMP_WAIT_POLICY", None)

    def lin(self, node=None, x=0.25):
        """ΔQ linearity test: Γ_raw vs ΔQ at the given node and phase; saves lin.json and figs/fig2_linearity.png."""
        node = (node or self.cfg["nodes"][0]).upper(); T0 = self.base()["T0"]
        dqs = [0.2, 0.5, 1, 2, 5, 10, 20, 50, 100]
        g = self.pmap(lambda iq: self.point(node, iq[1], x, f"lin_{iq[0]}"), list(enumerate(dqs)))
        for q, gi in zip(dqs, g): print(f"dQ={q:6.1f} fC  Γ_raw={gi*1e3:9.4f} mrad/fC", flush=True)
        dt = [gi * T0 * q / (2 * np.pi) for gi, q in zip(g, dqs)]
        json.dump({"node": node, "x": x, "dq_fC": dqs, "gamma_raw": g, "dt_s": dt, "dq_used": self.cfg["dq_fc"]}, open("lin.json", "w"))
        self.plot_lin()

    def isf(self):
        c = self.cfg; N = c["n_phase"]; B = self.base()
        for nd in c["nodes"]:
            def one(i, nd=nd):
                t0 = time.time(); v = self.point(nd, c["dq_fc"], i / N, f"s_{nd}_{i}")
                if os.environ.get("ISFPN_VERBOSE") or time.time() - t0 > 20:
                    print(f"  isf {nd}: phase {i}/{N}  {time.time() - t0:.1f} s", flush=True)
                return v
            g = self.pmap(one, range(N + 1))              # one independent ngspice run per phase
            print(f"  isf {nd}: sweep done", flush=True)
            json.dump({"T0": B["T0"], "node": nd, "dq_fC": c["dq_fc"], "x": [i / N for i in range(N + 1)], "gamma_raw": g},
                      open(f"isf_{nd}.json", "w"))
            print(f"isf {nd}: closure Γ(0)-Γ(1)={ (g[0]-g[-1])*1e3:+.3f} mrad/fC  mean={np.mean(g[:-1])*1e3:.3f}  rms={np.sqrt(np.mean(np.square(g[:-1])))*1e3:.3f} mrad/fC", flush=True)
        self.plot_isf(); self.write_isf_csv()

    # ---- 4. noise per device
    def phase_voltages(self):
        B = self.base(); W = np.loadtxt("wave_base.txt"); t = W[:, 0]; N = self.cfg["n_phase"]
        c0 = B["c"][12]; xs = np.arange(N) / N
        out = {n: np.interp(c0 + xs * B["T0"], t, W[:, 2 + i]) for i, n in enumerate(B["nodes"])}
        for r, v in self.rails.items(): out[r] = np.full(N, float(v))
        return out

    def noise_dev_run(self, nm, d, V, N, tag="nzc"):
        """Noise of one isolated transistor biased with the voltages V[node][k] (k = 0..N-1): thermal/flicker PSD vs frequency for each k.
        Returns {"kind","d","s","f","S"[k][freq]}. One ngspice process; files <tag>_<dev>*.txt are removed."""
        c = self.cfg; vm = vmax_model(d['model'], c["vdd"])
        def vol(n): return np.clip(V[n.upper()], 0, max(vm, max(self.rails.values())))
        vg, vd, vs, vb = vol(d["g"]), vol(d["d"]), vol(d["s"]), vol(d["b"])
        L = ["* isolated noise", "Vg g 0 0 ac 1", "Vd dd 0 0", "Vs s 0 0", "Vb b 0 0", "Rs dd d 1 noisy=0",
             f"XM d g s b {d['model']} {d['params']}", f".temp {c['temp']}", ".lib {LIB}",
             ".control", f"option reltol={c['reltol']}"]
        for k in range(N):
            L += [f"alter Vg dc = {vg[k]:.6f}", f"alter Vd dc = {vd[k]:.6f}", f"alter Vs dc = {vs[k]:.6f}",
                  f"alter Vb dc = {vb[k]:.6f}", "noise v(d) Vg dec 1 1 1e10", f"setplot noise{2*k+1}",
                  f"wrdata {tag}_{nm}_{k}.txt onoise_spectrum"]
        L += [".endc", ".end"]
        fn = f"{tag}_{nm}.spice"
        open(fn, "w").write(self.render("\n".join(L))); sh(["ngspice", "-b", fn]); os.remove(fn)
        S = []
        for k in range(N):
            a = np.loadtxt(f"{tag}_{nm}_{k}.txt"); f = a[:, 0]; S.append(a[:, 1] ** 2); os.remove(f"{tag}_{nm}_{k}.txt")
        return {"kind": d["kind"], "d": d["d"], "s": d["s"], "f": f.tolist(), "S": np.array(S).tolist()}

    def noise(self):
        c = self.cfg; N = c["n_phase"]; V = self.phase_voltages()

        def one(item):                                    # one ngspice process per device (its 30 phases run in sequence inside)
            nm, d = item
            r = self.noise_dev_run(nm, d, V, N)
            print(f"noise {nm} ({d['kind']}) done", flush=True)
            return nm, r

        res = dict(self.pmap(one, list(self.devs.items())))
        json.dump(res, open("noise_dev.json", "w"))
        self.plot_noise()

    # ---- 5. blocks
    def blocks(self):
        B = self.base(); W = np.loadtxt("wave_base.txt"); out = {}

        def one(b):
            nd = b["node"].upper(); j = B["nodes"].index(nd)
            vavg = float(np.mean(W[W[:, 0] > self.cfg["settle"] + 15e-9, 2 + j]))
            txt = open(b["file"]).read()
            if self.cfg["patch"]: txt = apply_patch(txt, self.cfg["patch"], f"block '{b['name']}'", required=False)
            subs = {"VNODE": f"{vavg:.6f}", "VDD": self.cfg["vdd"], "TEMP": self.cfg["temp"]}
            subs.update({k: v for k, v in self.cfg["params"].items() if k not in subs})
            for k, v in subs.items(): txt = txt.replace("{" + k + "}", str(v))
            fn = f"blk_run_{b['name']}.spice"
            open(fn, "w").write(self.render(txt)); sh(["ngspice", "-b", fn]); os.remove(fn)
            m = np.loadtxt(b["out"]); f, S = m[:, 0], m[:, 1] ** 2
            th = float(S[np.argmin(abs(f - b.get("th_freq", 1e8)))]); K = float(S[0] - th)
            print(f"block {b['name']}: V({nd})={vavg:.4f} V  Sth^0.5={np.sqrt(th)*1e12:.2f} pA/rtHz  K(1Hz)^0.5={np.sqrt(K)*1e12:.0f} pA/rtHz")
            return b["name"], {"node": nd, "Sth": th, "K1Hz": K, "ef": float(np.log10(max(S[0] - th, 1e-40) / max(S[1] - th, 1e-40)) / np.log10(f[1] / f[0])),
                               "vnode": vavg, "f": f.tolist(), "S": S.tolist()}

        out = dict(self.pmap(one, self.cfg["blocks"]))
        json.dump(out, open("blocks.json", "w"))
        if out: self.plot_blocks()

    # ---- sweep of a control value (e.g. the bias current of a current-starved oscillator), optionally at several PVT corners
    @staticmethod
    def parse_corner(c, pdk):
        """'ss:125:3.0' (process:temp[C]:VDD[V]) or {"proc","temp","vdd","name"} -> dict. 'typical'/'tt' are accepted for either PDK."""
        if isinstance(c, str):
            try: proc, temp, vdd = c.split(":"); c = {"proc": proc, "temp": float(temp), "vdd": float(vdd)}
            except ValueError: raise SystemExit(f"sweep: corner '{c}' must be process:temp_C:VDD, e.g. ss:125:3.0")
        proc = c["proc"].lower(); alias = {"tt": "typical", "typ": "typical"} if pdk else {"typical": "tt", "typ": "tt"}
        proc = alias.get(proc, proc)
        return {"proc": proc, "temp": float(c["temp"]), "vdd": float(c["vdd"]), "label": c.get("name") or corner_label(proc, c["temp"], c["vdd"])}

    @staticmethod
    def apply_corner_cfg(cfg, co):
        """Writes the corner into a point config: process section (in the pdk preamble line '.lib <file> <section>' or 'section'),
        temp and vdd (and an explicit params VDD / rails VDD if the config has them)."""
        cfg["temp"] = co["temp"]; cfg["vdd"] = co["vdd"]
        for d in (cfg.get("params") or {}, cfg.get("rails") or {}):
            for k in list(d):
                if k.upper() == "VDD": d[k] = co["vdd"]
        if cfg.get("pdk"):
            n = 0; pre = []
            for l in cfg["pdk"]["preamble"]:
                l2, k = re.subn(r"(?i)^(\s*\.lib\s+\S+\s+)\S+(\s*)$", lambda m: m.group(1) + co["proc"] + m.group(2), l); n += k; pre.append(l2)
            if n != 1: raise SystemExit(f"sweep: the pdk preamble must contain exactly one '.lib <file> <section>' line to apply a corner (found {n})")
            cfg["pdk"]["preamble"] = pre
        else: cfg["section"] = co["proc"]

    def sweep(self):
        """Wrapper: the console output of the sweep is also appended to <outdir>/sweep.log (no need for '| tee sweep.log'). See _sweep."""
        base = self.sweep_dir(); os.makedirs(base, exist_ok=True)
        class Tee:
            def __init__(self, *f): self.f = f
            def write(self, x):
                for f in self.f: f.write(x)
            def flush(self):
                for f in self.f: f.flush()
        old = sys.stdout
        with open(os.path.join(base, "sweep.log"), "a") as lg:
            lg.write(f"\n===== sweep started {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n"); sys.stdout = Tee(old, lg)
            try: self._sweep()
            finally: sys.stdout = old

    def sweep_dir(self):
        """runs/sweep_<variable>_<nominal|Ncorners>[_tag-<TAG>]  (or the 'outdir' of the sweep config, as given)."""
        sw = self.cfg["sweep"]
        if sw.get("outdir"): return os.path.abspath(sw["outdir"])
        n = len(sw.get("corners", []))
        return os.path.abspath(os.path.join("runs", f"sweep_{_clean(sw.get('param') or sw.get('line_prefix', 'x'))}_" + (f"{n}corners" if n else "nominal") + (f"_tag-{_clean(TAG[0])}" if TAG[0] else "")))

    def _sweep(self):
        """Runs the whole flow ('all') for each value of the control variable (and each PVT corner), one subdirectory per point, and
        collects sweep.csv (f0, Kvco, L at chosen offsets, validity, checks, time) and figures. Config key 'sweep':
          {"values": ["250u","500u","750u","1m"],                       SPICE numbers or numbers
           "line_prefix": "I0", "template": "I0 VBP 0 {v}",          rewrite the element line in the core AND in every block
           (or)  "param": "IBIAS",                                     set .param IBIAS (the netlists use 'IBIAS' / {IBIAS})
           "corners": ["ss:125:3.0", "typical:60:3.3", "ff:-40:3.6"],   optional: process:temp_C:VDD, the whole sweep is repeated at each
           "offsets": [1e4,1e5,1e6,1e7],  "outdir": "sweep",           optional
           "unit": "A",                                                unit of the control (axis label, Kvco in MHz/uA ...)
           "target_f0": 500e6, "target_refine": true}                  optional: control value for f0 = target (linear interpolation per corner),
                                                                       verified by a full run there (+ baseline at +-5 % for Kvco); target.csv
        The netlist files are never edited: patched copies are made. Finished points (timing.json present) are skipped, so an
        interrupted sweep resumes. jobs/threads apply inside each point (points run one after another)."""
        sw = self.cfg["sweep"]; vals = list(sw["values"]); base = self.sweep_dir()
        if not (sw.get("param") or (sw.get("line_prefix") and sw.get("template"))):
            raise SystemExit("sweep: give either 'param' or both 'line_prefix' and 'template'")
        if sw.get("template") and "{v}" not in sw["template"]: raise SystemExit("sweep: 'template' must contain {v}")
        raw = json.load(open(self.cfgpath)); os.makedirs(base, exist_ok=True)
        corners = [self.parse_corner(c, raw.get("pdk")) for c in sw.get("corners", [])]
        if len({c["label"] for c in corners}) != len(corners): raise SystemExit("sweep: two corners have the same label (give 'name')")
        for co in corners: self.apply_corner_cfg(json.loads(json.dumps(raw)), co)      # fail early if a corner cannot be applied
        cases = [(co, os.path.join(base, co["label"])) for co in corners] or [(None, base)]
        def mkpoint(co, v, d, stage_cfg=None):
            """Writes d/config.json for the control value v (and corner co); returns True if it is identical to the one already there."""
            os.makedirs(d, exist_ok=True)
            cfg = json.loads(json.dumps(raw)); cfg.pop("sweep", None)
            for kk in ("core", "compare_file"):
                if kk in cfg: cfg[kk] = os.path.abspath(cfg[kk])
            for b in cfg.get("blocks", []): b["file"] = os.path.abspath(b["file"])
            if co: self.apply_corner_cfg(cfg, co)
            if sw.get("param"): cfg.setdefault("params", {})[sw["param"]] = spice_number(v)
            else: cfg["patch"] = {"line_prefix": sw["line_prefix"], "template": sw["template"], "value": v}
            fn = os.path.join(d, "config.json"); same = os.path.exists(fn) and json.load(open(fn)) == cfg
            json.dump(cfg, open(fn, "w"), indent=1); return same

        def launch(d, stage="all", log="all.log"):
            with open(os.path.join(d, log), "w") as lg:
                return subprocess.run([sys.executable, os.path.abspath(__file__), "config.json", stage, "--here"], cwd=d, stdout=lg, stderr=subprocess.STDOUT).returncode

        n_tot = len(cases) * len(vals); k = 0; pts = []
        for co, cdir in cases:
            for v in vals:
                k += 1; label = f"{sw.get('param') or sw['line_prefix']}_{v}"; d = os.path.join(cdir, label)
                who = f"{co['label']} | {label}" if co else label
                mkpoint(co, v, d)
                if os.path.exists(os.path.join(d, "timing.json")) and not os.environ.get("ISFPN_FORCE"):
                    print(f"[sweep {k}/{n_tot}] {who}: already done (ISFPN_FORCE=1 repeats it)", flush=True)
                else:
                    print(f"[sweep {k}/{n_tot}] {who} ...", flush=True); t0 = time.time()
                    rc = launch(d)
                    print(f"    {'done' if rc == 0 else 'FAILED rc=%d (see %s/all.log)' % (rc, d)} in {time.time() - t0:.0f} s", flush=True)
                pts.append((co, v, d))
        # ---- collect
        offs = sw.get("offsets", [1e4, 1e5, 1e6, 1e7]); rows = []
        for co, v, d in pts:
            try:
                S = json.load(open(os.path.join(d, "summary.json"))); T = json.load(open(os.path.join(d, "timing.json")))
                A = np.genfromtxt(os.path.join(d, "phase_noise.csv"), delimiter=",", skip_header=2); A = A[~np.isnan(A).any(axis=1)]
                fo = os.path.join(d, "phase_noise_out.csv"); Ao = None          # buffer output (local ISF), when the point has it
                if os.path.exists(fo): Ao = np.genfromtxt(fo, delimiter=",", skip_header=2); Ao = Ao[~np.isnan(Ao).any(axis=1)]
                rows.append(dict(corner=co["label"] if co else "", label=v, x=spice_number(v), f0=S["f0"], dmin=S["dmin_valid_Hz"],
                                 Lo=(np.interp(np.log10(offs), np.log10(Ao[:, 0]), Ao[:, 4]).tolist() if Ao is not None else None), Lco=(Ao[:, 4] if Ao is not None else None),
                                 L=np.interp(np.log10(offs), np.log10(A[:, 0]), A[:, 3]).tolist(), off=A[:, 0], Lc=A[:, 3],
                                 nchk=sum(c.startswith("[CHECK") for c in S["checks"]), t=T["total_s"]))
            except Exception as e:
                print(f"sweep: point {co['label'] + ' ' if co else ''}{v} has no results ({e.__class__.__name__}: {e})")
        ok = rows
        names = [co["label"] for co, _ in cases] if corners else [""]
        unit = sw.get("unit", ""); xs_ = [abs(r["x"]) for r in ok if r["x"]]; med = float(np.median(xs_)) if xs_ else 1.0
        pref, psc = next(((pp, sc) for pp, sc in (("", 1.0), ("m", 1e-3), ("u", 1e-6), ("n", 1e-9)) if med >= sc), ("n", 1e-9))
        pref, psc = (pref, psc) if unit else ("", 1.0); ulab = f"{pref}{unit}" if unit else "unit"
        kmean = {}
        for nm in names:                                    # Kvco per corner: local slope df0/d(control) and mean slope
            R = sorted([r for r in ok if r["corner"] == nm], key=lambda r: r["x"])
            if len(R) >= 2:
                kv = np.gradient(np.array([r["f0"] for r in R]), np.array([r["x"] for r in R]))
                for r, kk in zip(R, kv): r["kvco"] = float(kk)
                kmean[nm] = float((R[-1]["f0"] - R[0]["f0"]) / (R[-1]["x"] - R[0]["x"])) * psc / 1e6
            else:
                for r in R: r["kvco"] = float("nan")
                kmean[nm] = float("nan")
        for r in ok: r["kv_d"] = r["kvco"] * psc / 1e6      # MHz per (prefixed unit)
        ok.sort(key=lambda r: (names.index(r["corner"]), r["x"]))
        cc = ("corner," if corners else ""); hasout = any(r["Lo"] is not None for r in ok)
        with open(os.path.join(base, "sweep.csv"), "w") as fh:
            fh.write(cc + "control,f0_Hz,kvco_Hz_per_unit,dmin_valid_Hz," + ",".join(f"L_{o:g}Hz_dBcHz" for o in offs) + (("," + ",".join(f"Lout_{o:g}Hz_dBcHz" for o in offs)) if hasout else "") + ",checks_failed,time_s\n")
            for r in ok:
                fh.write((r["corner"] + "," if corners else "") + f"{r['label']},{r['f0']:.6e},{r['kvco']:.6e},{r['dmin']:.1f}," + ",".join(f"{l:.3f}" for l in r["L"]) + (("," + ",".join(f"{l:.3f}" for l in (r["Lo"] or [float("nan")] * len(offs)))) if hasout else "") + f",{r['nchk']},{r['t']:.0f}\n")
        print(); print(f"{'corner':>18} " * bool(corners) + f"{'control':>10} {'f0[MHz]':>9} {'Kvco[MHz/' + ulab + ']':>15} {'dmin[kHz]':>10} " + " ".join(f"L@{o:.0e}".rjust(10) for o in offs) + "  checks")
        for r in ok:
            print((f"{r['corner']:>18} " if corners else "") + f"{r['label']:>10} {r['f0']/1e6:9.2f} {r['kv_d']:15.4g} {r['dmin']/1e3:10.1f} " + " ".join(f"{l:10.2f}" for l in r["L"]) + f"  {'OK' if r['nchk'] == 0 else str(r['nchk']) + ' CHECK'}")
        print("VCO gain, mean slope (last-first point): " + ", ".join(f"{nm or 'nominal'} {kmean[nm]:.4g}" for nm in names) + f" MHz/{ulab}. Kvco(control) above is the local slope df0/d(control). "
              "For a voltage control: Kvco[Hz/V] = df0/dI · gm of the V-to-I converter, or sweep the voltage source itself (line_prefix of Vctrl).")
        # ---- target frequency: control value that gives f0 = target_f0 (linear interpolation), then a real run there (refine) and Kvco from +-5 %
        trg = None
        if sw.get("target_f0"):
            trg = self._sweep_target(sw, cases, ok, offs, names, psc, ulab, mkpoint, launch, base)
        try:
            plt = self._plt(); colors = ["tab:red", "tab:green", "tab:blue", "tab:orange", "tab:purple", "tab:brown"]
            col = {nm: colors[i % len(colors)] for i, nm in enumerate(names)}
            sel = lambda nm: [r for r in ok if r["corner"] == nm]; xs = sorted({r["x"] for r in ok}); lb = {r["x"]: str(r["label"]) for r in ok}
            def ticks(a):                      # x ticks = the values exactly as written in the config ("250u", "1m", ...)
                a.set_xticks(xs); a.set_xticklabels([lb[x] for x in xs], rotation=30 if len(xs) > 6 else 0); a.set_xlabel(f"control [{ulab}]" if unit else "control"); a.grid(alpha=.3)
            fig, ax = plt.subplots(1, 3, figsize=(15, 4.4))
            for nm in names:
                R = sel(nm); c = col[nm]; lab = nm or None
                ax[0].plot([r["x"] for r in R], [r["f0"] / 1e6 for r in R], "o-", color=c, label=lab)
                ax[1].plot([r["x"] for r in R], [r["kv_d"] for r in R], "s-", color=c, label=(f"{nm} (mean {kmean[nm]:.3g})" if nm else f"mean slope {kmean[nm]:.3g}"))
            if trg:
                ax[0].axhline(sw["target_f0"] / 1e6, color="gray", ls="--", lw=0.8)
                for r_ in trg:
                    if r_.get("x") is not None: ax[0].plot([r_["x"]], [sw["target_f0"] / 1e6], "*", ms=11, color=col[r_["corner"]], mec="k")
            ax[0].set_ylabel("f0 [MHz]"); ax[0].set_title("tuning curve" + (" (star: target)" if trg else "")); ticks(ax[0])
            ax[1].set_ylabel(f"Kvco = df0/d(control) [MHz/{ulab}]"); ax[1].set_title("VCO gain"); ticks(ax[1])
            for j, o in enumerate(offs):                    # L vs control: one line style per offset, one colour per corner
                for nm in names:
                    R = sel(nm); ax[2].plot([r["x"] for r in R], [r["L"][j] for r in R], "o-", ms=3, color=col[nm], alpha=0.35 + 0.65 * (j + 1) / len(offs),
                                            label=(f"{o:.0e} Hz" if nm == names[0] else None))
            ax[2].set_ylabel("L(Δf) [dBc/Hz]"); ax[2].set_title("phase noise vs control (colour = corner)"); ticks(ax[2]); ax[2].legend(title="offset (fainter = lower)", fontsize=7)
            if corners:
                for a in ax[:2]: a.legend(fontsize=8)
            else: ax[1].legend(fontsize=8)
            fig.tight_layout(); fig.savefig(os.path.join(base, "sweep.png"), dpi=130); plt.close(fig)
            # L(Δf) curves: one panel per control value, one curve per corner (what the PLL model uses)
            n = len(xs); nc = min(n, 4); nr = -(-n // nc); fig, ax = plt.subplots(nr, nc, figsize=(4.2 * nc, 3.6 * nr), sharey=True, squeeze=False)
            for a, x in zip(ax.ravel(), xs):
                for nm in names:
                    for r in sel(nm):
                        if r["x"] == x:
                            a.semilogx(r["off"], r["Lc"], color=col[nm], label=nm or None); a.axvline(r["dmin"], color=col[nm], ls=":", lw=0.8)
                            if r["Lco"] is not None: a.semilogx(r["off"], r["Lco"], color=col[nm], ls="--", lw=1)
                a.set_title(f"control = {lb[x]}"); a.set_xlabel("offset Δf [Hz]"); a.grid(alpha=.3, which="both")
            for a in ax[:, 0]: a.set_ylabel("L(Δf) [dBc/Hz]")
            if corners: ax[0, 0].legend(fontsize=8, title="dotted = min. valid offset" + ("; dashed = buffer output" if hasout else ""))
            fig.tight_layout(); fig.savefig(os.path.join(base, "sweep_phase_noise.png"), dpi=130); plt.close(fig)
        except Exception as e: print("sweep plot skipped:", e)
        print(f"\nSaved: {base}/sweep.csv, sweep.png, sweep_phase_noise.png; per-point results in {base}/" + ("<corner>/" if corners else "") + "<control>/ (phase_noise.csv for the PLL model)")

    def _sweep_target(self, sw, cases, ok, offs, names, psc, ulab, mkpoint, launch, base):
        """For each corner: control value for f0 = sw['target_f0'] by linear interpolation of the swept points (no extrapolation); unless
        sw['target_refine'] is false, a full run at that value (<corner>/target_<f>MHz/) and baseline-only runs at +-5 % of it (kv_minus, kv_plus) for the
        gain Kvco = df0/d(control). Writes target.csv, target.png and prints the table, including how much the control must move across corners."""
        ft = float(sw["target_f0"]); refine = bool(sw.get("target_refine", True)); tag = f"target_{ft / 1e6:g}MHz"; out = []
        for co, cdir in cases:
            nm = co["label"] if co else ""; R = sorted([r for r in ok if r["corner"] == nm], key=lambda r: r["x"]); res = {"corner": nm}; out.append(res)
            br = [(a, b) for a, b in zip(R[:-1], R[1:]) if (a["f0"] - ft) * (b["f0"] - ft) <= 0 and a["f0"] != b["f0"]]
            if not br:
                rng = (min(r["f0"] for r in R) / 1e6, max(r["f0"] for r in R) / 1e6) if R else (0, 0)
                print(f"target: {nm or 'nominal'}: {ft / 1e6:g} MHz is outside the swept range {rng[0]:.1f}-{rng[1]:.1f} MHz (no extrapolation); widen 'values'"); continue
            if len(br) > 1: print(f"target: {nm or 'nominal'}: f0 is not monotonic, using the first bracket")
            a, b = br[0]; fr = (ft - a["f0"]) / (b["f0"] - a["f0"]); xs = a["x"] + fr * (b["x"] - a["x"])
            res.update(x=xs, kv_interp=(b["f0"] - a["f0"]) / (b["x"] - a["x"]), bracket=(a["label"], b["label"]),
                       L_interp=[(1 - fr) * p + fr * q for p, q in zip(a["L"], b["L"])],
                       Lo_interp=([(1 - fr) * p + fr * q for p, q in zip(a["Lo"], b["Lo"])] if a["Lo"] and b["Lo"] else None))
            if not refine: continue
            vs = lambda x: f"{x:.6g}"; d0 = os.path.join(cdir, tag); same = mkpoint(co, vs(xs), d0)
            if same and os.path.exists(os.path.join(d0, "timing.json")) and not os.environ.get("ISFPN_FORCE"):
                print(f"[target] {nm or 'nominal'} {vs(xs)}: already done", flush=True)
            else:
                print(f"[target] {nm or 'nominal'}: full run at {vs(xs)} ...", flush=True); t0 = time.time(); rc = launch(d0)
                print(f"    {'done' if rc == 0 else 'FAILED rc=%d (see %s/all.log)' % (rc, d0)} in {time.time() - t0:.0f} s", flush=True)
            fk = []
            for sub, x in (("kv_minus", xs * 0.95), ("kv_plus", xs * 1.05)):
                dk = os.path.join(d0, sub); same = mkpoint(co, vs(x), dk)
                if not (same and os.path.exists(os.path.join(dk, "base_ref.json"))) or os.environ.get("ISFPN_FORCE"):
                    print(f"[target] {nm or 'nominal'}: baseline at {vs(x)} ({sub}) ...", flush=True); launch(dk, "baseline", "baseline.log")
                try: fk.append((x, json.load(open(os.path.join(dk, "base_ref.json")))["f0"]))
                except Exception: pass
            if len(fk) == 2: res["kv_sim"] = (fk[1][1] - fk[0][1]) / (fk[1][0] - fk[0][0])
            try:
                S = json.load(open(os.path.join(d0, "summary.json"))); A = np.genfromtxt(os.path.join(d0, "phase_noise.csv"), delimiter=",", skip_header=2); A = A[~np.isnan(A).any(axis=1)]
                res.update(f0=S["f0"], dmin=S["dmin_valid_Hz"], nchk=sum(c.startswith("[CHECK") for c in S["checks"]), off=A[:, 0], Lc=A[:, 3],
                           L=np.interp(np.log10(offs), np.log10(A[:, 0]), A[:, 3]).tolist(), Lo=None, Lco=None)
                fo = os.path.join(d0, "phase_noise_out.csv")
                if os.path.exists(fo):
                    Ao = np.genfromtxt(fo, delimiter=",", skip_header=2); Ao = Ao[~np.isnan(Ao).any(axis=1)]
                    res["Lo"] = np.interp(np.log10(offs), np.log10(Ao[:, 0]), Ao[:, 4]).tolist(); res["Lco"] = Ao[:, 4]
            except Exception as e: print(f"target: {nm or 'nominal'} has no results ({e.__class__.__name__}: {e})")
        # ---- report
        got = [r for r in out if r.get("x") is not None]
        if not got: return out
        hdr = f"{'corner':>18} {'control':>12} {'f0 sim[MHz]':>12} {'err[%]':>7} {'Kvco[MHz/' + ulab + ']':>15} {'dmin[kHz]':>10} " + " ".join(f"L@{o:.0e}".rjust(10) for o in offs) + (" " * 3 + "L(out) same offsets" if any(r.get("Lo") for r in got) else "")
        print(f"\nTARGET f0 = {ft / 1e6:g} MHz (interpolated control{', verified with a full run' if refine else ''})"); print(hdr)
        with open(os.path.join(base, "target.csv"), "w") as fh:
            fh.write("corner,target_f0_Hz,control_interp,f0_sim_Hz,f0_error_pct,kvco_interp_Hz_per_unit,kvco_sim_Hz_per_unit,dmin_valid_Hz," + ",".join(f"L_interp_{o:g}Hz" for o in offs) + "," + ",".join(f"L_sim_{o:g}Hz" for o in offs) + "," + ",".join(f"Lout_sim_{o:g}Hz" for o in offs) + ",checks_failed\n")
            nan = float("nan")
            for r in got:
                f0 = r.get("f0"); err = (f0 - ft) / ft * 100 if f0 else nan
                kvs = r.get("kv_sim", nan)
                fh.write(f"{r['corner']},{ft:.6e},{r['x']:.6e},{f0 if f0 else nan:.6e},{err:.3f},{r['kv_interp']:.6e},{kvs:.6e},{r.get('dmin', nan):.1f}," + ",".join(f"{l:.3f}" for l in r["L_interp"]) + "," + ",".join(f"{l:.3f}" for l in r.get("L", [nan] * len(offs))) + "," + ",".join(f"{l:.3f}" for l in (r.get("Lo") or [nan] * len(offs))) + f",{r.get('nchk', nan)}\n")
                kv = (kvs if kvs == kvs else r["kv_interp"]) * psc / 1e6
                Ls = r.get("L", r["L_interp"])
                print(f"{r['corner'] or 'nominal':>18} {f"{r['x'] / psc:.4g} {ulab}":>12} {(f0 or nan) / 1e6:12.2f} {err:7.2f} {kv:15.4g} {r.get('dmin', nan) / 1e3:10.1f} " + " ".join(f"{l:10.2f}" for l in Ls) + ("   " + " ".join(f"{l:.2f}" for l in r["Lo"]) if r.get("Lo") else "") + ("" if r.get("nchk", 0) == 0 else f"  {r['nchk']} CHECK"))
        xs_ = [r["x"] for r in got]
        if len(xs_) > 1:
            nom = next((r["x"] for r in got if r["corner"].startswith(("typical", "tt"))), float(np.median(xs_)))
            print(f"Control needed for {ft / 1e6:g} MHz across corners: {min(xs_) / psc:.4g} to {max(xs_) / psc:.4g} {ulab} (max/min = {max(xs_) / min(xs_):.2f}; {100 * (min(xs_) / nom - 1):+.0f} % / {100 * (max(xs_) / nom - 1):+.0f} % around {nom / psc:.4g} {ulab}): "
                  "this is the range the control circuit must cover to hold the frequency over PVT.")
        try:
            plt = self._plt(); fig, ax = plt.subplots(1, 2, figsize=(11, 4.2)); colors = ["tab:red", "tab:green", "tab:blue", "tab:orange", "tab:purple", "tab:brown"]
            for i, r in enumerate(got):
                c = colors[i % len(colors)]; ax[0].bar(i, r["x"] / psc, color=c); ax[0].text(i, r["x"] / psc, f"{r['x'] / psc:.4g}", ha="center", va="bottom", fontsize=8)
                if r.get("off") is not None:
                    ax[1].semilogx(r["off"], r["Lc"], color=c, label=r["corner"] or "nominal")
                    if r.get("Lco") is not None: ax[1].semilogx(r["off"], r["Lco"], color=c, ls="--", lw=1)
                    ax[1].semilogx(offs, r["L_interp"], "x", color=c, ms=5)
            ax[0].set_xticks(range(len(got))); ax[0].set_xticklabels([r["corner"] or "nominal" for r in got], rotation=20, fontsize=8); ax[0].set_ylabel(f"control for f0 = {ft / 1e6:g} MHz [{ulab}]"); ax[0].set_title("control needed per corner"); ax[0].grid(alpha=.3, axis="y")
            ax[1].set_xlabel("offset Δf [Hz]"); ax[1].set_ylabel("L(Δf) [dBc/Hz]"); ax[1].set_title(f"phase noise at f0 = {ft / 1e6:g} MHz (line: run, x: interpolation, dashed: buffer output)"); ax[1].grid(alpha=.3, which="both"); ax[1].legend(fontsize=8)
            fig.tight_layout(); fig.savefig(os.path.join(base, "sweep_target.png"), dpi=130); plt.close(fig)
        except Exception as e: print("target plot skipped:", e)
        print(f"Saved: {base}/target.csv, sweep_target.png; runs in <corner>/{tag}/ (config.json, report.txt, phase_noise.csv: use it for the PLL model)")
        return out

    # ---- 5b. local ISF: non-accumulating (additive) jitter of the output buffer
    def local_devs(self):
        """Devices of the local analysis: config local.devices = list of names/regexes, or "auto" = every FET (also the skipped ones)
        with the drain or the source on one of local.nodes."""
        Lc = self.cfg["local"]; alld = self.parse_devices(all_=True); dv = Lc["devices"]
        if dv == "auto":
            nodes = {n.upper() for n in Lc.get("nodes", [])}
            if not nodes: raise SystemExit("local: give 'nodes' (nodes whose noise reaches the output) or an explicit 'devices' list")
            return {nm: d for nm, d in alld.items() if d["d"].upper() in nodes or d["s"].upper() in nodes}
        return {nm: d for nm, d in alld.items() if any(re.fullmatch(p, nm, re.I) for p in dv)}

    def point_local(self, node, i, tag):
        """Charge pulse at 'node' at the time cr[J] - w_i (w_i inside a window before the J-th reference crossing). Returns the shift of the
        first crossing after the pulse (J) and of the crossing nlate periods later (the persistent, accumulated part), in s."""
        c = self.cfg; Lc = c["local"]; B = self.base(); T0 = B["T0"]; cr = np.array(B["c"]); J, nl, M = Lc["cross"], Lc["nlate"], Lc["n_phase"]
        if J + nl + 1 >= len(cr): raise SystemExit(f"local: only {len(cr)} reference crossings after 'settle'; lower local.cross/nlate or raise tstop")
        w = Lc["window"] * T0 * (i + 0.5) / M; t0 = cr[J] - w; dq = c["dq_fc"]
        tend = min(c["tstop"], cr[J + nl] + 0.6 * T0)
        d = self.run(tag, (f"{node} 0", dq * 1e-15 / 2e-12, t0), tstop=tend); cc = crossings(d[:, 0], d[:, 1], c["ref"]["level"], c["ref"]["edge"])
        sh_ = lambda k: float(cc[np.argmin(abs(cc - cr[k]))] - cr[k])
        return sh_(J), sh_(J + nl)

    def local(self):
        """Local ISF h(t) [s/C] = transient shift of the output edge per unit charge injected at each node of the buffer path, minus the persistent
        shift (that part is the accumulated phase noise already given by the ISF stage), and the noise of the buffer devices at the same instants.
        Saves local_isf.json and noise_local.json; 'combine' turns them into the additive floor at the output."""
        c = self.cfg; Lc = c["local"]
        if not Lc: raise SystemExit("local: the config has no 'local' key")
        B = self.base(); T0 = B["T0"]; cr = np.array(B["c"]); M = Lc["n_phase"]; J = Lc["cross"]; dq = c["dq_fc"]
        devs = self.local_devs()
        if not devs: raise SystemExit("local: no device selected")
        nodes = sorted({n.upper() for d in devs.values() for n in (d["d"], d["s"]) if n.upper() not in self.rails})
        print(f"local: {len(devs)} devices, nodes {', '.join(nodes)}; {M} phases in a window of {Lc['window']} T0 before the crossing", flush=True)
        items = [(nd, i) for nd in nodes for i in range(M)]
        res = self.pmap(lambda it: self.point_local(it[0], it[1], f"l_{it[0]}_{it[1]}"), items)
        w = (Lc["window"] * T0 * (np.arange(M) + 0.5) / M)
        out = {"T0": T0, "dq_fC": dq, "cross": J, "nlate": Lc["nlate"], "window": Lc["window"], "w": w.tolist(), "nodes": {}}
        for k, nd in enumerate(nodes):
            r = np.array(res[k * M:(k + 1) * M]); h = (r[:, 0] - r[:, 1]) / (dq * 1e-15)          # s/C
            out["nodes"][nd] = {"h": h.tolist(), "first": (r[:, 0] / (dq * 1e-15)).tolist(), "late": (r[:, 1] / (dq * 1e-15)).tolist()}
            print(f"  local {nd}: max|h| = {np.max(abs(h)) * 1e-3:.3g} ps/fC (transient edge shift per fC), persistent part {np.mean(r[:, 1]) / (dq * 1e-15):.3g} fs/fC", flush=True)
        json.dump(out, open("local_isf.json", "w"))
        W = np.loadtxt("wave_base.txt"); tt = cr[J] - w
        V = {n: np.interp(tt, W[:, 0], W[:, 2 + j]) for j, n in enumerate(B["nodes"])}
        for r_, v in self.rails.items(): V[r_] = np.full(M, float(v))
        miss = {n.upper() for d in devs.values() for n in (d["d"], d["g"], d["s"], d["b"])} - set(V)
        if miss: raise SystemExit(f"local: nodes {sorted(miss)} are not in wave_base.txt; run 'baseline' again")
        res = dict(self.pmap(lambda it: (it[0], self.noise_dev_run(it[0], it[1], V, M, "nzl")), list(devs.items())))
        for nm in res: print(f"noise (local) {nm} done", flush=True)
        json.dump(res, open("noise_local.json", "w"))
        self.plot_local()

    def local_rows(self):
        """Per device: variance of the edge time [s^2] from thermal noise (1/2 ∫ h² S dt) and flicker amplitude A [s] (∫ h √K dt, coherent), EF."""
        I = json.load(open("local_isf.json")); Nz = json.load(open("noise_local.json")); M = len(I["w"]); dw = I["window"] * I["T0"] / M
        H = lambda n: np.array(I["nodes"][n.upper()]["h"]) if n.upper() in I["nodes"] else np.zeros(M)
        rows = {}
        for nm, d in Nz.items():
            S = np.array(d["S"]); Sth = S[:, -1]; Sfl1 = S[:, 0] - Sth; dom = Sfl1 > 5 * Sth; K = np.where(dom, Sfl1, 0.0)
            ef = float(np.median(np.log10(np.maximum(Sfl1[dom], 1e-40) / np.maximum(S[dom, 1] - Sth[dom], 1e-40)) / np.log10(d['f'][1] / d['f'][0]))) if dom.any() else 1.0
            h = H(d["d"]) - H(d["s"])
            rows[nm] = {"kind": d["kind"], "var_th": float(0.5 * np.sum(h ** 2 * Sth) * dw), "A": float(np.sum(h * np.sqrt(K)) * dw), "ef": ef}
        return rows

    def local_curves(self, lrows, df):
        """(L_th, L_fl) [1/Hz, linear] of the buffer at the output, offsets df. Both edges of the differential output carry independent jitter of the
        same variance (symmetry): sampled at 2·f0, L_th = 2π² f0 σt² (flat, valid up to Δf ≈ f0); L_fl = ½(2π f0)² ΣA²/Δf^EF (quasi-static)."""
        f0 = 1 / self.base()["T0"]; df = np.asarray(df, float)
        th = 2 * np.pi ** 2 * f0 * sum(r["var_th"] for r in lrows.values()) * np.ones_like(df)
        fl = 0.5 * (2 * np.pi * f0) ** 2 * sum(r["A"] ** 2 / df ** r["ef"] for r in lrows.values())
        return th, fl

    # ---- 6. combination
    def combine(self):
        c = self.cfg; N = c["n_phase"]
        isf = {nd: np.array(json.load(open(f"isf_{nd}.json"))["gamma_raw"][:-1]) * 1e15 for nd in c["nodes"]}
        zero = np.zeros(N); G = lambda n: isf.get(n.upper(), zero)
        nz = json.load(open("noise_dev.json")); rows = {}
        for nm, d in nz.items():
            S = np.array(d["S"]); Sth = S[:, -1]; Sfl1 = S[:, 0] - Sth
            dom = Sfl1 > 5 * Sth
            K = np.where(dom, Sfl1, 0.0)
            ef = float(np.median(np.log10(np.maximum(Sfl1[dom], 1e-40) / np.maximum(S[dom, 1] - Sth[dom], 1e-40))) / np.log10(d['f'][1] / d['f'][0])) if dom.any() else 1.0
            g = G(d["d"]) - G(d["s"])
            rows[nm] = {"kind": d["kind"], "th": float(np.mean(g ** 2 * Sth)), "coh": float(np.mean(g * np.sqrt(K)) ** 2), "ef": ef,
                        "Grms_mrad_fC": float(np.sqrt(np.mean(g ** 2)) * 1e-12)}
        if c["blocks"]:
            bl = json.load(open("blocks.json"))
            for nm, b in bl.items():
                g = G(b["node"]); rows[nm] = {"kind": "blk", "th": float(np.mean(g ** 2) * b["Sth"]),
                                              "coh": float(np.mean(g) ** 2 * b["K1Hz"]), "ef": b["ef"],
                                              "Grms_mrad_fC": float(np.sqrt(np.mean(g ** 2)) * 1e-12)}
        def L(df):
            w2 = (2 * np.pi * df) ** 2
            return (sum(r["th"] for r in rows.values()) / (2 * w2), sum(r["coh"] / df ** r["ef"] for r in rows.values()) / (2 * w2))
        dB = lambda v: 10 * np.log10(v)
        df = np.logspace(3.5, 9, 600); Lt = np.array([sum(L(d)) for d in df]); S = 2 * Lt
        sig = np.array([np.sqrt(_trapz(S[i:], df[i:])) for i in range(len(df))]); dmin = float(df[np.argmax(sig < 0.3)])
        T0 = self.base()["T0"]
        lines = [f"f0 = {1e-6/T0:.3f} MHz   minimum valid Δf (σφ<0.3 rad): {dmin/1e3:.0f} kHz", "",
                 f"{'Δf [Hz]':>10} {'thermal':>9} {'flicker':>9} {'total':>9}  dBc/Hz"]
        Ltab = {}
        for d in c["df_list"]:
            a, b = L(d); Ltab[str(int(d))] = {"th": dB(a), "fl": dB(b), "tot": dB(a + b)}
            lines.append(f"{d:10.3g} {dB(a):9.2f} {dB(b):9.2f} {dB(a + b):9.2f}")
        tth = sum(r["th"] for r in rows.values()); d0 = 1e5
        tfl = sum(r["coh"] / d0 ** r["ef"] for r in rows.values())
        lines += ["", f"{'device':<10}{'type':>5}{'Γrms[mrad/fC]':>15}{'% therm':>9}{'% flick(100k)':>15}{'EF':>6}"]
        for nm, r in rows.items():
            lines.append(f"{nm:<10}{r['kind']:>5}{r['Grms_mrad_fC']:>15.2f}{100*r['th']/tth:>9.1f}{100*r['coh']/d0**r['ef']/tfl:>15.1f}{r['ef']:>6.2f}")
        have_local = self.cfg["local"] and os.path.exists("local_isf.json") and os.path.exists("noise_local.json")
        if have_local: lines += self.local_report(rows, dmin)
        chk = self.checks(dmin)
        lines += ["", "CHECKS (no external reference)"] + chk
        open("report.txt", "w").write("\n".join(lines)); print("\n".join(lines))
        summ = {"f0": 1 / T0, "dmin_valid_Hz": dmin, "L": Ltab, "rows": rows, "checks": chk}
        if have_local: summ["local"] = self.local_summary
        json.dump(summ, open("summary.json", "w"), indent=1)
        self.write_csvs(rows, dmin)
        self.plot_combine()


    def local_report(self, rows, dmin):
        """Table of the phase noise at the output (oscillator + additive buffer floor) and per-device share of the buffer jitter; writes phase_noise_out.csv."""
        c = self.cfg; lrows = self.local_rows(); f0 = self.base()["f0"]; dB = lambda v: 10 * np.log10(np.maximum(v, 1e-300))
        var = sum(r["var_th"] for r in lrows.values()); sig = float(np.sqrt(var)); Lth = 2 * np.pi ** 2 * f0 * var
        out = ["", f"BUFFER OUTPUT (local ISF): additive jitter per edge σt = {sig * 1e15:.1f} fs  ->  white floor {dB(Lth):.1f} dBc/Hz (valid up to Δf ≈ f0 = {f0 / 1e6:.0f} MHz)",
               "  (the accumulated phase noise of the oscillator is unchanged by the buffer: L_out = L_osc + L_buffer, powers add)", "",
               f"{'Δf [Hz]':>10} {'L_osc':>9} {'L_buf th':>9} {'L_buf fl':>9} {'L_out':>9}  dBc/Hz"]
        for d in c["df_list"]:
            a, b = self.Lcurve(rows, [d]); th, fl = self.local_curves(lrows, [d]); tot = a + b + th + fl
            out.append(f"{d:10.3g} {dB(a + b)[0]:9.2f} {dB(th)[0]:9.2f} {dB(fl)[0]:9.2f} {dB(tot)[0]:9.2f}")
        out += ["", f"{'buffer device':<14}{'type':>5}{'% of σt²':>10}{'A_flick[fs]':>13}{'EF':>6}"]
        for nm, r in lrows.items(): out.append(f"{nm:<14}{r['kind']:>5}{100 * r['var_th'] / var:>10.1f}{r['A'] * 1e15:>13.3f}{r['ef']:>6.2f}")
        g = c.get("csv_grid", {}); f0g, f1g, ppd = g.get("fmin", 1e3), g.get("fmax", 1e9), g.get("ppd", 20)
        df = np.logspace(np.log10(f0g), np.log10(f1g), int(round(np.log10(f1g / f0g) * ppd)) + 1)
        a, b = self.Lcurve(rows, df); th, fl = self.local_curves(lrows, df); tot = a + b + th + fl
        with open("phase_noise_out.csv", "w") as f:
            f.write(f"# phase noise at the buffer output: oscillator (accumulated, ISF) + buffer additive floor (local ISF); f0_Hz={f0:.6e}; L = Sphi/2; valid=1 if dmin_osc <= offset <= f0\n")
            f.write("offset_Hz,L_osc_dBcHz,L_buf_thermal_dBcHz,L_buf_flicker_dBcHz,L_out_total_dBcHz,L_out_linear_1perHz,Sphi_out_rad2perHz,valid\n")
            for i in range(len(df)):
                f.write(f"{df[i]:.6e},{dB(a[i] + b[i]):.4f},{dB(th[i]):.4f},{dB(fl[i]):.4f},{dB(tot[i]):.4f},{tot[i]:.6e},{2 * tot[i]:.6e},{int(dmin <= df[i] <= f0)}\n")
        self.local_summary = {"sigma_t_fs": sig * 1e15, "L_floor_dBcHz": float(dB(Lth)), "devices": lrows}
        out.append("CSV: phase_noise_out.csv")
        return out

    # ---- outputs: CSV
    def Lcurve(self, rows, df):
        """(L_th, L_fl) linear [1/Hz] at offsets df (array) from the contribution rows."""
        df = np.asarray(df, float); w2 = (2 * np.pi * df) ** 2
        th = sum(r["th"] for r in rows.values()) / (2 * w2)
        fl = sum(r["coh"] / df ** r["ef"] for r in rows.values()) / (2 * w2)
        return th, fl

    def write_csvs(self, rows, dmin):
        """phase_noise.csv (dense grid for use in the PLL model), contributions.csv."""
        c = self.cfg; g = c.get("csv_grid", {})
        f0, f1, ppd = g.get("fmin", 1e3), g.get("fmax", 1e9), g.get("ppd", 20)
        df = np.logspace(np.log10(f0), np.log10(f1), int(round(np.log10(f1 / f0) * ppd)) + 1)
        th, fl = self.Lcurve(rows, df); tot = th + fl
        with open("phase_noise.csv", "w") as f:
            f.write(f"# f0_Hz={self.base()['f0']:.6e}  dmin_valid_Hz={dmin:.1f}  L=Sphi/2 ; Sphi unilateral [rad2/Hz] = 2L; valid=1 if offset>=dmin\n")
            f.write("offset_Hz,L_thermal_dBcHz,L_flicker_dBcHz,L_total_dBcHz,L_total_linear_1perHz,Sphi_rad2perHz,valid\n")
            for a, b, cc, t in zip(df, th, fl, tot):
                f.write(f"{a:.6e},{10*np.log10(b):.4f},{10*np.log10(cc):.4f},{10*np.log10(t):.4f},{t:.6e},{2*t:.6e},{int(a >= dmin)}\n")
        d0 = 1e5; tth = sum(r["th"] for r in rows.values()); tfl = sum(r["coh"] / d0 ** r["ef"] for r in rows.values())
        with open("contributions.csv", "w") as f:
            f.write("device,type,Grms_mrad_per_fC,pct_thermal,pct_flicker_at_100kHz,EF\n")
            for nm, r in rows.items():
                f.write(f"{nm},{r['kind']},{r['Grms_mrad_fC']:.4f},{100*r['th']/tth:.3f},{100*r['coh']/d0**r['ef']/tfl:.3f},{r['ef']:.3f}\n")
        print("CSV: phase_noise.csv, contributions.csv, isf.csv")

    def write_isf_csv(self):
        c = self.cfg; cols = []; names = []
        for nd in c["nodes"]:
            if os.path.exists(f"isf_{nd}.json"):
                d = json.load(open(f"isf_{nd}.json")); cols.append(np.array(d["gamma_raw"]) * 1e3); names.append(nd); x = d["x"]
        if cols:
            with open("isf.csv", "w") as f:
                f.write("x," + ",".join(f"Gamma_{n}_mrad_per_fC" for n in names) + "\n")
                for i in range(len(x)): f.write(f"{x[i]:.5f}," + ",".join(f"{cc[i]:.5f}" for cc in cols) + "\n")

    # ---- automatic checks (Spectre not required)
    def checks(self, dmin):
        c = self.cfg; out = []; B = self.base()
        out.append(f"[{'OK' if B['jitter_T0'] < 1e-3 * B['T0'] else 'CHECK'}] stable period: std(T0)={B['jitter_T0']:.2e} s ({100*B['jitter_T0']/B['T0']:.4f} % of T0)")
        for nd in c["nodes"]:
            d = json.load(open(f"isf_{nd}.json")); g = np.array(d["gamma_raw"]); rms = np.sqrt(np.mean(g[:-1] ** 2))
            e = abs(g[0] - g[-1]) / rms
            out.append(f"[{'OK' if e < 0.01 else 'CHECK'}] ISF cycle closure {nd}: |Γ(0)-Γ(1)|/Γrms = {100*e:.3f} %")
        if os.path.exists("lin.json"):
            d = json.load(open("lin.json")); q = np.array(d["dq_fC"]); g = np.array(d["gamma_raw"])
            ref = g[0]; j = int(np.argmin(abs(q - d["dq_used"]))); dev = abs(g[j] / ref - 1)
            out.append(f"[{'OK' if dev < 0.02 else 'CHECK'}] linearity at ΔQ={d['dq_used']} fC: Γ differs {100*dev:.2f} % from that at {q[0]} fC (node {d['node']})")
        out.append(f"[{'OK' if dmin < 5e6 else 'CHECK'}] minimum valid offset (σφ<0.3 rad): {dmin/1e3:.0f} kHz")
        if c["local"] and os.path.exists("local_isf.json"):
            I = json.load(open("local_isf.json"))
            for nd, d in I["nodes"].items():
                h = np.abs(np.array(d["h"])); r = h[-3:].mean() / max(h.max(), 1e-30)
                out.append(f"[{'OK' if r < 0.05 else 'CHECK'}] local window {nd}: |h| at the far end = {100 * r:.1f} % of its peak" + ("" if r < 0.05 else " (increase local.window)"))
        return out

    # ---- plots (one per stage; figs/)
    def _plt(self):
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        os.makedirs("figs", exist_ok=True); return plt

    def plot_all(self):
        for fn in (self.plot_baseline, self.plot_lin, self.plot_isf, self.plot_noise, self.plot_blocks, self.plot_combine, self.plot_local):
            try: fn()
            except FileNotFoundError as e: print("skipped:", fn.__name__, e)
        if "compare_file" in self.cfg and os.path.exists("summary.json"): self.compare()

    def plot_local(self):
        plt = self._plt(); I = json.load(open("local_isf.json")); w = np.array(I["w"]) * 1e12
        fig, ax = plt.subplots(1, 2, figsize=(11, 4))
        for nd, d in I["nodes"].items():
            ax[0].plot(w, np.array(d["h"]) * 1e-3, "o-", ms=3, lw=1, label=nd); ax[1].plot(w, np.array(d["late"]) * 1e-3, lw=1, label=nd)
        ax[0].set_xlabel("time before the output edge [ps]"); ax[0].set_ylabel("local ISF h = transient edge shift [ps/fC]"); ax[0].legend(ncol=2, fontsize=8); ax[0].grid(alpha=.3)
        ax[0].set_title("Local ISF of the buffer (non-accumulating part)")
        ax[1].set_xlabel("time before the output edge [ps]"); ax[1].set_ylabel("persistent shift [ps/fC]"); ax[1].grid(alpha=.3)
        ax[1].set_title("Persistent part (already in the oscillator ISF)")
        fig.tight_layout(); fig.savefig("figs/fig8_local_isf.png", dpi=130); plt.close(fig)

    def plot_baseline(self):
        plt = self._plt(); B = self.base(); W = np.loadtxt("wave_base.txt"); T0 = B["T0"]; cr = np.array(B["c"]); t = W[:, 0]
        names = open("wave_base.txt").readline().lstrip("# ").split()[2:]
        w = (t > cr[2]) & (t < cr[2] + 6 * T0)
        fig, ax = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
        ax[0].plot(t[w] * 1e9, W[w, 1], "k", label=self.cfg["ref"]["vec"])
        ax[0].axhline(self.cfg["ref"]["level"], color="gray", lw=.6)
        cc = cr[(cr > t[w][0]) & (cr < t[w][-1])]; ax[0].plot(cc * 1e9, np.full(len(cc), self.cfg["ref"]["level"]), "rv", label="crossings (x = 0)")
        ax[0].set_ylabel("reference [V]"); ax[0].legend(); ax[0].grid(alpha=.3)
        ax[0].set_title(f"Stage 0 - baseline: f0 = {1e-6/T0:.2f} MHz, T0 = {T0*1e9:.4f} ns, std(T0) = {B['jitter_T0']:.1e} s")
        for i, n in enumerate(names):
            if n in self.cfg["nodes"]: ax[1].plot(t[w] * 1e9, W[w, 2 + i], lw=1, label=n)
        ax[1].set_xlabel("t [ns]"); ax[1].set_ylabel("nodes [V]"); ax[1].legend(ncol=5, fontsize=8); ax[1].grid(alpha=.3)
        fig.tight_layout(); fig.savefig("figs/fig1_baseline.png", dpi=130); plt.close(fig)

    def plot_lin(self):
        plt = self._plt(); d = json.load(open("lin.json")); q = np.array(d["dq_fC"]); g = np.array(d["gamma_raw"]) * 1e3; dt = np.array(d["dt_s"]) * 1e12
        fig, ax = plt.subplots(1, 2, figsize=(10, 4))
        ax[0].loglog(q, abs(dt), "o-", label="measured"); ax[0].loglog(q, abs(dt[0]) * q / q[0], "--", color="gray", label="ideal line (small ΔQ)")
        ax[0].axvline(d["dq_used"], color="r", lw=.8, label=f"ΔQ used = {d['dq_used']} fC"); ax[0].set_xlabel("ΔQ [fC]"); ax[0].set_ylabel("|Δt| [ps]"); ax[0].legend(); ax[0].grid(alpha=.3, which="both")
        ax[1].semilogx(q, g, "o-"); ax[1].axvline(d["dq_used"], color="r", lw=.8); ax[1].axhspan(g[0] * .98, g[0] * 1.02, color="g", alpha=.15, label="±2 % of Γ(ΔQ→0)")
        ax[1].set_xlabel("ΔQ [fC]"); ax[1].set_ylabel("Γ_raw [mrad/fC]"); ax[1].legend(); ax[1].grid(alpha=.3, which="both")
        fig.suptitle(f"Stage 1 - ΔQ linearity (node {d['node']}, x = {d['x']})"); fig.tight_layout(); fig.savefig("figs/fig2_linearity.png", dpi=130); plt.close(fig)

    def plot_isf(self):
        plt = self._plt(); fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
        isf = {}
        for nd in self.cfg["nodes"]:
            if os.path.exists(f"isf_{nd}.json"):
                d = json.load(open(f"isf_{nd}.json")); isf[nd] = np.array(d["gamma_raw"]) * 1e3; x = np.array(d["x"]); ax[0].plot(x, isf[nd], "o-", ms=3, label=nd)
        ax[0].axhline(0, color="gray", lw=.5); ax[0].set_xlabel("x = t/T0"); ax[0].set_ylabel("Γ_raw [mrad/fC]"); ax[0].set_title("ISF per node (injection between the node and GND)"); ax[0].legend(ncol=2, fontsize=8); ax[0].grid(alpha=.3)
        zero = np.zeros_like(x); seen = set()
        for nm, d in self.devs.items():
            key = (d["d"].upper(), d["s"].upper())
            if key in seen: continue
            seen.add(key); g = isf.get(key[0], zero) - isf.get(key[1], zero)
            ax[1].plot(x, g, lw=1.3, label=f"{key[0]}-{key[1]} ({nm})")
        ax[1].axhline(0, color="gray", lw=.5); ax[1].set_xlabel("x = t/T0"); ax[1].set_ylabel("Γ_dev = Γ_D - Γ_S [mrad/fC]"); ax[1].set_title("Effective ISF per device"); ax[1].legend(fontsize=7); ax[1].grid(alpha=.3)
        fig.suptitle("Stage 2 - ISF from charge pulses"); fig.tight_layout(); fig.savefig("figs/fig3_isf.png", dpi=130); plt.close(fig)

    def plot_noise(self):
        plt = self._plt(); nz = json.load(open("noise_dev.json")); N = self.cfg["n_phase"]; x = np.arange(N) / N
        fig, ax = plt.subplots(1, 3, figsize=(15, 4.3)); amax = {"n": (0, None), "p": (0, None)}
        for nm, d in nz.items():
            S = np.array(d["S"]); ls = "-" if d["kind"] == "n" else "--"
            ax[0].plot(x, np.sqrt(S[:, -1]) * 1e12, ls, lw=1, color="C0" if d["kind"] == "n" else "C3")
            Sfl = np.maximum(S[:, 0] - S[:, -1], 0); ax[1].semilogy(x, np.sqrt(Sfl) * 1e12 + 1e-3, ls, lw=1, color="C0" if d["kind"] == "n" else "C3")
            m = float(np.sqrt(Sfl.max()))
            if d["kind"] in amax and m > amax[d["kind"]][0]: amax[d["kind"]] = (m, (nm, int(np.argmax(Sfl))))
        ax[0].plot([], [], "C0-", label="NMOS"); ax[0].plot([], [], "C3--", label="PMOS"); ax[0].legend()
        ax[0].set_xlabel("x = t/T0"); ax[0].set_ylabel("thermal, S(1e10 Hz)^½ [pA/√Hz]"); ax[0].set_title("thermal PSD per phase"); ax[0].grid(alpha=.3)
        ax[1].set_xlabel("x = t/T0"); ax[1].set_ylabel("flicker at 1 Hz, √(S-Sth) [pA/√Hz]"); ax[1].set_title("flicker per phase"); ax[1].grid(alpha=.3, which="both")
        for k, (m, who) in amax.items():
            if who:
                d = nz[who[0]]; f = np.array(d["f"]); S = np.array(d["S"])[who[1]]
                ax[2].loglog(f, np.sqrt(S) * 1e12, "o-", ms=3, label=f"{who[0]} phase {who[1]}/{N}")
        ax[2].set_xlabel("f [Hz]"); ax[2].set_ylabel("S^½ [pA/√Hz]"); ax[2].set_title("spectrum (phase of max flicker)"); ax[2].legend(); ax[2].grid(alpha=.3, which="both")
        fig.suptitle("Stage 4 - noise of each transistor at its instantaneous bias (.noise)"); fig.tight_layout(); fig.savefig("figs/fig4_device_noise.png", dpi=130); plt.close(fig)

    def plot_blocks(self):
        plt = self._plt(); bl = json.load(open("blocks.json"))
        if not bl: return
        fig, ax = plt.subplots(1, len(bl), figsize=(6 * len(bl), 4), squeeze=False)
        for a, (nm, b) in zip(ax[0], bl.items()):
            f = np.array(b["f"]); S = np.array(b["S"])
            a.loglog(f, np.sqrt(S) * 1e12, "o-", ms=3, label="block spectrum"); a.axhline(np.sqrt(b["Sth"]) * 1e12, color="gray", ls="--", label="thermal level")
            a.loglog(f, np.sqrt(b["K1Hz"] / f ** b["ef"]) * 1e12, ":", label=f"flicker K/f^{b['ef']:.2f}"); a.set_title(f"{nm} -> node {b['node']} (V={b['vnode']:.3f} V)")
            a.set_xlabel("f [Hz]"); a.set_ylabel("noise current [pA/√Hz]"); a.legend(); a.grid(alpha=.3, which="both")
        fig.suptitle("Stage 5 - noise of special blocks"); fig.tight_layout(); fig.savefig("figs/fig5_blocks.png", dpi=130); plt.close(fig)

    def plot_combine(self):
        plt = self._plt(); S = json.load(open("summary.json")); rows = S["rows"]; dmin = S["dmin_valid_Hz"]
        df = np.logspace(3.5, 9, 400); th, fl = self.Lcurve(rows, df); dB = lambda v: 10 * np.log10(v)
        fig, ax = plt.subplots(1, 2, figsize=(12, 4.6), gridspec_kw={"width_ratios": [1.4, 1]})
        ax[0].semilogx(df, dB(th + fl), "k", lw=2, label="total"); ax[0].semilogx(df, dB(th), "--", label="thermal (-20 dB/dec)"); ax[0].semilogx(df, dB(fl), ":", label="flicker")
        ax[0].axvspan(df[0], dmin, color="r", alpha=.12, label=f"invalid (< {dmin/1e3:.0f} kHz)")
        ax[0].set_ylim(-170, -20); ax[0].set_xlabel("Δf [Hz]"); ax[0].set_ylabel("L(Δf) [dBc/Hz]"); ax[0].grid(alpha=.3, which="both"); ax[0].legend()
        ax[0].set_title(f"f0 = {S['f0']*1e-6:.2f} MHz")
        d0 = 1e5; tth = sum(r["th"] for r in rows.values()); tfl = sum(r["coh"] / d0 ** r["ef"] for r in rows.values()); nm = list(rows)
        yy = np.arange(len(nm)); ax[1].barh(yy - .2, [100 * rows[n]["th"] / tth for n in nm], .4, label="thermal"); ax[1].barh(yy + .2, [100 * rows[n]["coh"] / d0 ** rows[n]["ef"] / tfl for n in nm], .4, label="flicker @100 kHz")
        ax[1].set_yticks(yy); ax[1].set_yticklabels(nm, fontsize=7); ax[1].invert_yaxis(); ax[1].set_xlabel("% of contribution"); ax[1].legend(); ax[1].set_title("share per device")
        fig.suptitle("Stage 6 - total phase noise"); fig.tight_layout(); fig.savefig("figs/fig6_phase_noise.png", dpi=130); plt.close(fig)

    def plot_compare(self, ref, mine):
        plt = self._plt(); fig, ax = plt.subplots(2, 1, figsize=(7.5, 6), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
        ax[0].semilogx(ref[:, 0], ref[:, 1], "k", label="reference"); ax[0].semilogx(ref[:, 0], mine, "--", label="ISF (ngspice)")
        ax[0].set_ylabel("L(Δf) [dBc/Hz]"); ax[0].grid(alpha=.3, which="both"); ax[0].legend()
        ax[1].semilogx(ref[:, 0], mine - ref[:, 1]); ax[1].axhline(0, color="gray", lw=.6); ax[1].set_ylabel("ISF - ref [dB]"); ax[1].set_xlabel("Δf [Hz]"); ax[1].grid(alpha=.3, which="both")
        fig.suptitle("Stage 7 - comparison with the reference"); fig.tight_layout(); fig.savefig("figs/fig7_comparison.png", dpi=130); plt.close(fig)

    # ---- 7. comparison
    def compare(self):
        ref = np.array([[float(a) for a in l.split()[:2]] for l in open(self.cfg["compare_file"]) if l.strip()])
        rows = json.load(open("summary.json"))["rows"]
        def Ld(df):
            w2 = (2 * np.pi * df) ** 2
            return 10 * np.log10((sum(r["th"] for r in rows.values()) + sum(r["coh"] / df ** r["ef"] for r in rows.values())) / (2 * w2))
        mine = np.array([Ld(f) for f in ref[:, 0]]); d = mine - ref[:, 1]
        print(f"{'Δf':>10} {'ISF':>9} {'ref':>9} {'dif':>7}")
        for fk in self.cfg["df_list"]:
            k = np.argmin(abs(ref[:, 0] - fk)); print(f"{ref[k,0]:10.3g} {mine[k]:9.2f} {ref[k,1]:9.2f} {d[k]:+7.2f}")
        m = ref[:, 0] >= 1e5; print(f"mean diff (Δf>=100k): {d[m].mean():+.2f} dB  range {d[m].min():+.2f}..{d[m].max():+.2f}")
        self.plot_compare(ref, mine)


if __name__ == "__main__":
    while "--set" in sys.argv:       # python3 isfpn.py CFG CMD --set IBIAS=300u --set tstop=2e-7  (not written to the JSON)
        i = sys.argv.index("--set"); SETS.append(sys.argv[i + 1]); del sys.argv[i:i + 2]
    while "--tag" in sys.argv:       # --tag NAME: added to the name of the runs/ folder
        i = sys.argv.index("--tag"); TAG[0] = sys.argv[i + 1]; del sys.argv[i:i + 2]
    HERE = "--here" in sys.argv      # --here: write the results in the current directory (the old behaviour of 'all')
    if HERE: sys.argv.remove("--here")
    if len(sys.argv) < 3:
        sys.exit("Usage: python3 isfpn.py CONFIG.json COMMAND [--set NAME=value] [--tag NAME] [--here]\n"
                 "  COMMAND: all (whole flow) | sweep (control sweep, needs the 'sweep' key) | baseline | lin | isf | noise | blocks | combine | compare | plots\n"
                 "  'all' writes in runs/<process>_<T>C_<VDD>V[_<--set>][_tag-<--tag>]/ ('sweep': runs/sweep_<variable>_<nominal|Ncorners>/); --here = current directory\n"
                 "  example: ISFPN_JOBS=8 python3 ../../isfpn.py cs.json all")
    cmd = sys.argv[2]
    if cmd == "all" and not HERE: sys.exit(run_in_folder(sys.argv[1]))
    cs = Case(sys.argv[1])
    if cmd == "all":
        T = {}; t_all = time.time()
        stages = [("baseline", cs.baseline), ("lin", cs.lin), ("isf", cs.isf), ("noise", cs.noise), ("blocks", cs.blocks)]
        if cs.cfg["local"]: stages.append(("local", cs.local))
        stages.append(("combine", cs.combine))
        if "compare_file" in cs.cfg: stages.append(("compare", cs.compare))
        for name, fn in stages:
            t0 = time.time(); fn(); T[name] = time.time() - t0
        total = time.time() - t_all
        jobs = int(os.environ.get("ISFPN_JOBS", cs.cfg["jobs"]))
        json.dump({"jobs": jobs, "threads": cs.cfg["threads"], "omp_wait": (getattr(Case, "omp_used", "?") if jobs > 1 else "default (serial)"), "n_phase": cs.cfg["n_phase"], "n_nodes": len(cs.cfg["nodes"]),
                   "n_devices": len(cs.devs), "stages_s": T, "total_s": total}, open("timing.json", "w"), indent=1)
        print(f"\nTIMING (jobs={jobs})   " + "   ".join(f"{k} {v:.0f} s" for k, v in T.items()) + f"   TOTAL {total:.0f} s ({total/60:.1f} min)   -> timing.json")
    elif cmd == "lin": cs.lin(sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "plots": cs.plot_all()
    else:
        t0 = time.time(); getattr(cs, cmd)(); print(f"[{cmd}: {time.time() - t0:.1f} s]")
