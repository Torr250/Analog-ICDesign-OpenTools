Version 4
SymbolType CELL
LINE Normal -32 -48 64 -48
LINE Normal -64 0 -32 -48
LINE Normal -32 48 -64 0
LINE Normal 64 48 -32 48
LINE Normal 64 -48 64 48
TEXT 64 0 Right 2 Q[0:15]
WINDOW 0 64 -39 Right 2
SYMATTR Prefix x
SYMATTR SpiceModel ADC16
SYMATTR Description 16 bit ADC, {N} bits conversion, {vhigh,vlow} output logic levels, {VinH,VinL} input range. Output is a bus.
SYMATTR ModelFile 0101.sub
SYMATTR SpiceLine N=16 VinH=32767 VinL=-32768
SYMATTR SpiceLine2 vhigh=1 vlow=0
PIN -64 0 LEFT 8
PINATTR PinName in
PINATTR SpiceOrder 1
PIN 64 0 NONE 1
PINATTR PinName [100:115]
PINATTR SpiceOrder 2
