* sky130A -> LTspice (generado por make_min_pdk.py --target ltspice)
* Geometria en METROS (el PDK original usa micras). Parametros: l w nf ad as pd ps nrd nrs sa sb sd mult
.param sw_tox_lv_nom = {4.148E-09}
.param sw_tox_hv_nom = {11.60E-09}
.param sw_tox_lv = {sw_tox_lv_corner+sw_tox_lv_mc}
.param sw_tox_hv = {sw_tox_hv_corner+sw_tox_hv_mc}
.param sw_func_tox_lv_ratio = {sw_tox_lv/sw_tox_lv_nom}
.param sw_func_tox_hv_ratio = {sw_tox_hv/sw_tox_hv_nom}
.param sw_func_nsd_pw_cj = {sw_nsd_pw_cj/1.35E-03}
.param sw_func_psd_nw_cj = {sw_psd_nw_cj/7.3802e-4}
.param sw_mm_vth0_sky130_fd_pr__nfet_01v8 = {3.356e-03}
.param sw_mm_vth0_sky130_fd_pr__nfet_01v8_lvt = {5.456e-03}
.param sw_mm_vth0_sky130_fd_pr__nfet_g5v0d10v5 = {8.200e-03}
.param sw_mm_vth0_sky130_fd_pr__pfet_01v8 = {5.856e-03}
.param sw_mm_vth0_sky130_fd_pr__pfet_01v8_lvt = {1.089e-02}
.param sw_mm_vth0_sky130_fd_pr__pfet_g5v0d10v5 = {1.200e-02}
.param sw_tox_lv_mc = {0}
.param sw_tox_hv_mc = {0}
.param sw_vth0_sky130_fd_pr__nfet_01v8_lvt_mc = {0}
.param sw_vth0_sky130_fd_pr__nfet_01v8_mc = {0}
.param sw_vth0_sky130_fd_pr__pfet_01v8_lvt_mc = {0}
.param sw_vth0_sky130_fd_pr__pfet_01v8_mc = {0}
.param sw_vth0_sky130_fd_pr__nfet_g5v0d10v5_mc = {0}
.param sw_vth0_sky130_fd_pr__pfet_g5v0d10v5_mc = {0}
