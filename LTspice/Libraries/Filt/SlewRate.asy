Version 4
SymbolType BLOCK
LINE Normal -24 0 -32 -8
LINE Normal -32 8 -24 0
LINE Normal 26 0 -20 0
LINE Normal -16 0 -16 -8
LINE Normal 0 8 0 -16
LINE Normal -12 -10 -16 0 2
LINE Normal 0 -16 -16 -8
LINE Normal 0 -16 12 14 2
LINE Normal 0 8 16 16
LINE Normal 16 16 16 0
LINE Normal 22 0 16 16 2
LINE Normal 24 -2 26 0
LINE Normal 26 0 24 2
RECTANGLE Normal 32 24 -32 -24
WINDOW 0 -31 -32 Left 2
SYMATTR Prefix x
SYMATTR SpiceModel SlewRate
SYMATTR SpiceLine Rise=1 Fall=-1
SYMATTR SpiceLine2 t0=1m
SYMATTR Description Slew-reate limiter. {t0} sets the time period over which the detection is done.
SYMATTR ModelFile filt.sub
PIN -32 0 NONE 0
PINATTR PinName in
PINATTR SpiceOrder 1
PIN 32 0 NONE 0
PINATTR PinName out
PINATTR SpiceOrder 2
