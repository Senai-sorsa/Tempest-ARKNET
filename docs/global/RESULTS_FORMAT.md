# What to send back from the cluster

One archive per finished job: `results_<G>_<config>_<YYYYMMDD>.tar` with the content of `results/<G>/`:

| File | Keep | Why |
|---|---|---|
| `run.log`, `*.log`, `*.done`, `NOT_BUILT.txt` | always | what ran, in which order, any failure |
| `*_headline.csv`, `*.score.csv`, `*_diag*.csv` (written by `tempest.scoring.score`) | always | the scores the gates are judged on |
| `*.calib2021.npz` | always | small; needed to rescore |
| `*.pt` (checkpoints) | the best config's only, unless asked | large; needed for G2+ and for packaging |
| the seeded config copies `*_s<seed>.toml` | always | exact settings of each run |

Also add a `MANIFEST.txt` with:
```
stage: G1
config: configs/generator_p2f.toml   (git hash of the bundle: <git rev-parse HEAD on the laptop before packing>)
seeds: 0 100
cluster: <name>, GPU <model>, wall time per step (from run.log)
python / torch / CUDA versions
anything changed by hand on the cluster (none expected)
```
`sha256sum` of every file in the archive goes in `SHA256SUMS`.

## How it is judged at home
- G1: `scripts/compare_headline.py <B-raw headline> <den0 headline>` per seed for the zero-shot gate G1-a. The same for NM/TX vs p2f (G1-b, seed tolerance 0.0006 / 0.0013 skill15) and for unified vs separate (G1-c).
- Results enter `docs/plans/GLOBAL_PLAN.md` §7 (decisions log) and AUTOPILOT. Nothing from 2026 is ever part of a returned result. If one shows up, the run is void.
