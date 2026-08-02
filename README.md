# claude-skills

个人使用的 Agent Skills 集合，由 [Claude Code](https://claude.com/claude-code)、Codex、Grok CLI、Cursor 四端共用。

## Skills

| Skill | 说明 |
| --- | --- |
| [`gpu-llm-service-ops`](skills/gpu-llm-service-ops) | GPU 服务器（SSH 访问）上的 conda 环境与推理/训练服务运维：vLLM、ComfyUI、ai-toolkit、kohya_ss、LlamaFactory、OneTrainer；共享 NFS conda 环境管理、tmux 会话、端口转发、存储 I/O 基准、KAS 多机分布式训练。 |

## 安装

本仓库是唯一真源。克隆到本地后，各端都软链过来，
改一处四端同时生效，`git push` 即备份：

```bash
git clone https://github.com/kevinchenkai/claude-skills.git ~/Work/claude-skills
S=~/Work/claude-skills/skills/gpu-llm-service-ops
ln -s "$S" ~/.claude/skills/gpu-llm-service-ops
ln -s "$S" ~/.codex/skills/gpu-llm-service-ops
ln -s "$S" ~/.grok/skills/gpu-llm-service-ops
ln -s "$S" ~/.cursor/skills/gpu-llm-service-ops
```

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
