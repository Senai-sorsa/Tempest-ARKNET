"""G5 global export (GLOBAL_PLAN G5): the generator as one ONNX graph, FP32 + FP16 + dynamic INT8, with the gates.

    python -m tempest.export_onnx --model models/global/G.pt --data data/train/g_test.npz --out models/global/onnx
           [--rows 2000 --m 100 --first-year 2024]

Graph: inputs cond (N, F) raw features, eps (N, noise_dim) standard normal noise and chi (N, dims) Chi2(nu) draws for
Student-t noise models (ones of width 1 otherwise; gates.json has nu and dims), N a multiple of the member count K;
output (N, D) raw targets, row i from member i % K (as tempest.generator.sample.Sampler). The surface-pressure offset
(standard_pressure of the elevation column, ckpt sp_offset) and the physical conversion stay outside the graph.
INT8: weights only (onnxruntime quantize_dynamic), the last matrix product before the output kept FP32.
Gates (results in <out>/gates.json): INT8 vs FP32 on held-out rows with the same noise: CRPS within 0.3 % (mean over columns of the relative change), 99.9th
percentile step shear within 1 %; 100 samples of one condition in < 250 ms on 4 threads; bundle (INT8 graph) < 75 MB.
Needs onnx and onnxruntime (uv pip install onnx onnxruntime; FP16 also onnxconverter-common), imported lazily.
"""
import argparse
import json
import os
import time

import numpy as np
import torch
from torch import nn

from tempest.profiles.to_heights import HEIGHTS

GATE_CRPS, GATE_TAIL, GATE_MS, GATE_MB = 0.003, 0.01, 250.0, 75.0
NH = len(HEIGHTS)


class Wrapped(nn.Module):
    """Members with their normalisation, rows interleaved over members (row i -> member i % K)."""

    def __init__(self, ckpt):
        super().__init__()
        from tempest.generator.model import Generator
        from tempest.generator.sample import Sampler
        s = Sampler(ckpt, device="cpu")
        if not all(isinstance(m, Generator) for m, _ in s.members):
            raise SystemExit("export_onnx: only the mlp generator takes external noise; TokenGenerator draws its own")
        self.nets = nn.ModuleList([m for m, _ in s.members])
        for k in ("cm", "cs", "ts", "tm"):
            self.register_buffer(k, torch.stack([n[k].float() for _, n in s.members]))
        self.K, self.noise_dim = len(s.members), s.members[0][0].noise_dim
        nt = s.members[0][0].noise_t
        if any(m.noise_t != nt for m, _ in s.members):
            raise SystemExit("export_onnx: members differ in noise_t")
        self.chi_dims, self.nu = (int(nt["dims"]), float(nt["nu"])) if nt else (1, 0.0)   # Student-t noise: Chi2 draw is an input
        self.sp_offset = s.sp_offset

    def forward(self, cond, eps, chi):
        c = cond.reshape(-1, self.K, cond.shape[-1])
        e = eps.reshape(-1, self.K, eps.shape[-1])
        x = chi.reshape(-1, self.K, chi.shape[-1])
        kw = (lambda k: {"chi": x[:, k]}) if self.nu else (lambda k: {})
        out = [self.nets[k]((c[:, k] - self.cm[k]) / self.cs[k], 1, eps=e[:, k], **kw(k))[:, 0] * self.ts[k] + self.tm[k] for k in range(self.K)]
        return torch.stack(out, 1).reshape(cond.shape[0], -1)


def export(ckpt, out_dir, n_cond):
    w = Wrapped(ckpt).eval()
    os.makedirs(out_dir, exist_ok=True)
    f32 = os.path.join(out_dir, "generator_fp32.onnx")
    ex = (torch.zeros(w.K * 2, n_cond), torch.zeros(w.K * 2, w.noise_dim), torch.ones(w.K * 2, w.chi_dims))
    torch.onnx.export(w, ex, f32, input_names=["cond", "eps", "chi"], output_names=["raw"], opset_version=17, dynamo=False,
                      dynamic_axes={k: {0: "n"} for k in ("cond", "eps", "chi", "raw")})
    return w, f32


def _last_products(path):
    """Names of the MatMul / Gemm nodes with no other MatMul / Gemm between them and the graph output."""
    import onnx
    g = onnx.load(path).graph
    users = {}
    for n in g.node:
        for i in n.input:
            users.setdefault(i, []).append(n)
    outs, keep = {o.name for o in g.output}, []
    for n in g.node:
        if n.op_type not in ("MatMul", "Gemm"):
            continue
        todo, seen, hit = list(n.output), set(), False
        while todo and not hit:
            t = todo.pop()
            if t in outs:
                hit = True
            for u in users.get(t, []):
                if u.op_type not in ("MatMul", "Gemm") and u.name not in seen:
                    seen.add(u.name)
                    todo += list(u.output)
        if hit:
            keep.append(n.name)
    return keep


def quantise(f32, out_dir):
    from onnxruntime.quantization import QuantType, quantize_dynamic
    i8 = os.path.join(out_dir, "generator_int8.onnx")
    quantize_dynamic(f32, i8, weight_type=QuantType.QInt8, nodes_to_exclude=_last_products(f32))
    paths = {"fp32": f32, "int8": i8}
    try:
        import onnx
        from onnxconverter_common import float16
        f16 = os.path.join(out_dir, "generator_fp16.onnx")
        onnx.save(float16.convert_float_to_float16(onnx.load(f32), keep_io_types=True), f16)
        paths["fp16"] = f16
    except ImportError:
        print("onnxconverter-common not installed: FP16 skipped", flush=True)
    return paths


def session(path, threads=4):
    import onnxruntime as ort
    o = ort.SessionOptions()
    o.intra_op_num_threads, o.inter_op_num_threads = threads, 1
    return ort.InferenceSession(path, o, providers=["CPUExecutionProvider"])


def step_shear(raw):
    """(..., D) raw targets (u, v as height steps) -> (..., 43) |dV| / dz, m/s per km."""
    dz = np.diff(np.asarray(HEIGHTS, float)) / 1000.0
    return np.hypot(raw[..., 1:NH], raw[..., NH + 1:2 * NH]) / dz


def gates(paths, w, cond, y, m=100, seed=0, threads=4):
    """cond (n, F), y (n, D) held-out rows -> dict of gate numbers (INT8 and FP16 against FP32, same noise)."""
    from tempest.scoring.score import crps_ensemble
    n = len(cond)
    m = -(-m // w.K) * w.K                                                        # whole member cycles per row
    c = np.repeat(np.asarray(cond, np.float32), m, 0)
    rng = np.random.default_rng(seed)
    e = rng.standard_normal((len(c), w.noise_dim)).astype(np.float32)
    x = (rng.chisquare(w.nu, (len(c), w.chi_dims)) if w.nu else np.ones((len(c), 1))).astype(np.float32)
    feed = {"cond": c, "eps": e, "chi": x}
    with torch.no_grad():
        ref_torch = w(*(torch.from_numpy(feed[k]) for k in ("cond", "eps", "chi"))).numpy()
    res, s, cc = {}, {}, {}
    for k, p in paths.items():
        try:
            sess = session(p, threads)
        except Exception as err:                                                  # FP16 is extra (no gate): record, go on
            if k == "fp16":
                res["fp16_error"] = str(err)[:300]
                continue
            raise
        s[k] = sess.run(None, feed)[0].reshape(n, m, -1)
        if w.sp_offset is not None:                                               # y holds the full sp; the graph leaves the offset out (as Sampler adds it)
            from tempest.generator.sample import standard_pressure
            j, ec = w.sp_offset
            s[k][..., j] += standard_pressure(np.asarray(cond, np.float64)[:, ec]).astype(np.float32)[:, None]
        cc[k] = np.nanmean(crps_ensemble(s[k], np.asarray(y, np.float32)), 0)          # per column: sp (Pa) would dominate a pooled mean
        res[f"{k}_crps"] = float(np.nanmean(cc[k]))
        res[f"{k}_shear999"] = float(np.nanquantile(step_shear(s[k]), 0.999))
        one = {q: v[:m] for q, v in feed.items()}
        sess.run(None, one)
        t = time.perf_counter()
        for _ in range(20):
            sess.run(None, one)
        res[f"{k}_ms_per_{m}"] = (time.perf_counter() - t) / 20 * 1000
        res[f"{k}_mb"] = os.path.getsize(p) / 1e6
    res["fp32_vs_torch_maxabs"] = float(np.abs(s["fp32"].reshape(len(c), -1) - ref_torch).max())
    res["int8_crps_rel"] = float(np.nanmean(cc["int8"] / cc["fp32"] - 1))           # mean over columns of the relative change
    res["int8_crps_rel_worst_col"] = float(np.nanmax(np.abs(cc["int8"] / cc["fp32"] - 1)))
    res["int8_tail_rel"] = res["int8_shear999"] / res["fp32_shear999"] - 1
    res["pass"] = dict(crps=abs(res["int8_crps_rel"]) <= GATE_CRPS, tail=abs(res["int8_tail_rel"]) <= GATE_TAIL,
                       speed=res["int8_ms_per_%d" % m] < GATE_MS, size=res["int8_mb"] < GATE_MB,
                       export=res["fp32_vs_torch_maxabs"] < 1e-3 * max(1.0, float(np.abs(ref_torch).max())))
    res["pass_all"] = all(res["pass"].values())
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--data", required=True, help="dataset .npz (cond, target, year) for the gate rows")
    ap.add_argument("--out", required=True)
    ap.add_argument("--rows", type=int, default=2000)
    ap.add_argument("--m", type=int, default=100)
    ap.add_argument("--first-year", type=int, default=2024)
    ap.add_argument("--threads", type=int, default=4)
    a = ap.parse_args()
    torch.set_num_threads(a.threads)
    from tempest.generator.train import load_npz
    d = load_npz(a.data)
    yr = np.asarray(d["year"])
    idx = np.flatnonzero((yr >= a.first_year) & (yr <= 2025))                     # G stages never read 2026 rows
    idx = np.sort(np.random.default_rng(0).choice(idx, min(a.rows, len(idx)), replace=False))
    ck = torch.load(a.model, map_location="cpu", weights_only=True)
    w, f32 = export(ck, a.out, d["cond"].shape[1])
    paths = quantise(f32, a.out)
    res = gates(paths, w, d["cond"][idx], d["target"][idx], a.m, threads=a.threads)
    res |= dict(model=os.path.basename(a.model), rows=len(idx), members=w.K, noise_dim=w.noise_dim, nu=w.nu, chi_dims=w.chi_dims, sp_offset=None if w.sp_offset is None else list(map(int, w.sp_offset)),
                cond_names=[str(x) for x in d["cond_names"]] if "cond_names" in d else None)
    with open(os.path.join(a.out, "gates.json"), "w") as fh:
        json.dump(res, fh, indent=1)
    print(json.dumps(res, indent=1), flush=True)
    print(f"G5 export gates: {'PASS' if res['pass_all'] else 'FAIL'}", flush=True)


if __name__ == "__main__":
    main()
