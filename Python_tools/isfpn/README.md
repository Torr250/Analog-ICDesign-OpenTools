# isfpn - oscillator phase noise in ngspice (no PSS + PNOISE): the ISF method

`isfpn.py` computes the phase noise L(Δf) of **any oscillator described by a sky130 transistor netlist** by combining
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
5. [Stages: what each one does, how to run it, inputs, outputs and figures](#5-stages)
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
- sky130A PDK in ngspice format. The reduced version generated with `tools/make_min_pdk.py --split-sections` is recommended, using the per-section lib
  (`.../libs.tech/combined/sections/sky130_tt.lib.spice`, section `tt`): one ngspice run drops from ~3.6 s to ~0.3 s.
- **The lib path** is not written in the netlists: it is defined in the config (`lib`) or with the environment variable `ISFPN_LIB`, and the program
  replaces the `.lib {LIB}` marker right before running (ngspice does not expand environment variables in `.lib`). `python3 isfpn.py CFG export_template`
  writes `templates/base.spice` with the marker visible.

```
isfpn/
├── isfpn.py                 program (docstring with all the config keys)
├── README.md                this document
├── tools/make_min_pdk.py    generates sky130A_min (and per-section libs)
└── cases/
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
| `lib`, `section` | -, `"tt"` | `.lib` file and section. `lib` is overridden by `ISFPN_LIB` |
| `temp`, `vdd` | 60, 1.8 | temperature [°C] and supply [V] (clipping limit for the bias of 1.8 V models) |
| `params`, `extra` | `{}`, `[]` | `.param` (e.g. `{"VDD":1.8}`) and extra SPICE lines (`.ic ...`, `.options ...`) |
| `rails` | `{"0":0,"VDD":vdd}` | ideal rail nodes: Γ = 0 and fixed voltage |
| `ref` | - | `{"vec":"v(n13)","level":0.0,"edge":"rise"}`: vector, threshold and edge that define $x=0$. Ring: `v(n1)`, 0.9; CS: `v(n13)`, 0 |
| `tstop`, `tstep`, `settle` | 70n, `"1p"`, 25n | transient [s], step and time after which steady state holds. `settle + (nper+13)·T0` must fit in `tstop` |
| `nper` | 20 | cycles between the pulse and the crossing measurement |
| `dq_fc` | 1.0 | pulse charge [fC] (according to stage 1) |
| `n_phase` | 30 | points per period (+1 for closure) |
| `nodes` | `"auto"` | nodes to perturb. `"auto"` = all D/S of the core FETs that are not rails (+ the node of each block) |
| `skip_devices` | `[]` | FETs not treated as core |
| `blocks` | `[]` | blocks: `{"name","node","file","out","th_freq"}` (see 4.3) |
| `compare_file` | (absent) | reference table `f[Hz] L[dBc/Hz]`; if missing, nothing is compared (section 7) |
| `df_list` | 10k..100M | offsets printed in `report.txt` |
| `csv_grid` | `{"fmin":1e3,"fmax":1e9,"ppd":20}` | grid of the final CSV |
| `reltol` | 1e-5 | ngspice tolerance (needed to see voltage jumps of tens of mV) |

### 4.3 Netlist of a special block (`blocks`)
An independent test bench (example: `mirror_noise.spice` of the CS) that contains **exact copies of the block's devices**, with the same bias, and where
the output (`net2`, which in the real circuit goes to node VCS) is connected like this:
```spice
Rs net2 vx 1 noisy=0          * current sensor: 1 Ω with no noise of its own
Vfix vx 0 {VNODE} ac 1        * fixes the node at its actual mean voltage; AC input of .noise
.temp {TEMP}                  * from the config (`temp`)
.lib {LIB}                    * the program replaces it with <lib> <section>
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
d = np.genfromtxt("phase_noise.csv", delimiter=",", skip_header=2, names=True)
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

---

## 9. Limitations and common problems
**Limitations:** quasi-static noise; only FETs + declared blocks; ideal rails; flicker extrapolated as $K/f^{EF}$; phase noise only; L not interpretable below $\Delta f_{min}$;
each temperature/corner implies repeating the flow; ~2 min per node (the time grows with the number of nodes and phases).

| Symptom | Cause and solution |
|---|---|
| `ngspice did not produce w_base.txt; r_base.spice is kept` | ngspice error (lib not found, nonexistent model, L out of the model's range). The end of the output is shown; run `ngspice -b r_base.spice` for details |
| `Could not find library file` | wrong `lib`/`ISFPN_LIB`; the path must be absolute or relative to the case. The `.lib {LIB}` lines of the block benches are replaced by the program |
| `could not find a valid modelname` | the model has no bin for that W/L (e.g. `pfet_01v8_lvt` with L=0.15 µm) |
| f0 does not match Spectre | check `nrd/nrs`: omitted ≠ 0 (finding at the top), and `ad/as/pd/ps` (in ngspice with `scale`, 265f = 0.265) |
| WARNING: ... model ... not recognized as a FET | `X...` instance of a resistor/capacitor/diode: its noise is not included |
| `ISF cycle closure` CHECK | `reltol` too large, step too large or `nper` insufficient |
| `no crossing` / `IndexError` in `point` | `tstop` too short for `settle + (nper+13)·T0`, or the oscillator does not start (missing `.ic`) |
| The run hangs | do not launch several ngspice runs at once in the sandbox; the program already runs everything serially |
| PMOS with source on an internal node give odd results | that node is missing from `nodes` (with `"auto"` it is always included) |

---

## 10. How to adapt it to another oscillator
1. Copy a case, replace `core.cir` with your netlist (without `.lib/.control/.ic`), with explicit `nrd/nrs` if you are going to compare against Spectre.
2. Define in the config `ref` (a clean crossing of a node or a differential output), `.ic` in `extra`, `settle` and `tstop` (check fig1), and the rails.
3. If there are noisy current sources/mirrors/bias circuits: take them out with `skip_devices` and write their test bench (4.3). If the oscillator has control nodes (VCS, VBP), their ISF is almost flat and gives $K_{vco}$.
4. `python3 ../../isfpn.py CFG baseline`, check fig1; `lin` and adjust `dq_fc`; then `all`.
5. Review the checks and the figures; use `phase_noise.csv` in the PLL.
6. LC oscillators or ones with noisy resistors: their sources (resistor/tank) are not included today; they can be added as noise blocks with their own test bench.

---

## 11. References
1. A. Hajimiri and T. H. Lee, "A general theory of phase noise in electrical oscillators," *IEEE JSSC*, vol. 33, no. 2, pp. 179-194, Feb. 1998.
2. A. Hajimiri, S. Limotyrakis and T. H. Lee, "Jitter and phase noise in ring oscillators," *IEEE JSSC*, vol. 34, no. 6, pp. 790-804, Jun. 1999.
3. J. A. McNeill, "Jitter in ring oscillators," *IEEE JSSC*, vol. 32, no. 6, pp. 870-879, Jun. 1997.
4. A. Demir, A. Mehrotra and J. Roychowdhury, "Phase noise in oscillators: a unifying theory and numerical methods for characterization," *IEEE TCAS-I*, vol. 47, no. 5, pp. 655-674, May 2000.
5. BSIM4 MOSFET Model, user's manual (UC Berkeley); sky130 models in `libs.tech/combined/sky130.lib.spice`.
