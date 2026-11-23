# isfpn - oscillator phase noise in ngspice (no PSS + PNOISE): the ISF method

`isfpn.py` computes the phase noise L(Δf) of **any oscillator described by a transistor netlist in sky130A or gf180mcuD** (other ngspice PDKs only need a PDK profile, section 3) by combining
the **impulse sensitivity function (ISF)** of each node with the noise power spectral density of each transistor
(and of special blocks, e.g. a current mirror). It generalizes the `ISF_pulse_test` proof-of-concept flow
(3-inverter ring): instead of editing constants and templates in 24 scripts, a single program is driven by a JSON
configuration file and delivers **L(Δf) in a CSV** ready to use in the PLL model,
**one plot per stage** and **automatic checks** that do not require an external reference.

**Reference results (sky130A tt, 60 °C)** - see section 8:

| Case | f0 (ISF) | f0 Spectre | L(1 MHz) ISF | L(1 MHz) Spectre | mean diff. vs Spectre | Minimum valid Δf |
|---|---|---|---|---|---|---|
| 3-stage ring, schematic (nrd/nrs ≠ 0) | 829.0 MHz | - | -90.92 dBc/Hz | - | (no reference) | 80 kHz |
| 3-stage ring, `nrd=nrs=0` | 945.5 MHz | 946 MHz | -89.63 dBc/Hz | −89.58 | −0.10 dB (−0.27 .. −0.03) | 93 kHz |
| 4-stage current-starved with mirror, `nrd=nrs=0` | 784.6 MHz | 784.8 MHz | -92.50 dBc/Hz | −92.49 | −0.03 dB (−0.11 .. +0.01) | 61 kHz |
| gf180mcuD, 3-stage ring (3.3 V) | 628.6 MHz | - | -98.50 dBc/Hz | - | (no reference) | 37 kHz |
| gf180mcuD, 4-stage current-starved with mirror (3.3 V) | 597.3 MHz | - | -102.73 dBc/Hz | - | (no reference) | 13 kHz |

> **Important finding about `nrd/nrs`.** In the ngspice sky130 model, **omitting** `nrd/nrs` on the instance is **not** the same
> as setting them to `0`: the subcircuit uses a non-zero default. Spectre (with the Cadence netlist, which does not
> write them) takes them as 0. That is why the ring gives 829 MHz with the schematic's `nrd=nrs=0.29/0.097` and **945.5 MHz with an explicit
> `nrd=nrs=0`** (Spectre: 946 MHz), and the CS gives 762.7 MHz if they are omitted and **784.6 MHz with an explicit `nrd=0 nrs=0`** (Spectre: 784.8 MHz).
> To compare against Spectre you must write `nrd=0 nrs=0` on every instance (the `*_nrd0` cases).

## Contents
1. [Theory](#1-theory)
2. [Algorithm](#2-algorithm)
3. [Requirements, installation and structure](#3-requirements-installation-and-structure)
4. [What the program needs: netlist, config and blocks](#4-what-the-program-needs)
5. [Stages: what each one does, how to run it, inputs, outputs and figures](#5-stages) - including 5.0 [speeding up a run](#50-speeding-up-a-run-what-to-change-in-the-config) and including 5.1 [running with parallel processes](#51-running-with-parallel-processes), 5.2 [benchmark script](#52-benchmark-script-toolsbench_jobspy), 5.3 [cheat sheet](#53-cheat-sheet-what-to-run-and-which-jobsthreads-to-use) 5.4 [sweep of a control value](#54-sweep-of-a-control-value-bias-current-vco-tuning) and 5.4a [target frequency](#54a-target-frequency-control-value-for-a-given-f0), 5.4b [where the results go: `runs/`](#54b-where-the-results-go-runs-names---tag---here) and 5.5 [output buffer: local ISF](#55-output-buffer-local-isf-additive-noise-floor)
6. [Outputs: the CSV for the PLL model](#6-outputs-and-use-in-the-pll-model)
7. [Without a Spectre reference: how to configure and what to verify](#7-without-a-spectre-reference)
8. [Included cases and results](#8-included-cases-and-results)
9. [Limitations and common problems](#9-limitations-and-common-problems)
10. [How to adapt it to another oscillator](#10-how-to-adapt-it-to-another-oscillator)
11. [References](#11-references)

---

## 1. Theory

### 1.1 Definitions
A noisy oscillator is written $v(t)=A\,f\big(\omega_0 t+\phi(t)\big)$, with $\phi(t)$ the phase fluctuation. The phase noise
at an offset $\Delta f$ from the carrier is

$$\mathcal{L}(\Delta f)=\tfrac12\,S_\phi(\Delta f)\qquad[\text{1/Hz};\ 10\log_{10}\ \text{in dBc/Hz}]$$

with $S_\phi$ the single-sided PSD of $\phi$ in rad²/Hz (valid while $\sigma_\phi\ll1$ rad). The phase of the oscillation is **a single one**
for the whole circuit: $\mathcal L$ is the same at any output node (e.g. N13 and its quadrature N24).

| Symbol | Meaning |
|---|---|
| $T_0,\ f_0$ | oscillation period and frequency (noiseless) |
| $x=t/T_0 \bmod 1$ | normalized cycle phase; $x=0$ is the reference crossing (`ref` in the config) |
| $\Gamma_k(x)$ | "raw" ISF of node $k$: $\Delta\phi/\Delta Q$ [rad/C; reported in rad/fC] when charge is injected into $k$ at phase $x$ |
| $\Gamma_{dev}(x)$ | ISF of a device: $\Gamma_D(x)-\Gamma_S(x)$ (ideal rails are 0) |
| $S_{th}(x),\ K(x),\ EF$ | thermal PSD [A²/Hz] and flicker coefficient/exponent $S_{fl}=K(x)/f^{EF}$ of a device |

### 1.2 Linear time-varying (LTV) model and the ISF
A noise current $i(t)$ injected into a node produces a phase shift that depends on **where in the cycle** it arrives
(Hajimiri and Lee, 1998): $\phi(t)=\int_{-\infty}^{t}\Gamma_{k}\!\big(\tau/T_0\big)\,i(\tau)\,d\tau$. Each node $k$ of the circuit has its own
ISF, which is measured directly (1.3). If $\Gamma_k=\frac{c_0}{2}+\sum c_n\cos(2\pi nx+\theta_n)$, the noise near $nf_0$ is translated
to $\Delta f$ with weight $c_n/2$ and the noise near DC with weight $c_0/2$ ($\Gamma_{dc}$).

### 1.3 ISF extraction with charge pulses (stage 2)
At phase $x_0$ a very short charge pulse $\Delta Q$ is injected into node $k$ and the reference crossing, `nper` cycles later, is compared
with that of the unperturbed simulation. Once the amplitude transient has died out, only the permanent phase shift remains:

$$\Gamma_k(x_0)=\frac{\Delta\phi}{\Delta Q}=\frac{2\pi\,\Delta t}{T_0\,\Delta Q},\qquad \Delta t=t^{pert}_{crossing}-t^{base}_{crossing}.$$

Requirements: $\Delta Q$ in the linear region (stage 1) and above the numerical floor. **Sign:** in SPICE a positive `Ipert N 0` *extracts*
charge and $\Delta t>0$ is a delay; the two inversions cancel and $\Gamma$ is positive when injecting positive charge advances the phase.
The crossing is computed in Python (linear interpolation) and the pulse is placed away from the threshold when calibrating, because a pulse right at the crossing
can create a spurious crossing. The closure test requires $\Gamma_k(0)=\Gamma_k(1)$.

### 1.4 ISF of a device: $\Gamma_D-\Gamma_S$
The channel noise current of a transistor flows between drain and source: it is equivalent to extracting charge from $D$ and injecting it into $S$.
By superposition (circuit linear around the trajectory) its ISF is $\Gamma_{dev}=\Gamma_D-\Gamma_S$, and an ideal rail has $\Gamma=0$.
This was verified with a direct injection between N1 and VCS of the CS: measured 0.775 / −10.143 / 0.538 mrad/fC against 0.778 / −10.139 / 0.503 predicted
at three phases. In a ring with sources at GND/VDD, $\Gamma_N$ is enough; in an oscillator with an internal supply node (VCS) the PMOS devices
also need $\Gamma_{VCS}$, which is why the program measures the ISF of **all** D/S nodes that are not rails.

### 1.5 Cyclostationary white (thermal) noise
The PSD of a transistor depends on its instantaneous bias: $S_{th}(x)$ is cyclostationary. For white noise, the noise of all
bands $nf_0\pm\Delta f$ folds onto $\Delta f$ and, summing the independent devices,

$$S_{eff}=\sum_{dev}\big\langle\Gamma_{dev}^2(x)\,S_{th,dev}(x)\big\rangle_x,\qquad
\boxed{\ \mathcal{L}_{th}(\Delta f)=\frac{S_{eff}}{2\,(2\pi\Delta f)^2}\ }\quad(-20\ \text{dB/dec}).$$

### 1.6 Flicker (1/f) noise: coherent conversion
Flicker is slow compared with the cycle: within one cycle it is a constant $u(t)$ that multiplies an amplitude that follows the bias,
$i(t)=a(x)u(t)$ with $a=\sqrt{K(x)}$. What is converted to phase is the **coherent** average $\langle\Gamma_{dev}\,a\rangle_x$ (not $\langle\Gamma^2S\rangle$):

$$\boxed{\ \mathcal{L}_{fl}(\Delta f)=\frac{1}{2\,(2\pi\Delta f)^2}\sum_{dev}\frac{\langle\Gamma_{dev}\,a_{dev}\rangle^2}{\Delta f^{\,EF_{dev}}}\ }\qquad(\approx -30\ \text{dB/dec}).$$

Each device is an independent source: powers are added across devices, but within a device the conversion is coherent.
Even though $\Gamma_{dc}\approx0$, $\langle\Gamma\,a\rangle$ does not vanish: the NMOS only has flicker while it conducts (where $\Gamma<0$) and the PMOS
while it conducts on the opposite edge. In sky130 the measured exponents are $EF_n=0.84$ and $EF_p=1.00$ (the program fits them from 1 to 10 Hz).

### 1.7 Special blocks and slow nodes (current mirror, bias)
In a current-controlled oscillator (such as the current-starved one) the current source injects its noise into a slow node (VCS) whose ISF is
almost flat: $\Gamma_{VCS}\approx\Gamma_{dc}$ and it equals the VCO sensitivity: $K_{vco}=\Gamma_{dc}/2\pi$ [Hz/A]
(CS: 5.07 mrad/fC = 807 kHz/µA, matching the sensitivity measured by DC, +803 kHz/µA). The block noise enters as
$\mathcal L=\Gamma_{dc}^2S_I/(2(2\pi\Delta f)^2)$ + coherent flicker.

The block noise source is obtained with a **separate test bench** (the block's `file`): the block's devices, copied as they are,
with their output node connected to a fixed voltage $V_{node}$ (its actual mean value, `{VNODE}`) through a noiseless 1 Ω. Since $V_{fix}$ is an ideal source the
node does not move in AC: all the noise comes out as a **short-circuit current** (Norton equivalent), which is the source injected into the node; the output
conductance of the block is already part of the simulated circuit.

### 1.8 Total, corner and validity range
$\mathcal L=\mathcal L_{th}+\mathcal L_{fl}$ (independent sources, sum in linear units). The **corner** is the offset where both are equal. The small-phase model is only
valid where $\sigma_\phi^2(\Delta f)=\int_{\Delta f}^{\infty}S_\phi(f)\,df<0.09\ \text{rad}^2$ ($\sigma_\phi<0.3$ rad). The program reports that
$\Delta f_{min}$ and sets `valid=0` in the CSV below it. In a PLL the loop suppresses the VCO noise at offsets below its bandwidth, so that region is not used.

### 1.9 How the transistor PSD is obtained
ngspice's `.noise` gives the drain-current PSD of a transistor at its DC point. For each core device and each of the
`n_phase` phases, an **isolated** transistor (same model and instance parameters) is biased with the four instantaneous voltages
$V_D,V_G,V_S,V_B$ taken from the baseline (**quasi-static** approximation), with a **noiseless** 1 Ω resistor at the drain that converts the noise current into a voltage.
The thermal floor is the PSD at 1e10 Hz (flat in BSIM4, with a flicker residue below ~10 %); flicker is $K=S(1\,\text{Hz})-S_{th}$ (only if $S(1\,\text{Hz})>5S_{th}$) with
the exponent fitted between 1 and 10 Hz. The PSD at 1e10 Hz is used as is in all cases to keep the rule that was validated against Spectre.

### 1.10 Assumptions and what is NOT included
1. Small perturbation, linear phase response (checked in stage 1). 2. Quasi-static noise. 3. White noise incoherent between bands, flicker coherent within a cycle.
4. Independent sources. 5. Only BSIM4 channel noise of the **FETs** and of the blocks you declare: resistors, capacitors, diodes or BJTs (`X...` with another model) are warned about and **not** included.
6. Ideal rails (no supply noise). 7. $\Delta f\ll f_0$ and $\sigma_\phi\ll1$ rad. 8. It does not compute amplitude noise, only phase noise.

---

## 2. Algorithm

```
 STAGE 0  baseline      unperturbed transient -> T0, f0, reference crossings, waveforms of all nodes                    fig1_baseline.png
 STAGE 1  lin           Γ_raw vs ΔQ at one node/phase -> confirms that ΔQ (dq_fc) is in the linear region               fig2_linearity.png
 STAGE 2  isf           a sweep of n_phase+1 pulses for each node -> Γ_k(x), cycle closure                              fig3_isf.png  isf.csv
 STAGE 4  noise         per device and phase: .noise with instantaneous (VD,VG,VS,VB) -> S(f) 1 Hz..1e10 Hz             fig4_device_noise.png
 STAGE 5  blocks        special blocks: short-circuit noise current into a node                                         fig5_blocks.png
 STAGE 6  combine       Γ_dev = Γ_D-Γ_S; L_th, L_fl, total; valid Δf; checks; CSV                                       fig6_phase_noise.png  phase_noise.csv
 STAGE 7  compare       (optional) difference against a reference table (Spectre or other)                              fig7_comparison.png
```
(The numbering follows that of the `ISF_pulse_test` package; stage 3, $q_{max}$, is not needed for $\mathcal L$ and is not included.)

1. **Baseline.** Simulated with a fine step; the crossing of `ref` (vector, level and edge) defines $x=0$; $T_0$ is the mean period of the crossings after `settle`.
2. **Linearity.** $\Delta Q$ is swept from 0.2 to 100 fC at one node at $x=0.25$ and it is verified that $\Gamma$ does not change by more than 2 % between 0.2 fC and `dq_fc`.
3. **ISF.** For each node, 30 phases (+1 for closure): pulse at $t_0=c_0+xT_0$, crossing measured `nper` cycles later.
4. **Noise.** For each core FET, 30 `.noise` runs (a single ngspice process per device).
5. **Blocks.** One `.noise` per block with the node fixed at its mean voltage.
6. **Combination.** $\mathcal L_{th}$, $\mathcal L_{fl}$ are assembled, and $\Delta f_{min}$, the checks and the CSVs are computed.
7. **Comparison** if there is a `compare_file`.

---

## 3. Requirements, installation and structure
- **ngspice** (tested with ngspice-42) in the `PATH`; **Python 3** with `numpy` and `matplotlib`.
- sky130A or gf180mcuD PDK in ngspice format. The reduced version generated with `tools/make_min_pdk.py --split-sections` is recommended, using the per-section lib
  (`.../libs.tech/combined/sections/sky130_tt.lib.spice`, section `tt`): one ngspice run drops from ~3.6 s to ~0.3 s.
- **PDKs that need several lines (gf180mcuD).** Instead of `lib`/`section`, the config has a `pdk` key:
  ```json
  "pdk": {"root": "/path/Analog-ICDesign-OpenTools/ngspice/gf180mcuD",
          "preamble": [".include {PDK}/design.ngspice", ".lib {PDK}/sm141064.ngspice typical"],
          "models": "{PDK}/sm141064.ngspice"}
  ```
  `root` can be overridden without touching the config with `ISFPN_PDK=/path/gf180mcuD`; `preamble` are the lines that load the PDK (`{PDK}` = root) and `models` is the file scanned to recognize the FET names. The tool replaces the line `.lib {LIB}` of every netlist (core runs, per-device noise benches and block benches) by that preamble, so the same block file works with either PDK. With sky130 nothing changes: `lib`/`section` keep working. The gf180mcuD 3.3 V devices (`nfet_03v3`, `pfet_03v3`, subcircuits with `m`, `nf`, `ad`, `as`, ... parameters) are recognized automatically; the bias clipping knows the 3.3 V, 5 V and 6 V families. Loading this PDK takes <1 s in ngspice, so no reduced PDK is needed.
- **The lib path** is not written in the netlists: it is defined in the config (`lib`) or with the environment variable `ISFPN_LIB`, and the program
  replaces the `.lib {LIB}` marker right before running (ngspice does not expand environment variables in `.lib`). `python3 isfpn.py CFG export_template`
  writes `templates/base.spice` with the marker visible.

```
isfpn/
├── isfpn.py                 program (docstring with all the config keys)
├── README.md                this document
├── tools/make_min_pdk.py    generates sky130A_min (and per-section libs)
├── docs/PARALLEL_NGSPICE.md findings and recipe for running ngspice in parallel (jobs, threads, diagnosis)
└── cases/
    ├── ring3_gf180mcuD/        3-inverter ring in gf180mcuD (3.3 V), NO external reference   (ring.json)
    ├── cs_n4_gf180mcuD/        4-stage current-starved with mirror in gf180mcuD, NO reference (cs.json, mirror_noise.spice)
    ├── ring3_sky130A/          3-inverter ring, schematic parameters, NO external reference  (ring.json)
    ├── ring3_sky130A_nrd0/     the same with explicit nrd=nrs=0, WITH the Spectre table        (ring.json, spectre_pn.txt)
    └── cs_n4__sky130A_nrd0/    4-stage pseudo-differential current-starved with mirror, WITH Spectre  (cs.json, mirror_noise.spice, spectre_pn.txt)
```
Each case is a self-contained directory: **run it from inside it** (`cd cases/<case>; python3 ../../isfpn.py CFG all`), because `core.cir`, the blocks
and the results are read/written in the current directory. It also includes the reference results (`figs/`, `*.csv`, `report.txt`, `summary.json`).

---

## 4. What the program needs

### 4.1 `core.cir`: the core netlist
It is **your complete circuit netlist, without the `.lib` line, without `.control`/`.endc`, without `.end` and without `.ic`/`.param`/`.temp`** (those go in the config).
It must contain *everything that determines the operating point and the dynamics*: transistors, load capacitors, power supplies (`V9 net1 0 'VDD'`, `V7 VDD net1 0`),
bias sources and, in the CS, **also the mirror and the current source** (XM17, XM18, I0, V1) and the output `E` sources. Rules:
- sky130 transistors as 4-terminal `X...` instances: `XM1 D G S B model W=.. L=.. ...`; lines starting with `+` are joined. The model must be declared in the lib
  (the `.subckt`/`.model` of the lib and its `.include` files are read; with the reduced PDK: `sky130_fd_pr__{nfet,pfet}_{01v8,01v8_lvt,g5v0d10v5}`).
- Transistors that must NOT be treated as core noise sources (the mirror, which is treated as a block) are listed in `skip_devices`.
- Node names are case-sensitive **only for you**: the program converts them to uppercase internally.
- **Write explicit `nrd=0 nrs=0`** if the other tool's schematic does not use them (see the finding at the top).
- It must oscillate on its own: it needs an initial condition (`extra`: `.ic v(n1)=0.2`) that breaks the symmetry; the transient uses `uic`.

### 4.2 JSON config (all keys)
| Key | Default | Meaning |
|---|---|---|
| `core` | - | core netlist (relative to the case) |
| `lib`, `section` | -, `"tt"` | `.lib` file and section (sky130). `lib` is overridden by `ISFPN_LIB` |
| `pdk` | (absent) | alternative to `lib`/`section` for PDKs with several lines (gf180mcuD): `{"root","preamble","models"}`, root overridden by `ISFPN_PDK` (section 3) |
| `temp`, `vdd` | 60, 1.8 | temperature [°C] and supply [V]. `vdd` is the only place where the supply is set: it defines `.param VDD`, the VDD rail, the bias clipping limit and `{VDD}` in the block benches |
| `params`, `extra` | `{}`, `[]` | extra `.param` (e.g. `{"TEMP":60}`; `VDD` is added automatically from `vdd`) and extra SPICE lines (`.ic ...`, `.options ...`) |
| `rails` | `{"0":0,"VDD":vdd}` | ideal rail nodes: Γ = 0 and fixed voltage. Only needed if there are rails other than 0 and VDD |
| `ref` | - | `{"vec":"v(n13)","level":0.0,"edge":"rise"}`: vector, threshold and edge that define $x=0$. Ring: `v(n1)`, 0.9; CS: `v(n13)`, 0 |
| `tstop`, `tstep`, `settle` | 70n, `"1p"`, 25n | transient [s], step and time after which steady state holds. `settle + (nper+13)·T0` must fit in `tstop` |
| `nper` | 20 | cycles between the pulse and the crossing measurement |
| `dq_fc` | 1.0 | pulse charge [fC] (according to stage 1) |
| `n_phase` | 30 | points per period (+1 for closure) |
| `nodes` | `"auto"` | nodes to perturb. `"auto"` = all D/S of the core FETs that are not rails (+ the node of each block) |
| `skip_devices` | `[]` | FETs not treated as core: exact names or regular expressions (full match, case-insensitive), e.g. `["XM17","XM18","XM(19|[23][0-9]|4[0-2])"]` for the mirror plus XM19..XM42 |
| `local` | (absent) | output-buffer analysis (local ISF), see 5.5: `{"nodes":[...],"devices":"auto","n_phase":40,"window":0.3,"cross":3,"nlate":3}` |
| `blocks` | `[]` | blocks: `{"name","node","file","out","th_freq"}` (see 4.3) |
| `compare_file` | (absent) | reference table `f[Hz] L[dBc/Hz]`; if missing, nothing is compared (section 7) |
| `sweep` | (absent) | sweep of a control value (bias current, ...) run with `isfpn.py CFG sweep`: see section 5.4 |
| `df_list` | 10k..100M | offsets printed in `report.txt` |
| `csv_grid` | `{"fmin":1e3,"fmax":1e9,"ppd":20}` | grid of the final CSV |
| `jobs` | 1 | parallel ngspice processes (also `ISFPN_JOBS=N`) in the stages `lin` (one per ΔQ), `isf` (one per phase), `noise` (one per transistor) and `blocks` (one per block); `baseline` and `combine` are single steps. The results do not depend on `jobs`. Default serial. With `jobs` > 1 the tool launches ngspice with `OMP_WAIT_POLICY=passive` (OpenMP threads sleep instead of busy-waiting, which otherwise makes simultaneous ngspice runs fight for the cores and stall); in serial it is not set because the default policy is faster. Each phase is an independent run, so on a multi-core PC `jobs` = 2-4 divides the time; if ngspice stalls in parallel, `run_timeout` stops it and you can go back to 1 (in the sandbox where this was developed, parallel runs hung until `OMP_WAIT_POLICY=passive` was set) |
| `threads` | 1 | OpenMP threads per ngspice process. The tool injects `set num_threads=N` in every `.control` (also in block benches), because a `num_threads` set in `~/.spiceinit`/`spinit` (as in some containers, e.g. IIC-OSIC-TOOLS) overrides `OMP_NUM_THREADS` and makes each ngspice use many cores, which slows small circuits down and prevents `jobs` from scaling. `0` leaves ngspice's own setting. Check with `docker stats` or `top`: serial should use ~100 % CPU |
| `run_timeout` | 300 | maximum seconds per ngspice run; on timeout the netlist `r_<tag>.spice` is kept so you can run `ngspice -b` on it by hand. `ISFPN_VERBOSE=1` prints every ISF point with its time |
| `reltol` | 1e-5 | ngspice tolerance (needed to see voltage jumps of tens of mV) |

### 4.3 Netlist of a special block (`blocks`)
An independent test bench (example: `mirror_noise.spice` of the CS) that contains **exact copies of the block's devices**, with the same bias, and where
the output (`net2`, which in the real circuit goes to node VCS) is connected like this:
```spice
Rs net2 vx 1 noisy=0          * current sensor: 1 Ω with no noise of its own
Vfix vx 0 {VNODE} ac 1        * fixes the node at its actual mean voltage; AC input of .noise
.temp {TEMP}                  * from the config (`temp`)
.lib {LIB}                    * the program replaces it with the PDK preamble (<lib> <section>, or the `pdk` lines)
.control
 noise v(net2,vx) Vfix dec 2 1 1e10
 setplot noise1
 wrdata mirror_noise.txt onoise_spectrum    * = name of "out" in the config
.endc
```
Placeholders substituted before running: `{VNODE}` (mean node voltage), `{VDD}` and `{TEMP}` (config `vdd` and `temp`), `{LIB}` (lib + section), and any key of `params` as `{NAME}`. Do not hard-code supply or temperature in the bench.
`onoise_spectrum` comes out in A/√Hz because V = I·1 Ω. If the current reference is not ideal, include its transistors in the bench. `th_freq` is the frequency at which the thermal level is read
(flat); flicker is the difference at 1 Hz. The `node` in the config determines which ISF is applied.

### 4.4 Optional reference
Two-column text, one pair per line (`10.00E3 -36.50`): offset [Hz] and L [dBc/Hz]. See section 7.

---

## 5. Stages
All times are from a 2-core container with the per-section lib. **ngspice must not be launched in parallel**: in the sandbox two processes hung.

```bash
cd cases/<case>
ISFPN_LIB=/path/to/sky130A_min/libs.tech/combined/sections/sky130_tt.lib.spice python3 ../../isfpn.py CFG.json all
python3 ../../isfpn.py CFG.json baseline | lin [NODE] | isf | noise | blocks | combine | compare | plots | export_template
```
`plots` regenerates all the figures from the saved files, without simulating.

**Measuring the run time.** `all` prints a timing line at the end and writes `timing.json` (time per stage, total, `jobs`, `threads`); a single stage prints `[stage: N s]`. To document the speed-up with `jobs`:
```bash
for J in 1 2 4 8; do ISFPN_JOBS=$J python3 ../../isfpn.py CFG.json all > run_j$J.log 2>&1; cp timing.json timing_j$J.json; done
python3 -c "import json,glob; [print(f['jobs'], round(f['total_s']), f['stages_s']) for f in sorted((json.load(open(x)) for x in glob.glob('timing_j*.json')), key=lambda d: d['jobs'])]"
```
The results are identical for every `jobs`; only the time changes.

### 5.0 Speeding up a run (what to change in the config)
Almost all the time is spent in the ngspice transients of `lin` and `isf`, and it is set by the transient settings in the JSON, not by the netlist. Measured on the gf180mcuD ring (T0 = 1.6 ns) and on the current-starved oscillator with mirror (T0 = 1.7 ns); "Γ error" is the largest difference in Γ against the default settings (`tstep 1p`, `reltol 1e-5`, `nper 20`), relative to Γ rms, at 4 phases of N1 (and VCS in the CS):

| Change | Speed-up per run (ring / CS) | Γ error (ring / CS) |
|---|---|---|
| `tstep` 1p → 2p | 1.7× / 1.9× | 0.22 % / 0.02 % |
| `tstep` 1p → 5p | 4.3× / 4.8× | 0.16 % / 0.23 % |
| `reltol` 1e-5 → 1e-4 | 1.1× / - | 0.2 % / - |
| `nper` 20 → 10 | 1.4× / 1.3× | 0.00 % / 0.00 % |
| `tstep 2p` + `reltol 1e-4` + `nper 10` + shorter `settle`/`tstop` | 3.6× / 3.5× | 0.22 % / 0.02 % |

- **`tstep` is the main lever**: in `tran tstep tstop` it is also the maximum internal step, so `1p` forces ~1600 points per period. Keep at least ~300 points per period (`T0/tstep`).
- **`nper`**: 10 periods were enough for these oscillators because the amplitude transient dies out quickly; check that the closure and linearity checks still pass. It also lets you shorten `tstop` and `settle` (the run only has to cover `settle + (nper+13)·T0`).
- **End-to-end check on the CS** with `tstep 2p`, `reltol 1e-4`, `nper 10`, `settle 15n`, `tstop 60n`: L(Δf) identical to the default settings (0.000 dB at 100 kHz, 1 MHz, 10 MHz and 100 MHz), all checks passed, whole flow 92 s with `jobs=2` in a 2-core sandbox.
- **Validate once** any new setting: run the case with the default settings and with the fast ones, and compare `phase_noise.csv`; an error of ~0.2 % in Γ is ~0.02 dB in L. Not measured: reducing `n_phase`.
- **The netlist itself matters little**: the tool builds its own runs (it only reads the devices, capacitors and sources of `core.cir`), so `save all`, `write ....raw` or the `.control` of your interactive netlists are not used. In your own interactive runs, avoid saving every vector (`save` only what you need) and a very small `tstep`.

### 5.1 Running with parallel processes
Each ngspice run in `lin` (one per ΔQ), `isf` (one per phase), `noise` (one per transistor) and `blocks` (one per block) is independent, so they can run at the same time. `baseline` (one transient) and `combine`/`compare`/`plots` (seconds) are not parallelized.

```bash
cd cases/cs_n4_gf180mcuD
ISFPN_VERBOSE=1 ISFPN_JOBS=8 python3 ../../isfpn.py cs.json all       # 8 ngspice processes at a time
```
or set `"jobs": 8` in the JSON (the environment variable wins). `jobs=1` (default) is serial.

| What | How |
|---|---|
| Number of processes | `jobs` / `ISFPN_JOBS`: use about the number of **physical** cores (`nproc` may count hyperthreads; check with `lscpu`). Measured on a 16-core machine (2 × Xeon Bronze 3106, no hyperthreading; CS gf180mcuD, whole flow): 1 / 2 / 4 / 8 / 12 / 16 jobs → 27.9 / 14.8 / 7.8 / 4.3 / 3.3 / 2.5 min (1.9× / 3.6× / 6.5× / 8.5× / 11.2×); the ISF stage alone scales 7.5× with 8 jobs. With the fast settings of 5.0 and 8 jobs: 78 s |
| One thread per process | `threads` = 1 (default), also the best choice: with the same 8 cores 8 jobs × 1 thread takes 257 s, 4 × 2 takes 399 s and 1 × 8 takes 1181 s. The tool writes `set num_threads=1` in every `.control`, because a `num_threads` in `~/.spiceinit`/`spinit` (e.g. the IIC-OSIC-TOOLS container) overrides `OMP_NUM_THREADS`; without it each ngspice can use ~8 cores and parallel runs do not scale |
| `OMP_WAIT_POLICY` | `ISFPN_OMP_WAIT=auto` (default): never set in serial (`passive` would make ngspice ~4× slower); with `jobs>1` it is `passive` only if `threads=0` or `jobs×threads` exceeds the visible CPUs (busy-waiting threads would stall), otherwise it is left alone. With `threads=1` the policy makes no difference (256 / 258 / 256 s for passive / active / none); with `threads=2` `passive` is harmful (634 s vs 399 s) |
| Stuck run | `run_timeout` (300 s) stops it and keeps `r_<tag>.spice`; run `ngspice -b` on it by hand |
| Check that it works | `docker stats` or `top`: serial ≈ 100 % CPU, `jobs=N` ≈ N·100 % |
| Result | identical for any `jobs` (verified: difference 0.0 in Γ, in the transistor PSDs and in the mirror block) |

Do not start parallel runs of the *program itself* in the same case directory (the intermediate files would collide); parallelism is inside each stage. If the environment has a CPU quota of one core (cgroup/VM), parallel runs do not help: keep `jobs=1`. The full diagnosis, the measurements and the open points are in [`docs/PARALLEL_NGSPICE.md`](docs/PARALLEL_NGSPICE.md).

| Stage | What it does | Inputs | Outputs | Time |
|---|---|---|---|---|
| `baseline` | transient with `ref` and all nodes; crossings; $T_0$ | core, config | `base_ref.json` (T0, f0, crossings, std(T0)), `wave_base.txt`, `figs/fig1_baseline.png` | ~6 s |
| `lin [NODE]` | Γ for 9 values of ΔQ (0.2-100 fC) at x=0.25 | `base_ref.json` | `lin.json`, `figs/fig2_linearity.png` | ~40 s |
| `isf` | n_phase+1 transients per node | `base_ref.json` | `isf_<NODE>.json`, `isf.csv`, `figs/fig3_isf.png` | ~2 min/node |
| `noise` | per FET, n_phase `.noise` runs in one process | `wave_base.txt` | `noise_dev.json`, `figs/fig4_device_noise.png` | ~2 s/device |
| `blocks` | one `.noise` per block | `wave_base.txt`, blocks | `blocks.json`, `figs/fig5_blocks.png` | seconds |
| `combine` | $\mathcal L$, $\Delta f_{min}$, checks, CSV | `isf_*.json`, `noise_dev.json`, `blocks.json` | `report.txt`, `summary.json`, `phase_noise.csv`, `contributions.csv`, `figs/fig6_phase_noise.png` | seconds |
| `compare` | difference vs `compare_file` | `summary.json` | on-screen table, `figs/fig7_comparison.png` | seconds |

Reading the figures: **fig1** must show a stable oscillation and the reference crossings (red triangles) on the threshold;
**fig2**, that Γ is flat (±2 %) at the ΔQ marked in red; **fig3**, the ISF per node (left panel, injection against GND) and the effective one per device $\Gamma_D-\Gamma_S$ (right panel);
**fig4**, the thermal PSD and the flicker amplitude per phase for each transistor and the spectrum of the phase with the most flicker (slopes 0.84 and 1.0); **fig5**, the block spectrum with its thermal level and its $K/f^{EF}$ fit;
**fig6**, $\mathcal L(\Delta f)$ (red zone = not valid) and the share per device; **fig7**, the comparison.

---

### 5.2 Benchmark script (`tools/bench_jobs.py`)

Runs a whole test matrix in one execution, from a case directory. For each run it saves `bench/<label>/timing.json`, `phase_noise.csv` and `run.log`, compares every CSV with the reference run (first `jobs=1` run) and prints a final table (total time, `isf` time, speed-up, max |ΔL| in dB, identical yes/no). Finished runs are skipped on re-launch (`--force` repeats them).

```bash
cd cases/cs_n4_gf180mcuD
python3 ../../tools/bench_jobs.py cs.json --dry-run          # list the runs
python3 ../../tools/bench_jobs.py cs.json                    # tests 1-5
python3 ../../tools/bench_jobs.py cs.json --tests 6 --jobs 8 # OpenMP wait policy
```

| Test | What |
|---|---|
| 1 | correctness: `jobs=1` vs `jobs=8`, CSV must be identical |
| 2 | jobs × threads with a fixed budget of 8 cores: 8×1, 4×2, 2×4, 1×8 (`--budget`) |
| 3 | `jobs=12` and `jobs=16` |
| 4 | fast settings (`tstep 2p`, `reltol 1e-4`, `nper 10`, `settle 15n`, `tstop 60n`) with `--jobs`; L should stay within ~0.1 dB |
| 5 | repeatability: 3 runs of `jobs=8` (`--repeat`) |
| 6 | `OMP_WAIT_POLICY` with `threads=1`: auto vs passive vs active vs untouched (`--jobs`) |
| 7 | `threads=2` with policy untouched / passive: 4×2 and 8×2 (the latter needs 16 cores) |

It uses two environment overrides that also work on their own: `ISFPN_THREADS=N` (overrides `threads`) and `ISFPN_OMP_WAIT=auto|passive|active|none` (policy used while `jobs > 1`). `bench/summary.json` accumulates the runs of all executions. A full run of tests 1-5 on the CS case is roughly 1 h on a 16-thread machine.

### 5.3 Cheat sheet: what to run and which jobs/threads to use

Measured on the reference machine (16 physical cores, CS gf180mcuD, whole flow). Rule of thumb: **`threads=1` and `jobs` = number of physical cores** (`lscpu`: sockets × cores per socket; `nproc` may count hyperthreads).

| jobs × threads | Total time | Speed-up | Comment |
|---|---|---|---|
| 1 × 1 | 1674 s (27.9 min) | 1.0× | serial reference |
| 8 × 1 | 257 s | 6.5× | |
| 12 × 1 | 198 s | 8.5× | |
| **16 × 1** | **150 s (2.5 min)** | **11.2×** | best measured; use this |
| 4 × 2 (policy untouched) | 399 s | 4.2× | threads are less efficient than processes |
| 2 × 4 / 1 × 8 | 1144 / 1181 s | 1.5× / 1.4× | avoid |
| 8 × 1 + fast settings | 78 s | 21× | for exploration only (ΔL ≈ 0.0004 dB here) |

**Everyday runs** (from the case directory, e.g. `cases/cs_n4_gf180mcuD`):
```bash
# 1. Normal run, all cores (add ISFPN_VERBOSE=1 to see the progress of every run)
ISFPN_JOBS=16 python3 ../../isfpn.py cs.json all

# 2. Same, keeping the console output and the timing table
ISFPN_JOBS=16 python3 ../../isfpn.py cs.json all 2>&1 | tee all.log      # timing.json is also written

# 3. Quick exploration: copy cs.json and add the fast settings (README 5.0), then run it with the same command
#    "tstep": "2p", "reltol": 1e-4, "nper": 10, "settle": 1.5e-8, "tstop": 6e-8

# 4. Different thread count / policy without editing the JSON
ISFPN_JOBS=4 ISFPN_THREADS=2 ISFPN_OMP_WAIT=none python3 ../../isfpn.py cs.json all
```

**Benchmark script** (to re-measure on another machine or after changing the environment; run from the case directory):
```bash
python3 ../../tools/bench_jobs.py cs.json --dry-run            # list the runs, nothing is executed
python3 ../../tools/bench_jobs.py cs.json                      # tests 1-5, about 1 h on the reference machine
python3 ../../tools/bench_jobs.py cs.json --tests 1,3          # only correctness and jobs 12/16 (~1 h with the serial reference)
python3 ../../tools/bench_jobs.py cs.json --tests 6 --jobs 8   # OpenMP policy with threads=1
python3 ../../tools/bench_jobs.py cs.json --tests 7            # threads=2: 4x2 and 8x2 with the policy untouched
python3 ../../tools/bench_jobs.py cs.json --tests 2 --budget 16 --force   # redo test 2 with a 16-core budget
python3 ../../tools/bench_jobs.py cs.json 2>&1 | tee bench_table.log      # keep the final table
```
It writes `bench/<run>/{timing.json,phase_noise.csv,run.log}` and the accumulated `bench/summary.json`; finished runs are skipped when relaunched. The `x` column needs the `jobs=1` run (test 1, or an earlier `bench/j1_t1`).

**To watch the CPU while it runs** (on the Docker host, after the first minute, when the `isf` stage has started):
```bash
for i in $(seq 1 6); do docker stats --no-stream --format "{{.Name}} CPU={{.CPUPerc}} MEM={{.MemUsage}}"; sleep 10; done
```
Expected: ≈ 100 % × (jobs × threads). Much less means idle or sleeping threads (wrong policy) or a CPU quota; much more means ngspice is multithreading on its own (`threads` not applied).

### 5.4 Sweep of a control value (bias current, VCO tuning)

For a VCO whose frequency is set by a control (e.g. the bias current of the current-starved oscillator) the `sweep` command runs the whole flow for every value and collects the result. The netlists are **not edited**: the program rewrites, in a copy, the line of the control element (same idea as `sweep` in `osc_characterization.py`), in the core **and in every block**, so the core and the mirror block always see the same value.

```json
"sweep": {
  "values": ["250u", "500u", "750u", "1m"],
  "line_prefix": "I0",
  "template": "I0 VBP 0 {v}",
  "offsets": [1e4, 1e5, 1e6, 1e7],
  "unit": "A"
}
```
```bash
cd cases/cs_n4_gf180mcuD
ISFPN_JOBS=16 python3 ../../isfpn.py cs_sweep.json sweep      # the console output is also saved in runs/sweep_I0_nominal/sweep.log
```

| Key | Meaning |
|---|---|
| `values` | control values: SPICE numbers (`"250u"`, `"1meg"`) or plain numbers |
| `line_prefix` + `template` | the element line starting with `line_prefix` (and its `+` continuation lines) is replaced by `template` with `{v}` = the value. It must be unique in the core (error otherwise); a block that does not contain it is left unchanged (message printed) |
| `param` | alternative: `"param": "IBIAS"` sets `.param IBIAS=<value>`; the netlists must then use `'IBIAS'` in the core and `{IBIAS}` in the blocks |
| `offsets` | offsets Δf [Hz] at which L is reported in `sweep.csv` (default 10k, 100k, 1M, 10M) |
| `unit` | unit of the control (`"A"`, `"V"`): used for the axis label and to express Kvco with a readable prefix (MHz/µA, MHz/mV...). Without it Kvco is in MHz per unit |
| `corners` | optional list of PVT corners `"process:temp_C:VDD"` (e.g. `["ss:125:3.0", "typical:60:3.3", "ff:-40:3.6"]`) or `{"name","proc","temp","vdd"}`. The **whole control sweep is repeated at every corner**: the process section of the `.lib` line of the PDK preamble (or `section`), `temp`, `vdd` (and an explicit `params.VDD` / `rails.VDD`) are rewritten in a copy of the config. `typical`/`tt` are accepted for both PDKs (gf180mcuD: typical, ss, ff, fs, sf) |
| `outdir` | output directory (default `sweep`) |

**With `corners`** the layout is `runs/sweep_<variable>_<N>corners/<corner>/<control>/` (e.g. `runs/sweep_I0_3corners/ss_125C_3p0V/I0_250u/`), `sweep.csv` gets a `corner` column, Kvco and its mean slope are computed per corner, and two figures are drawn:
- `sweep.png`: tuning curve, Kvco and L vs control, **one colour per corner** (the L panel uses a fainter shade for lower offsets);
- `sweep_phase_noise.png`: **L(Δf) vs offset, one panel per control value and one curve per corner** (dotted line = minimum valid offset of that corner): the comparison of the phase noise at the PVT corners.

Ready example: `cases/cs_n4_gf180mcuD/cs_sweep_corners.json` (4 currents × ss/125 °C/3.0 V, typical/60 °C/3.3 V, ff/−40 °C/3.6 V): `ISFPN_JOBS=16 python3 ../../isfpn.py cs_sweep_corners.json sweep`.

Cost = corners × values × time of one run (3 corners × 4 currents × ~2.5 min = ~30 min with `jobs=16`). The slowest corner (ss, 125 °C, 3.0 V) at the lowest current sets the `tstop`/`settle` you need; check it first with a one-point sweep (one value, only that corner) and look at `all.log` of the point: *stable period* and *ISF closure* must be OK.

Output (in `runs/sweep_I0_nominal/`, or `runs/sweep_I0_3corners/` with corners): one subdirectory per value (`I0_250u/` with its own `phase_noise.csv`, report, figures and `config.json`: **use that `phase_noise.csv` for the PLL model at that control value**), plus `sweep.csv` (f0, Kvco, minimum valid offset, L at the offsets, number of failed checks, time per point) and `sweep.png` (tuning curve and L vs control). The plot has three panels (tuning curve f0, **VCO gain Kvco**, L vs control) whose x ticks are the values exactly as written in `values` (`250u`, `500u`...). **Kvco** is the local slope df0/d(control) (central differences, one-sided at the ends; `sweep.csv` keeps it in Hz per unit, the console and the plot in MHz per prefixed unit, e.g. MHz/µA) plus the mean slope between the first and last point; it needs 3 or more points to be meaningful. For the CS (reduced test) the gain falls from 0.92 to 0.66 MHz/µA as the current grows: the tuning curve is compressive. When the real control becomes a voltage, either sweep the voltage source itself (`line_prefix` of the `Vctrl` line: Kvco comes out directly in Hz/V) or multiply this Kico by the gm of the V→I converter.

Notes:
- Points run one after another; `jobs`/`threads` apply inside each point (README 5.3). Time = number of points × time of one run (about 2.5 min per point with `jobs=16` for the CS).
- The console output is appended automatically to `sweep.log` in the sweep folder (and each point keeps its own `all.log`); `| tee` is not needed.
- It resumes: points with a `timing.json` are skipped when you relaunch (`ISFPN_FORCE=1` repeats them).
- **`tstop` and `settle` must cover the slowest point** (lowest current): the oscillator starts later and has a longer period. A longer `tstop` costs nothing in the perturbed runs (they stop at the measured crossing); only the baseline pays for it. The checks of each point (stable period, ISF closure, linearity) flag a point that did not settle.
- A ready example is `cases/cs_n4_gf180mcuD/cs_sweep.json` (4 bias currents; `tstop` 240 ns and `settle` 60 ns so that the slowest point, 250 µA, settles): `ISFPN_JOBS=16 python3 ../../isfpn.py cs_sweep.json sweep`. Expected time ~10 min with 16 jobs. Sandbox test (reduced, `n_phase=4`): f0 = 366.1 / 597.3 / 925.8 MHz for 250 µ / 500 µ / 1 mA; the mirror block followed each value (V(VCS) 1.04 / 1.22 / 1.48 V).
- The fixed pulse charge `dq_fc` (1 fC) is a larger fraction of the oscillation charge at low current: the linearity check may flag the lowest point (it did at 250 µA: 2.0 % > 2 %). Reduce `dq_fc` (e.g. 0.5) if it does.
- **`--set NAME=value`** (after the command, repeatable) changes one value for a single run without editing the JSON: a scalar key of the config (`tstop`, `temp`, `vdd`, `jobs`...) or, if it is not one, a `.param` (needs the netlists to use `'NAME'` / `{NAME}`): `python3 ../../isfpn.py cs.json all --set tstop=2.4e-7 --set IBIAS=300u`. It is not applied to the points of a `sweep`.
- The control must be a current source or an element that can be written as one line. A voltage control with a V→I converter inside the circuit is not covered yet: the converter's own noise would have to go in a block (with `{VCTRL}` as a parameter).

### 5.4a Target frequency: control value for a given f0

`"target_f0": 500e6` in the `sweep` key (and `"target_refine": true`, the default; `false` = interpolation only):
1. per corner, the control value that gives f0 = target by **linear interpolation** between the two bracketing sweep points (no extrapolation: if the target is outside the swept f0 range the corner is skipped with a message; widen `values`);
2. **refinement**: a full `all` run at that value (`<corner>/target_500MHz/`, with its own `phase_noise.csv` for the PLL model) and two *baseline-only* runs at ±5 % of it (`kv_minus`, `kv_plus`, ~20 s each) that give **Kvco = Δf0/Δcontrol at the target** (`kv_sim`);
3. report and files in the sweep folder: `target.csv` (control, f0 simulated and its error vs the target, Kvco interpolated and simulated, L interpolated and simulated, L at the buffer output when `local` is used), `sweep_target.png` (control needed per corner; L(Δf) at the target) and a star on the tuning curve of `sweep.png`.

The console also prints how much the control moves across corners (min/max and ±% around typical): that is the range the bias/control circuit must cover to hold the frequency over PVT. The f0 error of the full run shows the quality of the interpolation (ring test: −0.11 %); if it matters, add sweep points near the target. Relaunching the sweep reuses the target runs if the value did not change. In `cases/cs_ls_gf180mcuD/cs_sweep*.json` the target is 500 MHz.

### 5.4b Where the results go: `runs/` (names, `--tag`, `--here`)

The case folder keeps only the inputs (`core.cir`, `cs.json`, block netlists); every run writes into `runs/`:

| Command | Folder |
|---|---|
| `isfpn.py cs.json all` | `runs/<process>_<T>C_<VDD>V/` e.g. `runs/typical_60C_3p3V/` |
| `... all --set I0=400u` | `runs/typical_60C_3p3V_I0-400u/` (every `--set` except `jobs`, `threads`, `temp`, `vdd` is added to the name) |
| `... all --set temp=-40 --set vdd=3.6` | `runs/typical_m40C_3p6V/` (`-40` is written `m40`, `3.3` as `3p3`) |
| `... all --tag buffer_x2` | `runs/typical_60C_3p3V_tag-buffer_x2/` (for variants the name cannot see, e.g. an edited netlist) |
| `isfpn.py cs_sweep.json sweep` | `runs/sweep_I0_nominal/<control>/` |
| `isfpn.py cs_sweep_corners.json sweep` | `runs/sweep_I0_3corners/<corner>/<control>/` with corners named like the `all` runs (`ss_125C_3p0V`, `ff_m40C_3p6V`) |

- The process comes from the section of the `.lib <file> <section>` line of the pdk preamble (or `section`); `temp` and `vdd` from the config.
- Each folder has a self-contained `config.json` (absolute netlist paths, `--set` values already applied) and `all.log`. To rerun a single stage there: `cd runs/<name> && python3 ../../../../isfpn.py config.json isf`.
- The same name is the same folder: an `all` run overwrites it; a `sweep` resumes (points with `timing.json` are skipped, `ISFPN_FORCE=1` repeats them; use `--tag` if you changed the circuit).
- `sweep` names are fixed by the variable (`line_prefix` or `param`) and `nominal` / `<N>corners`; the range of values is not in the name (it is in `sweep.csv` and in `config.json`). `"outdir"` in the `sweep` key overrides the name.
- `--here` writes in the current directory as before (single stages always do; `tools/bench_jobs.py` uses it). The reference results of the included cases (8.x) were produced this way and are in the case folder.

### 5.5 Output buffer: local ISF (additive noise floor)

A buffer after the oscillator does two things. (1) It **loads** the oscillator (its input capacitance lowers f0: 663.5 → 500.6 MHz in the `cs_ls` case at 622 µA); this is automatic if the buffer is in `core.cir`. (2) Its own device noise adds jitter to the edges it produces. That jitter does **not accumulate** (the buffer has no memory of the phase), so the persistent ISF of the oscillator does not see it. The `local` key computes it and adds it to the oscillator's L.

**Configuration** (`cases/cs_ls_gf180mcuD/cs.json`):
- Keep the buffer in `core.cir`, take it out of the oscillator analysis with `skip_devices` (`nodes: "auto"` then perturbs only the oscillator nodes) and add `"local": {"nodes": ["CLK0L","CLK180L","CLK0","CLK180"]}`: the nodes of the path from the oscillator to the reference output (`ref.vec`). Devices with a drain or source on those nodes are the buffer devices (`local.devices` can be a list of names/regexes instead of `"auto"`). The symmetric path (CLK90/CLK270) has the same contribution and is not needed.
- `n_phase` (40) points in a window `window`·T0 (0.3) before the edge, `cross`: index of the output edge that is observed, `nlate`: edges later at which the persistent part is measured.

**Method.** A charge ΔQ is injected at each node at time t0 = (edge) − w. The edge shift measured right away minus the shift measured `nlate` periods later is the transient (non-persistent) part: h(w) [s/C], the local ISF. For each buffer device the noise PSD is computed at the same instants (same isolated-transistor bench as stage 4) and
σt² = ½ Σ ∫ (h_D − h_S)² S_th dt (thermal), A = ∫ (h_D − h_S) √K dt (flicker, coherent).
The output has two edges per period, so the white floor is **L_buf,th = 2π² f0 σt²** (flat, valid up to Δf ≈ f0) and **L_buf,fl = ½ (2π f0)² ΣA² / Δf^EF**. Powers add: L_out = L_osc + L_buf,th + L_buf,fl.

**Outputs:** `local_isf.json`, `noise_local.json`, `figs/fig8_local_isf.png`, a "BUFFER OUTPUT" table in `report.txt` (σt, floor, share per device) and `phase_noise_out.csv` (columns L_osc, L_buf_thermal, L_buf_flicker, L_out_total, ...), plus a check that |h| falls to <5 % at the far end of the window (otherwise increase `window`). The accumulated oscillator noise (`phase_noise.csv`) is unchanged.

**Result for the project buffer** (gf180mcuD, 622 µA, f0 = 500.56 MHz, reduced run): h ≈ 0.3–0.7 ps/fC, σt ≈ 105 fs per edge, floor −159.6 dBc/Hz; 92 % of it comes from the level shifter (XM19–XM22), about 8 % from the output inverters. The oscillator is at −105 dBc/Hz at 1 MHz and −146 dBc/Hz at 100 MHz, so the buffer floor is irrelevant for a PLL (offsets ≤ tens of MHz); it only matters if the buffer is made much weaker or the output is used at large offsets.

**Sweep.** If the case has `local`, each point also writes `phase_noise_out.csv`; `sweep.csv` gets `Lout_*` columns and `sweep_phase_noise.png` draws the output as dashed lines. `cs_sweep.json` / `cs_sweep_corners.json` of this case use 250 µ, 400 µ, 622 µ, 800 µ, 1 m (f0 ≈ 500 MHz at 622 µ). They use `window` 0.5: the buffer's edge-transition time is fixed, so at high current (short T0) a window of 0.3·T0 is too short (with 1 mA it flagged `local window` at 13.9 %). Reduced sandbox test (n_phase 8, 2 cores): 250 µ → f0 255.3 MHz, σt 195 fs, floor −157.2 dBc/Hz; 1 m → f0 690.8 MHz, σt 84 fs, floor −160.2 dBc/Hz; the buffer only shows above ≈ 100 MHz offset.

**Limits:** it assumes small noise (linear h), independent noise of the two edges, and the white floor only up to Δf < f0; the buffer's own input-referred noise from the oscillator side (kT/C of the loading) is part of the oscillator ISF.

## 6. Outputs and use in the PLL model

`phase_noise.csv` (grid `csv_grid`, 20 points per decade by default, 1 kHz to 1 GHz):

| Column | Meaning |
|---|---|
| `offset_Hz` | Δf |
| `L_thermal_dBcHz`, `L_flicker_dBcHz`, `L_total_dBcHz` | L(Δf) per component and total |
| `L_total_linear_1perHz` | linear $\mathcal L$ [1/Hz] |
| `Sphi_rad2perHz` | $S_\phi=2\mathcal L$ [rad²/Hz], single-sided PSD of the phase, which is what enters the linear PLL model |
| `valid` | 1 if Δf ≥ Δf_min (σφ < 0.3 rad) |

The first line is a comment with `f0` and `dmin`. `contributions.csv` gives the share per device and `isf.csv` the ISF per node (mrad/fC).

Typical use in a PLL model (Python):
```python
import numpy as np
d = np.genfromtxt("phase_noise.csv", delimiter=",", skip_header=1, names=True)
ok = d["valid"] == 1
Sphi = lambda f: np.interp(np.log10(f), np.log10(d["offset_Hz"][ok]), np.log10(d["Sphi_rad2perHz"][ok]))   # log10 Sφ(f)
# In a PLL with bandwidth f_bw: output noise due to the VCO = Sφ_vco(f) * |1 - H(f)|^2  (high-pass)
```
Recommendation: extrapolate with the model slopes (−20 and −30 dB/dec) only towards larger offsets; do not use the points with `valid=0`, the PLL loop already suppresses that region.

---

## 7. Without a Spectre reference
Simply **omit `compare_file`** in the config (the `ring3_sky130A` case is an example): the comparison is not run and validation relies on the **automatic checks** printed in `report.txt` and `summary.json`:

| Check | What it verifies | Criterion |
|---|---|---|
| stable period | `std(T0)/T0` of the baseline crossings (steady oscillation, simulation without numerical jitter) | < 0.1 % |
| ISF cycle closure | $\lvert\Gamma_k(0)-\Gamma_k(1)\rvert/\Gamma_{rms}$ per node (the pulse at x=0 and x=1 is the same phase) | < 1 % |
| linearity | Γ at `dq_fc` versus Γ at 0.2 fC (stage 1) | < 2 % |
| validity | $\Delta f_{min}$ for σφ < 0.3 rad | < 5 MHz (otherwise the oscillator is too noisy for this method) |

More recommended checks when there is no reference: (i) **symmetry**: in circuits with equivalent nodes (ring, quadrature) the ISFs are shifted copies and the contributions per device are equal (fig3 and `contributions.csv`);
(ii) **DC sensitivities**: Γ_dc of a current node ≈ $2\pi\,\Delta f/\Delta I$ from a frequency simulation with the current changed (in the CS: 807 kHz/µA against +803 kHz/µA);
(iii) **sweep of `dq_fc`, `n_phase` and `reltol`**: L must not change by more than ~0.1 dB; (iv) compare the slope with −20/−30 dB/dec.
When you later get a reference, add `"compare_file":"my_table.txt"` and run `python3 ../../isfpn.py CFG compare`.

---

## 8. Included cases and results

### 8.1 `ring3_sky130A` - 3-inverter ring, schematic parameters (no external reference)
`Ring_InvN3` netlist: 3 sky130A inverters (NMOS W=1 µm, PMOS W=3 µm, L=0.15 µm), 25 fF to GND and 25 fF to VDD per node, VDD=1.8 V, 60 °C. Reference: N1 rising through 0.9 V. f0 = 828.97 MHz.
It reproduces the original `ISF_pulse_test` package (−90.94 dBc/Hz at 1 MHz, validity 79 kHz) with a single command. No `compare_file`: validation is the automatic checks.

| Δf | thermal | flicker | total (ISF) |
|---|---|---|---|
| 100 kHz | -83.40 | -62.76 | **-62.72** |
| 1 MHz | -103.40 | -91.18 | **-90.92** |
| 10 MHz | -123.40 | -119.59 | **-118.08** |
| 100 MHz | -143.40 | -148.00 | **-142.10** |

### 8.2 `ring3_sky130A_nrd0` - the same with explicit `nrd=nrs=0`, against Spectre PNOISE
f0 = 945.49 MHz (Spectre: 946 MHz). Spectre (Cadence Virtuoso, 10 kHz-100 MHz):

| Δf | thermal | flicker | total (ISF) | Spectre | diff |
|---|---|---|---|---|---|
| 100 kHz | -82.29 | -61.45 | **-61.42** | -61.38 | -0.04 dB |
| 1 MHz | -102.29 | -89.87 | **-89.63** | -89.58 | -0.05 dB |
| 10 MHz | -122.29 | -118.29 | **-116.83** | -116.70 | -0.13 dB |
| 100 MHz | -142.29 | -146.69 | **-140.95** | -140.70 | -0.25 dB |

### 8.3 `cs_n4__sky130A_nrd0` - 4-stage pseudo-differential current-starved with mirror, against Spectre PNOISE
16-transistor core (XM1-XM16: main and cross-coupled inverters giving N1/N3 in phase and N2/N4 in quadrature), 25 fF capacitors to GND and to VCS, XM17/XM18 current mirror (m=40, I0=500 µA, delivers ≈ 420 µA) feeding node VCS,
and pseudo-differential outputs `E1: N13=N1−N3`, `E2: N24=N2−N4` (the phase reference is the rising crossing of N13 through 0 V; N24 is in quadrature and has the same L). f0 = 784.62 MHz (Spectre: 784.79 MHz).
Perturbed nodes (auto): N1, N2, N3, N4 and VCS; the mirror enters as a block (`mirror_noise.spice`). Breakdown: the mirror contributes 53 % of the thermal noise; flicker is dominated by the NMOS XM1/XM3/XM5/XM7 (≈ 18 % each at 100 kHz).

| Δf | thermal | flicker | total (ISF) | Spectre | diff |
|---|---|---|---|---|---|
| 100 kHz | -79.06 | -65.07 | **-64.90** | -64.91 | +0.01 dB |
| 1 MHz | -99.06 | -93.58 | **-92.50** | -92.49 | -0.01 dB |
| 10 MHz | -119.06 | -122.06 | **-117.30** | -117.20 | -0.10 dB |
| 100 MHz | -139.06 | -150.52 | **-138.76** | -138.70 | -0.06 dB |

**Lesson from the CS:** with `nrd/nrs` *omitted* (as in the Spectre netlist) ngspice gives 762.7 MHz and L(1 MHz) = −92.90 dBc/Hz (0.41 dB above Spectre); with explicit `nrd=0 nrs=0` the frequency matches (0.02 %) and the difference drops to 0.03 dB.
The 2.8 % disagreement in f0 was not due to the PDK: it was the default value of `nrd/nrs`.

### 8.4 `ring3_gf180mcuD` - 3-inverter ring in gf180mcuD (no external reference)
`Ring_InvN3` of the repository (NMOS `nfet_03v3` W=1 µm, PMOS `pfet_03v3` W=3 µm, L=0.28 µm, `nrd/nrs = 0.18u/W` explicit), 25 fF to GND and to VDD per node, VDD=3.3 V, 60 °C, `typical` corner. Reference: N1 rising through 1.65 V. f0 = 628.64 MHz (a plain ngspice transient of the original netlist gives 628.56 MHz).
The three nodes and the three inverter pairs give identical ISF and contributions (symmetry check). The thermal PSD is flat from 1e8 to 1e10 Hz and the flicker corner of these devices is at a few MHz, with EF ≈ 0.95 (NMOS) and 1.12 (PMOS). Minimum valid offset: 37 kHz. All automatic checks pass.

| Δf | thermal | flicker | total (ISF) |
|---|---|---|---|
| 100 kHz | -90.23 | -69.20 | **-69.17** |
| 1 MHz | -110.23 | -98.80 | **-98.50** |
| 10 MHz | -130.23 | -128.37 | **-126.19** |
| 100 MHz | -150.23 | -157.92 | **-149.54** |

### 8.5 `cs_n4_gf180mcuD` - 4-stage current-starved with mirror in gf180mcuD (no external reference)
Same topology as 8.3 with gf180mcuD 3.3 V devices (inverters W=3 µm/1 µm with m=8 and m=4, mirror XM17/XM18 W=4 µm, L=0.6 µm, m=50, I0=500 µA), VDD=3.3 V. f0 = 597.31 MHz (plain transient of the original netlist: 597.29 MHz); V(VCS) = 1.216 V. The mirror is a block (`mirror_noise.spice`, with `{VNODE}`, `{VDD}`, `{TEMP}`, `{LIB}`) and contributes 69 % of the thermal noise and 32 % of the flicker at 100 kHz; the NMOS of the first four stages (XM2/4/6/8) give ≈ 13 % each of the flicker.
Independent check without Spectre: $\Gamma_{VCS}$ = 4.94 mrad/fC corresponds to $K_{vco}$ = 786 kHz/µA, against 801 kHz/µA measured by DC (I0 = 480 µA and 520 µA: 581.1 and 613.2 MHz), 1.8 % apart. Minimum valid offset: 13 kHz.

| Δf | thermal | flicker | total (ISF) |
|---|---|---|---|
| 100 kHz | -84.03 | -78.56 | **-77.48** |
| 1 MHz | -104.03 | -108.61 | **-102.73** |
| 10 MHz | -124.03 | -138.52 | **-123.88** |
| 100 MHz | -144.03 | -168.32 | **-144.01** |

These two cases have no Spectre reference, so their validation relies on the automatic checks and on the DC sensitivity check above; the same algorithm and rules were validated against Spectre in sky130 (8.2, 8.3).

### 8.6 `cs_ls_gf180mcuD` - same oscillator + level shifter and pseudo-differential inverter buffer
See 5.5. `cd cases/cs_ls_gf180mcuD && ISFPN_JOBS=16 python3 ../../isfpn.py cs.json all`; the sweeps with `cs_sweep.json` / `cs_sweep_corners.json` and the command `sweep`.

---

## 9. Limitations and common problems
**Limitations:** quasi-static noise; only FETs + declared blocks; ideal rails; flicker extrapolated as $K/f^{EF}$; phase noise only; L not interpretable below $\Delta f_{min}$;
each temperature/corner implies repeating the flow; ~2 min per node on a fast machine (the perturbed runs stop 3 periods after the measured crossing, so `tstop` only needs to cover the baseline; the time grows with the number of nodes and phases).

| Symptom | Cause and solution |
|---|---|
| `ngspice did not produce w_base.txt; r_base.spice is kept` | ngspice error (lib not found, nonexistent model, L out of the model's range). The end of the output is shown; run `ngspice -b r_base.spice` for details |
| `Could not find library file` | wrong `lib`/`ISFPN_LIB`; the path must be absolute or relative to the case. The `.lib {LIB}` lines of the block benches are replaced by the program |
| `could not find a valid modelname` | the model has no bin for that W/L (e.g. `pfet_01v8_lvt` with L=0.15 µm) |
| f0 does not match Spectre | check `nrd/nrs`: omitted ≠ 0 (finding at the top), and `ad/as/pd/ps` (in ngspice with `scale`, 265f = 0.265) |
| WARNING: ... model ... not recognized as a FET | `X...` instance of a resistor/capacitor/diode: its noise is not included |
| `ISF cycle closure` CHECK | `reltol` too large, step too large or `nper` insufficient |
| `no crossing` / `IndexError` in `point` | `tstop` too short for `settle + (nper+13)·T0`, or the oscillator does not start (missing `.ic`) |
| The run seems stuck at `isf Nx: closure ...` | that line is printed when node Nx **finishes**, so the slow run is the next node. Use `ISFPN_VERBOSE=1` to see each phase and its time; `run_timeout` stops a stalled run and keeps its `r_s_<node>.spice` to run by hand |
| The run hangs | do not launch several ngspice runs at once in the sandbox; the program already runs everything serially |
| PMOS with source on an internal node give odd results | that node is missing from `nodes` (with `"auto"` it is always included) |

---

## 10. How to adapt it to another oscillator
1. Copy a case, replace `core.cir` with your netlist (without `.lib/.control/.ic`), with explicit `nrd/nrs` if you are going to compare against Spectre.
2. Define in the config `ref` (a clean crossing of a node or a differential output), `.ic` in `extra`, `settle` and `tstop` (check fig1), and the rails.
3. If there are noisy current sources/mirrors/bias circuits: take them out with `skip_devices` and write their test bench (4.3). If the oscillator has control nodes (VCS, VBP), their ISF is almost flat and gives $K_{vco}$.
4. `python3 ../../isfpn.py CFG baseline`, check fig1; `lin` and adjust `dq_fc`; then `all`.
5. Review the checks and the figures; use `phase_noise.csv` in the PLL.
6. Another PDK: copy a gf180mcuD case, change the `pdk` preamble/`models`, `vdd` and `ref.level` (VDD/2 for an inverter ring); check that the model names are recognized (no `WARNING: ... not recognized as a FET`) and that the thermal PSD is flat at 1e10 Hz in fig4.
7. LC oscillators or ones with noisy resistors: their sources (resistor/tank) are not included today; they can be added as noise blocks with their own test bench.

---

## 11. References
1. A. Hajimiri and T. H. Lee, "A general theory of phase noise in electrical oscillators," *IEEE JSSC*, vol. 33, no. 2, pp. 179-194, Feb. 1998.
2. A. Hajimiri, S. Limotyrakis and T. H. Lee, "Jitter and phase noise in ring oscillators," *IEEE JSSC*, vol. 34, no. 6, pp. 790-804, Jun. 1999.
3. J. A. McNeill, "Jitter in ring oscillators," *IEEE JSSC*, vol. 32, no. 6, pp. 870-879, Jun. 1997.
4. A. Demir, A. Mehrotra and J. Roychowdhury, "Phase noise in oscillators: a unifying theory and numerical methods for characterization," *IEEE TCAS-I*, vol. 47, no. 5, pp. 655-674, May 2000.
5. BSIM4 MOSFET Model, user's manual (UC Berkeley); sky130 models in `libs.tech/combined/sky130.lib.spice`.
