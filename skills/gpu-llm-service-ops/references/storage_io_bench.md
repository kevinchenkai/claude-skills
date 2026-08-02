# Storage And I/O Benchmarking (H20 fleet)

Use this reference when asked to compare storage backends, explain why a mount is slow, choose a location for checkpoints / conda envs / datasets, or run a reproducible I/O benchmark on a GPU host.

## Mount Topology

**Mounts differ per host — probe before assuming.** Verified on `juscent-train-h20-0` (2026-07-17) and `juscent-train-1-0` (2026-07-24).

| Code | Mount | Filesystem | Backing volume | Present on | Notes |
| --- | --- | --- | --- | --- | --- |
| **S1** | `/home/share1` | JuiceFS | `kingsoft-ai-kpfs` | **train-h20 only** | 221T, often >90% full. Same volume as `/home/model`. |
| **NFS** | `/nfs` | NFS 4.2 | `shared-conda-env-nfs` | both | 4.9T. `rsize/wsize=1048576`, `hard`, `proto=tcp`. Holds `/nfs/envs`. |
| **S2** | `/home/share` | JuiceFS | `bj-jfs-prod` | both | 200T, roomiest. Juscent + Seasun model stores live here. |
| `model-ro` | `/home/model` | JuiceFS (**ro**) | `kingsoft-ai-kpfs` | **train-h20 only** | Read-only view of the S1 volume — report separately from S1 scratch. |

On **train-1**, `/home/share1` and `/home/model` do **not exist** (confirmed 2026-07-24) — a three-way comparison is only possible on train-h20. train-1 has `/` on `overlay` (7.0T local), the fast path for genuinely scratch data. `train-h20` additionally has `/home/jovyan` on NFS4.2 (a different export than `/nfs`).

```bash
# Always confirm first:
ssh <host> 'df -hT / /home/share /nfs /home/share1 /home/model 2>&1 | grep -v "^df:"'
```

## Measured Baseline (train-h20, lite run 2026-07-17)

Qwen3-4B shards + 2 GiB synthetic, block size 1 MiB. Full data: `Work/GPU-Ops/io-bench-results/lite_20260717_164110/`.

| Metric | S1 (kpfs) | NFS | S2 (bj-prod) |
| --- | ---: | ---: | ---: |
| seq write 2 GiB | 945 MB/s | **145 MB/s** | **965 MB/s** |
| seq read cold | 447 MB/s | 444 MB/s | **709 MB/s** |
| seq read hot | 5660 MB/s | **534 MB/s** | 5124 MB/s |
| model shard cp (3.7 GiB) | 916 MB/s | **141 MB/s** | 864 MB/s |
| shard read post-copy | 611 MB/s | 405 MB/s | **934 MB/s** |
| small-file create (4 KiB) | **23.7 fps** | **193 fps** | (see results.md) |
| concurrent write c4 | 1197 MB/s | **174 MB/s** | (see results.md) |

### What this means operationally

- **NFS writes are ~6.7× slower than either JuiceFS volume** and do not scale with concurrency (c1 183 MB/s → c4 174 MB/s, i.e. flat/negative). This is the quantitative reason behind the standing rule *never `pip install` into `/nfs/envs`* — a large install is both slow and contends with every other host sharing the volume.
- **JuiceFS hot reads hit ~5 GB/s** because of page cache + local block cache; NFS hot read only reaches ~534 MB/s. Never quote a hot number as throughput.
- **JuiceFS small-file create is catastrophic** (S1 23.7 fps vs NFS 193 fps). Do not untar, `pip install`, or build source trees directly on S1/S2. NFS wins on metadata; local overlay wins outright.
- **S2 (`/home/share`) is the best general-purpose shared volume** — fastest cold read and post-copy read, and the most free space. It is already where the model stores live.

### Placement guidance

| Workload | Put it on |
| --- | --- |
| Model weights, shared read-mostly | **S2** `/home/share/game/{juscent,seasun}/models` |
| Checkpoints / training output | **S2** `…/train_outputs` |
| conda envs (shared across hosts) | **NFS** `/nfs/envs` — accept slow writes; never install from multiple hosts |
| pip install / build / untar | **local overlay** (`/tmp`, `/home/jovyan/code`), then move |
| Scratch during benchmarking | per-target scratch dirs (below) |

## Running The Benchmark

Harness: `Work/GPU-Ops/scripts/io_bench_h20.py` (self-contained, stdlib only — copy to the host and run).

```bash
scp Work/GPU-Ops/scripts/io_bench_h20.py train-h20:/tmp/
ssh train-h20 'source /opt/conda/etc/profile.d/conda.sh && python3 /tmp/io_bench_h20.py \
  --run-id "lite_$(date +%Y%m%d_%H%M%S)" --targets s1,nfs,s2 --lite --cleanup'
```

Key flags: `--targets` (subset of `s1,nfs,s2`), `--lite` (2 GiB instead of 10 GiB), `--large-mb`, `--mid-n`, `--small-n`, `--conc` (default `1,4,8,16,32`), `--result-root`, `--cleanup`.

Scratch paths — **`/home/share` root is not writable by this account**, so S2 scratch must go under `game/`:

```text
S1   /home/share1/tmp/io_bench_scratch
NFS  /nfs/io_bench_scratch
S2   /home/share/game/io_bench_scratch
```

### Methodology constraints (these are host limitations, not preferences)

- **No `fio` on these hosts** — the Python harness is the tool. `dd` is available for cross-checking.
- **No passwordless `sudo` → `drop_caches` is impossible.** You cannot get a true cold read.
- **~1 TiB RAM means the page cache is enormous.** Without care every read is a cache hit and JuiceFS reports multi-GB/s. Cold reads are approximated by: reading a path never touched this session, using a different offset/file, always measuring cold *before* hot, and optionally `posix_fadvise(DONTNEED)` (process-local only).
- Always report `cold_read` and `hot_read` as **separate columns**. Never merge or average them.
- Repeat each measurement ≥3× and report median + min/max.
- Treat "copy A→B then read on B" as a *hot* read of B, not a cold one.
- Model source trees (`/home/share1/model/**`, `/home/share/game/seasun/models/**`) are **read-only sources** — never write or delete there.

## KS3 Object Storage

Tool `/home/share/game/ks3util` with config `/home/share/game/ks3.config`; internal endpoint `ks3-cn-beijing-internal.ksyuncs.com`.

```bash
KS3=/home/share/game/ks3util; KS3CFG=/home/share/game/ks3.config
$KS3 -c $KS3CFG ls ks3://<bucket>/<prefix>/ --limited-num 50
```

When comparing KS3 download throughput across the three mounts, download the **same object** to each scratch dir so the source is identical.
