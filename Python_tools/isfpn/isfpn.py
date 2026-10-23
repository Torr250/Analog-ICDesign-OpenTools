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
    python3 isfpn.py CONFIG.json baseline|lin NODO|isf|noise|blocks|combine|compare|plots|export_template
    The lib path can be changed without touching the config:  ISFPN_LIB=/ruta/sky130_tt.lib.spice
    All netlists are generated with the line  .lib {LIB}  and the program replaces it by '<lib> <section>' at run time
    (ngspice does not expand environment variables in .lib). 'export_template' writes templates/base.spice with {LIB} visible.

CONFIG (JSON)  keys
    core        core netlist (relative to the case). Must contain the supplies and the capacitors.
    lib         the .lib file;   section  section (e.g. "tt");   temp [°C];   vdd [V]
    params      {"VDD":1.8,"TEMP":60}  -> .param;     extra  list of SPICE lines (".ic v(n1)=0.2", ...)
    rails       {"0":0.0,"VDD":1.8}  ideal rail nodes (Γ=0 and fixed voltage)
    ref         {"vec":"v(n13)","level":0.0,"edge":"rise"}   crossing that defines the phase (x=0)
    tstop, tstep, settle   transient [s], step ("1p"), time after which steady state holds
    nper        periods between the pulse and the measurement (20);  dq_fc  pulse charge (1.0);  n_phase  (30)
    nodes       list of nodes to perturb; "auto" = all D/S of the FETs that are not rails
    skip_devices  devices NOT treated as core (they go in a block)
    blocks      [{"name":"MIRROR","node":"VCS","file":"mirror_noise.spice","out":"mirror_noise.txt","th_freq":1e8}]
                The block netlist may use {VNODE} (mean node voltage), {VDD} and {TEMP} (the config's vdd and temp) and any
                key of "params" as {NAME}, all substituted before running, and must write the onoise_spectrum
                spectrum with wrdata to 'out' (short-circuit current into a noiseless 1 Ω resistor).
    df_list     offsets for the table (Hz);   compare_file  reference table f[Hz] dBc/Hz

OUTPUTS (in the case directory)
    base_ref.json  T0, f0, crossings;  wave_base.txt;  lin.json;  isf_<NODO>.json;  noise_dev.json;  blocks.json
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
import json, os, re, subprocess, sys
import numpy as np

_trapz = getattr(np, "trapezoid", None) or np.trapz
ENV = dict(os.environ, OMP_NUM_THREADS="1")


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
        if m and "/" in m.group(2) or (m and m.group(2).endswith((".spice", ".lib"))):
            out |= lib_models(os.path.join(base, m.group(2)), _seen)
    return out


def vmax_model(model, vdd):
    """Maximum reasonable terminal voltage used to clip a model's bias (per sky130 family)."""
    m = model.lower()
    for key, v in (("g5v0d16", 17.0), ("g5v0", 5.5), ("05v0", 5.5), ("03v3", 3.6), ("20v0", 21.0)):
        if key in m: return v
    return vdd


class Case:
    """A case = directory with CONFIG.json, core netlist and blocks."""

    def __init__(self, cfgpath):
        self.cfg = c = json.load(open(cfgpath))
        c.setdefault("section", "tt"); c.setdefault("temp", 60); c.setdefault("vdd", 1.8)
        c.setdefault("params", {}); c.setdefault("extra", []); c.setdefault("rails", {"0": 0.0, "VDD": c["vdd"]})
        c.setdefault("tstop", 70e-9); c.setdefault("tstep", "1p"); c.setdefault("settle", 25e-9)
        c.setdefault("nper", 20); c.setdefault("dq_fc", 1.0); c.setdefault("n_phase", 30)
        c.setdefault("nodes", "auto"); c.setdefault("skip_devices", []); c.setdefault("blocks", [])
        c.setdefault("df_list", [1e4, 1e5, 3e5, 1e6, 3e6, 1e7, 3e7, 1e8]); c.setdefault("reltol", 1e-5)
        c["lib"] = os.environ.get("ISFPN_LIB", c["lib"])
        self.rails = {k.upper(): v for k, v in c["rails"].items()}
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
    def parse_devices(self):
        """Core FETs: X... instances whose model is declared in the lib (or, if the lib cannot be read, whose
        name contains 'fet'). Returns {name: {d,g,s,b,model,kind,params}}. Warns about unsupported X instances
        (resistors, capacitors, diodes, BJTs...: their noise is NOT included)."""
        known = {m for m in lib_models(self.cfg["lib"]) if "fet" in m}
        self.known_models = known
        text = re.sub(r"\n\+", " ", open(self.cfg["core"]).read())
        devs, skip = {}, [x.upper() for x in self.cfg["skip_devices"]]
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
            if nm in skip: continue
            i = tk.index(model)
            devs[nm] = {"d": tk[1], "g": tk[2], "s": tk[3], "b": tk[4], "model": model,
                        "kind": "p" if "pfet" in ml else "n", "params": " ".join(tk[i + 1:])}
        if not known: print("WARNING: could not read the lib; the model name ('fet') was used to detect FETs")
        return devs

    # ---- common netlist
    def netlist(self, pert=None, wr="v(n1)", wfile="w.txt", extra_control=""):
        c = self.cfg
        L = [f".include {c['core']}"]
        if pert: L.append(f"Ipert {pert[0]} PULSE(0 {pert[1]} {pert[2]} 1p 1p 1p 1)")
        L += c["extra"]
        L += [f".param {k}={v}" for k, v in c["params"].items()]
        L += [f".temp {c['temp']}", f".options reltol={c['reltol']}",
              ".lib {LIB}", ".GLOBAL VDD", ".control", f" tran {c['tstep']} {c['tstop']} uic",
              " option remzerovec", f" wrdata {wfile} {wr}", ".endc", ".end"]
        return "\n".join(L)

    def render(self, text):
        """Replaces {LIB} by '<lib> <section>' (lib from the config or from ISFPN_LIB). ngspice does not expand environment variables
        in .lib, so the substitution is done here."""
        return text.replace("{LIB}", f"{self.cfg['lib']} {self.cfg['section']}")

    def export_template(self, name="base"):
        """Writes templates/<name>.spice with .lib {LIB} (template without a fixed path) to inspect or edit by hand."""
        os.makedirs("templates", exist_ok=True)
        open(f"templates/{name}.spice", "w").write(self.netlist(None, self.cfg["ref"]["vec"], "w_base.txt"))
        print(f"template written to templates/{name}.spice (line: .lib {{LIB}})")

    def run(self, tag, pert=None, wr=None):
        wr = wr or self.cfg["ref"]["vec"]
        fn, wf = f"r_{tag}.spice", f"w_{tag}.txt"
        open(fn, "w").write(self.render(self.netlist(pert, wr, wf))); r = sh(["ngspice", "-b", fn])
        if not os.path.exists(wf):
            raise RuntimeError(f"ngspice did not produce {wf}; {fn} is kept. Output:\n" + (r.stdout + r.stderr)[-800:])
        d = np.loadtxt(wf); os.remove(wf); os.remove(fn)
        return d

    # ---- 1. baseline
    def baseline(self):
        c = self.cfg
        nodes = c["nodes"] + [n.upper() for d in self.devs.values() for n in (d["g"], d["b"]) if n.upper() not in self.rails]
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
        d = self.run(tag, (pn, iamp, t0)); t, v = d[:, 0], d[:, 1]
        cc = crossings(t, v, c["ref"]["level"], c["ref"]["edge"])
        tgt = cr[0] + c["nper"] * T0
        dt = cc[np.argmin(abs(cc - tgt))] - cr[np.argmin(abs(cr - tgt))]
        return float(2 * np.pi * dt / T0 / dq_fc)                         # Γ_raw rad/fC

    def lin(self, node=None, x=0.25):
        """ΔQ linearity test: Γ_raw vs ΔQ at the given node and phase; saves lin.json and figs/fig2_linearity.png."""
        node = (node or self.cfg["nodes"][0]).upper(); T0 = self.base()["T0"]
        dqs = [0.2, 0.5, 1, 2, 5, 10, 20, 50, 100]; g = []
        for q in dqs:
            g.append(self.point(node, q, x, "lin"))
            print(f"dQ={q:6.1f} fC  Γ_raw={g[-1]*1e3:9.4f} mrad/fC", flush=True)
        dt = [gi * T0 * q / (2 * np.pi) for gi, q in zip(g, dqs)]
        json.dump({"node": node, "x": x, "dq_fC": dqs, "gamma_raw": g, "dt_s": dt, "dq_used": self.cfg["dq_fc"]}, open("lin.json", "w"))
        self.plot_lin()

    def isf(self):
        c = self.cfg; N = c["n_phase"]; B = self.base()
        for nd in c["nodes"]:
            g = [self.point(nd, c["dq_fc"], i / N, f"s_{nd}") for i in range(N + 1)]
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

    def noise(self):
        c = self.cfg; N = c["n_phase"]; VDD = c["vdd"]; V = self.phase_voltages(); res = {}
        for nm, d in self.devs.items():
            vm = vmax_model(d['model'], VDD)
            def vol(n): return np.clip(V[n.upper()], 0, max(vm, max(self.rails.values())))
            vg, vd, vs, vb = vol(d["g"]), vol(d["d"]), vol(d["s"]), vol(d["b"])
            L = ["* isolated noise", "Vg g 0 0 ac 1", "Vd dd 0 0", "Vs s 0 0", "Vb b 0 0", "Rs dd d 1 noisy=0",
                 f"XM d g s b {d['model']} {d['params']}", f".temp {c['temp']}", ".lib {LIB}",
                 ".control", f"option reltol={c['reltol']}"]
            for k in range(N):
                L += [f"alter Vg dc = {vg[k]:.6f}", f"alter Vd dc = {vd[k]:.6f}", f"alter Vs dc = {vs[k]:.6f}",
                      f"alter Vb dc = {vb[k]:.6f}", "noise v(d) Vg dec 1 1 1e10", f"setplot noise{2*k+1}",
                      f"wrdata nzc_{k}.txt onoise_spectrum"]
            L += [".endc", ".end"]
            open("nzc.spice", "w").write(self.render("\n".join(L))); sh(["ngspice", "-b", "nzc.spice"])
            S = []
            for k in range(N):
                a = np.loadtxt(f"nzc_{k}.txt"); f = a[:, 0]; S.append(a[:, 1] ** 2); os.remove(f"nzc_{k}.txt")
            res[nm] = {"kind": d["kind"], "d": d["d"], "s": d["s"], "f": f.tolist(), "S": np.array(S).tolist()}
            print(f"noise {nm} ({d['kind']}) done", flush=True)
        json.dump(res, open("noise_dev.json", "w"))
        self.plot_noise()

    # ---- 5. blocks
    def blocks(self):
        B = self.base(); W = np.loadtxt("wave_base.txt"); out = {}
        for b in self.cfg["blocks"]:
            nd = b["node"].upper(); j = B["nodes"].index(nd)
            vavg = float(np.mean(W[W[:, 0] > self.cfg["settle"] + 15e-9, 2 + j]))
            txt = open(b["file"]).read()
            subs = {"VNODE": f"{vavg:.6f}", "VDD": self.cfg["vdd"], "TEMP": self.cfg["temp"]}
            subs.update({k: v for k, v in self.cfg["params"].items() if k not in subs})
            for k, v in subs.items(): txt = txt.replace("{" + k + "}", str(v))
            open("blk_run.spice", "w").write(self.render(txt)); r = sh(["ngspice", "-b", "blk_run.spice"])
            m = np.loadtxt(b["out"]); f, S = m[:, 0], m[:, 1] ** 2
            th = float(S[np.argmin(abs(f - b.get("th_freq", 1e8)))]); K = float(S[0] - th)
            out[b["name"]] = {"node": nd, "Sth": th, "K1Hz": K, "ef": float(np.log10(max(S[0] - th, 1e-40) / max(S[1] - th, 1e-40)) / np.log10(f[1] / f[0])),
                              "vnode": vavg, "f": f.tolist(), "S": S.tolist()}
            print(f"block {b['name']}: V({nd})={vavg:.4f} V  Sth^0.5={np.sqrt(th)*1e12:.2f} pA/rtHz  K(1Hz)^0.5={np.sqrt(K)*1e12:.0f} pA/rtHz")
        json.dump(out, open("blocks.json", "w"))
        if out: self.plot_blocks()

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
        chk = self.checks(dmin)
        lines += ["", "CHECKS (no external reference)"] + chk
        open("report.txt", "w").write("\n".join(lines)); print("\n".join(lines))
        json.dump({"f0": 1 / T0, "dmin_valid_Hz": dmin, "L": Ltab, "rows": rows, "checks": chk}, open("summary.json", "w"), indent=1)
        self.write_csvs(rows, dmin)
        self.plot_combine()


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
        return out

    # ---- plots (one per stage; figs/)
    def _plt(self):
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        os.makedirs("figs", exist_ok=True); return plt

    def plot_all(self):
        for fn in (self.plot_baseline, self.plot_lin, self.plot_isf, self.plot_noise, self.plot_blocks, self.plot_combine):
            try: fn()
            except FileNotFoundError as e: print("skipped:", fn.__name__, e)
        if "compare_file" in self.cfg and os.path.exists("summary.json"): self.compare()

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
    cs = Case(sys.argv[1]); cmd = sys.argv[2]
    if cmd == "all":
        cs.baseline(); cs.lin(); cs.isf(); cs.noise(); cs.blocks(); cs.combine()
        if "compare_file" in cs.cfg: cs.compare()
    elif cmd == "lin": cs.lin(sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "plots": cs.plot_all()
    else: getattr(cs, cmd)()
