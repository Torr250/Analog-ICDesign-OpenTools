* sky130A -> LTspice (generado por make_min_pdk.py --target ltspice)
* Geometria en METROS (el PDK original usa micras). Parametros: l w nf ad as pd ps nrd nrs sa sb sd mult
.param sw_tox_lv_corner = {4.148e-09+corner_factor*1.5199999999999948e-10}
.param sw_tox_hv_corner = {1.16e-08+corner_factor*5.000000000000012e-10}
.param sw_polycd = {0.0+corner_factor*5.5e-09 + process_mc_factor*MC_PR_SWITCH*gauss((1.5e-09)/(1))}
.param sw_activecd = {0.0+corner_factor*2.25e-08 + process_mc_factor*MC_PR_SWITCH*gauss((5e-09)/(1))}
.param sw_nsd_pw_cj = {0.00135+corner_factor*0.00019999999999999987 + process_mc_factor*MC_PR_SWITCH*0}
.param sw_psd_nw_cj = {0.0007408+corner_factor*4.629999999999999e-05 + process_mc_factor*MC_PR_SWITCH*0}
.param sw_vth0_sky130_fd_pr__nfet_01v8 = {0.0+corner_factor*0.015}
.param sw_vth0_sky130_fd_pr__nfet_01v8_lvt = {0.0+corner_factor*0.019}
.param sw_vth0_sky130_fd_pr__nfet_g5v0d10v5 = {0.0+corner_factor*0.02}
.param sw_vth0_sky130_fd_pr__pfet_01v8 = {0.0+corner_factor*-0.01}
.param sw_vth0_sky130_fd_pr__pfet_01v8_lvt = {0.0+corner_factor*-0.09}
.param sw_vth0_sky130_fd_pr__pfet_g5v0d10v5 = {0.0+corner_factor*-0.04}
