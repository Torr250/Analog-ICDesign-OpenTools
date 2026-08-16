v {xschem version=3.4.6 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
B 2 550 -400 1350 0 {flags=graph
y1=-0.014
y2=1.9
ypos1=0
ypos2=2
divy=5
subdivy=1
unity=1
x1=2.1120371e-08
divx=5
subdivx=1
xlabmag=1.0
ylabmag=1.0
legendmag=1.0
node="in
out
outb"
color="4 5 6"
dataset=-1
unitx=1
logx=0
logy=0
rawfile=$netlist_dir/TB_not.raw
linewidth_mult=4
x2=2.3697351e-08
hilight_wave=-1}
B 2 550 70 1350 470 {flags=graph
y1=-0.018
y2=1.9
ypos1=-0.49751241
ypos2=1.5024876
subdivy=1
unity=1
x1=2.1120371e-08
divx=5
subdivx=1
xlabmag=1.0
ylabmag=1.0
legendmag=1.0
node="out
outb"
color="4 1"
dataset=-1
unitx=1
logx=0
logy=0
rawfile=$netlist_dir/TB_not.raw
linewidth_mult=4
digital=0
divy=5
vlegend=0
hilight_wave=-1
x2=2.3697351e-08}
B 2 1420 -400 2220 0 {flags=graph
y1=0
y2=1.8
ypos1=0
ypos2=2
divy=5
subdivy=1
unity=1
x1=2.1120371e-08
divx=5
subdivx=1
xlabmag=1.0
ylabmag=1.0
legendmag=1.0
node="out3
in
out4"
color="4 5 10"
dataset=-1
unitx=1
logx=0
logy=0
rawfile=$netlist_dir/TB_not.raw
linewidth_mult=4
x2=2.3697351e-08
hilight_wave=-1}
T {tcleval(trise: [to_eng [xschem raw value trise_not 0]])} 640 540 0 0 0.4 0.4 {floater=1}
T {tcleval(tfall: [to_eng [xschem raw value tfall_not 0]])} 640 570 0 0 0.4 0.4 {floater=1}
T {tcleval(tDrise: [to_eng [xschem raw value tplh_not 0]])} 640 600 0 0 0.4 0.4 {floater=1}
T {tcleval(tDfall: [to_eng [xschem raw value tphl_not 0]])} 640 630 0 0 0.4 0.4 {floater=1}
T {tcleval(trise: [to_eng [xschem raw value trise_buffer 0]])} 830 540 0 0 0.4 0.4 {floater=1}
T {tcleval(tfall: [to_eng [xschem raw value tfall_buffer 0]])} 830 570 0 0 0.4 0.4 {floater=1}
T {tcleval(tDrise: [to_eng [xschem raw value tplh_buffer 0]])} 830 600 0 0 0.4 0.4 {floater=1}
T {tcleval(tDfall: [to_eng [xschem raw value tphl_buffer 0]])} 830 630 0 0 0.4 0.4 {floater=1}
T {Inverter} 640 500 0 0 0.4 0.4 {floater=1}
T {Buffer} 830 500 0 0 0.4 0.4 {floater=1}
N -90 -160 -50 -160 {lab=in}
N -90 -160 -90 40 {lab=in}
N 70 -160 120 -160 {lab=outb}
N 120 -160 120 -140 {lab=outb}
N -270 -70 -270 -50 {lab=in}
N -270 -70 -90 -70 {lab=in}
N -200 -110 -200 -70 {lab=in}
N 200 90 300 90 {lab=out}
N 340 -160 390 -160 {lab=#net1}
N 390 -160 390 -140 {lab=#net1}
N 120 -160 220 -160 {lab=outb}
N 160 90 200 90 {lab=out}
N -90 90 40 90 {lab=in}
N -90 40 -90 90 {lab=in}
N -30 310 40 310 {lab=in}
N 300 90 300 110 {lab=out}
N 160 310 200 310 {lab=#net2}
N 320 310 370 310 {lab=out2}
N -30 450 40 450 {lab=in}
N 160 450 210 450 {lab=out3}
N -30 570 40 570 {lab=in}
N 160 570 210 570 {lab=out4}
C {devices/code.sym} 160 -390 0 0 {name=TT_MODELS
only_toplevel=true
format="tcleval( @value )"
value="
** opencircuitdesign pdks install
.lib $::SKYWATER_MODELS/sky130.lib.spice tt
"
spice_ignore=false}
C {vdd.sym} 0 -210 0 0 {name=l1 lab=VDD}
C {gnd.sym} 0 -110 0 0 {name=l2 lab=0}
C {capa.sym} 120 -110 0 0 {name=C1
m=1
value=25f
footprint=1206
device="ceramic capacitor"}
C {gnd.sym} 120 -80 0 0 {name=l5 lab=0}
C {vsource.sym} -350 -70 0 0 {name=V1 value=1.8 savecurrent=false}
C {vdd.sym} -350 -100 0 0 {name=l7 lab=VDD}
C {gnd.sym} -350 -40 0 0 {name=l8 lab=0}
C {vsource.sym} -270 -20 0 0 {name=V2
value="pulse(0 'VDD' '0.5/freq' '0.1/freq' '0.1/freq' '0.5/freq' '1/freq')" 
savecurrent=false}
C {gnd.sym} -270 10 0 0 {name=l10 lab=0}
C {lab_pin.sym} -200 -110 0 0 {name=p1 sig_type=std_logic lab=in}
C {lab_pin.sym} 120 -160 2 0 {name=p2 sig_type=std_logic lab=outb}
C {lab_pin.sym} 200 90 2 0 {name=p3 sig_type=std_logic lab=out}
C {code_shown.sym} -1200 130 0 0 {name=SPICE only_toplevel=false 
value="
.param freq=500e6 VDD=1.8
.param vhigh=\{VDD*0.9\} vlow=\{VDD*0.1\} vswitch=\{VDD*0.5\}

 .csparam vdd1=\{VDD\}
**** interactive sim
.control
  save all
  tran 10p 30n 
  let vlow = \{0.1*vdd1\}
  let vhigh = \{0.9*vdd1\}
  let vswitch = \{0.5*vdd1\}
  meas tran trise_not    trig V(outb) val=vlow    td=0 rise=1 targ V(outb) val=vhigh   td=0 rise=1
  meas tran tfall_not    trig V(outb) val=vhigh   td=0 fall=1 targ V(outb) val=vlow    td=0 fall=1 
  meas tran tplh_not     trig V(in)   val=vswitch td=0 fall=1 targ V(outb) val=vswitch td=0 rise=1
  meas tran tphl_not     trig V(in)   val=vswitch td=0 rise=1 targ V(outb) val=vswitch td=0 fall=1
  meas tran trise_buffer trig V(out)  val=vlow    td=0 rise=1 targ V(out)  val=vhigh   td=0 rise=1
  meas tran tfall_buffer trig V(out)  val=vhigh   td=0 fall=1 targ V(out)  val=vlow    td=0 fall=1 
  meas tran tplh_buffer  trig V(in)   val=vswitch td=0 rise=1 targ V(out)  val=vswitch td=0 rise=1
  meas tran tphl_buffer  trig V(in)   val=vswitch td=0 fall=1 targ V(out)  val=vswitch td=0 fall=1
  write TB_not.raw
.endc
"}
C {devices/launcher.sym} -415 -225 0 0 {name=h4 
descr="Select arrow and 
Ctrl-Left-Click to load/unload
simulation .raw file" 
tclcommand="
xschem raw_read $netlist_dir/[file tail [file rootname [xschem get current_name]]].raw
"
}
C {devices/launcher.sym} -420 -300 0 0 {name=h1
descr="Annotate OP" 
tclcommand="set show_hidden_texts 1; xschem annotate_op"
}
C {vdd.sym} 270 -210 0 0 {name=l13 lab=VDD}
C {gnd.sym} 270 -110 0 0 {name=l14 lab=0}
C {capa.sym} 390 -110 0 0 {name=C4
m=1
value=25f
footprint=1206
device="ceramic capacitor"}
C {gnd.sym} 390 -80 0 0 {name=l15 lab=0}
C {gate_not_x1.sym} -30 -160 0 0 {name=x1}
C {gate_not_x1.sym} 240 -160 0 0 {name=x2}
C {lab_pin.sym} -30 310 0 0 {name=p4 sig_type=std_logic lab=in}
C {vdd.sym} 90 40 0 0 {name=l4 lab=VDD}
C {gnd.sym} 90 140 0 0 {name=l6 lab=0}
C {gate_buff_x1.sym} 90 90 0 0 {name=x3}
C {capa.sym} 300 140 0 0 {name=C3
m=1
value=25f
footprint=1206
device="ceramic capacitor"}
C {gnd.sym} 300 170 0 0 {name=l9 lab=0}
C {gate_not.sym} 80 310 0 0 {name=X4 vhigh=1.8 trise=200p}
C {gate_not.sym} 240 310 0 0 {name=X5 vhigh=1.8 trise=200p}
C {lab_pin.sym} 370 310 2 0 {name=p5 sig_type=std_logic lab=out2}
C {lab_pin.sym} -30 450 0 0 {name=p6 sig_type=std_logic lab=in}
C {lab_pin.sym} 210 450 2 0 {name=p7 sig_type=std_logic lab=out3}
C {/foss/designs/atorralba/cyc/sky130A/analog/behavioral/INV.sym} 80 450 0 0 {name=X6 VDD=1.8 k=20}
C {code_shown.sym} -1270 -30 0 0 {name=s1 only_toplevel=false value="
.inc /foss/designs/atorralba/cyc/sky130A/analog/behavioral/logic_gates_behavioral.spice"}
C {lab_pin.sym} -30 570 0 0 {name=p8 sig_type=std_logic lab=in}
C {lab_pin.sym} 210 570 2 0 {name=p9 sig_type=std_logic lab=out4}
C {/foss/designs/atorralba/cyc/sky130A/analog/behavioral/BUF.sym} 80 570 0 0 {name=X7 VDD=1.8 k=20}
