v {xschem version=3.4.8RC file_version=1.3}
G {}
K {}
V {}
S {}
F {}
E {}
B 2 1020 -220 1820 180 {flags=graph
y1=-36
y2=0
ypos1=0
ypos2=2
divy=5
subdivy=1
unity=1
x1=0.001
divx=5
subdivx=1
xlabmag=1.0
ylabmag=1.0
legendmag=1.0
dataset=-1
unitx=1
logx=0
logy=0
linewidth_mult=4
x2=8e+09
hilight_wave=-1
color=7
node="Synth Channel for 1Gbps; m10at500mhz log10() 20 *"}
N 590 110 650 110 {lab=in}
N 770 110 850 110 {lab=m10at500MHz}
N 460 170 460 190 {lab=in}
C {devices/code_shown.sym} 10 270 0 0 {name=sPICE only_toplevel=false 
value="
.options method=gear
.param TEMP=27
.temp \{TEMP\}
**** interactive sim
.control
  ac lin 100 1M 2G
  save all
  option remzerovec
  write TB_channel_model_1Gbps_AC.raw
  *write /foss/designs/atorralba/cyc/gf180mcuD/analog/eye_diagram/tline_model_PRBS.raw
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
C {lab_wire.sym} 460 170 0 0 {name=p4 sig_type=std_logic lab=in}
C {lab_wire.sym} 840 110 0 0 {name=p5 sig_type=std_logic lab=m10at500MHz}
C {code_shown.sym} -80 40 0 0 {name=s1 only_toplevel=false value="
.include /foss/designs/gf180mcuD/channel_model/tline_m10at500MHz.sp
"}
C {vsource.sym} 460 220 0 0 {name=V1 value="DC 0 AC 1" savecurrent=false}
C {gnd.sym} 460 250 0 0 {name=l1 lab=0}
C {lab_wire.sym} 590 110 0 0 {name=p3 sig_type=std_logic lab=in}
C {channel_model/tline_m10at500MHz.sym} 670 140 0 0 {name=x1}
