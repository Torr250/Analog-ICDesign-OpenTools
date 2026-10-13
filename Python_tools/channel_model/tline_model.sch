v {xschem version=3.4.8RC file_version=1.3}
G {}
K {}
V {}
S {}
F {}
E {}
B 2 1020 -220 1820 180 {flags=graph
y1=-1.1
y2=4.3
ypos1=0
ypos2=2
divy=5
subdivy=1
unity=1
x1=0
divx=5
subdivx=1
xlabmag=1.0
ylabmag=1.0
legendmag=1.0
node="in
out"
color="4 5"
dataset=-1
unitx=1
logx=0
logy=0
linewidth_mult=4
x2=1e-07
hilight_wave=-1}
N 500 110 550 110 {lab=out}
N 550 110 550 130 {lab=out}
N 770 110 820 110 {lab=#net1}
N 820 110 820 130 {lab=#net1}
N 550 110 650 110 {lab=out}
N -150 60 -150 90 {lab=VDD}
N -150 150 -150 180 {lab=#net2}
N -70 140 -70 180 {lab=IVDD}
N -70 140 -40 140 {lab=IVDD}
N 280 110 380 110 {lab=in}
N 550 330 550 360 {lab=VRAND}
N 550 330 580 330 {lab=VRAND}
N 780 330 810 330 {lab=D}
N 810 330 930 330 {lab=D}
N 780 330 780 360 {lab=D}
N 620 610 690 610 {lab=D}
N 520 520 520 570 {lab=#net3}
N 520 520 740 520 {lab=#net3}
N 740 520 740 560 {lab=#net3}
N 810 610 880 610 {lab=in}
N 550 70 550 110 {lab=out}
C {devices/vdd.sym} 430 60 0 0 {name=l1 lab=VDD}
C {devices/gnd.sym} 430 160 0 0 {name=l2 lab=0}
C {devices/capa.sym} 550 160 0 0 {name=C1
m=1
value=25f
footprint=1206
device="ceramic capacitor"}
C {devices/gnd.sym} 550 190 0 0 {name=l5 lab=0}
C {devices/lab_pin.sym} 280 110 0 0 {name=p1 sig_type=std_logic lab=in}
C {devices/lab_pin.sym} 550 70 2 0 {name=p2 sig_type=std_logic lab=out}
C {devices/code_shown.sym} -120 490 0 0 {name=sPICE only_toplevel=false 
value="
.options method=gear
.param freq=1e9 VDD=3.3 TEMP=27
.param vhigh=\{VDD*0.9\} vlow=\{VDD*0.1\} vswitch=\{VDD*0.5\}
.csparam vdd1=\{VDD\} freq=\{freq\}
.temp \{TEMP\}
**** interactive sim
.control
  save all
  tran 10p 100n 
  let vlow = \{0.1*vdd1\}
  let vhigh = \{0.9*vdd1\}
  let vswitch = \{0.5*vdd1\}
  meas tran ivdd_rms RMS v(IVDD)
  let effy = (vdd1*ivdd_rms*1e3)/(freq*1e-9)
  print effy
  option remzerovec
  write TB_not_PRBS.raw
  write /foss/designs/atorralba/cyc/gf180mcuD/analog/eye_diagram/TB_not_PRBS.raw
.endc
"}
C {devices/launcher.sym} 55 -45 0 0 {name=h4 
descr="Select arrow and 
Ctrl-Left-Click to load/unload
simulation .raw file" 
tclcommand="
xschem raw_read $netlist_dir/[file tail [file rootname [xschem get current_name]]].raw
"
}
C {devices/launcher.sym} 50 -120 0 0 {name=h1
descr="Annotate OP" 
tclcommand="set show_hidden_texts 1; xschem annotate_op"
}
C {devices/vdd.sym} 700 60 0 0 {name=l13 lab=VDD}
C {devices/gnd.sym} 700 160 0 0 {name=l14 lab=0}
C {devices/capa.sym} 820 160 0 0 {name=C4
m=1
value=25f
footprint=1206
device="ceramic capacitor"}
C {devices/gnd.sym} 820 190 0 0 {name=l15 lab=0}
C {gate_not_x1.sym} 400 110 0 0 {name=x1}
C {gate_not_x1.sym} 670 110 0 0 {name=x2}
C {devices/code_shown.sym} -120 350 0 0 {name=MODELS only_toplevel=true
format="tcleval( @value )"
value="
.include $::180MCU_MODELS/design.ngspice
.lib $::180MCU_MODELS/sm141064.ngspice typical
.param sw_stat_global=0
.param sw_stat_mismatch=0
"}
C {vsource.sym} -150 210 0 0 {name=V9 value='VDD' savecurrent=false}
C {vdd.sym} -150 60 0 0 {name=l3 lab=VDD}
C {gnd.sym} -150 240 0 0 {name=l4 lab=0}
C {vsource.sym} -150 120 0 0 {name=V7 value=0 savecurrent=false}
C {ccvs.sym} -70 210 0 0 {name=H2 vnam=v7 value=1}
C {gnd.sym} -70 240 0 0 {name=l26 lab=0}
C {lab_pin.sym} -40 140 2 0 {name=p25 sig_type=std_logic lab=IVDD}
C {gnd.sym} 550 420 0 0 {name=l6 lab=0}
C {lab_pin.sym} 580 330 2 0 {name=p3 sig_type=std_logic lab=VRAND}
C {vsource.sym} 550 390 0 0 {name=V1 value="trrandom (2 '1/freq' 750p 1 0)" savecurrent=false}
C {lab_pin.sym} 930 330 2 0 {name=p6 sig_type=std_logic lab=D
}
C {gnd.sym} 780 420 0 0 {name=l7 lab=0}
C {bsource.sym} 780 390 0 0 {name=B1 VAR=V FUNC="sgn(V(VRAND))*VDD/2+VDD/2" m=1}
C {devices/gnd.sym} 740 660 0 0 {name=l9 lab=0}
C {lab_pin.sym} 620 610 2 1 {name=p4 sig_type=std_logic lab=D
}
C {vsource.sym} 520 600 0 0 {name=V2 value='VDD' savecurrent=false}
C {gnd.sym} 520 630 0 0 {name=l8 lab=0}
C {devices/lab_pin.sym} 880 610 0 1 {name=p5 sig_type=std_logic lab=in}
C {gate_not_xn.sym} 730 610 0 0 {name=X3 nfing=8}
