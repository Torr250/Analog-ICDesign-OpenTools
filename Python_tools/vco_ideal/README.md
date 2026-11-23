# vco_ideal

Ideal (behavioral) VCO models for ngspice, meant for system-level PLL simulations where a transistor-level VCO is not needed.

| File | Purpose |
|---|---|
| `vco_ideal_lib.spice` | Library with two subcircuits: `vco_ideal` (noiseless) and `vco_ideal_noisy` (white frequency noise, i.e. −20 dB/dec phase noise). |
| `vco_top_clean.spice` | Example netlist: noiseless VCO, 100 ns transient. |
| `vco_top_noisy.spice` | Example netlist: VCO with phase noise (`L1m = -100 dBc/Hz` at 1 MHz offset), 2 µs transient, fixed `rndseed`. |

## Model

- Frequency: `f = f0 + kvco·(v(vctrl) − vc0)`. The phase is accumulated **in cycles** by a 1 F capacitor that integrates `f` in Hz.
- Output: rail-to-rail `0..vdd` with finite edges, `vdd/2·(1 + tanh(sharp·sin(2π·phase)))`.
- Ports: `vctrl` (control voltage) and `out` (referenced to global ground).
- Parameters (defaults): `vdd=3.3`, `f0=500meg`, `kvco=80meg` (Hz/V), `vc0=1.65` (V), `sharp=8`.
- `vco_ideal_noisy` adds `L1m` (phase-noise level at 1 MHz offset, dBc/Hz, default −100) and `dt`. White noise is injected into the frequency integrator, so `L(f) = sigf²·dt/f²`.

**Important:** `dt` must be equal to the `.tran` time step (`tstep`), because the noise amplitude `sigf` is derived from it.

## Usage

```bash
ngspice -b vco_top_clean.spice   # writes vco_top_clean.raw
ngspice -b vco_top_noisy.spice   # writes vco_top_noisy.raw
```

The `.raw` files can be analyzed with [`../clk_jitter/clock_jitter.py`](../clk_jitter/) or [`../osc_characterization/`](../osc_characterization/).

To use the VCO in your own netlist:

```spice
.include vco_ideal_lib.spice
Xvco vctrl out vco_ideal_noisy vdd=3.3 f0=500meg kvco=80meg vc0=1.65 L1m=-100 dt=10p
```
