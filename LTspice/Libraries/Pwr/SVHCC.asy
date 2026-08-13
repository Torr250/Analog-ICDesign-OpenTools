Version 4
SymbolType CELL
LINE Normal 13 -20 -11 -20
LINE Normal -11 -20 -21 0
LINE Normal -21 0 -11 20
LINE Normal -11 20 13 20
LINE Normal 13 20 23 0
LINE Normal 23 0 13 -20
LINE Normal 16 25 -14 -25 2
LINE Normal -14 25 16 -25 2
LINE Normal 28 0 -25 0 2
LINE Normal 15 -9 1 0
LINE Normal 14 -7 15 -9
LINE Normal 13 -9 15 -9
LINE Normal 50 -64 44 -64
LINE Normal 50 -59 50 -69
LINE Normal 58 -64 50 -59
LINE Normal 50 -69 58 -64
LINE Normal 64 -64 58 -64
LINE Normal 50 -48 44 -48
LINE Normal 50 -43 50 -53
LINE Normal 58 -48 50 -43
LINE Normal 50 -53 58 -48
LINE Normal 50 -16 44 -16
LINE Normal 50 -11 50 -21
LINE Normal 58 -16 50 -11
LINE Normal 50 -21 58 -16
LINE Normal 64 -16 58 -16
LINE Normal 50 0 44 0
LINE Normal 50 5 50 -5
LINE Normal 58 0 50 5
LINE Normal 50 -5 58 0
LINE Normal 50 32 44 32
LINE Normal 50 37 50 27
LINE Normal 58 32 50 37
LINE Normal 50 27 58 32
LINE Normal 64 32 58 32
LINE Normal 50 48 44 48
LINE Normal 50 53 50 43
LINE Normal 58 48 50 53
LINE Normal 50 43 58 48
RECTANGLE Normal 64 64 -64 -80
CIRCLE Normal 64 -45 58 -51
CIRCLE Normal 64 3 58 -3
CIRCLE Normal 64 51 58 45
TEXT -64 -64 Left 2 a*
TEXT -64 -48 Left 2 b*
TEXT -64 -32 Left 2 c*
TEXT -64 16 Left 2 a
TEXT -64 32 Left 2 b
TEXT -64 48 Left 2 c
TEXT 0 68 Bottom 2 _EN
TEXT 0 -48 Center 2 SVHCC
WINDOW 0 -64 -88 Left 2
SYMATTR Prefix x
SYMATTR SpiceModel SVHCC
SYMATTR SpiceLine hi=0.5 ho=1 Vhigh=1 Vlow=0 dt=1u
SYMATTR Description Simple space-vector hysteresis current controller. {Vhigh/Vlow} [V] - output logic levels, {dt} [s] - dead-time, {hi/ho} [V] the inner/outer bands. {*} inputs are the references.
SYMATTR ModelFile pwr.sub
PIN -64 -64 NONE 3
PINATTR PinName ia*
PINATTR SpiceOrder 1
PIN -64 -48 NONE 3
PINATTR PinName ib*
PINATTR SpiceOrder 2
PIN -64 -32 NONE 3
PINATTR PinName ic*
PINATTR SpiceOrder 3
PIN -64 16 NONE 3
PINATTR PinName ia
PINATTR SpiceOrder 4
PIN -64 32 NONE 3
PINATTR PinName ib
PINATTR SpiceOrder 5
PIN -64 48 NONE 3
PINATTR PinName ic
PINATTR SpiceOrder 6
PIN 64 -64 NONE 3
PINATTR PinName Sa
PINATTR SpiceOrder 7
PIN 64 -48 NONE 2
PINATTR PinName _Sa
PINATTR SpiceOrder 8
PIN 64 -16 NONE 3
PINATTR PinName Sb
PINATTR SpiceOrder 9
PIN 64 0 NONE 2
PINATTR PinName _Sb
PINATTR SpiceOrder 10
PIN 64 32 NONE 3
PINATTR PinName Sc
PINATTR SpiceOrder 11
PIN 64 48 NONE 2
PINATTR PinName _Sc
PINATTR SpiceOrder 12
PIN 0 64 NONE 0
PINATTR PinName _EN
PINATTR SpiceOrder 13
