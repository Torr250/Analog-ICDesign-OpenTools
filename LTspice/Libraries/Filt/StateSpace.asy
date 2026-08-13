Version 4
SymbolType CELL
LINE Normal -60 -4 -64 -4
LINE Normal -56 0 -60 -4
LINE Normal -60 4 -56 0
LINE Normal -64 4 -60 4
RECTANGLE Normal 48 32 -64 -32
TEXT -8 -14 Center 2 x'=Ax+Bu
TEXT -7 14 Center 2 y=Cx+Du
WINDOW 38 -64 -39 Left 2
SYMATTR SpiceModel 1st
SYMATTR Prefix x
SYMATTR ModelFile statespace.sub
SYMATTR Description 1st/2nd/3rd order, SISO, state-space equations.
SYMATTR Value A11=0 A12=0 A13=0 B11=0
SYMATTR Value2 A21=0 A22=0 A23=0 B21=0
SYMATTR SpiceLine A31=0 A32=0 A33=0 B31=0
SYMATTR SpiceLine2 C11=0 C12=0 C13=0 D11=0 ic1=0 ic2=0 ic3=0
PIN -64 0 NONE 8
PINATTR PinName in
PINATTR SpiceOrder 1
PIN 48 0 NONE 8
PINATTR PinName out
PINATTR SpiceOrder 2
