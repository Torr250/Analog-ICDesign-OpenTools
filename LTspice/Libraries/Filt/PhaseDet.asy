Version 4
SymbolType BLOCK
LINE Normal -11 12 -6 -9
LINE Normal -28 -4 -32 -4
LINE Normal -24 0 -28 -4
LINE Normal -28 4 -24 0
LINE Normal -32 4 -28 4
RECTANGLE Normal 16 16 -32 -16
ARC Normal -13 -13 -1 -1 -12 -9 -3 -12
ARC Normal -6 -12 -2 -6 -3 -11 -6 -9
WINDOW 0 -31 -24 Left 2
WINDOW 39 -6 29 Center 2
SYMATTR SpiceLine f=1k deg=1
SYMATTR Prefix x
SYMATTR SpiceModel PhaseDet
SYMATTR Description Phase detector, {f} [Hz] input frequency, {deg} outputs degrees (1, default) or radians (0).
SYMATTR ModelFile filt.sub
PIN -32 0 NONE 1
PINATTR PinName in
PINATTR SpiceOrder 1
PIN 16 0 NONE 1
PINATTR PinName out
PINATTR SpiceOrder 2
