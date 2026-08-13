Version 4
SymbolType CELL
LINE Normal 32 -48 -64 -48
LINE Normal 64 0 32 -48
LINE Normal 32 48 64 0
LINE Normal -64 48 32 48
LINE Normal -64 -48 -64 48
TEXT -64 0 Left 2 D[0:15]
TEXT 64 0 Right 2 out
WINDOW 0 -64 -39 Left 2
SYMATTR Prefix x
SYMATTR SpiceModel DAC16
SYMATTR Description 16 bit DAC. {N} bits conversion, {Vhigh,Vlow} output levels, {ref} input logic threshold. Unused inputs should be grounded.
SYMATTR ModelFile 0101.sub
SYMATTR SpiceLine N=16 Vhigh=32767 Vlow=-32768 ref=0.5
PIN -64 0 NONE 1
PINATTR PinName [100:115]
PINATTR SpiceOrder 1
PIN 64 0 NONE 8
PINATTR PinName -1
PINATTR SpiceOrder 2
