Version 4
SymbolType CELL
LINE Normal -16 16 -16 -16
LINE Normal -12 10 -16 16
LINE Normal -20 10 -16 16
LINE Normal 16 -16 16 16
LINE Normal 12 -10 16 -16
LINE Normal 20 -10 16 -16
LINE Normal -24 32 -16 24
LINE Normal -8 32 -16 24
LINE Normal -28 4 -32 4
LINE Normal -32 -4 -28 -4
LINE Normal -24 0 -28 -4
LINE Normal -28 4 -24 0
LINE Normal 16 32 21 27
LINE Normal 16 32 11 27
RECTANGLE Normal 32 32 -32 -32
TEXT 0 0 Center 2 N
WINDOW 0 -32 -40 Left 2
SYMATTR SpiceLine f0=1k N=2 index=0
SYMATTR Prefix x
SYMATTR SpiceModel UpDnSpl
SYMATTR Description Up-/downsampler. {f0} [Hz] sets the unscaled sampling frequency, N<-1 means downsampling, N>1 - upsampling (integer) and SH=<0,1> disables (used in .AC)/enables(forces, used in .TRAN) a S&H at the output. External synchronization at pin '3' (Rclkin=1G).
SYMATTR ModelFile filt.sub
PIN -32 0 NONE 8
PINATTR PinName in+
PINATTR SpiceOrder 1
PIN 32 0 NONE 8
PINATTR PinName out
PINATTR SpiceOrder 2
PIN -16 32 NONE 8
PINATTR PinName 3
PINATTR SpiceOrder 3
PIN 16 32 NONE 8
PINATTR PinName 4
PINATTR SpiceOrder 4
