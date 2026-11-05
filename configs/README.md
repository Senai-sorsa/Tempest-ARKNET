# configs

`generator.toml` is the E12 baseline training setting; `generator_<variant>.toml` files are the Phase 2/3 variants named in docs/PLAN.md
(`p2f` is the adopted one: E12 + `shear_tail_weight = 1.0` + `ema_decay = 0.999`, trained on the dpd-humidity dataset). `sites.toml` is the site registry
the forecast loggers read. Small text files only; no keys (`.ecmwfdatastoresrc` stays in your user folder).
