Version 4
SymbolType CELL
LINE Normal -3 -10 -13 9
LINE Normal -3 -10 -3 9
LINE Normal 7 -10 -3 9
LINE Normal 7 -10 7 9
LINE Normal 7 9 9 5
LINE Normal 12 13 12 8
LINE Normal 15 10 11 10
RECTANGLE Normal 16 16 -16 -16
ARC Normal 4 11 7 15 4 11 9 14
ARC Normal 10 11 7 15 6 14 10 11
ARC Normal 12 12 15 15 12 13 15 13
WINDOW 39 1 26 Center 2
SYMATTR SpiceLine f=50 phi=0
SYMATTR Prefix x
SYMATTR SpiceModel wt
SYMATTR Description Mainly for grid PLL's angle (wt), but can be used like any other saw-tooth generator, fixed 2*pi amplitude. Specify {f} [Hz] and {phi} [rad].
SYMATTR ModelFile pwr.sub
PIN 16 0 NONE 8
PINATTR PinName out
PINATTR SpiceOrder 1
