Version 4
SymbolType CELL
LINE Normal -19 -10 -19 9
LINE Normal 3 -10 -19 -10
LINE Normal 3 9 3 -10
LINE Normal 7 9 3 9
LINE Normal -24 9 -19 9
LINE Normal -13 9 -19 9 2
LINE Normal -13 -10 -13 9 2
LINE Normal -28 4 -32 4
LINE Normal -32 -4 -28 -4
LINE Normal -24 0 -28 4
LINE Normal -28 -4 -24 0
RECTANGLE Normal 16 16 -32 -16
WINDOW 40 -8 24 Center 2
SYMATTR SpiceLine2 dt=1u
SYMATTR Prefix x
SYMATTR SpiceModel DeadTime
SYMATTR Description Dead time block, dt>0 [s]. {Vhigh,Vlow} - logic levels, {ref} input's logic threshold.
SYMATTR ModelFile filt.sub
SYMATTR SpiceLine Vhigh=1 Vlow=0 ref=0.5
PIN -32 0 NONE 8
PINATTR PinName in
PINATTR SpiceOrder 1
PIN 16 0 NONE 8
PINATTR PinName out
PINATTR SpiceOrder 2
