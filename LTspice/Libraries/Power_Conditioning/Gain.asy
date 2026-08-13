Version 4
SymbolType CELL
LINE Normal -16 24 -16 -24
LINE Normal 32 0 -16 24
LINE Normal -16 -24 32 0
TEXT 1 0 Center 2 k
WINDOW 39 -16 32 Left 2
SYMATTR SpiceLine G=-1
SYMATTR SpiceLine2 db=0  Rout=1
SYMATTR Prefix x
SYMATTR SpiceModel Gain
SYMATTR Description Linear/logarithmic (db=<0,1>) gain/buffer, {Rout} [Ohm] defaults to 1.
SYMATTR ModelFile filt.sub
PIN -16 0 NONE 8
PINATTR PinName in
PINATTR SpiceOrder 1
PIN 32 0 NONE 8
PINATTR PinName out
PINATTR SpiceOrder 2
