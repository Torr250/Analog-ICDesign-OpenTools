Version 4
SymbolType BLOCK
LINE Normal -7 -22 -19 -22
LINE Normal -19 -22 -19 -26
LINE Normal -7 -26 -19 -26
LINE Normal -7 -22 -7 -26
LINE Normal -2 -24 -7 -24
LINE Normal 18 -28 18 -20
LINE Normal 20 -28 20 -20
LINE Normal 18 -24 13 -24
LINE Normal 25 -24 20 -24
LINE Normal -19 -24 -24 -24
LINE Normal -16 29 -9 18
LINE Normal -1 29 -16 29
LINE Normal -9 18 -1 29
LINE Normal 6 17 13 21
LINE Normal 13 29 13 21
LINE Normal 20 17 13 21
LINE Normal 6 10 -6 10
LINE Normal -6 10 -6 6
LINE Normal 6 6 -6 6
LINE Normal 6 10 6 6
LINE Normal 11 8 6 8
LINE Normal -6 8 -11 8
LINE Normal -7 -2 -11 -2
LINE Normal 11 -2 8 -2
LINE Normal -1 -14 -1 -6
LINE Normal 1 -14 1 -6
LINE Normal -1 -10 -11 -10
LINE Normal 11 -10 1 -10
LINE Normal -11 8 -11 -10
LINE Normal 11 8 11 -10
LINE Normal -11 -2 -14 -2
LINE Normal 14 -2 11 -2
RECTANGLE Normal 32 40 -32 -40
ARC Normal -2 -26 3 -21 -2 -24 3 -24
ARC Normal 3 -26 8 -21 3 -24 8 -24
ARC Normal 8 -26 13 -21 8 -24 13 -24
ARC Normal -7 -4 -2 1 -7 -2 -2 -2
ARC Normal -2 -4 3 1 -2 -2 3 -2
ARC Normal 3 -4 8 1 3 -2 8 -2
WINDOW 0 -32 -48 Left 2
SYMATTR Prefix X
SYMATTR SpiceModel RLC
SYMATTR SpiceLine V=400 f=50 NUL=1 DY=1 SP=0
SYMATTR SpiceLine2 P=10k QL=5k QC=2k Rd=1
SYMATTR ModelFile pwr.sub
SYMATTR Description Universal RLC load: {SP} series(0)/parallel(1), {DY} delta(0)/wye(1), {NUL} with(1)/without(0) null. {V} [V] peak L-L voltage, {f} [Hz] frequency. Powers: {P} [W] active, {QL} [VAr] inductive reactive, {QC} [VAr] capacitive reactive, {Rd} [Ohm] damping resistor (only active where L or C are directly driven).
PIN -32 -32 NONE 8
PINATTR PinName R
PINATTR SpiceOrder 1
PIN -32 0 NONE 8
PINATTR PinName S
PINATTR SpiceOrder 2
PIN -32 32 NONE 8
PINATTR PinName T
PINATTR SpiceOrder 3
PIN 32 0 NONE 8
PINATTR PinName NUL
PINATTR SpiceOrder 4
