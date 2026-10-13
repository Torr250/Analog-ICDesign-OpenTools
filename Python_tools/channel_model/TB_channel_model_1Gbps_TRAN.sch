v {xschem version=3.4.8RC file_version=1.3}
G {}
K {}
V {}
S {}
F {}
E {}
B 2 430 -530 1230 -130 {flags=graph
y1=1.1e-24
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
m10at500mhz"
color="9 7"
dataset=-1
unitx=1
logx=0
logy=0
linewidth_mult=4
x2=5e-08
hilight_wave=-1}
N 380 170 380 200 {lab=VRAND}
N 380 170 410 170 {lab=VRAND}
N 610 170 640 170 {lab=D}
N 640 170 760 170 {lab=D}
N 610 170 610 200 {lab=D}
N 430 40 470 40 {lab=D}
N 510 0 510 30 {lab=in_}
N 510 0 560 0 {lab=in_}
N 620 0 680 0 {lab=in}
N 650 0 650 30 {lab=in}
N 1040 120 1100 120 {lab=in}
N 1220 120 1300 120 {lab=m10at500MHz}
C {devices/code_shown.sym} 1540 -40 0 0 {name=sPICE only_toplevel=false 
value="
.options method=gear
.param freq=1e9 VDD=1 TEMP=27
.temp \{TEMP\}
**** interactive sim
.control
  save all
  tran 10p 100n 
  option remzerovec
  write TB_channel_model_1Gbps_TRAN.raw
  write /foss/designs/gf180mcuD/eye_diagram/TB_channel_model_1Gbps_TRAN.raw
.endc
"}
C {devices/launcher.sym} 1635 -305 0 0 {name=h4 
descr="Select arrow and 
Ctrl-Left-Click to load/unload
simulation .raw file" 
tclcommand="
xschem raw_read $netlist_dir/[file tail [file rootname [xschem get current_name]]].raw
"
}
C {devices/launcher.sym} 1630 -380 0 0 {name=h1
descr="Annotate OP" 
tclcommand="set show_hidden_texts 1; xschem annotate_op"
}
C {gnd.sym} 380 260 0 0 {name=l6 lab=0}
C {lab_pin.sym} 410 170 2 0 {name=p3 sig_type=std_logic lab=VRAND}
C {vsource.sym} 380 230 0 0 {name=V1 value="trrandom (2 '1/freq' 750p 1 0)" savecurrent=false}
C {lab_pin.sym} 760 170 2 0 {name=p6 sig_type=std_logic lab=D
}
C {gnd.sym} 610 260 0 0 {name=l7 lab=0}
C {bsource.sym} 610 230 0 0 {name=B1 VAR=V FUNC="sgn(V(VRAND))*VDD/2+VDD/2" m=1}
C {vcvs.sym} 510 60 0 0 {name=E1 value=1}
C {gnd.sym} 510 90 0 0 {name=l1 lab=0}
C {gnd.sym} 470 80 0 0 {name=l2 lab=0}
C {lab_pin.sym} 430 40 2 1 {name=p1 sig_type=std_logic lab=D
}
C {lab_wire.sym} 540 0 0 0 {name=p2 sig_type=std_logic lab=in_}
C {res.sym} 590 0 1 0 {name=R1
value=50
footprint=1206
device=resistor
m=1}
C {lab_wire.sym} 660 0 0 0 {name=p4 sig_type=std_logic lab=in}
C {capa.sym} 650 60 0 0 {name=C1
m=1
value=1p
footprint=1206
device="ceramic capacitor"}
C {gnd.sym} 650 90 0 0 {name=l3 lab=0}
C {code_shown.sym} 1510 -200 0 0 {name=s1 only_toplevel=false value="
.include /foss/designs/gf180mcuD/channel_model/tline_m10at500MHz.sp
"}
C {lab_wire.sym} 1290 120 0 0 {name=p5 sig_type=std_logic lab=m10at500MHz}
C {lab_wire.sym} 1040 120 0 0 {name=p7 sig_type=std_logic lab=in}
C {channel_model/tline_m10at500MHz.sym} 1120 150 0 0 {name=x1}
