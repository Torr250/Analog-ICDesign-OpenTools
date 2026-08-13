Version 4
SymbolType CELL
LINE Normal -44 -4 -48 -4
LINE Normal -40 0 -44 -4
LINE Normal -44 4 -40 0
LINE Normal -48 4 -44 4
LINE Normal 16 -16 32 -16
LINE Normal -16 16 16 -16
LINE Normal -32 16 -16 16
RECTANGLE Normal 48 24 -48 -24
WINDOW 0 -48 -32 Left 2
WINDOW 39 0 33 Center 2
WINDOW 38 0 0 Center 2
SYMATTR SpiceLine Kp=0 Ki=0 Kd=0
SYMATTR SpiceModel PID
SYMATTR SpiceLine2 Ts=1m method=0
SYMATTR Prefix x
SYMATTR Description Universal PID controller with anti-windup: Kp+Ki/s+sKd, or Kp+Ki*Ts/(1-z)+Kd*Ts*(1-z). Any combination of {Kp}, {Ki}, or {Kd} works. Select {PIDd} model for the digital version, {Ts} [s] is the sampling time (no internal s&h).
SYMATTR ModelFile filt.sub
SYMATTR Value2 min=0 max=0 Klim=1
SYMATTR Value ic=0
PIN -48 0 NONE 8
PINATTR PinName in+
PINATTR SpiceOrder 1
PIN 48 0 NONE 8
PINATTR PinName out
PINATTR SpiceOrder 2
