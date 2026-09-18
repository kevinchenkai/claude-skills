# 知识库地图与已验证的重点结论

本文件帮你在 1607 个 .md 里**快速落到正确的页**，并记下几条实测确认过的结论，
免得每次都从头查。所有内容以知识库为准；这里的摘要**只作导航**，
**引用数字时必须回到 `sources/` 原始记录**（`wiki.sh trace`）。

规模（2026-09-18 实测）：`sources/` 1491 · `experiments/` 47 · `findings/` 43 ·
`evaluations/` 9 · `topics/` 7 · `datasets/` 6。

## 六层目录 = 认识可靠程度的阶梯

目录不是按主题分的，是**按认识的可靠程度**分的。往上一层，门槛高一级：

```
findings/     门槛最高 · 周报进不来 —— 跨实验、当前仍成立，必须列支撑实验
topics/       门槛高       —— 横切主题，保留结论的演变过程
datasets/     门槛中       —— 版本、来源、被哪些实验使用
evaluations/  门槛中       —— 指标必须能回溯到原始记录
experiments/  有设计书或评测结果才建页
sources/      门槛最低 · 允许冲突与过时 —— 只增不改
```

`sources/` **故意不清场**：允许过时、允许互相打架。价值正在于不必先把历史洗干净
才能开始积累。给人和 Agent 当下引用的是上面几层——**但数字仍要回到 `sources/` 核对**。
这两句不矛盾：上层负责「当前怎么理解」，下层负责「凭什么这么说」。

它要对抗的失败模式很具体（原文）：实验编号被当成能力版本、run 名被当成配置；
Agent 只读过综述里的数字而数字已经漂了；冲突的旧文档被「整理掉」导致后人
看不到当时为什么那样做；知识只存在某次聊天里，换个会话就丢。

## 项目是什么

单个 VLA（视觉-语言-动作）训练项目：让模型看游戏画面、跟随指令、输出动作串。
技术栈 VeOmni + Qwen3-VL-4B，run 从 v0002 排到 v0023，训练在 H100 / H200。
`findings/project-endpoint-is-in-game-companion-vla-is-cerebellum.md` 说明产品定位。

## 六条主线（`topics/` 是每条的主线认识）

| 主线 | 入口 | 一句话 |
|---|---|---|
| IF 指令跟随 | `topics/instruction-following-evolution.md` | 从「有 prompt」到「动作真的依赖指令」 |
| PT 预训练 | `topics/training-timeline.md` | 训练主线编年，v0011→v0021 |
| 动作串 token 优化 | `topics/action-token-optimization.md` | tokopt 在 V0017D 落地 |
| 推理与部署性能 | `topics/inference-deployment-performance.md` | 200ms 目标的延迟分解 |
| 训练吞吐与硬件 | `topics/h200-migration-and-mfu.md` | H200 同配置没变快，价值在解锁新配置 |
| 离线评测账本 | `topics/offline-eval-ledger.md` | 评测口径与索引 |

## 样板案例：880 image tokens（照着做一次溯源）

这是本库最有代表性的一条，**适合当作检索范例**，也是一条真实的高危坑。

```bash
./scripts/wiki.sh trace '880'                 # 分层看证据
./scripts/wiki.sh grepall 'image_grid_thw'    # 找判据字段
```

**结论**：`880` 不是任何人选的配置，是**没人能从 yaml 看出来的涌现值**。

- 几何：1280×720 →smart_resize→ 1280×704，grid `[1,44,80]`，44×80=3520 patch，
  ÷4（merge_size=2）= **880 token**。对照档 **576** 是 1024×576、grid `[*,36,64]`。差 **304**。
- 机制：**tokens/image 不受任何 yaml key 控制**。`data.mm_configs.image_max_pixels`
  只喂一个空转预过滤器，从不进 `build_processor`。真正上限硬编码在
  `veomni/trainer/vlm_trainer.py:35`（`MAX_PIXELS=602112`），
  但**是否生效取决于用哪个 processor**：`Qwen2VLImageProcessorFast` 静默忽略
  `max_pixels`（⇒880），`Qwen2VLImageProcessor`（slow）遵守（⇒576）。
  根因精确到 `image_processing_qwen2_vl_fast.py:122-128`：只在 `min_pixels`
  同时非 None 时才采纳 `max_pixels`，而 `vlm_trainer.py` 从不传 `min_pixels`。
- 时间线：v0004–v0013、V0016/V0018 跑在 **880**；**V0014 中途 resume（2026-07-18）**
  换了 processor，此后 V0015/V0017*/V0019/V0020 跑在 **576**。证据是同数据同 config 下
  `max_length_q` 均值 1095.0→785.6（Δ309，与算术预测 Δ304 吻合）。**没人主动改过它。**
- 后果：① v0021 的 `max_seq_len: 16384` 建立在「576」的错误注释上，按 880 算
  20 帧窗是 17,600 image tokens，**超上限**；② 已确认的 train/eval 失配——V0017* 训练在 576、
  2026-08-11 IF 探针端点在 880，使 `R=0.94%` 是否被污染**未定**，不能直接当「模型忽视指令」的干净证据；
  ③ 底座血统实验被迫把分辨率列为必须锁死的一轴；④ 推理侧图像占 prompt 的 84%/74%
  且每帧都变，前缀缓存理论上限只有 15.4%/25.7%。
- **纪律**：tokens/image **必须从 run log 读 `image_grid_thw`**
  （`[*,36,64]`=576，`[*,44,80]`=880），**不得从配置推**。
  `vlm_trainer.py:247-250` 那条日志只打印配置值不打印实际 grid，**坐实不了这件事**。

⚠️ 溯源时会同时读到 `sources/docs/nexus-tmp/SPEC-O10-maxpixels.md`，它描述的是
**把全链路收敛到 576 的整改目标**（KR 式目标 + 断言测试），与上面「历史上曾是 880」
并不矛盾，但**分属不同时间点**。这正是 `sources/` 允许冲突的典型场景——
判断现状要看 run log，不要看任一份文档的声称。

## 已验证结论速查

跨实验且当前仍成立的在 `findings/`（43 条）。挑几条容易踩的：

- `archived-config-is-not-what-trained.md` —— 归档配置 ≠ 实训配置
- `veomni-training-checkout-is-vla-code.md` —— 真正的训练 checkout 是 `vla_code/VeOmni`
- `import-veomni-resolves-to-site-packages.md` —— `import veomni` 会落到旧包上
- `count-flops-uses-wrong-head-dim.md` —— MFU 数字全体受影响
- `utilization-was-always-in-tensorboard.md` —— 利用率一直在，只是没进日志
- `veomni-shuffles-row-order-by-default.md` —— 单 jsonl 默认全长洗牌
- `h100-has-no-external-internet.md` —— H100 无外网，交互须离线可用

**已被推翻的**（`wiki.sh stale` 可列全）：
`no-run-has-ever-exceeded-mfu-036.md` 已被 0.3617/0.3733 推翻，标 superseded。

## 证据链的已知缺口

知识库自己标注的【待校准】，引用时要连缺口一起说：

- V0014 那次 resume 的直接证据（`max_length_q` 1095.0→785.6）**在 H100 的 run log 上，
  工作区没有**；本地只有 v0019/v0020/v0021 报告提到 `image_grid_thw`。
- V0017D 导出的 `global_step_9080` 到底是 ep2 还是 ep4 终态未定
  （命名写 ep4，而 `floor(1,162,311/256)×2=9,080` 数字上正好是 ep2）。
  **按 rows/gbs 复算，不要采信目录名。**
- 880/576 这条结论**目前没有独立的 `findings/` 页**（43 条里没有），
  知识散在 6–7 份 `sources/` 文档和几个 `experiments/` 页里。按该库
  「findings = 跨实验且当前仍成立的结论」的定义，**这是一个缺页**。
