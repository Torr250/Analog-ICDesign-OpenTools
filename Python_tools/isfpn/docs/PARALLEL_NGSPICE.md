# Running ngspice in parallel with isfpn: findings and recipe

Reference note (written 2026-10-27) with everything learned while speeding up `isfpn.py`. Intended for the user and for future
conversations with Claude: it says what was measured, what is only a hypothesis, and which settings to use.

## 1. TL;DR

| Setting | Value | Why |
|---|---|---|
| `jobs` / `ISFPN_JOBS` | number of **physical** cores (start with 4-8; 1 = serial) | `lin`, `isf`, `noise`, `blocks` split into independent ngspice processes |
| `threads` | `1` (default) | forces `set num_threads=1` in every `.control`; without it each ngspice may start many OpenMP threads |
| `OMP_WAIT_POLICY` / `ISFPN_OMP_WAIT` | `auto` (default): nothing in serial; with `jobs>1` `passive` only if `threads=0` or `jobs×threads` > visible CPUs, else untouched | with `threads=1` it makes no difference; with `threads>=2` `passive` is harmful (3.7) |
| `run_timeout` | 300 s (default) | a stalled run is stopped and its `r_<tag>.spice` is kept |

Best measured configuration on the user's 16-core machine: `ISFPN_JOBS=16` (150 s whole flow, 11.2×); add the fast settings (README 5.0) for exploration (78 s with 8 jobs).
Command: `ISFPN_VERBOSE=1 ISFPN_JOBS=16 python3 ../../isfpn.py cs.json all`
Results are **identical for every `jobs`** (maximum difference 0.0 in Γ, in the PSD of every transistor and in the mirror block).

## 2. What can be parallelized

| Stage | Parallel? | Unit of work |
|---|---|---|
| `baseline` | no | single transient; everything depends on it |
| `lin` | yes | one run per ΔQ (9) |
| `isf` | yes | one run per phase (n_phase+1 = 31) for each node, nodes in sequence |
| `noise` | yes | one process per transistor (its 30 phases run in sequence inside it) |
| `blocks` | yes | one process per block |
| `combine`, `compare`, `plots` | not needed | seconds, no ngspice |

Parallel runs need unique file names (`r_s_<node>_<phase>.spice`, `nzc_<dev>.spice`, `blk_run_<block>.spice`); this is already done.

## 3. Findings

### 3.1 Always-valid speed-up: do not simulate past the measured crossing (no parallelism needed)
A perturbed run only has to reach the crossing it measures (`cr[0] + (nper+3)·T0`), not the whole `tstop`.
Same results (difference 0.0), 12 s → 7 s per phase on the user's CS case (≈ 12 s × 0.58).

### 3.2 Parallel ngspice processes can stall: `OMP_WAIT_POLICY=passive`
- ngspice (built with OpenMP) uses threads that **busy-wait** by default. With several processes at once they compete for cores even when idle.
- Sandbox with 2 cores: 4 simultaneous runs took 13-42 s with the default policy and ~0.3 s with `passive` (finding from an earlier conversation).
- `OMP_NUM_THREADS=1` alone did **not** solve it.
- Reproduced here (ring, gf180mcuD, node N1, 31 phases, 2 cores): `jobs=2` without `passive` hit the 120 s timeout; with `passive` it took 26 s.

### 3.3 `passive` makes **serial** runs slower
Same test, serial: 36 s with the default policy, 2 min 17 s with `passive` (≈ 4×). So the tool sets `passive` only while a parallel pool is running and removes it afterwards (`Case.pmap`).

### 3.4 `set num_threads=N` in `.spiceinit`/`spinit` overrides `OMP_NUM_THREADS`
- Test (ring, 1 core): CPU time 0.21 s without `.spiceinit`; 0.38 s with `set num_threads=8` in `~/.spiceinit` even with `OMP_NUM_THREADS=1`.
- Putting `set num_threads=1` inside the netlist's `.control` forces one thread and gives the same result. The tool injects it into every `.control` it renders (core runs, per-transistor noise benches, block benches). Config key `threads` (default 1; `0` = leave ngspice alone).
- User's container (IIC-OSIC-TOOLS, Docker): `docker stats` showed **805 % CPU** while a serial run was going, i.e. each ngspice used ~8 cores. This matches an inherited `num_threads`. **Hypothesis:** the contents of the container's `.spiceinit`/`spinit` were not inspected. After the `threads` change the user reported one process uses 100 % CPU.

### 3.5 Measurements on the user's machine (CS gf180mcuD, 5 nodes × 31 phases, Docker, 16 logical CPUs)

| Run | Time per phase | Notes |
|---|---|---|
| Original code, serial | 12.2 s | looked like a hang; ~50 % CPU |
| With crossing trim, serial | 7.0 s | ISF stage ≈ 18 min |
| `jobs=2`, **before** the `threads` fix | 14.7 s per run (2 at once) | no gain (7.35 s/phase of throughput); ngspice was using ~8 threads each |
| `jobs=8`, **after** the `threads` fix | 10.4 s per run (8 at once) | node ≈ 42 s, ISF stage ≈ 3.5 min (≈ 5× faster than serial) |

The 5× of this early measurement compared 8 parallel single-thread runs (10.4 s each) with a serial run that was itself using ~8 threads (7 s); the full study in 3.6 compares like with like and gives 7.5× for `isf` with 8 jobs.

### 3.6 Full-flow study on the user's machine (CS gf180mcuD, default settings, `threads=1`, measured 2026-10-28)
`for J in 1 2 4 8; do ISFPN_JOBS=$J python3 ../../isfpn.py cs.json all; done` (Docker, 16 logical CPUs). Seconds per stage:

| jobs | baseline | lin | isf | noise | blocks | combine | **total** | speed-up | efficiency |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 21.7 | 92.4 | 1551.8 | 5.6 | 1.6 | 1.1 | **1674 s (27.9 min)** | 1.00× | - |
| 2 | 21.6 | 51.4 | 806.7 | 4.2 | 1.6 | 1.1 | **887 s (14.8 min)** | 1.89× | 94 % |
| 4 | 21.2 | 31.7 | 408.7 | 3.3 | 1.6 | 1.1 | **468 s (7.8 min)** | 3.58× | 89 % |
| 8 | 21.5 | 21.6 | 207.6 | 3.1 | 1.6 | 1.2 | **257 s (4.3 min)** | 6.51× | 81 % |

- `isf` (the bulk) scales almost linearly: 1.92× / 3.79× / 7.46× (96 / 95 / 93 % efficiency). Each run takes ~10 s whether it runs alone or with 7 others, so the 8 processes really had separate cores.
- The total efficiency drops because `baseline` (21.5 s, one transient) does not scale: at `jobs=8` it is 8 % of the time, `lin` another 8 %, `isf` 81 %.
- The times are **rounds × time per run**. `lin` has 9 runs: 5, 3 and 2 rounds with 2, 4 and 8 jobs (51.4, 31.7, 21.6 s ≈ rounds × 10.3 s). `isf` has 31 runs per node: 4 rounds with 8 jobs (5 nodes × 4 rounds × 10.4 s = 208 s). With 8 jobs the last round of each node has only 7 runs. Only values of `jobs` that reduce the number of rounds help: for `isf`, 4 rounds per node with 8-15 jobs, 2 rounds with 16 jobs, 1 round with 31; for `lin`, 2 rounds with 8 jobs, 1 round with 9 or more.
- `jobs=16` was measured in 3.7 (the machine has 16 **physical** cores, not 8 + hyperthreads: `lscpu` = 2 sockets × 8 cores × 1 thread).
- Observation (cause not confirmed): the serial time per run is now ~10 s with `threads=1`, while the earlier serial runs at ~7 s per run (before the `threads` fix, `docker stats` ≈ 805 % CPU) were using ~8 threads each. A multithreaded ngspice can therefore be ~1.4× faster *per run* but uses 8× the cores, so in throughput `jobs=8` with `threads=1` wins by far. Test if curious: one node with `"threads": 0` vs `1`.
- The fast settings of README 5.0 were measured in 3.7: 78 s with `jobs=8` (as estimated, ~1.3 min).

### 3.7 Test matrix on the user's machine (`tools/bench_jobs.py`, CS gf180mcuD, measured 2026-10-28)
Hardware: 2 × Xeon Bronze 3106, 8 cores each, **1 thread per core** (16 physical cores, no hyperthreading), Docker (IIC-OSIC-TOOLS), 16 GiB.

| Run | jobs × threads | policy | total [s] | isf [s] | speed-up | max ΔL [dB] |
|---|---|---|---|---|---|---|
| j1_t1 | 1×1 | - | 1674 | 1552 | 1.00 | reference |
| j8_t1 | 8×1 | passive | 257 | 208 | 6.52 | 0.0000 |
| j12_t1 | 12×1 | passive | 198 | 159 | 8.46 | 0.0000 |
| j16_t1 | 16×1 | passive | 150 | 111 | 11.16 | 0.0000 |
| j4_t2 | 4×2 | passive | 634 | 566 | 2.64 | 0.0000 |
| j4_t2 (retest) | 4×2 | none | **399** | 349 | 4.20 | 0.0000 |
| j2_t4 | 2×4 | passive | 1144 | 1051 | 1.46 | 0.0000 |
| j1_t8 | 1×8 | passive | 1181 | 1091 | 1.42 | 0.0000 |
| fast_j8_t1 | 8×1, fast settings | passive | 78 | 60 | 21.3 | 0.0004 (expected to differ slightly) |
| j8_t1 ×3 | 8×1 | passive | 257 / 257 / 256 | 208 / 209 / 208 | 6.5 | 0.0000 |
| policy, `threads=1` | 8×1 | passive / active / none | 256 / 258 / 256 | 208 / 209 / 207 | - | 0.0000 |

Conclusions:
- **Correctness**: results are identical (0.0000 dB) for any jobs/threads/policy; repeatability < 0.5 %.
- **Processes beat threads**: with the same 8 cores 8×1 → 257 s, 4×2 → 399 s (best case), 1×8 → 1181 s. `threads=1` is the right default.
- **`jobs=16` still scales** (11.2×, 70 % efficiency; the limit is the serial `baseline` of ~20 s and the number of rounds in `isf`: 31 runs per node = 2 rounds with 16 jobs).
- **Policy with `threads=1`**: no difference (256 / 258 / 256 s).
- **`docker stats`** (iic-osic-tools container, host view): 8×1 → ~800 % CPU; 4×2 with `passive` → ~530 % (threads asleep, 1.3 cores per process); 4×2 with the policy untouched → ~800 %. Memory 190-320 MiB in all cases (not a limit; ~0.6 GiB expected for 16 jobs). The ~200 % dip seen once is the tail of an incomplete round at the end of a node.
- **`passive` hurts threaded ngspice**: 4×2 went from 634 s (14.2 s per run, 530 %) to 399 s (8.7 s per run, 800 %) when the policy was left alone, in line with finding 3.3 (serial ×4 slower with `passive`). Hence the tool's `auto` policy.
- **Threads are inefficient even then**: with `threads=2` a run takes 8.7 s vs 10.4 s with `threads=1` (1.2× for twice the cores); the serial `baseline` improved 21.5 → 18.1 s. Per used core, 8×1 gives 0.81 and 4×2 gives 0.52 of ideal speed-up.
- **Caveat for `auto`**: when `jobs×threads` exceeds the visible CPUs, busy-waiting threads stall (reproduced in the 2-core sandbox with jobs=2, threads=2 and no policy), so `auto` switches to `passive` in that case.

## 4. Diagnosing a slow or non-scaling environment

Inside the container:
```bash
nproc                                              # CPUs visible (logical)
cat /sys/fs/cgroup/cpu.max                         # "max 100000" = no quota; "100000 100000" = 1 CPU (cgroup v2)
cat ~/.spiceinit; grep -n num_threads $(dirname $(dirname $(which ngspice)))/share/ngspice/scripts/spinit
python3 - <<'EOF'                                  # real parallel capacity: should print the same time for 1, 2, 4
import time, multiprocessing as mp
def burn(_):
    x = 0
    for i in range(20_000_000): x += i
for n in (1, 2, 4):
    t = time.time()
    with mp.Pool(n) as p: p.map(burn, range(n))
    print(n, "processes:", round(time.time() - t, 1), "s")
EOF
```
On the host: `docker info | grep -i cpus`, `docker stats` (CPU % of the container while isfpn runs; serial should be ~100 %, `jobs=N` ~N·100 %), `docker inspect <c> --format 'NanoCpus={{.HostConfig.NanoCpus}} Quota={{.HostConfig.CpuQuota}}'`.
Docker Desktop / WSL2 limits live in Settings → Resources or `.wslconfig` (`processors=`).

| Symptom | Likely cause |
|---|---|
| 1, 2 and 4 python processes take the same time | at least that many real cores; no quota |
| 2 processes take 2× as long as 1 | effectively one core (cgroup quota, VM with 1 CPU) → keep `jobs=1` |
| `docker stats` ≫ 100 % with `jobs=1` | ngspice multithreading: check `num_threads` (`threads` key handles it) |
| `jobs>1` stalls | check `OMP_WAIT_POLICY`; `run_timeout` keeps the stuck `r_*.spice` |

## 5. Documenting a speed-up study
```bash
cd cases/cs_n4_gf180mcuD
for J in 1 2 4 8; do
  ISFPN_JOBS=$J python3 ../../isfpn.py cs.json all > run_j$J.log 2>&1
  cp timing.json timing_j$J.json
done
```
`timing.json` holds time per stage, total, `jobs`, `threads`, `n_phase`, number of nodes and devices. A serial full run of the CS is ~25-30 min on the user's machine, so start with `1` and `8` if short on time.

## 6. Benchmark script
`tools/bench_jobs.py` (wrapper `bench_jobs.sh`) runs the pending tests in one go and prints the comparison table; see README section 5.2.
Tests: 1 correctness jobs=1 vs 8, 2 jobs×threads at 8 cores, 3 jobs=12/16, 4 fast settings + jobs=8, 5 repeatability, 6 `OMP_WAIT_POLICY` with `threads=1`, 7 `threads=2` with the policy untouched/passive (env `ISFPN_OMP_WAIT=auto|passive|active|none`; `ISFPN_THREADS=N` overrides `threads`). `bench/summary.json` accumulates runs across executions. Results of tests 1-6 are in 3.7.

## 7. Open points
- `jobs=16` with the fast settings (expected ~50 s) and `8×2` with the policy untouched (test 7, needs 16 cores) are not measured yet.
- Whether the container's `.spiceinit`/`spinit` really sets `num_threads` (inferred from the 805 % CPU, not inspected).
- Scaling beyond the physical core count (16 here, no hyperthreads) was not measured: `jobs=24/32` would only oversubscribe.
- Memory at 16 jobs was extrapolated, not measured.
- The sandbox used for development had 2 cores (1 for part of the session), so its absolute speed-ups are small; the user's machine is the reference.
