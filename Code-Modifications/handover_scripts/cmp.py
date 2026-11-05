import pandas as pd, sys
a, b = [pd.read_csv(f) for f in sys.argv[1:3]]
for d in (a, b):
    d["var"] = d.column.str.split("_").str[0]
    d["h"] = pd.to_numeric(d.column.str.split("_").str[1], errors="coerce")
    d["band"] = pd.cut(d.h, [-1, 1000, 5000, 12000, 18001], labels=["0-1", "1-5", "5-12", "12-18"]).astype(str)
    d["cov"] = 1 - d.miss_lo - d.miss_hi
ga = a.groupby(["var", "band"])[["cov", "ss_ratio"]].agg({"cov": ["mean", "min"], "ss_ratio": "mean"})
gb = b.groupby(["var", "band"])[["cov", "ss_ratio"]].agg({"cov": ["mean", "min"], "ss_ratio": "mean"})
print(pd.concat([ga, gb], axis=1, keys=[sys.argv[1][-30:], sys.argv[2][-30:]]).round(4).to_string())
