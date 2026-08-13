v {xschem version=3.4.8RC file_version=1.3}
G {}
K {}
V {}
S {}
F {}
E {}
B 2 620 -10 1420 390 {flags=graph
y1=71
y2=180
ypos1=0
ypos2=2
divy=5
subdivy=1
unity=1
x1=3
x2=10
divx=5
subdivx=8
xlabmag=1.0
ylabmag=1.0
dataset=-1
unitx=1
logx=1
logy=0
color=4
node="Phase (deg); ph(out)"}
B 2 620 -460 1420 -60 {flags=graph
y1=-20
y2=20
ypos1=0
ypos2=2
divy=5
subdivy=1
unity=1
x1=3
x2=10
divx=5
subdivx=8
xlabmag=1.0
ylabmag=1.0
dataset=-1
unitx=1
logx=1
logy=0
color=4
node="Gain (dB); 20 v(out) log10() *"}
T {tcleval(gmIDN: [to_eng [xschem raw value gmidn 0]])} -110 240 0 0 0.3 0.3 {floater=1}
T {Calculated Parameters} -110 200 0 0 0.5 0.5 {floater=1}
T {tcleval(VDSatN: [to_eng [xschem raw value vdsatn 0]])} -110 270 0 0 0.3 0.3 {floater=1}
T {tcleval(Av: [to_eng [xschem raw value av 0]] V/V)} -110 330 0 0 0.3 0.3 {floater=1}
T {tcleval(Av: [to_eng 20*log10([xschem raw value av 0])] dB)} -110 360 0 0 0.3 0.3 {floater=1}
T {tcleval(Gain max: [to_eng [xschem raw value gainmax_db 0]] dB)} 240 250 0 0 0.3 0.3 {floater=1}
T {tcleval(Bandwidth: [to_eng [xschem raw value bw 0]] Hz)} 240 280 0 0 0.3 0.3 {floater=1}
T {tcleval(Unit-Gain: [to_eng [xschem raw value gbw 0]] Hz)} 240 310 0 0 0.3 0.3 {floater=1}
T {tcleval(Phase Margin: [to_eng [xschem raw value pm 0]] Deg)} 240 340 0 0 0.3 0.3 {floater=1}
T {tcleval(Phase at GBW: [to_eng [xschem raw value phi0 0]] Deg)} 240 370 0 0 0.3 0.3 {floater=1}
T {Measured Parameters} 240 200 0 0 0.5 0.5 {floater=1}
T {tcleval(VDSN: [to_eng [xschem raw value vdsn 0]])} -110 300 0 0 0.3 0.3 {floater=1}
T {tcleval(gmN: [to_eng [xschem raw value gmn 0]])} -110 390 0 0 0.3 0.3 {floater=1}
T {tcleval(gdsN: [to_eng [xschem raw value gdsn 0]])} -110 420 0 0 0.3 0.3 {floater=1}
T {tcleval(idn: [to_eng [xschem raw value idn 0]])} -110 450 0 0 0.3 0.3 {floater=1}
N -300 -160 -300 -130 {lab=#net1}
N 130 -230 130 -170 {lab=VDD}
N 50 -20 90 -20 {lab=#net2}
N -60 -20 -10 -20 {lab=in}
N -60 -20 -60 10 {lab=in}
N 130 -80 280 -80 {lab=out}
N 280 -80 280 -50 {lab=out}
N 130 -20 180 -20 {lab=0}
N 180 -20 180 40 {lab=0}
N 130 40 180 40 {lab=0}
N 130 10 130 40 {lab=0}
N 130 40 130 60 {lab=0}
N -200 60 -200 80 {lab=#net3}
N -200 60 -100 60 {lab=#net3}
N -130 -190 -130 -160 {lab=#net4}
N -130 -190 -40 -190 {lab=#net4}
N 20 -190 220 -190 {lab=out}
N 220 -190 220 -80 {lab=out}
N -180 -190 -130 -190 {lab=#net4}
N -180 -190 -180 20 {lab=#net4}
N -180 20 -100 20 {lab=#net4}
N 130 -110 130 -50 {lab=out}
C {symbols/nfet_03v3.sym} 110 -20 0 0 {name=M1
L=0.33u
W=4.2u
nf=1
m=10
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {vcvs.sym} -60 40 0 0 {name=E1 value=100}
C {res.sym} -10 -190 1 0 {name=R1
value=1e9
footprint=1206
device=resistor
m=1}
C {capa.sym} -130 -130 0 0 {name=C1
m=1
value=1
footprint=1206
device="ceramic capacitor"}
C {vsource.sym} 20 -20 1 0 {name=V1 value="DC 0 AC 1 0" savecurrent=false}
C {devices/code_shown.sym} -820 -420 0 0 {name=MODELS only_toplevel=true
format="tcleval( @value )"
value="
.include $::180MCU_MODELS/design.ngspice
.lib $::180MCU_MODELS/sm141064.ngspice typical
.param sw_stat_global=0
.param sw_stat_mismatch=0
"}
C {gnd.sym} -60 70 0 0 {name=l11 lab=0}
C {devices/code_shown.sym} -830 -260 0 0 {name=SPICE only_toplevel=false 
value="
*.options method=gear
.param VDD=3.3 TEMP=27
.temp \{TEMP\}
.csparam vdd = \{vdd\}
**** interactive sim
.control
  op
  ac dec 50 1k 10G
  let gmn = @m.xm1.m0[gm]
  let gdsn = @m.xm1.m0[gds]
  let idn = @m.xm1.m0[id]
  let vdsatn = @m.xm1.m0[vdsat]
  let vdsn = @m.xm1.m0[vds]
  let gmIDn = gmn/idn
  let rl = (vdd-vdsn)/(idn)
  let Av = gmn/(gdsn + 1/rl)
  let gain_db = db(v(out))
  let gainmax_db = vecmax(gain_db)
  let phase = (180/PI)*vp(out)
  meas ac gbw WHEN gain_db = 0 fall=1
  meas ac bw  WHEN gain_db = (gainmax_db-3) fall=1
  meas ac phi0 FIND phase at =gbw
  let pm = phi0 + 180  
  print gmidn
  print pm
  print idn
  option remzerovec
  save all
  write gmID_Course_S05_02.raw
.endc
"}
C {vdd.sym} 130 -230 0 0 {name=l3 lab=VDD}
C {vsource.sym} -300 -100 0 0 {name=V9 value='VDD' savecurrent=false}
C {vsource.sym} -300 -190 0 0 {name=V7 value=0 savecurrent=false}
C {capa.sym} 280 -20 0 0 {name=C2
m=1
value=500f
footprint=1206
device="ceramic capacitor"}
C {vsource.sym} -200 110 0 0 {name=V2 value='1.8' savecurrent=false}
C {vdd.sym} -300 -220 0 0 {name=l1 lab=VDD}
C {gnd.sym} -200 140 0 0 {name=l2 lab=0}
C {gnd.sym} -300 -70 0 0 {name=l4 lab=0}
C {gnd.sym} -130 -100 0 0 {name=l5 lab=0}
C {gnd.sym} 280 10 0 0 {name=l6 lab=0}
C {gnd.sym} 130 60 0 0 {name=l7 lab=0}
C {lab_wire.sym} 260 -80 0 0 {name=p1 sig_type=std_logic lab=out}
C {lab_wire.sym} -50 -20 0 0 {name=p2 sig_type=std_logic lab=in}
C {devices/launcher.sym} -185 -435 0 0 {name=h4 
descr="Select arrow and 
Ctrl-Left-Click to load/unload
simulation .raw file" 
tclcommand="
xschem raw_read $netlist_dir/[file tail [file rootname [xschem get current_name]]].raw
"
}
C {devices/launcher.sym} -190 -500 0 0 {name=h2
descr="Annotate OP" 
tclcommand="set show_hidden_texts 1; xschem annotate_op"
}
C {res.sym} 130 -140 2 0 {name=R2
value=3.8k
footprint=1206
device=resistor
m=1}
