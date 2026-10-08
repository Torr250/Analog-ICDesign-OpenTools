[Noise Spectral Density - (V/Hz½ or A/Hz½)]
{
   Npanes: 2
   {
      traces: 3 {268959747,0,"v(u1:x1:m0)"} {268959748,0,"v(u1:x1:m0.1overf)"} {268959749,0,"v(u2:x1:m0.1overf)"}
      X: ('G',0,1e+07,0,1e+10)
      Y[0]: ('n',0,0,2e-09,1.8e-08)
      Y[1]: (' ',0,1e+308,10,-1e+308)
      Units: "V/Hz½" ('n',0,0,0,0,2e-09,1.8e-08)
      Log: 1 0 0
      GridStyle: 1
      PltMag: 1
      PltPhi: 1 0
   },
   {
      traces: 1 {524290,0,"v(onoise)"}
      X: ('G',0,1e+07,0,1e+10)
      Y[0]: ('n',0,0,2e-09,2.2e-08)
      Y[1]: (' ',0,1e+308,10,-1e+308)
      Units: "V/Hz½" ('n',0,0,0,0,2e-09,2.2e-08)
      Log: 1 0 0
      GridStyle: 1
      PltMag: 1
      PltPhi: 1 0
   }
}
[Transient Analysis]
{
   Npanes: 1
   {
      traces: 2 {268959747,0,"V(vin)"} {524290,0,"V(vout)"}
      X: ('n',0,0,2e-09,1.99999999999974e-08)
      Y[0]: (' ',1,-0.4,0.4,3.6)
      Y[1]: (' ',0,1e+308,10,-1e+308)
      Volts: (' ',0,0,1,-0.4,0.4,3.6)
      Log: 0 0 0
      GridStyle: 1
      PltMag: 1
      PltPhi: 1 0
   }
}
