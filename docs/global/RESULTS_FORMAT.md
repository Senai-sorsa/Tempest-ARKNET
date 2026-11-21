# What to send back from the cluster

One archive per finished job: `results_<G>_<config>_<YYYYMMDD>.tar` with the content of `results/<G>/`:

| File | Keep | Why |
|---|---|---|
| `run.log`, `*.log`, `*.done`, `NOT_BUILT.txt` | always | what ran, in which order, any failure |
| `gate_*.csv`, `lobo_*/`, `*_runs.csv`, `seam_*.csv`, `rotate.txt`, `mf_*.csv`, `balloon_cov_cv.csv`, `egpd_check.csv`, `bundle.csv` | always (G2-G5) | the gate inputs and verdicts |
| `*_report/` and `*_tail.csv` (written by `tempest.scoring.score --tail`) | always (G2-G4) | per-variable summaries and shear tails the gates read |
| `models/global/*.npz` (tropo_clim, koppen, clim_2deg, aoa, balloon_cov, egpd) | G4 | small tables; G5 packs them |
| `models/global/onnx/gates.json` + `models/global/bundle/` | G5 | the export gates and the packed bundle |
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
- G2-G5: the gate files carry the verdict per check (`gate_g2_*.csv`, `gate_g3.csv`, `gate_g4.csv`, `gates.json` + `bundle.csv`); they can be rebuilt at home from the returned score files with `python -m tempest.scoring.spatial gate-g2|gate-g3|gate-g4`.
- Results enter `docs/plans/GLOBAL_PLAN.md` §7 (decisions log) and AUTOPILOT. Nothing from 2026 is ever part of a returned result. If one shows up, the run is void.
