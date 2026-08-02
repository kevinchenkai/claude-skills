# claude-skills

个人使用的 [Claude Code](https://claude.com/claude-code) Skills 集合。

## Skills

| Skill | 说明 |
| --- | --- |
| [`gpu-llm-service-ops`](skills/gpu-llm-service-ops) | GPU 服务器（SSH 访问）上的 conda 环境与推理/训练服务运维：vLLM、ComfyUI、ai-toolkit、kohya_ss、LlamaFactory、OneTrainer；共享 NFS conda 环境管理、tmux 会话、端口转发、存储 I/O 基准、KAS 多机分布式训练。 |

## 安装

克隆后软链到 `~/.claude/skills/`：

```bash
git clone https://github.com/kevinchenkai/claude-skills.git ~/Work/claude-skills
ln -s ~/Work/claude-skills/skills/gpu-llm-service-ops ~/.claude/skills/gpu-llm-service-ops
```

Claude Code 启动时会自动加载 `~/.claude/skills/` 下的所有 skill。

## 目录结构

每个 skill 遵循 Claude Code 的 skill 约定：

```
skills/<name>/
├── SKILL.md        # 入口，含 frontmatter（name / description）
├── references/     # 按主题拆分的详细 runbook，按需加载
├── scripts/        # 可直接执行的辅助脚本
└── agents/         # 可选的 agent 配置
```

## 说明

其中的主机别名（`train-1`、`train-h20`、`vscode` 等）、NFS 路径和端口约定来自我自己的环境，
使用前请按实际情况替换。仓库内不包含任何凭据、密钥或对外可路由的地址。
