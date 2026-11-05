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

```
git update-ref refs/heads/main split-main ba2e2df && git push --force-with-lease=main:ba2e2df origin main && git worktree remove <old scratchpad>/splitwt && git branch -D split-main
```
The scratchpad of the old session is gone; if the worktree folder has vanished run `git worktree prune` first.
Local commits made by Claude would sit on top of `ba2e2df`; rebase them onto `split-main` before pushing.

## 3. A2 go/no-go limits (P(scrub), PHASED_PLAN 3.9)

Not built: needs the wind, shear, temperature and RH limits per vehicle or launch from the user. Send them and
3.9 plus any go/no-go output get built.
