Version 4
SymbolType CELL
LINE Normal 13 -20 -11 -20
LINE Normal -11 -20 -21 0
LINE Normal -21 0 -11 20
LINE Normal -11 20 13 20
LINE Normal 13 20 23 0
LINE Normal 23 0 13 -20
LINE Normal 16 25 -14 -25 2
LINE Normal -14 25 16 -25 2
LINE Normal 28 0 -25 0 2
LINE Normal 15 -9 1 0
LINE Normal 14 -7 15 -9
LINE Normal 13 -9 15 -9
LINE Normal 50 -64 44 -64
LINE Normal 50 -59 50 -69
LINE Normal 58 -64 50 -59
LINE Normal 50 -69 58 -64
LINE Normal 64 -64 58 -64
LINE Normal 50 -48 44 -48
LINE Normal 50 -43 50 -53
LINE Normal 58 -48 50 -43
LINE Normal 50 -53 58 -48
LINE Normal 50 -16 44 -16
LINE Normal 50 -11 50 -21
LINE Normal 58 -16 50 -11
LINE Normal 50 -21 58 -16
LINE Normal 64 -16 58 -16
LINE Normal 50 0 44 0
LINE Normal 50 5 50 -5
LINE Normal 58 0 50 5
LINE Normal 50 -5 58 0
LINE Normal 50 32 44 32
LINE Normal 50 37 50 27
LINE Normal 58 32 50 37
LINE Normal 50 27 58 32
LINE Normal 64 32 58 32
LINE Normal 50 48 44 48
LINE Normal 50 53 50 43
LINE Normal 58 48 50 53
LINE Normal 50 43 58 48
RECTANGLE Normal 64 64 -64 -80
CIRCLE Normal 64 -45 58 -51
CIRCLE Normal 64 3 58 -3
CIRCLE Normal 64 51 58 45
TEXT 0 68 Bottom 2 _EN
TEXT 0 -48 Center 2 SVPWM
WINDOW 0 -64 -88 Left 2
SYMATTR Prefix x
SYMATTR SpiceModel SVPWM
SYMATTR SpiceLine f=2k sym=0.5 Vhigh=1 Vlow=0
SYMATTR SpiceLine2 dt=1u td=1u a=-1 b=-1
SYMATTR Description Space-vector PWM. {fsw} [Hz] carrier, sym=<1m..999m> controls its symmetry, {Vhigh/Vlow} [V] output logic levels, {dt} [s] dead-time, {a} and {b} control the signum for the internal angle: atan2(b*v(b),a*v(a)). Quadrature input (sin/-cos).
SYMATTR ModelFile pwr.sub
PIN -64 -64 LEFT 3
PINATTR PinName A
PINATTR SpiceOrder 1
PIN -64 -32 LEFT 3
PINATTR PinName B
PINATTR SpiceOrder 2
PIN 64 -64 NONE 3
PINATTR PinName Sa
PINATTR SpiceOrder 3
PIN 64 -48 NONE 2
PINATTR PinName _Sa
PINATTR SpiceOrder 4
PIN 64 -16 NONE 3
PINATTR PinName Sb
PINATTR SpiceOrder 5
PIN 64 0 NONE 2
PINATTR PinName _Sb
PINATTR SpiceOrder 6
PIN 64 32 NONE 3
PINATTR PinName Sc
PINATTR SpiceOrder 7
PIN 64 48 NONE 2
PINATTR PinName _Sc
PINATTR SpiceOrder 8
PIN 0 64 NONE 0
PINATTR PinName _EN
PINATTR SpiceOrder 9
