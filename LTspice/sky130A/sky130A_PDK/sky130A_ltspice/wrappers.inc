* sky130A -> LTspice (generado por make_min_pdk.py --target ltspice)
* Geometria en METROS (el PDK original usa micras). Parametros: l w nf ad as pd ps nrd nrs sa sb sd mult

.subckt xnfet_01v8 D G S B
.param l=0.15u w=1u m=1 nf=1
.param ad = {int((nf+1)/2) * W/nf * 0.29u}
.param as = {int((nf+2)/2) * W/nf * 0.29u}
.param ps = {2*int((nf+2)/2) * (W/nf + 0.29u)}
.param pd = {2*int((nf+1)/2) * (W/nf + 0.29u)}
.param nrd = {0.29u / W}
.param nrs = {0.29u / W}
X1 D G S B sky130_fd_pr__nfet_01v8 l=l w=w nf=nf ad=ad as=as pd=pd ps=ps nrd=nrd nrs=nrs mult=m
.ends

.subckt xnfet_01v8_lvt D G S B
.param l=0.15u w=1u m=1 nf=1
.param ad = {int((nf+1)/2) * W/nf * 0.29u}
.param as = {int((nf+2)/2) * W/nf * 0.29u}
.param ps = {2*int((nf+2)/2) * (W/nf + 0.29u)}
.param pd = {2*int((nf+1)/2) * (W/nf + 0.29u)}
.param nrd = {0.29u / W}
.param nrs = {0.29u / W}
X1 D G S B sky130_fd_pr__nfet_01v8_lvt l=l w=w nf=nf ad=ad as=as pd=pd ps=ps nrd=nrd nrs=nrs mult=m
.ends

.subckt xnfet_g5v0d10v5 D G S B
.param l=0.5u w=1u m=1 nf=1
.param ad = {int((nf+1)/2) * W/nf * 0.29u}
.param as = {int((nf+2)/2) * W/nf * 0.29u}
.param ps = {2*int((nf+2)/2) * (W/nf + 0.29u)}
.param pd = {2*int((nf+1)/2) * (W/nf + 0.29u)}
.param nrd = {0.29u / W}
.param nrs = {0.29u / W}
X1 D G S B sky130_fd_pr__nfet_g5v0d10v5 l=l w=w nf=nf ad=ad as=as pd=pd ps=ps nrd=nrd nrs=nrs mult=m
.ends

.subckt xpfet_01v8 D G S B
.param l=0.15u w=1u m=1 nf=1
.param ad = {int((nf+1)/2) * W/nf * 0.29u}
.param as = {int((nf+2)/2) * W/nf * 0.29u}
.param ps = {2*int((nf+2)/2) * (W/nf + 0.29u)}
.param pd = {2*int((nf+1)/2) * (W/nf + 0.29u)}
.param nrd = {0.29u / W}
.param nrs = {0.29u / W}
X1 D G S B sky130_fd_pr__pfet_01v8 l=l w=w nf=nf ad=ad as=as pd=pd ps=ps nrd=nrd nrs=nrs mult=m
.ends

.subckt xpfet_01v8_lvt D G S B
.param l=0.35u w=1u m=1 nf=1
.param ad = {int((nf+1)/2) * W/nf * 0.29u}
.param as = {int((nf+2)/2) * W/nf * 0.29u}
.param ps = {2*int((nf+2)/2) * (W/nf + 0.29u)}
.param pd = {2*int((nf+1)/2) * (W/nf + 0.29u)}
.param nrd = {0.29u / W}
.param nrs = {0.29u / W}
X1 D G S B sky130_fd_pr__pfet_01v8_lvt l=l w=w nf=nf ad=ad as=as pd=pd ps=ps nrd=nrd nrs=nrs mult=m
.ends

.subckt xpfet_g5v0d10v5 D G S B
.param l=0.5u w=1u m=1 nf=1
.param ad = {int((nf+1)/2) * W/nf * 0.29u}
.param as = {int((nf+2)/2) * W/nf * 0.29u}
.param ps = {2*int((nf+2)/2) * (W/nf + 0.29u)}
.param pd = {2*int((nf+1)/2) * (W/nf + 0.29u)}
.param nrd = {0.29u / W}
.param nrs = {0.29u / W}
X1 D G S B sky130_fd_pr__pfet_g5v0d10v5 l=l w=w nf=nf ad=ad as=as pd=pd ps=ps nrd=nrd nrs=nrs mult=m
.ends
