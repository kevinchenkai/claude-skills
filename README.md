# claude-skills

个人使用的 Agent Skills 集合，由 [Claude Code](https://claude.com/claude-code) 与 Codex 共用。

## Skills

| Skill | 说明 |
| --- | --- |
| [`gpu-llm-service-ops`](skills/gpu-llm-service-ops) | GPU 服务器（SSH 访问）上的 conda 环境与推理/训练服务运维：vLLM、ComfyUI、ai-toolkit、kohya_ss、LlamaFactory、OneTrainer；共享 NFS conda 环境管理、tmux 会话、端口转发、存储 I/O 基准、KAS 多机分布式训练。 |

## 安装

本仓库是唯一真源。克隆到本地后，Claude Code 与 Codex 两侧都软链过来，
改一处两边同时生效，`git push` 即备份：

```bash
git clone https://github.com/kevinchenkai/claude-skills.git ~/Work/claude-skills
ln -s ~/Work/claude-skills/skills/gpu-llm-service-ops ~/.claude/skills/gpu-llm-service-ops
ln -s ~/Work/claude-skills/skills/gpu-llm-service-ops ~/.codex/skills/gpu-llm-service-ops
```

两个 CLI 启动时会各自扫描 `~/.claude/skills/`、`~/.codex/skills/` 并自动加载。

## 目录结构

```
skills/<name>/
├── SKILL.md        # 入口，含 frontmatter（name / description）——两侧通用
├── references/     # 按主题拆分的详细 runbook，按需加载——与平台无关
├── scripts/        # 可直接执行的辅助脚本——与平台无关
└── agents/
    └── openai.yaml # 仅 Codex 读取（显示名/配色/默认 prompt/隐式调用策略）
                    # Claude Code 忽略此文件，共用无副作用
```

## 说明

其中的主机别名（`train-1`、`train-h20`、`vscode` 等）、NFS 路径和端口约定来自我自己的环境，
使用前请按实际情况替换。仓库内不包含任何凭据、密钥或对外可路由的地址。
