# KAS Multi-Node IB Training (VeOmni / torchrun)

Use this reference for multi-node distributed training on the KAS platform: reading or editing multinode launch scripts, mapping `KAS_*` rendezvous variables to `torchrun`, tuning NCCL over InfiniBand/RoCE, and diagnosing "is it actually using IB?" questions.

Reference job: `veomni-seasun-vla-jx3-V0014-071602` · code root `/home/share/game/code/VeOmni` · entry `run_seasun_jx3_qwen3_vla_multinode.sh`.

## Layer Boundaries

| Layer | Responsible for | NOT responsible for |
| --- | --- | --- |
| **KAS platform** | Launching N worker Pods, GPU binding, shared-disk mounts, injecting `KAS_*` rendezvous vars, master DNS | `torchrun` flags, training loop |
| **`…_multinode.sh`** | `KAS_*` → `torchrun` env mapping, NCCL/IB tuning, YAML + CLI overrides, `OUTPUT_DIR` | Discovering nodes itself |
| **`train.sh`** | Counting visible GPUs → `nproc-per-node`, assembling `torchrun` | IB device/driver setup |
| **NCCL + driver** | Cross-node bulk collectives over mlx5 | Scheduling |
| **VeOmni (FSDP2)** | Sharded training, optimizer step | Replacing platform rendezvous |

Traffic planes: **eth0** = rendezvous / bootstrap / control. **IB-RoCE (mlx5)** = NCCL collectives, the real bandwidth. **NVLink** = intra-node GPU P2P. **Shared disk** = data / checkpoints / logs.

## KAS → torchrun Variable Mapping

| KAS variable | Meaning | Maps to |
| --- | --- | --- |
| `KAS_NNODES` | total node count (≥2) | `NNODES` |
| `KAS_NODE_RANK` | this node's rank, 0-based | `NODE_RANK` |
| `KAS_MASTER_ADDR` | rank0 / master address (in-cluster DNS) | `MASTER_ADDR` |
| `KAS_MASTER_PORT` | rendezvous port (optional, default `12345`; platform often sets `23456`) | `MASTER_PORT` |

```bash
export NNODES="${KAS_NNODES:?}"
export NODE_RANK="${KAS_NODE_RANK:?}"
export MASTER_ADDR="${KAS_MASTER_ADDR:?}"
export MASTER_PORT="${KAS_MASTER_PORT:-12345}"
```

**Every node runs the identical command.** Only `KAS_NODE_RANK` (and locally visible GPUs) differ per node. The master address is a Kubernetes service DNS name, e.g. `kas-distributed-train-mission-job-12613-7wc97-master-0`.

Resulting launch:

```bash
torchrun --nnodes=${NNODES} --nproc-per-node=8 --node-rank=${NODE_RANK} \
         --rdzv_endpoint=${MASTER_ADDR}:${MASTER_PORT} ...
# single node instead uses: --standalone
```

`world_size = nnodes × nproc_per_node`. Do **not** hardcode `nproc-per-node=8` — derive it from visible GPUs; it is 8 only when the platform exposes 8 cards.

## NCCL / IB Tuning

Set by the multinode script:

| Variable | Value | Purpose |
| --- | --- | --- |
| `NCCL_DEBUG` | `INFO` | multinode default (single-node scripts use `WARN`) |
| `NCCL_TIMEOUT` | `1.8e8` | avoid false timeouts on long steps |
| `NCCL_IB_TIMEOUT` | `22` | IB transport timeout |
| `NCCL_IB_RETRY_CNT` | `13` | IB retry count |
| `NCCL_IB_GID_INDEX` | `3` | RoCE/IB GID index — cluster-specific |
| `NCCL_P2P_LEVEL` | `NVL` | restrict intra-node P2P to NVLink |
| `NCCL_SOCKET_NTHREADS` | `8` | socket-path threads |
| `TORCH_NCCL_AVOID_RECORD_STREAMS` | `1` | PyTorch NCCL stream behavior |
| `CUDA_DEVICE_MAX_CONNECTIONS` | `1` | comm/compute overlap strategy |
| `NCCL_SOCKET_IFNAME` | default-route NIC | bootstrap/control over ethernet |

```bash
export NCCL_SOCKET_IFNAME="$(ip r | grep 'default' | awk '{print $NF}')"   # usually eth0 in a Pod
```

**The script does not set `NCCL_IB_DISABLE=1`** — that is deliberate. Given IB/RoCE devices and drivers, NCCL prefers IB automatically. Never add `NCCL_IB_DISABLE=1` as a "fix" unless deliberately forcing the socket path for diagnosis.

## Verifying IB Is Actually Used

```bash
ls /sys/class/infiniband/           # expect mlx5_0, mlx5_1, mlx5_bond_0, …
ls /dev/infiniband/
```

(Confirmed present on `train-1` 2026-07-24: `mlx5_0`, `mlx5_1`, `mlx5_bond_0`.)

In training logs with `NCCL_DEBUG=INFO`, grep for `NET/IB`, `IBHCA`, `mlx5`, `Using network`. If you see `NET/Socket` instead, NCCL fell back to ethernet — check device visibility and GID index first.

> **Important caveat:** a development Pod (e.g. a `vscode` Pod) having `mlx5` devices does **not** mean the training Pod sees the same devices. Judge from the **training job's own log** and the **training node's** `/sys/class/infiniband`, not from a dev box.

Platform-side prerequisites: containers can see IB devices, nodes share an IB subnet (same fabric / correct GID), and GPUDirect RDMA if the image and driver support it.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| Hang at startup, no rank progress | rendezvous failure — check `MASTER_ADDR` DNS resolves in-cluster and `MASTER_PORT` matches on all nodes |
| Works single-node, hangs multi-node | IB not reachable across nodes, or wrong `NCCL_IB_GID_INDEX` |
| Very low cross-node bandwidth | NCCL fell back to socket — confirm `NET/IB` in logs |
| Spurious timeouts on long steps | `NCCL_TIMEOUT` too low |
| Only rank 0 starts | `KAS_NODE_RANK` not differing per node |
