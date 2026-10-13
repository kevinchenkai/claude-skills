# KS3 (ks3util) upload / download

Key points only. Full manual, command catalogue and pitfall table live in the project repo
`chenkai_airepo`: `GPU-Ops/storage/ks3util-guide-claude-20261013.md` (source of truth).
Items marked *measured* were verified 2026-10-10 → 10-13.

## Two environments

| | Cluster (hosts mounting `/home/share`) | Mac |
| --- | --- | --- |
| Binary | `/home/share/game/ks3util` (2.12) | `ks3util` (2.18) |
| Config | `--config-file=/home/share/game/ks3.config` | `~/.ks3utilconfig` |
| Endpoint | internal `ks3-cn-beijing-internal.ksyuncs.com` | **external only** `ks3-cn-beijing.ksyuncs.com` |
| sudo | **not needed** (config is 644); sudo makes outputs root-owned | — |

- Mac internal endpoint routes via aTrust but every connection is reset (*measured*). A
  `connection reset` on Mac usually means the endpoint was switched back to internal.
- No direct Mac ↔ shared-disk path: **relay through KS3** (Mac uploads, cluster downloads).
- Bucket `ks3://share-dataset/`; write **only under your own project prefix**.

## Four hard rules

1. **Always `-f` when overwriting.** Without it ks3util asks `(y or N)`: downloads hang, uploads
   are silently skipped. (10-11: `MD5SUMS` missed 60 entries this way; the script only checked tar sizes.)
2. **Run in a work dir or pass `--log-path`** (also `--output-dir`, `--checkpoint-dir`), otherwise
   `logs/`, `ks3util_output/`, `.ks3util_checkpoint/` land in the current directory.
3. **Long jobs in tmux** with `< /dev/null` and a final `EXIT=$?` marker line; poll the marker.
4. **Verify after transfer** — never trust the exit code (see below).

## Verification

- Ship an `MD5SUMS.txt` (`md5  name`, two spaces) with the data; `md5sum -c` after download.
  On Mac use `md5 -q`, its default format differs.
- Compare **per-file** sizes, not just totals. `ls` long format: `split()` index 4 = bytes,
  6 = Etag. Re-download files you overwrote (`MD5SUMS.txt`, `README.md`) and `cmp` / count lines.
- **Etag equals md5 only for single-part uploads ≤ 100 MB**; larger files are multipart and the
  Etag is not an md5 (*measured*, 130 / 150 MB).
- `du` object count includes zero-byte directory placeholders — compare bytes, not counts.
  2.12 prints `Object Size is: N`, 2.18 prints `Total object size: N(byte)`; parse both.
- `-u` is mtime-based: a file edited again within minutes of the last upload can be skipped.
  When verification disagrees, upload that file alone with `-f` and no `-u`.
- `--exclude` matches file names only; use `--only-current-dir` for top-level files.

## Safety

- Never print the config file, never pass keys with `-i` / `-k`, never copy the config off the cluster.
- `rm` / `mv` / `sync --delete` need the **data owner's explicit consent**; `ls` the scope first;
  never recursive-delete a prefix. `cp -u` does not delete anything remotely.
- Do not write into prefixes you do not own (ownership of most top-level prefixes is unverified).

## Reference implementations (project repo `chenkai_airepo`)

- `MacOS/movies/moviedb/ops/ks3_sync.sh` — cluster → KS3 incremental delivery with MD5SUMS + `du` check
- `MacOS/movies/moviedb/ops/mac_media_to_share.sh` — Mac → KS3 → shared disk, md5 on both ends
- `Claude/GPU_ops/ks3_backup_task.md` — TB-scale backup, dry-run + per-directory checkpoints
