v {xschem version=3.4.8RC file_version=1.2}
G {}
K {}
V {}
S {}
F {}
E {}
T {https://www.engineerwikis.com/wikis/backannotation-in-xschem
https://xschem.sourceforge.io/stefan/xschem_man/tutorial_ngspice_backannotation.html
https://www.up-microlab.org/resources/tutorials/tutorial-using-ngspice/} 590 230 0 0 0.25 0.25 {}
T {Voltages [V]} 50 430 0 0 0.25 0.25 {}
T {Ratios} 290 360 0 0 0.25 0.25 {}
T {Capacitances [F]} 50 640 0 0 0.25 0.25 {}
T {Conductances [S]} 50 570 0 0 0.25 0.25 {}
T {CGS = CGS_channel + CGS_overlap} 120 660 0 0 0.25 0.25 {}
T {CGB = CGB_channel + CGB_overlap} 120 690 0 0 0.25 0.25 {}
T {CGD = CGD_channel + CGD_overlap} 120 720 0 0 0.25 0.25 {}
T {CBD = CBD0 + CBDSW0} 120 750 0 0 0.25 0.25 {}
T {CBS = CBS0 + CBSSW0} 120 780 0 0 0.25 0.25 {}
T {Drain Area Diffusion Capacitance} 120 930 0 0 0.25 0.25 {}
T {Drain Perimeter Diffusion Capacitance} 120 960 0 0 0.25 0.25 {}
T {Source Area Diffusion Capacitance} 120 990 0 0 0.25 0.25 {}
T {Source Perimeter Diffusion Capacitance} 120 1020 0 0 0.25 0.25 {}
T {Diffusion Capacitances [F]} 50 910 0 0 0.25 0.25 {}
T {Transconductance Efficiency [S]
gmID = gm/ID} 350 380 0 0 0.25 0.25 {}
T {Intrisnic Gain [V/V]
Aintr = gm/gds = gm*ro} 350 430 0 0 0.25 0.25 {}
T {Transit Frequency [Hz]
ft = gm/2*pi*cgg} 350 480 0 0 0.25 0.25 {}
T {Early Voltage Reciprocal [S]
gdsID = gds/ID} 350 530 0 0 0.25 0.25 {}
T {MOSFET Operating Points and Ratios:} 40 310 0 0 0.4 0.4 {}
T {Print Variables Examples} -440 320 0 0 0.4 0.4 {}
T {To print at the schematic operating points add:
ngspice_get_expr.sym from the symbols and 
modify "note" for the desired value.
Note: Need to save the operating point first

Print Current
node="[to_eng [ngspice::get_node \{i(@m.xm1.m1[id])\}]]"
node="[to_eng [ngspice::get_node \{i(id1)\}]]"

Print Voltage
node="[to_eng [ngspice::get_voltage \{@m.xm1.m1[vdsat]\}]]"
node="[to_eng [ngspice::get_voltage \{vdsat1\}]]"

Print Capacitance/Transconductance
node="[to_eng [ngspice::get_node \{@m.xm1.m1[gm]\}]]"
node="[to_eng [ngspice::get_node \{gm1\}]]"

to_eng : Engineer notation

NGSpice Notation
@m=mosfet
.xm1 Subcircuit number (from schematic)
.m1  Transistor number (from library)
[id] Parameter, in this case id
@m.xm1.m1[id]
} -440 510 0 0 0.25 0.25 {}
T {Ctrl-Click to annotate operating point data.} -510 150 0 0 0.3 0.3 {layer=15}
T {Currents [A]} 50 360 0 0 0.25 0.25 {}
T {Vth not recognized
in ngspice model1} 100 490 0 0 0.2 0.2 {}
T {Gate and Drain Capacitances [F]} 50 820 0 0 0.25 0.25 {}
T {CGG = CGS + CGB + CGD, not recognized by ngspice Model1} 110 850 0 0 0.25 0.25 {}
T {CDD = CDB + CGD, not recognized by ngspice Model1} 110 880 0 0 0.25 0.25 {}
N 80 30 120 30 {lab=VGS}
N 180 170 230 170 {lab=GND}
N 230 120 230 170 {lab=GND}
N 230 30 230 60 {lab=#net1}
N 160 60 160 170 {lab=GND}
N 180 170 180 200 {lab=GND}
N 50 30 50 50 {lab=VGS}
N 50 30 80 30 {lab=VGS}
N 160 170 180 170 {lab=GND}
N 230 170 300 170 {lab=GND}
N 300 90 300 170 {lab=GND}
N 160 -30 160 0 {lab=#net2}
N 300 -30 300 30 {lab=#net3}
N 160 30 230 30 {lab=#net1}
N 160 -30 200 -30 {lab=#net2}
N 260 -30 300 -30 {lab=#net3}
C {nmos4.sym} 140 30 0 0 {name=M1 model=xnch w=2u l=0.18u del=0 m=1 spiceprefix=X}
C {gnd.sym} 180 200 0 0 {name=l4 lab=GND}
C {vsource.sym} 230 90 2 0 {name=V1 value=0 savecurrent=false}
C {gnd.sym} 50 110 0 0 {name=l6 lab=GND}
C {lab_wire.sym} 70 30 0 0 {name=p1 sig_type=std_logic lab=VGS}
C {code_shown.sym} 590 320 0 0 {name=NGSPICE
only_toplevel=false 
value="
.include /foss/designs/cmos101/razavi_cmos_lambda_0p1.lib
.param vdd=1.8 vgs=1
.option savecurrents
.control
  save @m.xm1.m1[id]
  save @m.xm1.m1[vdsat]
  save @m.xm1.m1[vgs]
  save @m.xm1.m1[vds]
  save @m.xm1.m1[vbs]
  save @m.xm1.m1[vth]
  save @m.xm1.m1[gm]
  save @m.xm1.m1[gmb]
  save @m.xm1.m1[gds]
  save @m.xm1.m1[cgs]
  save @m.xm1.m1[cgb]
  save @m.xm1.m1[cgd]
  save @m.xm1.m1[cbd]
  save @m.xm1.m1[cbs]
  save @m.xm1.m1[cbd0]
  save @m.xm1.m1[cbdsw0]
  save @m.xm1.m1[cbs0]
  save @m.xm1.m1[cbssw0]
  save @m.xm1.m1[cgg]
  save @m.xm1.m1[cdd]
  save all
  op
  let gm1 = @m.xm1.m1[gm]
  let id1 = @m.xm1.m1[id]
  let vdsat1 = @m.xm1.m1[vdsat]
  let gmid1 = gm1/id1
  print @m.xm1.m1[id]
  print @m.xm1.m1[gm]
  print @m.xm1.m1[vdsat]
  print gm1
  print id1
  print vdsat1
  print gmid1
  write 01_ICS_NMOS.raw
.endc
"}
C {ammeter.sym} 230 -30 1 0 {name=Vmeas savecurrent=true spice_ignore=0}
C {vsource.sym} 50 80 0 0 {name=V2 value="\{vgs\} ac 1" savecurrent=false}
C {vsource.sym} 300 60 0 0 {name=V3 value=\{vdd\} savecurrent=false}
C {ngspice_probe.sym} 290 -30 0 0 {name=r1}
C {ngspice_get_expr.sym} 60 620 0 0 {name=r2 
node="[to_eng [ngspice::get_node \{@m.xm1.m1[gm]\}]]"
descr="gm"}
C {ngspice_get_expr.sym} -440 400 0 0 {name=r4 
node="[to_eng [ngspice::get_node \{gm1\}]]"
descr="gm1 variable"}
C {ngspice_get_expr.sym} 60 410 0 0 {name=r5 
node="[to_eng [ngspice::get_node \{i(@m.xm1.m1[id])\}]]"
descr="id"}
C {ngspice_get_expr.sym} -440 440 0 0 {name=r6 
node="[to_eng [ngspice::get_node \{i(id1)\}]]"
descr="id1 variable"}
C {ngspice_get_expr.sym} -440 480 0 0 {name=r7 
node="[to_eng [ngspice::get_voltage \{vdsat1\}]]"
descr="vdsat1 variable"}
C {ngspice_get_expr.sym} -300 440 0 0 {name=r8 
node="[to_eng [ngspice::get_node \{gm1\}] / [ngspice::get_node \{i(id1)\}]]"
descr="gmID1 Calculation"}
C {ngspice_get_expr.sym} 60 550 0 0 {name=r9 
node="[to_eng [ngspice::get_voltage \{@m.xm1.m1[vdsat]\}]]"
descr="vdsat"}
C {ngspice_get_expr.sym} -300 400 0 0 {name=r10 
node="[to_eng [ngspice::get_node \{gmID1\}]]"
descr="gmID1 variable"}
C {ngspice_get_expr.sym} 180 620 0 0 {name=r20 
node="[to_eng [ngspice::get_node \{@m.xm1.m1[gds]\}]]"
descr="gds"}
C {ngspice_get_expr.sym} 60 690 0 0 {name=r21 
node="[to_eng [ngspice::get_node \{@m.xm1.m1[cgs]\}]]"
descr="cgs"}
C {ngspice_get_expr.sym} 60 720 0 0 {name=r22 
node="[to_eng [ngspice::get_node \{@m.xm1.m1[cgb]\}]]"
descr="cgb"}
C {ngspice_get_expr.sym} 60 750 0 0 {name=r23 
node="[to_eng [ngspice::get_node \{@m.xm1.m1[cgd]\}]]"
descr="cgd"}
C {ngspice_get_expr.sym} 60 780 0 0 {name=r24 
node="[to_eng [ngspice::get_node \{@m.xm1.m1[cbd]\}]]"
descr="cbd"}
C {ngspice_get_expr.sym} 60 810 0 0 {name=r25 
node="[to_eng [ngspice::get_node \{@m.xm1.m1[cbs]\}]]"
descr="cbs"}
C {ngspice_get_expr.sym} 60 960 0 0 {name=r26 
node="[to_eng [ngspice::get_node \{@m.xm1.m1[cbd0]\}]]"
descr="cbd0"}
C {ngspice_get_expr.sym} 60 990 0 0 {name=r27 
node="[to_eng [ngspice::get_node \{@m.xm1.m1[cbdsw0]\}]]"
descr="cbdsw0"}
C {ngspice_get_expr.sym} 60 1020 0 0 {name=r28 
node="[to_eng [ngspice::get_node \{@m.xm1.m1[cbs0]\}]]"
descr="cbs0"}
C {ngspice_get_expr.sym} 60 1050 0 0 {name=r29 
node="[to_eng [ngspice::get_node \{@m.xm1.m1[cbssw0]\}]]"
descr="cbssw0"}
C {ngspice_get_expr.sym} 60 480 0 0 {name=r30 
node="[to_eng [ngspice::get_voltage \{@m.xm1.m1[vds]\}]]"
descr="vds"}
C {ngspice_get_expr.sym} 100 480 0 0 {name=r31 
node="[to_eng [ngspice::get_voltage \{@m.xm1.m1[vgs]\}]]"
descr="vgs"}
C {ngspice_get_expr.sym} 120 620 0 0 {name=r32 
node="[to_eng [ngspice::get_node \{@m.xm1.m1[gmb]\}]]"
descr="gmb"}
C {ngspice_get_expr.sym} 290 410 0 0 {name=r33 
node="[to_eng [ngspice::get_node \{@m.xm1.m1[gm]\}] / [ngspice::get_node \{i(@m.xm1.m1[id])\}]]"
descr="gmID1"}
C {ngspice_get_expr.sym} 290 460 0 0 {name=r34 
node="[to_eng [ngspice::get_node \{@m.xm1.m1[gm]\}] / [ngspice::get_node \{@m.xm1.m1[gds]\}]]"
descr="aintr"}
C {ngspice_get_expr.sym} 290 510 0 0 {name=r35 
node="[to_eng [ngspice::get_node \{@m.xm1.m1[gm]\}] / (2*acos(-1)*( [ngspice::get_node \{@m.xm1.m1[cgs]\}]+ [ngspice::get_node \{@m.xm1.m1[cgd]\}] + [ngspice::get_node \{@m.xm1.m1[cgb]\}] ) )]"
descr="ft"}
C {ngspice_get_expr.sym} 290 560 0 0 {name=r36 
node="[to_eng [ngspice::get_node \{@m.xm1.m1[gds]\}] / [ngspice::get_node \{i(@m.xm1.m1[id])\}]]"
descr="gdsID"}
C {launcher.sym} -450 190 0 0 {name=h1
descr="Annotate OP" 
tclcommand="set show_hidden_texts 1; xschem annotate_op"
}
C {ngspice_get_expr.sym} 140 480 0 0 {name=r3 
node="[to_eng [ngspice::get_voltage \{@m.xm1.m1[vbs]\}]]"
descr="vbs"}
C {ngspice_get_expr.sym} 60 520 0 0 {name=r11 
node="[to_eng [ngspice::get_voltage \{@m.xm1.m1[vth]\}]]"
descr="vth"}
C {ngspice_get_expr.sym} 110 410 0 0 {name=r12 
node="[to_eng [ngspice::get_node \{i(@m.xm1.m1[is])\}]]"
descr="is"}
C {ngspice_get_expr.sym} 160 410 0 0 {name=r13 
node="[to_eng [ngspice::get_node \{i(@m.xm1.m1[ig])\}]]"
descr="ig"}
C {ngspice_get_expr.sym} 200 410 0 0 {name=r14 
node="[to_eng [ngspice::get_node \{i(@m.xm1.m1[ib])\}]]"
descr="ib"}
C {ngspice_get_expr.sym} 50 870 0 0 {name=r15 
node="[to_eng [ngspice::get_node \{@m.xm1.m1[cgg]\}]]"
descr="cgg"}
C {ngspice_get_expr.sym} 50 900 0 0 {name=r16 
node="[to_eng [ngspice::get_node \{@m.xm1.m1[cdd]\}]]"
descr="cdd"}
