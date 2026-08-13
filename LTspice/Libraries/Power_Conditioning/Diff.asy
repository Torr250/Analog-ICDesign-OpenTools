Version 4
SymbolType CELL
LINE Normal -32 32 -32 -32
LINE Normal 32 0 -32 32
LINE Normal -32 -32 32 0
TEXT -28 0 Left 2 d/dt
WINDOW 39 -36 41 Left 2
SYMATTR SpiceLine tau=1m
SYMATTR Prefix x
SYMATTR SpiceModel Diff
SYMATTR Description Differentiator.
SYMATTR ModelFile filt.sub
PIN -32 0 NONE 8
PINATTR PinName in
PINATTR SpiceOrder 1
PIN 32 0 NONE 8
PINATTR PinName out
PINATTR SpiceOrder 2
