v {xschem version=3.4.8RC file_version=1.3}
G {}
K {}
V {}
S {}
F {}
E {}
B 2 1020 -220 1820 180 {flags=graph
y1=0
y2=1
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
N 230 120 230 150 {lab=VRAND}
N 230 120 260 120 {lab=VRAND}
N 460 120 490 120 {lab=D}
N 490 120 610 120 {lab=D}
N 460 120 460 150 {lab=D}
N 670 380 710 380 {lab=D}
N 750 340 750 370 {lab=in2}
N 750 340 800 340 {lab=in2}
N 860 340 920 340 {lab=in}
N 1040 340 1120 340 {lab=out}
N 1120 340 1120 360 {lab=out}
N 890 340 890 370 {lab=in}
C {devices/code_shown.sym} -160 370 0 0 {name=sPICE only_toplevel=false 
value="
.options method=gear
.param freq=2e9 VDD=1 TEMP=27
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
  option remzerovec
  write tline_model_PRBS.raw
  write /foss/designs/atorralba/cyc/gf180mcuD/analog/eye_diagram/tline_model_PRBS.raw
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
C {gnd.sym} 230 210 0 0 {name=l6 lab=0}
C {lab_pin.sym} 260 120 2 0 {name=p3 sig_type=std_logic lab=VRAND}
C {vsource.sym} 230 180 0 0 {name=V1 value="trrandom (2 '1/freq' 750p 1 0)" savecurrent=false}
C {lab_pin.sym} 610 120 2 0 {name=p6 sig_type=std_logic lab=D
}
C {gnd.sym} 460 210 0 0 {name=l7 lab=0}
C {bsource.sym} 460 180 0 0 {name=B1 VAR=V FUNC="sgn(V(VRAND))*VDD/2+VDD/2" m=1}
C {vcvs.sym} 750 400 0 0 {name=E1 value=1}
C {gnd.sym} 750 430 0 0 {name=l1 lab=0}
C {gnd.sym} 710 420 0 0 {name=l2 lab=0}
C {lab_pin.sym} 670 380 2 1 {name=p1 sig_type=std_logic lab=D
}
C {lab_wire.sym} 780 340 0 0 {name=p2 sig_type=std_logic lab=in2}
C {res.sym} 830 340 1 0 {name=R1
value=50
footprint=1206
device=resistor
m=1}
C {lab_wire.sym} 900 340 0 0 {name=p4 sig_type=std_logic lab=in}
C {res.sym} 1120 390 0 1 {name=R2
value=50
footprint=1206
device=resistor
m=1}
C {gnd.sym} 1120 420 0 0 {name=l5 lab=0}
C {lab_wire.sym} 1110 340 0 0 {name=p5 sig_type=std_logic lab=out}
C {code_shown.sym} 740 670 0 0 {name=s1 only_toplevel=false value="
.include /foss/designs/gf180mcuD/analog/tline_model/tline_fr408_1m.sp"}
C {capa.sym} 890 400 0 0 {name=C1
m=1
value=1p
footprint=1206
device="ceramic capacitor"}
C {gnd.sym} 890 430 0 0 {name=l3 lab=0}
C {tline_model/tline_fr408_1m.sym} 940 370 0 0 {name=x1}
