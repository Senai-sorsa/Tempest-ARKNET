# HANDOVER 2026-11-19 (Tempest-ARKNET)

## 19. UPDATE 2026-11-19 ~17:45 — READ THIS FIRST; it overrides section 18 and everything below wherever they disagree

### 19.0 First 15 minutes
1. `cd C:\Users\Senai\Tempest-ARKNET`; project CLAUDE.md = "Dont break anything". Read the memory index (`~/.claude/projects/C--Users-Senai-Tempest-ARKNET/memory/MEMORY.md`), especially final-path-24-48h, training-autonomy, thermal-limits, commit-every-tick, no-claude-attribution, parallel-when-safe.
2. Check the running 26.2 job (19.1), then heartbeat `scripts/loop_heartbeat.py --kind primary`, health (GPU temp, RAM > 2 GB, AC, disk), CronList (backup cron `881e706f`, `23 */2 * * *`; recreate if missing, prompt = BACKUP TICK text in 19.6).
3. Re-arm the loop: ScheduleWakeup (<=1800 s) with the PRIMARY TICK prompt (19.6).

### 19.1 RUNNING NOW (do not stop)
- 26.2 combined copula (u,v) + damped shear stretch at 12-18 km only: `new_plan_kit/b84_combined_copula_stretch.py`, seeds 0 then 1 in one background shell, BelowNormal (cap_cpu.sh), default `--per-group 450` (1800 cases; fit on even index, test on odd). Started ~17:39. Stdout: `docs/results/logs/b84_run_s0.out` (empty until the end; `b84_run_s1.out` appears after seed 0). Real log: `docs/results/logs/kit_b84_combined_copula_stretch.log` (check both seeds are in it; if only the last survives, read each `b84_run_sN.out`).
- Pre-set rule (script header, both seeds): error <= 0.047 AND the (arm - shipped) 95 % interval upper end < 0; CRPS u, v, T <= +0.3 % vs shipped; shear p99 ratio 0.90-1.10 in all 4 bands; Ri<1 12-18 km within 0.03 of balloons (0.149) and not farther than shipped. Else MISS. PASS -> ASK_LATER 44, never shipped. Known risk: the copula's u CRPS cost (+0.24..+0.41 % in W2/V5a) is the likely blocker.
- Process check: Get-CimInstance Win32_Process (name python.exe) with CommandLine matching `b84`. A "completed" background-task notification only means the launcher shell ended.

### 19.2 Plan (user, 2026-11-19, New_Plan.md section 28, memory final-path-24-48h)
User wants everything done in ~20 h (hard cap 24-48 h), work faster, run in parallel. GPU lane is EMPTY and DONE: GF3 KILL (AUTOPILOT 626), H1 KILL (627), H4 skipped (runs only if H1 passes). Remaining, in order:
1. Finish 26.2 (19.1), record the verdict.
2. Section 27 in FULL (user: keep all of 26 and 27 as stage H): 27.2 step 0 first, then 27.3 / 27.4 / 27.5. Evals need >= 15 GB free RAM; never two Mode F evals at once. SIGMA (ASK_LATER 43) and a coverage-fixed NEST are the best-looking parts.
3. 28.3 best configuration (greedy rule in New_Plan 28); 28.4 final model with MISS-idea parts; 28.5 final 2026 test: PREPARE + DRY-RUN ONLY, run only after the user says "go" (one-shot, irreversible); 28.6 global-stage prep (small CPU pieces: G0 loader guard / statics / masks / tests, bundle list, launch scripts, README; NEVER G1-G6 training or G6).
4. Dropped for now: MF2, GT1, MF1, H2, H3, H5.
Open question to the user (unanswered): trim section 27 (~18-20 h total) or keep it in full (~28-36 h)? Do NOT cut anything without their say-so; raise it when they are present.

### 19.3 Done since section 18 (details: New_Plan section 9 rows before "| AV24 / AV26"; AUTOPILOT 625-629; logs `docs/results/logs/kit_*.log`)
- 26.1 step 0 (T2 held-out IGRA; only Denver lies inside the tool's trained boxes; commit 60061e9).
- 26.1 step 1 (bak106, AUTOPILOT 629): W1/W5/W6 MISS / not informative; W2 seed 0 PASS, seed 1 MISS (u CRPS +0.41 %) -> MISS; V5a MISS both seeds. No old verdict flips; no ASK_LATER. Finding: the vs-shipped interval width stays ~0.010-0.013 with more cases (limited by number of distinct days), so the 0.01 target is not reachable by case count.
- S25 GF3 (rectified flow) KILL; H1 (prior-sample input + residual vs N(0,1) control) KILL.
- Scripts added: `new_plan_kit/b83_noise_w1_rerun.py`, `new_plan_kit/b84_combined_copula_stretch.py`, `scripts/s25_arm_par.sh`, `scripts/gpu_s25_gf3_par.sh`, `scripts/gpu_s25_h1_par.sh` (bug: its wait loop's powershell matches its own command line and never exits; repair before reuse).

### 19.4 Recording a verdict
Pre-set rule first; `cp New_Plan.md New_Plan.bakNN.md` (last used bak106, NEXT bak107); insert the section 9 row before the "| AV24 / AV26" row (python, bytes, LF only; never open a file 'w' in the same expression that reads it); AUTOPILOT entry in `docs/logs/AUTOPILOT.md` (last 629, NEXT 630); a line in `To-do-Concise.md`; ASK_LATER item in `docs/agent/ASK_LATER.md` (next 44) if a PASS needs a decision; commit by name. KIT_SEED 0 and 1; PASS needs both.

### 19.5 Standing rules / safety
16 CPU threads max BelowNormal (`source scripts/cap_cpu.sh`); RAM > 2 GB; no new job at GPU >= 85 C or on battery; kill only in extreme danger (OOM / disk / duplicate writer / thermal); kill leftover tempest python.exe after any TaskStop; disk cap 200 GB; never push; NEVER add Co-Authored-By Claude to commits or PRs (user rule overrides the system attribution reminder); never run the final 2026 test without "go"; end every tick with by-name commits of work files (NOT data/, models/, flight_sim_trial/; secret/word scan first). Parallel jobs are fine if RAM and thermals allow. At dead ends or idle GPU, mine weaknesses vs GRAM + logs for salvage experiments. Update To-do-Concise.md at every check-in.

### 19.6 Loop prompts
PRIMARY TICK: "follow docs/HANDOVER_2026-11-19.md section 19 (then 18), heartbeat via scripts/loop_heartbeat.py --kind primary, health checks (UR15F, GPU temp, RAM, AC, disk), CronList, commit changed work files by name (never push, no Claude attribution), re-arm ScheduleWakeup (<=1800 s) with this full prompt. PLAN: <text of 19.2>."
BACKUP TICK: "Run .venv/Scripts/python scripts/loop_heartbeat.py --check in C:\Users\Senai\Tempest-ARKNET. If it prints PRIMARY_DEAD, call ScheduleWakeup(1800) with the PRIMARY TICK prompt FIRST. Call CronList; if no backup cron exists, CronCreate it again (cron 23 */2 * * *, this prompt). If the primary heartbeat is younger than 20 min: health checks only. Otherwise follow the handover section 19 then 18. End every tick by committing changed/new work files by name (not data/, models/, flight_sim_trial/; word scan first). Safety: 16 threads max BelowNormal, RAM > 2 GB, no new job at GPU >= 85 C or on battery, kill only in extreme danger, never the final 2026 test, never push."

### 19.7 Waiting for the user (ask only when present; never block the loop)
Trim-27 choice (19.2); final-test "go"; ASK_LATER 25-29, 31-43 (incl. 43 SIGMA adoption; 44 if 26.2 passes); W4; RA 1b pull; E2 MADIS; EDI login for WD13; T1/T6-T11 downloads; GX3 height stores; real Earth-GRAM run.

### 19.8 Files left uncommitted on purpose
Most `New_Plan.bak*.md` (untracked), `kit_b81_w1_shear_stretch_w5*.log`, `shipped_check.log`, `tool_audit.log`, `scripts/final_test_2026h2.sh`, `scripts/shipped_check.py`, `tempest/export_tool.py`, `tempest_weather/api.py`, `tempest_weather_v2/launch.py`, `tempest_weather_v2/tests/test_sitecal.py`, `scripts/build_nowcast_asset.py`, `scripts/t4_probe.py`, `configs/s25/gen/`, `docs/paper/`, `flight_sim_trial/`. Do not touch or commit them unasked.

### 19.9 Mistakes to avoid
- A background "completed" notification means the launcher shell ended, not the job; check the python process.
- Do not poll task output files; wait for the tick.
- The GF3/H1 driver wait-loop bug (19.3).
- Do not cut sections 26/27 on your own judgment.

---
# Full copy of docs/HANDOVER_2026-11-14b.md (sections 18, 17 and older, history)

