"""test3_mc_mm_1000.cir: mismatch (mm) with 1000 runs; ngspice reference with 3000 runs.

Writes only test3_mc_mm_1000.cir (the 300-run test3_mc_mm.cir is left untouched).
"""
import shutil, tempfile
from pathlib import Path
import gf180_tests as t, gf180_tests2 as t2

dst = Path("final/gf180mcuD_ltspice_min")
ng = shutil.which("ngspice")
tmp = Path(tempfile.mkdtemp(prefix="gf180t3_"))
t2._setup_geos()
ref = t.stats(t.ng_mc(ng, dst, "mm", tmp, 3000))
t2.write_test3(tmp, "mm", ref)  # written to tmp, not to dst
s = (tmp / "test3_mc_mm.cir").read_text()
s = s.replace("300 runs", "1000 runs").replace("run 1 300 1", "run 1 1000 1").replace("(300 runs)", "(1000 runs)")
(dst / "test3_mc_mm_1000.cir").write_text(s)
for r, (d, _, _) in zip(ref, t2.MC3_GEOS):
    print(d, r)
