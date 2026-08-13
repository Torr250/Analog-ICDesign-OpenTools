Version 4
SymbolType CELL
LINE Normal -48 -64 -48 48
LINE Normal -48 48 48 48
LINE Normal 48 48 48 -64
LINE Normal 48 -64 -48 -64
LINE Normal -32 48 -16 32
LINE Normal -16 32 0 48
CIRCLE Normal 48 8 64 24
SYMATTR Prefix X
SYMATTR SpiceModel D_FF
SYMATTR SpiceLine vhigh=1 vlow=0 ref=0.5 td=10p tau=2p
SYMATTR ModelFile Digital_Lib.sub
PIN -48 -16 LEFT 8
PINATTR PinName D
PINATTR SpiceOrder 1
PIN -16 48 BOTTOM 8
PINATTR PinName CLK
PINATTR SpiceOrder 2
PIN 48 -32 RIGHT 8
PINATTR PinName Q
PINATTR SpiceOrder 3
PIN 64 16 RIGHT 20
PINATTR PinName QN
PINATTR SpiceOrder 4
