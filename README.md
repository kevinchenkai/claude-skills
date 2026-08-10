# claude-skills

个人使用的 Agent Skills 集合，由 [Claude Code](https://claude.com/claude-code)、Codex、Grok CLI、Cursor 四端共用。

## Skills

| Skill | 说明 |
| --- | --- |
| [`gpu-llm-service-ops`](skills/gpu-llm-service-ops) | GPU 服务器（SSH 访问）上的 conda 环境与推理/训练服务运维：vLLM、ComfyUI、ai-toolkit、kohya_ss、LlamaFactory、OneTrainer；共享 NFS conda 环境管理、tmux 会话、端口转发、存储 I/O 基准、KAS 多机分布式训练。 |
| [`h3-creative-video`](skills/h3-creative-video) | 用 MiniMax-H3 FL2VA 做创意短视频：创意与技术可行性、FL2VA 提示词（官方三字段 + 多镜头）、关键帧出图工单与真人感规范、ComfyUI 出片、判据验收与交付。含模型硬上限、已证伪的死路、双向标定过的判据脚本。 |

## 安装

本仓库是唯一真源。克隆到本地后，各端都软链过来，
改一处四端同时生效，`git push` 即备份：

```bash
git clone https://github.com/kevinchenkai/claude-skills.git ~/Work/claude-skills

for S in gpu-llm-service-ops h3-creative-video; do
  for D in ~/.claude ~/.codex ~/.grok ~/.cursor; do
    mkdir -p "$D/skills" && ln -sfn ~/Work/claude-skills/skills/$S "$D/skills/$S"
  done
done
```

---

## 用 `h3-creative-video` 开一个新的视频创意

### 两种模式

| 模式 | 分工 |
| --- | --- |
| **Codex 全流程** | Codex 一个人跑完：环境预检 → 创意 → 建项目 → **自己调 image gen 出关键帧** → SSH 出片 → 验收 → 交付 |
| **Claude + Codex** | **Codex 只负责出关键帧图片**；创意、工单、出片、验收、交付都由 Claude 做 |

> 🔴 **两个都在场时优先用第二种** —— 出片方和验收方分开。
> 实测:出片方把 0.7–1.0 秒的冻结报成「不足 1 秒的低运动段」,数字没错但表述让人低估,
> 是独立验收方核出来的。**谁生成的,谁不要独自签字。**

### 第一条 prompt 怎么写

**别写「帮我做个视频」,也别自己先把技术参数定死。** 说清这四件事就够,
skill 会带着你把技术约束在**创意阶段**就撞一遍 —— 而不是等素材做完才发现要返工:

1. **画面内容** —— 谁、在哪、做什么
2. **时长和画幅** —— 说你想要的,不用管能不能实现
3. **风格** —— 🔴 **「真人感」还是「戏剧化/电影感」**,这是个岔路口不是旋钮
4. **人物参考图**（如果有固定人物）

给 Codex 的开场白,可以直接抄:

```text
用 h3-creative-video 做一条新视频。

内容：<谁 + 在哪 + 做什么>
时长画幅：<例如 15 秒以内，竖版 9:16>
风格：真实自然，要真人感，不要 AI 味
人物参考：<路径，可选>

先给我剧本和技术可行性，确认之后再动手。
```

Claude + Codex 模式,把最后一句换成:

```text
你负责出关键帧图片，出片和验收交给 Claude。
```

### 它会怎么回你（正常流程）

1. **先撞技术上限再谈创意** —— 例如你要 15 秒,它会告诉你
   **FL2VA 一次生成最多 277 帧 = 11.54 秒**,超了会静默出全黑;
   要更长只能拼接,而**拼接处音频必然断裂**。这一步就要你拍板。
2. **给剧本 + 分镜**,并说明每一镜只演一个动作,
   以及 🔴 **末镜的动作不能有终点**（转身/站定/笑完这类"做完就没了"的动作,
   剩下的秒数会停住）。
3. **你确认后**才建项目目录、写工单、出图。
4. **关键帧不过验收,不准投视频** —— 真人感只能在出图那层解决,
   视频提示词补不回来（双 seed 已证伪）。
5. **验收按 像素 → 判据 → 人眼 → 人耳 的顺序**,
   `status=success` 不算验收（静默 NaN 也报 success）。

### 想直接看规则

| 想知道 | 看 |
| --- | --- |
| 提示词怎么写 | [`references/prompt_authoring.md`](skills/h3-creative-video/references/prompt_authoring.md) |
| 官方规范 + 我们在哪偏离 | [`references/official_h3_guide.md`](skills/h3-creative-video/references/official_h3_guide.md) |
| 出图工单 / 去 AI 味 | [`references/keyframe_imagegen_order.md`](skills/h3-creative-video/references/keyframe_imagegen_order.md) |
| 判据与标定 | [`references/acceptance_criteria.md`](skills/h3-creative-video/references/acceptance_criteria.md) |
| 🔴 **哪些路已经走死了** | [`references/known_findings.md`](skills/h3-creative-video/references/known_findings.md) |

> **提实验前先看 `known_findings.md`。** 里面「已证伪」那一栏,
> 每一条都是别人花过双 seed 成本走过的死路。

## 各端兼容性

四端都采用同一套 Agent Skills 约定——扫描各自的 skills 目录，
读取 `SKILL.md` 的 `name` / `description` frontmatter——因此同一份目录可以直接共用：

| 工具 | 扫描目录 | 状态 |
| --- | --- | --- |
| Claude Code | `~/.claude/skills/` | ✅ 已验证 |
| Codex | `~/.codex/skills/` | ✅ 已验证 |
| Grok CLI | `~/.grok/skills/` | ✅ 已验证 |
| Cursor | `~/.cursor/skills/` | ✅ 已验证 |

> Cursor 另有 `~/.cursor/skills-cursor/` 存放其内置 skill，由官方同步管理
> （带 `.sync-manifest.json`），不要往里放自己的东西。自建 skill 一律放 `~/.cursor/skills/`。
>
> 实测 Cursor 除自身目录外，还会一并扫描 `~/.claude/skills/` 与 `~/.codex/skills/`，
> 因此即使不建第 4 个软链它也能发现该 skill。但显式软链更稳妥，
> 不依赖这一未文档化的跨读行为。

验证方式：在源文件 `SKILL.md` 末尾写入一个唯一标记，
再分别让各端 CLI 读回自己目录下的同名文件，四端均返回该标记，
确认读的是同一份实体而非各自的副本。

## 目录结构

```
skills/<name>/
├── SKILL.md        # 入口，含 frontmatter（name / description）——四端通用
├── references/     # 按主题拆分的详细 runbook，按需加载——与平台无关
├── scripts/        # 可直接执行的辅助脚本——与平台无关
└── agents/
    └── openai.yaml # 仅 Codex 读取（显示名/配色/默认 prompt/隐式调用策略）
                    # 其余三端忽略此文件，共用无副作用
```

保持 `SKILL.md` frontmatter 只用 `name` / `description` 这两个标准字段，
平台特有配置放进 `agents/` 之类的独立文件——这是四端能共用同一份目录的前提。

## 说明

其中的主机别名（`train-1`、`train-h20`、`vscode` 等）、NFS 路径和端口约定来自我自己的环境，
使用前请按实际情况替换。仓库内不包含任何凭据、密钥或对外可路由的地址。
