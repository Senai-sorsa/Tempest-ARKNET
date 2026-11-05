# ASK_LATER: items for the user to decide or run

Each entry has the reason, the evidence and the exact command or change.

## 1. Make the forecast logger survive reboots (Windows Task Scheduler)

- **Reason:** the logger (`tempest.ops.logger`) currently runs as a background loop (`--loop 12`) started by Claude.
  It stops when the machine reboots or the session's processes are cleaned up. Days not logged are lost for good,
  because Open-Meteo does not keep past ensemble members.
- **Why not done by Claude:** creating a scheduled task is persistent system configuration, which the permission
  check blocked.
- **Evidence:** `data/ops/logger.log` (one line per request), files in `data/ops/raw/<site>/<model>/`.
- **Command (run in PowerShell; twice a day, low priority, safe to run any time because stored slots are skipped):**
  ```
  schtasks /Create /TN "TempestForecastLogger" /TR "C:\Users\Senai\Tempest-ARKNET\scripts\run_logger.cmd" /SC DAILY /ST 03:15 /RI 720 /DU 24:00 /F
  ```
  Remove with `schtasks /Delete /TN "TempestForecastLogger" /F`.

## 2. History split and force-push (from HANDOVER section 9)

**Status (2026-11-05):** the history is rebuilt locally as 75 small commits with the same final tree (backup branch `backup-pre-rewrite` keeps the old one). Only the push is left, because the auto-mode classifier blocks force-pushes: run `git push --force-with-lease=main:ba2e2df origin main` yourself (type `! git push --force-with-lease=main:ba2e2df origin main` in the prompt). The old `update-ref` command below is no longer needed.


```
git update-ref refs/heads/main split-main ba2e2df && git push --force-with-lease=main:ba2e2df origin main && git worktree remove <old scratchpad>/splitwt && git branch -D split-main
```
The scratchpad of the old session is gone; if the worktree folder has vanished run `git worktree prune` first.
Local commits made by Claude would sit on top of `ba2e2df`; rebase them onto `split-main` before pushing.

## 3. A2 go/no-go limits (P(scrub), PHASED_PLAN 3.9)

Not built: needs the wind, shear, temperature and RH limits per vehicle or launch from the user. Send them and
3.9 plus any go/no-go output get built.

## 4. Real NASA Earth-GRAM for the comparison (PHASED_PLAN section 8)

- **Reason:** the user wants the final system shown to beat Earth-GRAM. A statistical stand-in ("gauss", built the same way)
  is scored already; the real program needs the NASA GRAM Suite, which must be requested from NASA (software catalog).
- **Not done by Claude:** getting software that needs an account/agreement with an external party.
- **Evidence:** E12 vs gauss table in PHASED_PLAN section 8.
- **What to do:** obtain the GRAM Suite (Linux/WSL, has a Python API), tell Claude where it is installed; Claude then runs
  it at Spaceport America and Midland for the 2024-25 test hours and scores it with the existing code.

## 5. Data for the thermals check (PHASED_PLAN 3.3): sshf and high-resolution soundings

- **Reason:** `tempest/output/thermals.py` (convective boundary-layer scaling) needs the surface sensible heat flux H.
  ERA5's `sshf` is not in the Earthmover store (checked: `single/temporal` has blh, fg10, ssrd, ssr, slhf but no sshf). It
  has to come from the Copernicus CDS (`reanalysis-era5-single-levels`, variable `surface_sensible_heat_flux`, box
  31-34 N, 108-101 W, 1991-2025, hourly). The check of the coefficients needs NWS 1-second radiosonde data (balloon rise
  rates) at Santa Teresa and Midland, which is not yet downloaded.
- **Why not done:** the one CDS downloader (`fetch_cds`, 420 monthly requests, 33 done after a day) already fills the
  user's queue; a second job would compete with it and break the "one downloader" rule in HANDOVER section 1.
- **Evidence:** thermals module and its 4 physics unit tests exist; no data check yet. The module is off everywhere.
- **What to do after `fetch_cds` finishes:** run a one-year-per-request pull of `surface_sensible_heat_flux` (35 requests,
  small), then `tempest.profiles.surface_hourly` gets `sshf`, then compare `w_sigma` with rise-rate variance.

## 6. Chronos-2 and CPC/IRI/NMME in the index-forecast bake-off (PHASED_PLAN 3.7)

- Not run: needs a model download (Chronos-2 weights from Hugging Face) or archives of the other forecasts. The run that
  was done (persistence, climatology, ridge regression, analog draw) already shows regression beating the analog draw.
  Chronos-2 is a candidate for the improvement loop. Command idea: `pip install chronos-forecasting` into the venv, then add a
  method in `scripts/index_bakeoff.py`.

## 7. Two Colab notebooks to run when you are at the computer (optional, each saves hours or days)

Both extract a small box from Google's public archives inside Google's network, so nothing large comes to your machine.
- `notebooks/arco_fill_colab.md`: the 8 boundary-layer ERA5 levels (975-750 hPa) from ARCO-ERA5, as `<yyyymm>.nc`, run newest month first. Speeds up or replaces the CDS download.
- `notebooks/wb2_colab.md`: IFS HRES forecasts 2016-2022 at 1/3/5/7 days (a few MB per year). Needed for the calibrated forecast modes (IL-6).
Copy the outputs to `data/raw/era5_cds/` and `data/raw/wb2_hres/`, then tell Claude.
