"""New_Plan 25: build one run's training config from a base config, an arm's delta file and key=value overrides.

    python scripts/s25_cfg.py DELTA.toml OUT.toml [key=value ...]          (value is TOML: 3e-4, "x", true, {K = 3}; dotted keys go into tables: s25.K=5)

DELTA.toml holds only what the arm changes, plus `base = "configs/generator_c4w.toml"` (default: the shipped c4w line). The train CLI has no
seed / steps flags, so every seed and step count gets its own written copy. Keys are checked against tempest.generator.train.DEFAULTS
(plus `members`), so a typo fails here instead of training silently with the default.
"""
import os
import sys
import tomllib

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "configs/generator_c4w.toml"


def _val(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_val(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k} = {_val(x)}" for k, x in v.items()) + "}"
    raise TypeError(f"cannot write {type(v).__name__} to TOML")


def dumps(cfg):
    return "".join(f"{k} = {_val(v)}\n" for k, v in cfg.items())


def default_keys():
    """Keys of train.DEFAULTS = dict(...), read from the source so the check does not import torch (seconds per call)."""
    import ast
    with open(os.path.join(REPO, "tempest", "generator", "train.py"), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "DEFAULTS" for t in node.targets):
            return {k.arg for k in node.value.keywords}
    raise SystemExit("train.DEFAULTS not found")


def build(delta_path, overrides=()):
    with open(delta_path, "rb") as f:
        delta = tomllib.load(f)
    with open(delta.pop("base", BASE), "rb") as f:
        cfg = tomllib.load(f)
    for k, v in delta.items():
        cfg[k] = {**cfg[k], **v} if isinstance(v, dict) and isinstance(cfg.get(k), dict) else v
    for kv in overrides:
        k, v = kv.split("=", 1)
        v = tomllib.loads(f"x = {v}")["x"]
        if "." in k:
            top, sub = k.split(".", 1)
            cfg[top] = {**(cfg.get(top) or {}), sub: v}
        else:
            cfg[k] = v
    bad = sorted(set(cfg) - default_keys() - {"members"})
    if bad:
        raise SystemExit(f"unknown config keys {bad} (not in train.DEFAULTS)")
    return cfg


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    cfg = build(sys.argv[1], sys.argv[3:])
    text = dumps(cfg)
    assert tomllib.loads(text) == cfg, "TOML round trip changed the config"
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(text)
    print(f"{sys.argv[2]}: " + ", ".join(f"{k}={cfg[k]}" for k in ("seed", "steps", "lr", "weight_decay", "batch", "arch") if k in cfg))


if __name__ == "__main__":
    main()
