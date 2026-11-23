#!/usr/bin/env python3
"""Parallelism benchmark for isfpn: runs a test matrix in one go and prints a final table.

Run it from a case directory (it writes bench/<label>/ with timing.json, phase_noise.csv and the log of every run):

    cd cases/cs_n4_gf180mcuD
    python3 ../../tools/bench_jobs.py cs.json                # tests 1-5 (about 1 h on the CS case)
    python3 ../../tools/bench_jobs.py cs.json --tests 1,3    # only some tests
    python3 ../../tools/bench_jobs.py cs.json --tests 6 --jobs 8   # OpenMP wait policy switch
    python3 ../../tools/bench_jobs.py cs.json --dry-run      # list the runs without executing

Tests
  1  correctness: jobs=1 (reference) vs jobs=8; the CSV must be identical
  2  jobs x threads at a fixed budget of --budget cores (default 8): 8x1, 4x2, 2x4, 1x8
  3  jobs=12 and jobs=16 (hyperthreads / oversubscription)
  4  fast settings (tstep 2p, reltol 1e-4, nper 10, settle 15n, tstop 60n) with jobs=8; L must stay within ~0.1 dB
  5  repeatability: --repeat (3) runs of jobs=8
  6  OMP_WAIT_POLICY with threads=1: auto vs passive vs active vs none, with --jobs (default 8)
  7  threads=2 with policy none / passive: 4x2 and 8x2 (the latter needs 16 cores)

Every run is compared against the reference run (the first jobs=1 run, or the first run executed) with the maximum
difference of L_total [dB] over all offsets. Runs already done (bench/<label>/timing.json exists) are skipped unless --force.
Settings of tests 4 are applied to a temporary copy of the config, the original is never modified.
"""
import argparse, json, os, shutil, subprocess, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ISFPN = os.path.join(os.path.dirname(HERE), "isfpn.py")
FAST = {"tstep": "2p", "reltol": 1e-4, "nper": 10, "settle": 15e-9, "tstop": 60e-9}


def plan(a):
    t = {int(x) for x in a.tests.split(",")}
    runs = []          # (label, test, jobs, threads, omp, fast)
    B = a.budget
    if 1 in t:
        runs += [("j1_t1", 1, 1, 1, "auto", False), ("j8_t1", 1, 8, 1, "auto", False)]
    if 2 in t:
        for j in (B, B // 2, B // 4, 1):
            if j >= 1: runs.append((f"j{j}_t{B // j}", 2, j, B // j, "auto", False))
    if 3 in t:
        runs += [("j12_t1", 3, 12, 1, "auto", False), ("j16_t1", 3, 16, 1, "auto", False)]
    if 4 in t:
        runs += [(f"fast_j{a.jobs}_t1", 4, a.jobs, 1, "auto", True)]
    if 5 in t:
        runs += [(f"j8_t1_rep{k + 1}", 5, 8, 1, "auto", False) for k in range(a.repeat)]
    if 7 in t:   # threads > 1 with the policy left alone (the old 'passive' penalised them): 4x2 and 8x2 (needs 16 cores)
        runs += [("j4_t2_none", 7, 4, 2, "none", False), ("j8_t2_none", 7, 8, 2, "none", False), ("j4_t2_passive", 7, 4, 2, "passive", False)]
    if 6 in t:
        runs += [(f"omp_{p}_j{a.jobs}", 6, a.jobs, 1, p, False) for p in ("auto", "passive", "active", "none")]
    seen, out = set(), []
    for r in runs:                      # drop duplicates (same label)
        if r[0] not in seen: seen.add(r[0]); out.append(r)
    return out


def load_L(path):
    return np.genfromtxt(path, delimiter=",", skip_header=1)[:, 3]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config"); ap.add_argument("--tests", default="1,2,3,4,5")
    ap.add_argument("--jobs", type=int, default=8, help="jobs for tests 4 and 6 (default 8)")
    ap.add_argument("--budget", type=int, default=8, help="cores budget for test 2 (default 8)")
    ap.add_argument("--repeat", type=int, default=3, help="runs of test 5 (default 3)")
    ap.add_argument("--force", action="store_true"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    runs = plan(a)
    if a.dry_run:
        for r in runs: print("  %-18s test %d  jobs=%-2d threads=%-2d omp=%-7s %s" % (r[0], r[1], r[2], r[3], r[4], "fast" if r[5] else ""))
        return
    cfg0 = json.load(open(a.config)); os.makedirs("bench", exist_ok=True)
    rows, ref = [], None
    for label, test, jobs, thr, omp, fast in runs:
        d = os.path.join("bench", label); os.makedirs(d, exist_ok=True)
        tj = os.path.join(d, "timing.json")
        if os.path.exists(tj) and not a.force:
            print(f"[skip] {label} (already done)")
        else:
            cfgname = a.config
            if fast:
                cfgname = os.path.join(d, "fast_" + os.path.basename(a.config))
                json.dump({**cfg0, **FAST}, open(cfgname, "w"), indent=1)
            env = dict(os.environ, ISFPN_JOBS=str(jobs), ISFPN_THREADS=str(thr), ISFPN_OMP_WAIT=omp)
            print(f"[run ] {label}: jobs={jobs} threads={thr} omp={omp}{' fast' if fast else ''} ...", flush=True)
            t0 = time.time()
            with open(os.path.join(d, "run.log"), "w") as lg:
                rc = subprocess.run([sys.executable, ISFPN, cfgname, "all", "--here"], env=env, stdout=lg, stderr=subprocess.STDOUT).returncode
            if rc != 0 or not os.path.exists("timing.json"):
                print(f"       FAILED rc={rc} (see {d}/run.log)"); rows.append((label, test, jobs, thr, omp, None, None, None)); continue
            for f in ("timing.json", "phase_noise.csv"): shutil.copy(f, os.path.join(d, f))
            print(f"       {time.time() - t0:.0f} s")
        T = json.load(open(tj)); L = load_L(os.path.join(d, "phase_noise.csv"))
        if ref is None and not fast: ref = (label, L)
        rows.append((label, test, jobs, thr, omp, T, L, fast))
    # --- final table
    ok = [r for r in rows if r[5] is not None]
    bj = os.path.join('bench', 'j1_t1', 'timing.json')
    base = next((r[5]["total_s"] for r in ok if r[2] == 1 and r[3] == 1 and not r[7]), None)
    if base is None and os.path.exists(bj): base = json.load(open(bj))["total_s"]   # earlier execution
    print("\n%-18s %2s %4s %3s %-8s %8s %8s %6s %9s %7s %s" % ("run", "T", "jobs", "thr", "omp", "total[s]", "isf[s]", "x", "dL_max[dB]", "ident", ""))
    for label, test, jobs, thr, omp, T, L, fast in rows:
        if T is None: print("%-18s %2d %4d %3d %-8s   FAILED" % (label, test, jobs, thr, omp)); continue
        st = T["stages_s"]; dL = float(np.nanmax(np.abs(L - ref[1]))) if ref and len(L) == len(ref[1]) else float("nan")
        sp = base / T["total_s"] if base else float("nan")
        print("%-18s %2d %4d %3d %-8s %8.0f %8.0f %6.2f %9.4f %7s %s" % (label, test, jobs, thr, omp, T["total_s"], st.get("isf", float("nan")), sp, dL, "yes" if dL == 0 else "no", "(fast settings)" if fast else ""))
    print("\nx = speed-up vs the jobs=1 run (needs it in the matrix); dL_max = max |L_total - reference| over all offsets; reference = %s" % (ref[0] if ref else "-"))
    old = {}                                      # accumulate: runs of earlier executions are kept
    if os.path.exists("bench/summary.json"):
        try: old = {e["run"]: e for e in json.load(open("bench/summary.json"))}
        except Exception: pass
    for r in rows: old[r[0]] = {"run": r[0], "test": r[1], "jobs": r[2], "threads": r[3], "omp": r[4], "timing": r[5]}
    json.dump(list(old.values()), open("bench/summary.json", "w"), indent=1)


if __name__ == "__main__":
    main()
