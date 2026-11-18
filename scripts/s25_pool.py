"""New_Plan 25 GT2 (IL-23): pool the members of two trained models into one ensemble file; the shipped Sampler builds every member from its
own cfg (arch, width, model_kw) and normalisation, and splits samples evenly over all members.

    python scripts/s25_pool.py A.pt B.pt OUT.pt          (e.g. models/s25/base_s0.pt models/s25/gt2_il8b_s0.pt models/s25/gt2_pool_s0.pt)
    python scripts/s25_pool.py --selfcheck

Refuses to pool models whose data contract differs (input columns, targets, humidity target, sp offset, n_cond, n_out): a pooled file must
read the same rows the same way in every member.
"""
import os
import sys

import torch

SAME = ("cond_names", "target_names", "rh_target", "sp_offset", "n_cond", "n_out")


def members(path):
    ck = torch.load(path, map_location="cpu", weights_only=True)
    return ck.get("members", [ck])


def pool(paths):
    ms = [m for p in paths for m in members(p)]
    for k in SAME:
        vals = {repr(m.get(k)) for m in ms}
        if len(vals) > 1:
            raise ValueError(f"cannot pool: members differ in {k}: {sorted(vals)}")
    return dict(members=ms)


def main():
    if sys.argv[1:] == ["--selfcheck"]:
        return _selfcheck()
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    out = sys.argv[3]
    if os.path.exists(out):
        raise SystemExit(f"{out} exists; not overwriting")
    ck = pool(sys.argv[1:3])
    torch.save(ck, out + ".part")
    os.replace(out + ".part", out)
    print(f"wrote {out}: {len(ck['members'])} members, archs {[m['cfg'].get('arch', 'mlp') for m in ck['members']]}")


def _selfcheck():
    import tempfile
    a = dict(members=[dict(n_cond=3, n_out=5, cond_names=["x"], cfg=dict(arch="mlp"))] * 2)
    b = dict(n_cond=3, n_out=5, cond_names=["x"], cfg=dict(arch="tokens"))
    with tempfile.TemporaryDirectory() as d:
        pa, pb, pc = (os.path.join(d, n) for n in ("a.pt", "b.pt", "c.pt"))
        torch.save(a, pa)
        torch.save(b, pb)
        assert [m["cfg"]["arch"] for m in pool([pa, pb])["members"]] == ["mlp", "mlp", "tokens"]
        torch.save({**b, "n_out": 6}, pc)
        try:
            pool([pa, pc])
            raise AssertionError("pooled different n_out")
        except ValueError:
            pass
    print("selfcheck ok")


if __name__ == "__main__":
    sys.exit(main())
