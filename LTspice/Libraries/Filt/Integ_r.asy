Version 4
SymbolType CELL
LINE Normal -19 14 -16 -10
LINE Normal -32 32 -32 -32
LINE Normal 32 0 -32 32
LINE Normal -32 -32 32 0
LINE Normal -18 14 -15 -10
LINE Normal 0 16 0 32
ARC Normal -25 19 -19 8 -24 18 -18 14
ARC Normal -25 19 -18 8 -24 18 -17 14
ARC Normal -9 -15 -15 -4 -10 -14 -16 -10
ARC Normal -9 -15 -16 -4 -10 -14 -17 -10
WINDOW 39 1 -41 Center 2
SYMATTR SpiceLine tau=1m
SYMATTR SpiceLine2 edge=0
SYMATTR Prefix x
SYMATTR SpiceModel Integ_r
SYMATTR Description Resetable integrator (bottom center pin) with external period control (pin in the corner). Anything connected to the 'TAU' pin overrides {tau}. sgn(tau)==sgn(V(out)), irrespective of 'TAU' pin. {edge} sets the behaviour of the reset: 0 means reset and hold reset, 1 means edge-triggered reset (mod()-like behaviour).
SYMATTR ModelFile filt.sub
SYMATTR Value2 ic=0
PIN -32 0 NONE 8
PINATTR PinName in
PINATTR SpiceOrder 1
PIN 32 0 NONE 8
PINATTR PinName out
PINATTR SpiceOrder 2
PIN 0 32 NONE 8
PINATTR PinName RESET
PINATTR SpiceOrder 3
PIN -32 32 NONE 8
PINATTR PinName TAU
PINATTR SpiceOrder 4
