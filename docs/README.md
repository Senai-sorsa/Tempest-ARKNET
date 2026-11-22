# Documents — index

Every project document lives under `docs/`, one folder per kind. Start with **`../To-do-Concise.md`** (root) for what is happening now.

| Folder | What is in it | Start with |
|---|---|---|
| [`plans/`](plans/) | Plans and build specs: what will be built and why | [PLAN.md](plans/PLAN.md) (master plan + experiment log) |
| [`specs/`](specs/) | Detailed technical specs for single parts | — |
| [`reviews/external/`](reviews/external/) | **External reviews, as received** (other AIs / outside reviewers). Not edited by us | — |
| [`reviews/triage/`](reviews/triage/) | **Our verdicts on those reviews** (what is wrong, done, to-do, skipped) | [GLOBAL_REVIEW_TRIAGE.md](reviews/triage/GLOBAL_REVIEW_TRIAGE.md) |
| [`reviews/internal/`](reviews/internal/) | Claude's own recommendation lists | — |
| [`logs/`](logs/) | Live experiment logs (updated every check-in) | [LOOP3.md](logs/LOOP3.md) (current), [AUTOPILOT.md](logs/AUTOPILOT.md) (all runs) |
| [`results/`](results/) | Final results and what is applied where | [FINAL_REPORT.md](results/FINAL_REPORT.md) |
| [`final_test/`](final_test/) | Raw outputs of the final test (CSV, logs; written by `scripts/final_test.sh`) | [tables.md](final_test/tables.md) |
| [`data/`](data/) | Data: what is downloaded, disk budget, download lists; [`data/colab/`](data/colab/) = steps **you** run in Colab | [DATA_NEEDS.md](data/DATA_NEEDS.md) |
| [`research/`](research/) | Background research, prompts, idea backlog | [FUTURE_OPTIONS.md](research/FUTURE_OPTIONS.md) |
| [`agent/`](agent/) | Session handover and questions waiting for **you** | [ASK_LATER.md](agent/ASK_LATER.md) |
| [`notes/`](notes/) | The user's working notes and idea lists (read as data) | [Useful results.md](notes/Useful%20results.md) |

## Every file

**plans/** — [PLAN.md](plans/PLAN.md) master plan · [PHASE1.md](plans/PHASE1.md) phases 1–2 build spec · [PHASED_PLAN.md](plans/PHASED_PLAN.md) phased improvements · [PHASE4_FORECAST.md](plans/PHASE4_FORECAST.md) forecast system · [TOOL_PLAN.md](plans/TOOL_PLAN.md) query-tool skeleton · [PHASE5_TOOL.md](plans/PHASE5_TOOL.md) query tool rework ([original note](plans/phase5_inputs/original_tool_plan_from_downloads.md)) · [STAGE6_PLAN.md](plans/STAGE6_PLAN.md) flight-sim tools · [REGION_PLAN.md](plans/REGION_PLAN.md) other regions · [GLOBAL_PLAN.md](plans/GLOBAL_PLAN.md) global model (G0–G4) · [LAUNCH_PLAN.md](plans/LAUNCH_PLAN.md) 80 km extension, launch-day correction, wind tails

**specs/** — [atmosphere-outputs.md](specs/atmosphere-outputs.md) · [coupled-atmosphere.md](specs/coupled-atmosphere.md) · [operations.md](specs/operations.md)

**reviews/external/** — [External review 2checks.md](reviews/external/External%20review%202checks.md) · [global-fixes.md](reviews/external/global-fixes.md) (global extension) · [GPT-suggestions.md](reviews/external/GPT-suggestions.md) · [suggestions-copoilet.md](reviews/external/suggestions-copoilet.md) · [gemini-review.pdf](reviews/external/gemini-review.pdf)

**reviews/triage/** — [GLOBAL_REVIEW_TRIAGE.md](reviews/triage/GLOBAL_REVIEW_TRIAGE.md) ← global-fixes · [GEMINI_REVIEW_TRIAGE.md](reviews/triage/GEMINI_REVIEW_TRIAGE.md) ← gemini-review.pdf · [review-triage.md](reviews/triage/review-triage.md) ← outside architecture review · [Strong improvment.md](reviews/triage/Strong%20improvment.md) ← AI-model comparison + Gemini audit

**reviews/internal/** — [claude-recommendations-v2.md](reviews/internal/claude-recommendations-v2.md) · [AUDIT_2026-11-08.md](reviews/internal/AUDIT_2026-11-08.md)

**logs/** — [LOOP3.md](logs/LOOP3.md) · [LOOP2.md](logs/LOOP2.md) · [AUTOPILOT.md](logs/AUTOPILOT.md) · [PHASE4_LOG.md](logs/PHASE4_LOG.md) · [SIDELINED.md](logs/SIDELINED.md) (skipped items)

**results/** — [FINAL_REPORT.md](results/FINAL_REPORT.md) · [APPLIED_STATUS.md](results/APPLIED_STATUS.md)

**data/** — [DATA_NEEDS.md](data/DATA_NEEDS.md) · [Downloads to do.md](data/Downloads%20to%20do.md) · colab/: [Colab downloads.md](data/colab/Colab%20downloads.md), [Colab HRES refetch.md](data/colab/Colab%20HRES%20refetch.md), [Colab IFS ENS fetch.md](data/colab/Colab%20IFS%20ENS%20fetch.md), [Colab ARCO fill.md](data/colab/Colab%20ARCO%20fill.md), [Colab HRES global fetch.md](data/colab/Colab%20HRES%20global%20fetch.md), [Colab IFS extended range fetch.md](data/colab/Colab%20IFS%20extended%20range%20fetch.md)

**research/** — [research-notes.md](research/research-notes.md) · [argon-prompt-general.md](research/argon-prompt-general.md) · [FUTURE_OPTIONS.md](research/FUTURE_OPTIONS.md)

**agent/** — [HANDOVER.md](agent/HANDOVER.md) · [START_PROMPT.md](agent/START_PROMPT.md) · [ASK_LATER.md](agent/ASK_LATER.md) · handovers/: [2026-11-09](agent/handovers/HANDOVER_2026-11-09.md), [2026-11-10](agent/handovers/HANDOVER_2026-11-10.md), [2026-11-10b](agent/handovers/HANDOVER_2026-11-10b.md), [2026-11-11](agent/handovers/HANDOVER_2026-11-11.md), [2026-11-14](agent/handovers/HANDOVER_2026-11-14.md), [2026-11-14b](agent/handovers/HANDOVER_2026-11-14b.md) · current: [HANDOVER_2026-11-19.md](HANDOVER_2026-11-19.md)

**notes/** — [Almost ideas.md](notes/Almost%20ideas.md) · [Beat Earth-GRAM.md](notes/Beat%20Earth-GRAM.md) · [Fixes-Concise.md](notes/Fixes-Concise.md) · [FlightSIM&Validation with Tempest-ARKNET.md](notes/FlightSIM%26Validation%20with%20Tempest-ARKNET.md) · [Improvements-Concise.md](notes/Improvements-Concise.md) · [Innovative idea review.md](notes/Innovative%20idea%20review.md) · [Limitations to solve.md](notes/Limitations%20to%20solve.md) · [Secondary ideas.md](notes/Secondary%20ideas.md) · [Useful results.md](notes/Useful%20results.md) · [Wind and rule-fix ideas.md](notes/Wind%20and%20rule-fix%20ideas.md) · [fixing final issue.md](notes/fixing%20final%20issue.md)

**docs/ root** — [AI_MISTAKES_CHECKLIST.md](AI_MISTAKES_CHECKLIST.md) · [GEMINI_BUGS_2026-11-09.md](GEMINI_BUGS_2026-11-09.md) (both cited by code comments, so not moved) · [index.html](index.html) = the v3 documentation website (GitHub Pages)

Elsewhere (kept next to their code): `README.md`, `configs/README.md`, `scripts/README.md`, `tests/README.md`, `tempest_weather/README.md`, `notebooks/*.md` (Colab notebook guides), `Code-Modifications/handover_scripts/` (old scripts).

## Moved on 2026-11-06
Links and code comments were rewritten. Old paths still appear in a few `scripts/*.sh` that were running during the move (they were left untouched) and in old git history:
`Code-Modifications/{LOOP2,LOOP3,AUTOPILOT,SIDELINED}.md` → `logs/` · `Code-Modifications/{PHASED_PLAN,PHASE4_FORECAST,PHASE5_TOOL,STAGE6_PLAN}.md` → `plans/` · `Code-Modifications/{atmosphere-outputs,coupled-atmosphere,operations}.md` → `specs/` · `Code-Modifications/{HANDOVER,START_PROMPT,ASK_LATER}.md` → `agent/` · `Code-Modifications/review-triage.md` → `reviews/triage/` · `Code-Modifications/claude-recommendations-v2.md` → `reviews/internal/` · `docs/{PLAN,PHASE1,GLOBAL_PLAN,REGION_PLAN,TOOL_PLAN}.md` → `plans/` · `docs/{FINAL_REPORT,APPLIED_STATUS}.md` → `results/` · `docs/PHASE4_LOG.md` → `logs/` · `docs/DATA_NEEDS.md` → `data/` · `docs/{research-notes,argon-prompt-general,FUTURE_OPTIONS}.md` → `research/` · `docs/GLOBAL_REVIEW_TRIAGE.md` → `reviews/triage/` · root `External review 2checks.md`, `global-fixes.md`, `GPT-suggestions.md`, `suggestions-copoilet.md` → `reviews/external/` · root `Strong improvment.md` → `reviews/triage/` · root `Downloads to do.md` → `data/` · root `Colab *.md` → `data/colab/`.

## Cleaned up on 2026-11-22
Deleted: root `New_Plan.bak19.md` … `New_Plan.bak149.md` (131 backups, still in git history at commit `a83e8eb`; now git-ignored) and `docs/HANDOVER_2026-11-19_head.md` (an older copy of section 19 of `HANDOVER_2026-11-19.md`). Moved (mentions in `New_Plan.md`, `To-do-Concise.md` and `HANDOVER_2026-11-19.md` were rewritten on the same lines, so line numbers did not change): root `Almost ideas.md`, `Beat Earth-GRAM.md`, `Fixes-Concise.md`, `FlightSIM&Validation with Tempest-ARKNET.md`, `Improvements-Concise.md`, `Innovative idea review.md`, `Limitations to solve.md`, `Secondary ideas.md`, `Useful results.md`, `Wind and rule-fix ideas.md`, `fixing final issue.md` → `notes/` · `docs/HANDOVER_2026-11-{09,10,10b,11,14,14b}.md` → `agent/handovers/` · `docs/AUDIT_2026-11-08.md` → `reviews/internal/`. Kept in place because code, configs, tests or the live loop read them: `New_Plan.md`, `To-do-Concise.md`, `docs/HANDOVER_2026-11-19.md`, `plans/`, `specs/`, `agent/`, `logs/`, `results/`.
