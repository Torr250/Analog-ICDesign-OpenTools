Version 4
SymbolType CELL
LINE Normal -12 -4 -16 -4
LINE Normal -8 0 -12 -4
LINE Normal -12 4 -8 0
LINE Normal -16 4 -12 4
RECTANGLE Normal 32 16 -16 -16
ARC Normal 7 10 20 -11 6 0 20 0
ARC Normal 7 -10 -6 11 8 0 -6 0
ARC Normal 12 10 25 -11 11 0 25 0 2
ARC Normal 12 -10 -1 11 13 0 -1 0 2
WINDOW 39 8 -26 Center 2
SYMATTR SpiceLine f=50 phi=pi/4
SYMATTR Prefix x
SYMATTR SpiceModel LeadLag
SYMATTR Description Voltage-controlled phase-shift. {f} is in [Hz] and phi=<-inf:inf>. There are startup transients (shoud be a few periods, at most).
SYMATTR ModelFile filt.sub
PIN -16 0 NONE 8
PINATTR PinName in
PINATTR SpiceOrder 1
PIN 32 0 NONE 8
PINATTR PinName out
PINATTR SpiceOrder 2
PIN 0 16 NONE 8
PINATTR PinName ctl
PINATTR SpiceOrder 3
