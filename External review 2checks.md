# External review 2checks

## Scope and review standard

This is an independent review of the current Tempest-ARKNET implementation,
including the expanded generator, feature modes, calibration, scoring, routing,
past/near-term forecast modules, profile conversion, and output-related paths.

Items are classified as:

- **Confirmed defect:** directly observable from current code and likely to produce
  incorrect results, crashes, or misleading evaluation.
- **High-risk flaw:** may be valid by design, but can make results look better than
  they are unless explicitly tested.
- **Structural safeguard:** not necessarily a current bug, but needed to prevent
  future silent regressions.

No finite review can guarantee zero defects. Every scientific result should still
be reproduced from a clean environment and an untouched verification set.

---

## 1. Confirmed or near-certain implementation defects

### 1.1 GPU training silently changes the training data precision

`train.py` stores normalized training features and targets in `float16` when the
device is CUDA:

