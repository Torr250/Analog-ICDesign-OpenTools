Version 4
SymbolType BLOCK
LINE Normal -30 -3 -30 -21
LINE Normal -8 -3 -30 -3
LINE Normal -8 -21 -8 -3
LINE Normal -30 -21 -8 -21
LINE Normal -23 -7 -14 -16
LINE Normal 8 -3 8 -21
LINE Normal 30 -3 8 -3
LINE Normal 30 -21 30 -3
LINE Normal 8 -21 30 -21
LINE Normal 13 -7 13 -17
LINE Normal 18 -7 13 -7
LINE Normal 21 -7 21 -17
LINE Normal 26 -17 21 -17
LINE Normal 25 -12 21 -12
LINE Normal -16 19 -16 1
LINE Normal 15 19 -16 19
LINE Normal 15 1 15 19
LINE Normal -16 1 15 1
LINE Normal -13 6 -9 15
LINE Normal -5 6 -9 15
LINE Normal -30 -15 -36 -15
LINE Normal -36 -9 -30 -9
LINE Normal -36 10 -36 -9
LINE Normal -16 10 -36 10
LINE Normal 37 10 15 10
LINE Normal 37 -12 37 10
LINE Normal 30 -12 37 -12
LINE Normal 8 -12 -8 -12
RECTANGLE Normal 48 72 -48 -72
CIRCLE Normal -14 -7 -23 -16
CIRCLE Normal 11 15 4 6
ARC Normal -4 6 3 15 3 7 3 13
WINDOW 0 -48 -80 Left 2
SYMATTR Prefix x
SYMATTR SpiceModel PLL
SYMATTR SpiceLine f=50 kp=6.1 ki=81
SYMATTR Description Phase-locked loop. {f} [Hz] working frequency, {kp,ki} parameters for the active PI LF. Hidden: {ic} [V] initial frequency, {Kerr} quality factor for the adaptive SOGI.
SYMATTR ModelFile filt.sub
PIN -48 -64 LEFT 1
PINATTR PinName in
PINATTR SpiceOrder 1
PIN 48 -64 RIGHT 1
PINATTR PinName sin
PINATTR SpiceOrder 2
PIN 48 -32 RIGHT 1
PINATTR PinName cos
PINATTR SpiceOrder 3
PIN 48 32 RIGHT 1
PINATTR PinName freq
PINATTR SpiceOrder 4
PIN 48 64 RIGHT 1
PINATTR PinName theta
PINATTR SpiceOrder 5
