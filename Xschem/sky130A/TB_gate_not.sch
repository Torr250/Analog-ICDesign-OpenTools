v {xschem version=3.4.6 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
B 2 720 -160 1520 240 {flags=graph
y1=0
y2=2
ypos1=0
ypos2=2
divy=5
subdivy=1
unity=1
x1=3.627519e-09
x2=5.9468013e-09
divx=5
subdivx=1
xlabmag=1.0
ylabmag=1.0
node="in
out_post
out_pre"
color="4 5 6"
dataset=-1
unitx=1
logx=0
logy=0
digital=0}
T {tcleval(trise: [to_eng [xschem raw value trise_pre 0]])} 750 310 0 0 0.3 0.3 {floater=1}
T {tcleval(tfall: [to_eng [xschem raw value tfall_pre 0]])} 750 350 0 0 0.3 0.3 {floater=1}
T {tcleval(tDrise: [to_eng [xschem raw value tplh_pre 0]])} 750 390 0 0 0.3 0.3 {floater=1}
T {tcleval(tDfall: [to_eng [xschem raw value tphl_pre 0]])} 750 430 0 0 0.3 0.3 {floater=1}
T {Inverter Pre} 750 270 0 0 0.3 0.3 {floater=1}
T {This Test Bench was used for post-layout simulations of the inverter} -300 -280 0 0 0.5 0.5 {floater=1}
T {tcleval(trise: [to_eng [xschem raw value trise_post 0]])} 950 310 0 0 0.3 0.3 {floater=1}
T {tcleval(tfall: [to_eng [xschem raw value tfall_post 0]])} 950 350 0 0 0.3 0.3 {floater=1}
T {tcleval(tDrise: [to_eng [xschem raw value tplh_post 0]])} 950 390 0 0 0.3 0.3 {floater=1}
T {tcleval(tDfall: [to_eng [xschem raw value tphl_post 0]])} 950 430 0 0 0.3 0.3 {floater=1}
T {Inverter Post} 950 270 0 0 0.3 0.3 {floater=1}
N -60 -60 -60 -30 {lab=in}
N -60 -60 -30 -60 {lab=in}
N 270 -100 430 -100 {lab=out_post}
N 270 120 430 120 {lab=out_pre}
N 350 -100 350 -80 {lab=out_post}
N 550 -100 590 -100 {lab=#net1}
N 590 -100 590 -80 {lab=#net1}
N 350 120 350 140 {lab=out_pre}
N 550 120 590 120 {lab=#net2}
N 590 120 590 140 {lab=#net2}
N 100 -100 150 -100 {lab=in}
N 100 120 150 120 {lab=in}
N 320 -130 320 -100 {lab=out_post}
N 320 90 320 120 {lab=out_pre}
C {vsource.sym} -250 0 0 0 {name=V1 value='VDD' savecurrent=false}
C {vsource.sym} -60 0 0 0 {name=V2 
value="pulse(0 'VDD' '0.5/freq' '0.01/freq' '0.01/freq' '0.5/freq' '1/freq')"
savecurrent=false}
C {capa.sym} 350 -50 0 0 {name=C1
m=1
value=25f
footprint=1206
device="ceramic capacitor"}
C {capa.sym} 590 -50 0 0 {name=C2
m=1
value=25f
footprint=1206
device="ceramic capacitor"}
C {capa.sym} 350 170 0 0 {name=C3
m=1
value=25f
footprint=1206
device="ceramic capacitor"}
C {capa.sym} 590 170 0 0 {name=C4
m=1
value=25f
footprint=1206
device="ceramic capacitor"}
C {gnd.sym} 350 -20 0 0 {name=l1 lab=GND}
C {vdd.sym} -250 -30 0 0 {name=l2 lab=VDD}
C {vdd.sym} 200 -150 0 0 {name=l3 lab=VDD}
C {vdd.sym} 480 -150 0 0 {name=l4 lab=VDD}
C {gnd.sym} 200 -50 0 0 {name=l5 lab=GND}
C {gnd.sym} 480 -50 0 0 {name=l6 lab=GND}
C {gnd.sym} 200 170 0 0 {name=l7 lab=GND}
C {gnd.sym} 480 170 0 0 {name=l8 lab=GND}
C {vdd.sym} 200 70 0 0 {name=l9 lab=VDD}
C {vdd.sym} 480 70 0 0 {name=l10 lab=VDD}
C {gnd.sym} 590 -20 0 0 {name=l11 lab=GND}
C {gnd.sym} 350 200 0 0 {name=l12 lab=GND}
C {gnd.sym} 590 200 0 0 {name=l13 lab=GND}
C {gnd.sym} -60 30 0 0 {name=l14 lab=GND}
C {lab_pin.sym} -30 -60 0 1 {name=p7 sig_type=std_logic lab=in}
C {lab_pin.sym} 100 -100 0 0 {name=p1 sig_type=std_logic lab=in}
C {lab_pin.sym} 100 120 0 0 {name=p2 sig_type=std_logic lab=in}
C {lab_pin.sym} 320 -130 0 0 {name=p3 sig_type=std_logic lab=out_post}
C {lab_pin.sym} 320 90 0 0 {name=p4 sig_type=std_logic lab=out_pre}
C {code_shown.sym} -440 300 0 0 {name=SPICE only_toplevel=false value="
.param freq=500e6 VDD=1.8
.para vhigh=\{VDD*0.9\} vlow=\{VDD*0.1\} vswitch=\{VDD*0.5\}
 .csparam vdd1=\{VDD\}
**** interactive sim
.control
  save all
  tran 10p 10n 
  let vlow = \{0.1*vdd1\}
  let vhigh = \{0.9*vdd1\}
  let vswitch = \{0.5*vdd1\}
  meas tran trise_post   trig V(out_post) val=vlow    td=0 rise=1 targ V(out_post) val=vhigh   td=0 rise=1
  meas tran tfall_post   trig V(out_post) val=vhigh   td=0 fall=1 targ V(out_post) val=vlow    td=0 fall=1 
  meas tran tplh_post    trig V(in)      val=vswitch td=0 fall=1 targ V(out_post) val=vswitch td=0 rise=1
  meas tran tphl_post    trig V(in)      val=vswitch td=0 rise=1 targ V(out_post) val=vswitch td=0 fall=1
  meas tran trise_pre    trig V(out_pre) val=vlow    td=0 rise=1 targ V(out_pre) val=vhigh   td=0 rise=1
  meas tran tfall_pre    trig V(out_pre) val=vhigh   td=0 fall=1 targ V(out_pre) val=vlow    td=0 fall=1 
  meas tran tplh_pre     trig V(in)      val=vswitch td=0 fall=1 targ V(out_pre) val=vswitch td=0 rise=1
  meas tran tphl_pre     trig V(in)      val=vswitch td=0 rise=1 targ V(out_pre) val=vswitch td=0 fall=1
  write TB_gate_not.raw
.endc
"}
C {gnd.sym} -250 30 0 0 {name=l15 lab=GND}
C {devices/launcher.sym} -270 -200 0 0 {name=h1
descr="Annotate OP" 
tclcommand="set show_hidden_texts 1; xschem annotate_op"
}
C {launcher.sym} -270 -150 0 0 {name=h5
descr="Ctrl + Left-Click to load waves" 
tclcommand="xschem raw_read $netlist_dir/TB_gate_not.raw tran"
}
C {devices/code.sym} -510 20 0 0 {name=TT_MODELS
only_toplevel=true
format="tcleval( @value )"
value="
** opencircuitdesign pdks install
.lib $::SKYWATER_MODELS/sky130.lib.spice tt

"
spice_ignore=false}
C {code_shown.sym} -440 220 0 0 {name=Include only_toplevel=false value="
.inc /foss/designs/atorralba/cyc/sky130A/analog/layout/gate_not_x1.spice"}
C {gate_not_x1.sym} 170 -100 0 0 {name=x1}
C {gate_not_x1.sym} 450 -100 0 0 {name=x2}
C {gate_not_xn.sym} 190 120 0 0 {name=X3 nfing=1}
C {gate_not_xn.sym} 470 120 0 0 {name=X4 nfing=1}
