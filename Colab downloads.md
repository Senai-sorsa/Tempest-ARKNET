# Colab downloads (need the user to run a notebook)

These are the WeatherBench2 (WB2) pulls. Automatic downloads are in `Downloads to do.md`. **Nothing here has been started**, and the user's current rule is no downloads beyond what is already running.

## Why these need Colab

- WB2 is a public, no-login Google Cloud bucket (`gs://weatherbench2/datasets/`, IL-6).
- Each chunk is **one whole-globe forecast**, so pulling it from home moves far too much data (about 200 GB even for today's small HRES set).
- So the extraction runs **inside Google, in a free Colab notebook**, like `notebooks/wb2_colab.md`. Only the 13x29 box leaves Colab.
- Claude cannot run Colab. The user runs the cells, then copies the files into `data/raw/`.
- Reference sizes for today's set (00Z every 4th day, 4 leads): 38 MB per year on disk, about 30 GB read per year inside Google, 20-90 min per year. The sizes below are scaled from that and are not measured.

## Code changes first

Do these after the other session's queue is idle. They are additive: the defaults keep today's behaviour.

1. **Add `--hours`** (start hours, default `0`) to `tempest/ingest/wb2_fetch.py`. `year()` selects 00 UTC only today.
2. **Save per month** (`<out>/<year><mm>.nc`, skipped if present). A big year takes longer than one free Colab session (about 12 h).
3. **Add `--url`** (default the current `weatherbench2/datasets/hres/2016-2022-0012-1440x721.zarr`), so the script can pull other models.
4. **Add `--levels`** (default all 13), for `ifs_ens`, which has 500/700/850 only.
5. One self-check: fetch one start, then assert the shape (lead, 13, 13, 29) and the times.

## C1. HRES refetch: 00Z + 12Z starts (item A; enables E and D parts 1-2) — highest value

**The one to do. Ready-to-run, self-contained instructions are in `Colab HRES refetch.md`.** It needs no repo code changes, which makes the code-change list above optional. The rest of this section is background.

| Option | Starts | Leads | Local disk (7 yrs) | Read in Google per yr | Colab time per yr |
|---|---|---|---|---|---|
| **Recommended** | 00+12Z, every 2nd day | 12, 24, …, 240 h (20) | about 5 GB | about 600 GB | about 7-30 h (resumes per month) |
| Full | 00+12Z, every day | 6, 12, …, 240 h (40) | about 20 GB | about 2.4 TB | days, not practical |
| Small | 00+12Z, every 4th day | 12, 24, …, 240 h (20) | about 2.5 GB | about 300 GB | about 4-15 h |

```python
!pip -q install gcsfs zarr xarray netCDF4
from google.colab import drive; drive.mount('/content/drive')
# upload tempest/ingest/wb2_fetch.py to the Colab files, then:
!mkdir -p /content/drive/MyDrive/tempest_wb2_v2
!python wb2_fetch.py --out /content/drive/MyDrive/tempest_wb2_v2 --first 2016 --last 2022 \
    --every-days 2 --hours 0 12 --leads $(seq 12 12 240) --workers 32
```

- Re-run the cell after a disconnect; finished months are skipped.
- Copy the files into a **new** folder, `data/raw/wb2_hres_v2/`. Never overwrite `data/raw/wb2_hres/`.

## C2. GraphCast, then Pangu (item F)

- **First:** in Colab, list `gs://weatherbench2/datasets/` (`gcsfs.GCSFileSystem(token='anon').ls(...)`) for the exact zarr paths, years, start hours and lead steps. Check the variable names; add a rename map if they differ.
- **Download:** the same command with `--url <path>` and `--out .../tempest_wb2_graphcast`. The size is about the same as C1 per model.
- **On your PC:** `data/raw/wb2_graphcast/`, `data/raw/wb2_pangu/`.
- **Check first:** the same model must be available live with pressure levels, or the tool cannot use it.

## C3. IFS ensemble, 500/700/850 hPa (the early version of item C) — most optional

**Ready-to-run, self-contained notebook: `Colab IFS ENS fetch.md`.** It needs no repo code changes, and cell 2 measures the chunking and read size before anything downloads. The notes below are background.

- **Skip it** if waiting 60-90 days for the logger is fine.
- **First:** check the chunking of `ifs_ens` in Colab. With 50 members, the read per start is much larger than HRES.
- **Download:** `--url <ifs_ens path> --levels 500 700 850`, 00Z every 8th day, leads 24-168 h every 24 h, 2016-2024.
- **Size:** about 5 GB on disk (pilot + Denver, from the store layout), which fits under the 100 GB cap.
- **On your PC:** `data/raw/wb2_ifs_ens/`.
