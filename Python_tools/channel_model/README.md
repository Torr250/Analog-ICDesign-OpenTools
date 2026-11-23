# channel_model

Loss-only channel model for SerDes simulations, plus a pulse-response analysis of that model.

| File | Purpose |
|---|---|
| `channel_model_generator.py` | Generates a SPICE subcircuit that models the channel **loss** as a cascade of "shelving" filters (0 dB at DC by default, with the roll-off needed to pass through two loss/frequency points). Optionally validates it with an ngspice `.AC` run. |
| `channel_pulse_analysis.py` | Computes the pulse response, AC response and **worst-case eye height** (channel-coefficients method) from the generated `.sp`, with an optional CTLE model and FFE taps. No ngspice run needed: the transfer function is known analytically. |
| `*.sp`, `*.sym` | Example channel models (`fr408_1m`, `nelco4000_13_12inch`, `nelco4000_13_20inch`, `tline_m10at500MHz`) and their Xschem symbols. |
| `channel_model/` | Output of a generator run (`channel_model.sp`, `_validation_ac.sp`, theoretical-response plot, copies of the examples). |
| `TB_*.sch`, `tline_model*.sch` | Xschem testbenches (AC / transient, 1 Gbps variants). |

The model has **no transmission lines and no reflections**: only the magnitude loss.

## Requirements

```
pip install numpy scipy matplotlib --break-system-packages
```
ngspice in the `PATH` is only needed for the automatic `.AC` validation (`--no-validate` skips it).

## Usage

```bash
# Generate a channel: 0 dB at DC, 2 dB at 1 GHz, 6 dB at 4 GHz
python3 channel_model_generator.py --loss-dc 0 --f1 1e9 --loss1-db 2 --f2 4e9 --loss2-db 6

# If the slope between f1 and f2 is too steep for one stage, add stages
python3 channel_model_generator.py --f1 1e9 --loss1-db 2 --f2 4e9 --loss2-db 12 --n-stages 2

# Pulse response and worst-case eye height at 1 Gbps
python3 channel_pulse_analysis.py channel_model/channel_model.sp --datarate 1e9
python3 channel_pulse_analysis.py channel_model/channel_model.sp --datarate 1e9 --n-precursors 10 --n-postcursors 100
```

The generated subcircuit is used as `X1 input_node output_node <subckt_name>`.

`channel_pulse_analysis.py` also accepts `--fp1/--fp2/--loss-dc/--n-stages` explicitly, FFE taps (`--ffe-pre`, `--ffe-post`), CTLE parameters (`--ctle-*`, models `analytic`, `measured`, `gains`), `--plot-worst-case-eye` and `--overlay-eye-npz` (overlay an eye from `../eye_diagram/`). Run it with `--help` for the full list.

## Note on the `.sp` header

When `fp1`, `fp2`, `loss-dc` or the number of stages are not passed, `channel_pulse_analysis.py` **reads them from the comment header** of the `.sp` file. The parser accepts both the current English header and the older Spanish one, so previously generated files keep working. If you change the header text in the generator, update `parse_channel_sp` accordingly.
