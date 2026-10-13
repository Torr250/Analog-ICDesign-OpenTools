"""test3_mc_mm_pfet03v3_3000.cir: mismatch (mm), pfet_03v3 only, 3000 runs in LTspice.

Reference: ngspice with 6000 runs of the same library (gauss -> agauss, different seeds).
Writes only that netlist into final/gf180mcuD_ltspice_min.
"""
import shutil, tempfile
from pathlib import Path
import gf180_tests as t, gf180_tests2 as t2

dst = Path("final/gf180mcuD_ltspice_min")
GEO = [("pfet_03v3", 0.55, 2)]
N_REF, N_LT = 6000, 3000

REPS = [
    ("with 03v3, 06v0 and 05v0", "with pfet_03v3 only"), ("of id0..id5", "of id0"),
    ("~10 % relative on sigma/mean", "~3 % relative on sigma/mean"),
    ("(3000 runs).", "(3000 runs, ~1.3 % uncertainty per side)."),
]
ng = shutil.which("ngspice")
tmp = Path(tempfile.mkdtemp(prefix="gf180t4_"))
t2.MC3_GEOS = GEO          # write_test3 reads this
t.MC_GEOS = GEO            # ng_mc / mc_netlist read this
for d, _, _ in GEO:
    vd, vg = t._bias(d)
    t.VD_MC[d], t.VG_MC[d] = vd, vg
ref = t.stats(t.ng_mc(ng, dst, "mm", tmp, N_REF))
t2.write_test3(tmp, "mm", ref)      # written to tmp, not to dst
s = (tmp / "test3_mc_mm.cir").read_text()
s = s.replace("300 runs", f"{N_LT} runs").replace("run 1 300 1", f"run 1 {N_LT} 1").replace("(300 runs)", f"({N_LT} runs)")
for a, b in REPS:
    s = s.replace(a, b)
(dst / "test3_mc_mm_pfet03v3_3000.cir").write_text(s)
print(ref)
