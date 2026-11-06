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

## Every file

**plans/** — [PLAN.md](plans/PLAN.md) master plan · [PHASE1.md](plans/PHASE1.md) phases 1–2 build spec · [PHASED_PLAN.md](plans/PHASED_PLAN.md) phased improvements · [PHASE4_FORECAST.md](plans/PHASE4_FORECAST.md) forecast system · [TOOL_PLAN.md](plans/TOOL_PLAN.md) query-tool skeleton · [PHASE5_TOOL.md](plans/PHASE5_TOOL.md) query tool rework ([original note](plans/phase5_inputs/original_tool_plan_from_downloads.md)) · [STAGE6_PLAN.md](plans/STAGE6_PLAN.md) flight-sim tools · [REGION_PLAN.md](plans/REGION_PLAN.md) other regions · [GLOBAL_PLAN.md](plans/GLOBAL_PLAN.md) global model (G0–G4)

**specs/** — [atmosphere-outputs.md](specs/atmosphere-outputs.md) · [coupled-atmosphere.md](specs/coupled-atmosphere.md) · [operations.md](specs/operations.md)

**reviews/external/** — [External review 2checks.md](reviews/external/External%20review%202checks.md) · [global-fixes.md](reviews/external/global-fixes.md) (global extension) · [GPT-suggestions.md](reviews/external/GPT-suggestions.md) · [suggestions-copoilet.md](reviews/external/suggestions-copoilet.md)

**reviews/triage/** — [GLOBAL_REVIEW_TRIAGE.md](reviews/triage/GLOBAL_REVIEW_TRIAGE.md) ← global-fixes · [review-triage.md](reviews/triage/review-triage.md) ← outside architecture review · [Strong improvment.md](reviews/triage/Strong%20improvment.md) ← AI-model comparison + Gemini audit

**reviews/internal/** — [claude-recommendations-v2.md](reviews/internal/claude-recommendations-v2.md)

**logs/** — [LOOP3.md](logs/LOOP3.md) · [LOOP2.md](logs/LOOP2.md) · [AUTOPILOT.md](logs/AUTOPILOT.md) · [PHASE4_LOG.md](logs/PHASE4_LOG.md) · [SIDELINED.md](logs/SIDELINED.md) (skipped items)

**results/** — [FINAL_REPORT.md](results/FINAL_REPORT.md) · [APPLIED_STATUS.md](results/APPLIED_STATUS.md)

**data/** — [DATA_NEEDS.md](data/DATA_NEEDS.md) · [Downloads to do.md](data/Downloads%20to%20do.md) · colab/: [Colab downloads.md](data/colab/Colab%20downloads.md), [Colab HRES refetch.md](data/colab/Colab%20HRES%20refetch.md), [Colab IFS ENS fetch.md](data/colab/Colab%20IFS%20ENS%20fetch.md), [Colab ARCO fill.md](data/colab/Colab%20ARCO%20fill.md)

**research/** — [research-notes.md](research/research-notes.md) · [argon-prompt-general.md](research/argon-prompt-general.md) · [FUTURE_OPTIONS.md](research/FUTURE_OPTIONS.md)

**agent/** — [HANDOVER.md](agent/HANDOVER.md) · [START_PROMPT.md](agent/START_PROMPT.md) · [ASK_LATER.md](agent/ASK_LATER.md)

Elsewhere (kept next to their code): `README.md`, `configs/README.md`, `scripts/README.md`, `tests/README.md`, `tempest_weather/README.md`, `notebooks/*.md` (Colab notebook guides), `Code-Modifications/handover_scripts/` (old scripts).

## Moved on 2026-11-06
Links and code comments were rewritten. Old paths still appear in a few `scripts/*.sh` that were running during the move (they were left untouched) and in old git history:
`Code-Modifications/{LOOP2,LOOP3,AUTOPILOT,SIDELINED}.md` → `logs/` · `Code-Modifications/{PHASED_PLAN,PHASE4_FORECAST,PHASE5_TOOL,STAGE6_PLAN}.md` → `plans/` · `Code-Modifications/{atmosphere-outputs,coupled-atmosphere,operations}.md` → `specs/` · `Code-Modifications/{HANDOVER,START_PROMPT,ASK_LATER}.md` → `agent/` · `Code-Modifications/review-triage.md` → `reviews/triage/` · `Code-Modifications/claude-recommendations-v2.md` → `reviews/internal/` · `docs/{PLAN,PHASE1,GLOBAL_PLAN,REGION_PLAN,TOOL_PLAN}.md` → `plans/` · `docs/{FINAL_REPORT,APPLIED_STATUS}.md` → `results/` · `docs/PHASE4_LOG.md` → `logs/` · `docs/DATA_NEEDS.md` → `data/` · `docs/{research-notes,argon-prompt-general,FUTURE_OPTIONS}.md` → `research/` · `docs/GLOBAL_REVIEW_TRIAGE.md` → `reviews/triage/` · root `External review 2checks.md`, `global-fixes.md`, `GPT-suggestions.md`, `suggestions-copoilet.md` → `reviews/external/` · root `Strong improvment.md` → `reviews/triage/` · root `Downloads to do.md` → `data/` · root `Colab *.md` → `data/colab/`.
