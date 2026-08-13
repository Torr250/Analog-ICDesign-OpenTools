Version 4
SymbolType BLOCK
LINE Normal -40 0 -48 -8
LINE Normal -48 8 -40 0
LINE Normal 48 -64 -48 -64
LINE Normal 48 64 48 -64
LINE Normal 48 64 -48 64
LINE Normal -48 64 -48 -64
CIRCLE Normal 64 40 48 24
TEXT -40 0 Left 2 CLK
TEXT 48 -32 Right 2 Q[0:15]
TEXT 48 32 Right 2 _Q[0:15]
TEXT -32 64 Bottom 2 S
TEXT 32 64 Bottom 2 R
WINDOW 0 -48 -71 Left 2
SYMATTR Description A 16 bit asynchronous counter. {Vhigh}, {Vlow}, {td} are LTspice's specific parameters for A-devices. Note: rename BOTH outputs with bus names, even if only one is used.
SYMATTR ModelFile 0101.sub
SYMATTR Prefix x
SYMATTR SpiceModel CNT16asy
SYMATTR SpiceLine N=16 Vigh=1 Vlow=0 td=10n
PIN -48 0 NONE 8
PINATTR PinName -1
PINATTR SpiceOrder 1
PIN -32 64 NONE 1
PINATTR PinName 999
PINATTR SpiceOrder 2
PIN 32 64 NONE 1
PINATTR PinName 666
PINATTR SpiceOrder 3
PIN 48 -32 NONE 1
PINATTR PinName [100:115]
PINATTR SpiceOrder 4
PIN 64 32 NONE 17
PINATTR PinName [200:215]
PINATTR SpiceOrder 5
