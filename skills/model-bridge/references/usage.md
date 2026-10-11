# Model Bridge 使用与维护

## 多端调用同一入口（目标支持 5 个 AI）

多个调用方都读取本仓库 `skills/model-bridge/SKILL.md`，执行同一个 Python 脚本。
目标通过 `run claude|codex|cursor|grok|agy` 选择（Claude、Codex、Cursor、Grok、Antigravity/Gemini 共 5 个 AI）；无需在各端重复写规则。
运行环境为 macOS / Linux、Python 3.9+、已安装的目标 CLI 和有效登录。

本机入口：

```bash
BRIDGE=/Users/kk/Work/claude-skills/skills/model-bridge/scripts/call.py
python3 "$BRIDGE" doctor
python3 "$BRIDGE" run codex --prompt '简要解释梯度下降。' --format text
```

`doctor` 只执行 help/version，并输出凭据环境变量是否存在，不显示值；
它不能证明认证仍有效、模型可用或余额充足。正式调用才验证这些条件。
不指定材料文件时，`--prompt` 或 stdin 都可用；文件可用 `--prompt-file`。

CLI 搜索依次使用 PATH、`~/.local/bin/`，Codex 额外探测 macOS 桌面 App 内置 CLI。
Cursor 优先 `cursor-agent`，只在 help 身份验证通过后接受 `agent`，避免调用同名 Grok。
非标准安装用 `--cli /absolute/path/to/cli`，或设置以下**路径变量**：
`MODEL_BRIDGE_CODEX_BIN`、`MODEL_BRIDGE_CLAUDE_BIN`、
`MODEL_BRIDGE_CURSOR_BIN`、`MODEL_BRIDGE_GROK_BIN`、`MODEL_BRIDGE_AGY_BIN`。它们不涉及凭据。
另有 `MODEL_BRIDGE_AGY_HOME`：agy 状态目录（默认 `~/.gemini/antigravity-cli`），出图来源校验从这里读会话转录。

## 协作示例

### Claude 调 Codex 和 Grok 评审方案、评测结果

先由调用方将必要材料写入本地文件。`request.txt` 应包含目标、关键约束、
希望回答的问题；`plan.md` 提供方案，`criteria.txt` 提供验收标准，
`results.md` 提供真实输出和已执行的验证记录。不提交整个历史对话。

```bash
python3 "$BRIDGE" run codex --task plan-review \
  --model gpt-6.1-sol --effort medium \
  --prompt-file /absolute/path/request.txt --context /absolute/path/plan.md

python3 "$BRIDGE" run grok --task result-eval \
  --model grok-4.7 --effort high \
  --prompt-file /absolute/path/criteria.txt --context /absolute/path/results.md
```

若要求两家评审同一个方案，两次都用 `plan-review` 并提供同一份材料。
调用方报告每家的意见、分歧及可验证依据；评审意见不能直接变成修改授权。
一家的失败不应被另一家的成功掩盖。

自然语言入口：

```text
用 model-bridge，请 Codex（gpt-6.1-sol / medium）和
Grok（grok-4.7 / high）分别评审刚才的方案，汇总问题和分歧。
```

### Claude / Cursor / Grok 调 Codex imagegen 生成素材

```bash
python3 "$BRIDGE" run codex --task image \
  --model gpt-6.1-sol --effort medium --timeout 600 \
  --prompt '生成一张网站素材：橘猫坐在窗边，柔和自然光，写实摄影，方形构图，无文字。'
```

编辑已有图片：

```bash
python3 "$BRIDGE" run codex --task image \
  --model gpt-6.1-sol --effort medium \
  --image /absolute/path/reference.png \
  --prompt '保留主体与构图，将背景改为浅蓝色。只生成一张。'
```

该模式启用目标 Codex 的 `image_generation` 功能，提示调用 `$imagegen`
技能与内置工具，使用 `workspace-write` 在本次产物目录工作；不把原项目设为可写工作区。
`--workspace` 只用于文本任务，图片始终在本次 `artifacts/` 执行。
目标 Codex 必须能发现 imagegen 技能并拥有内置工具权限；仅有技能文件不保证能出图。
当工具不可用、账号权限不足或产物缺失时返回失败，不生成替代 SVG，也不切换 Image API。

`artifacts` 给出真实 PNG/JPEG/WebP 的绝对路径、格式、大小和 SHA-256。
格式检查只验证文件头与基本结构；调用方仍应打开图片检查画面。
每个产物的 SHA-256 必须递归匹配 `$CODEX_HOME/generated_images`（默认
`~/.codex/generated_images`）中的来源文件，且不得与任何 `--image` 参考图的调用前哈希相同。
仅接受 mtime 在子进程启动至结束期间的来源文件，排除历史缓存，避免依赖可能缺失的 thread_id 事件。
此来源校验依赖 Codex 的内部目录实现；目录缺失、不可读或哈希不匹配均返回 `status: error`，
请核对 CODEX_HOME 与读取权限；CLI 升级改变内部路径时需更新校验，不自动切换 Image API。
图片尺寸由 Codex 自行决定，脚本不控制，也不保证精确纵横比；需要精确尺寸请调用方后处理。
验收后将需要的素材复制到项目目标路径，缓存路径不能充当长期项目依赖。

### Codex 调 Claude Sonnet 做 code review

在可信项目中生成任务相关差异（下面只读取差异，不暂存或提交）：

```bash
git diff -- src/example.py > /absolute/path/change.diff
python3 "$BRIDGE" run claude --task code-review \
  --model claude-sonnet-5-5 --effort medium \
  --prompt '审查附件 diff。调用合同：除数为 0 时返回 None。重点检查异常路径。' \
  --context /absolute/path/change.diff
```

提交的代码最好包含文件名、行号、相关调用方与测试结果，不能仅有几行无上下文差异。
Claude 文本模式关闭工具、MCP 与 slash skills，并使用 `dontAsk`，
因此它只能审查提供的材料。若要查原文件，先由调用方读取并用额外 `--context` 提交。
默认使用本机已验证的 `claude-sonnet-5-5`；`sonnet` 仍可作为 Claude CLI 动态别名传入。
若用户要用已登录的 claude.ai 账号，而调用方继承了旧环境 token，可显式加
`--claude-auth login`；不要在错误后偷偷重试或切换认证。

**Effort 与设置来源（2026-10-05 实测）**：

- `--effort` 对 Claude 只能是 `low/medium/high/xhigh/max`。实测 `none`、`ultra`、任意乱值都只在
  stderr 打 `Unknown --effort value … ignoring it` 并以退出码 0 继续，会悄悄改变用户指定的档位，
  因此脚本在调用前拒绝（退出码 2）。`--model` 写错则 CLI 返回错误文本，脚本判为 `error`，不会冒充成功。
- 默认继承**用户级设置**（`~/.claude/settings.json` 的 env、插件、模型配置等）。实测子进程的系统提示里
  有账号邮箱和 memory 目录说明（无 memory 内容；工具关闭，无法读写文件；用户设置里现有的只是 Pre/PostToolUse hook，工具关闭时按理不触发，未专门验证）。
- `--claude-settings project` 传 `--setting-sources project`，不加载用户级设置：行为更可复现，
  同一小请求的 `total_cost_usd` 实测由 0.0116 降到 0.0057（单次样本）。实测 `--effort high` 下思考照常进行、默认继承与 `login` 认证都可用。
  但若网关/Key 只配在用户设置的 `env` 里，隔离后会退回缓存的 claude.ai 登录，计费路径随之改变，
  所以它是显式选项，不是默认。

自然语言入口：

```text
用 model-bridge，调用 Claude Sonnet / medium 审查本次改动，
传入相关 diff 和调用合同，只输出可行动问题，不修改文件。
```

### 调 Cursor

```bash
python3 "$BRIDGE" run cursor --task plan-review --model grok-4.7-high \
  --prompt-file /absolute/path/request.txt --context /absolute/path/plan.md
```

Cursor 使用只读 `--mode ask`，新生成的空工作目录使用专门的 `--trust`。
显式传入 `--workspace` 表示调用方已核实该项目可信；不要把不可信下载目录传进去。
脚本不使用 `--force` / `--yolo` / `--approve-mcps`。
不传 `--model` 时默认 `auto`（不带 effort）。本账号的 effort 编码在模型 ID 里
（如 `grok-4.7-high`，另有 `-low` / `-medium` / `-xhigh` 与 `-fast`，以及
`claude-sonnet-5-5-*`、`gpt-5.6-sol-*`）；不存在裸 ID `grok-4.7`。
不要传 `--effort`：脚本不会拼接 `[effort=…]`。若仍传入且 `--model` 不含 `[`，
调用前报错（退出码 2），不发请求；`auto` 也不接受 effort。
含 `[` 的模型字符串原样透传，但本账号下 bracket 形式（包括 `cursor-agent --help` 示例
`claude-opus-4-8[effort=high]`）会被 Cursor 拒绝。模型 ID 以 `cursor-agent --list-models` 为准。
脚本不猜测、不改写模型 ID，调用前也不拉取模型列表。

### 调 agy（Antigravity / Gemini）

```bash
python3 "$BRIDGE" run agy --task ask --model gemini-3.8-flash-medium --prompt '用一句话解释幂等性。'
python3 "$BRIDGE" run agy --task image --prompt '生成一张水彩风格的江南古镇雨巷插画，横幅，无文字。'
python3 "$BRIDGE" run agy --task image --image /absolute/path/ref.jpg --prompt '保留构图，改为夜晚。'
```

agy 是订阅登录的完整代理，不是只读的聊天接口。2026-10-07 本机实测（agy 1.3.1，同一订阅账号）：

- **无头不只读**：默认、`--mode plan`、`--sandbox` 下都真的创建了文件、改了文件、执行了 `touch`，
  读了工作区外文件；用户级设置为 `always-proceed` 时还写了工作区外文件、联网、列了 `$HOME`。
  `--mode plan` 在无头下被忽略（二进制里有 `--mode %s is not supported headless`）。
- **提示词尾部被静默截断**：stdin 提示词超过约 191 KB 时保留量恒为约 191.4 KB（200/220/300 KB 分别截掉
  8602/28602/108664 字节），回复要么反问「您想问什么」，要么原样回 `<truncated N bytes>`，`status` 仍是 `SUCCESS`。
  160 KB 以内「大海捞针」暗号全部找回。脚本因此在 150 KiB 处拒绝。
- **成功状态不可信**：未登录（退出码 1 加 stderr 登录链接）、过滤器误拦、`--print-timeout` 部分输出（退出码 0、
  回复为空）、`denied_actions` 非空，都可能伴随 `SUCCESS`；脚本逐项识别。
- **出图**：无头下主代理可能在子代理完成前就结束，或自己想 `cp` 图片被拒后停下，回复里没有路径。
  脚本不依赖回复文本：用事件流里的子代理会话 ID 读 `brain/<id>/.system_generated/logs/transcript.jsonl`，
  找 `generate_image` 的 `Generated image is saved at …` 记录并核对时间窗，再复制产物。
  提示词里要求「等子代理完成并报告路径」，并禁止它自己执行命令。
- **档位**：裸模型名加 `--effort high` 可用；带档位后缀的模型 ID 再加 `--effort` 会报 `conflicts with --effort`。
  只验证了 `low/medium/high`，`xhigh/max` 被拒绝。
- **API Key**：用假的 `GEMINI_API_KEY` 直接调用 agy 仍正常，说明环境变量 Key 并没有抢走已登录会话；
  脚本仍在子进程里移除它们作为防御，但这一步是否必要未验证。
- 输入走 stdin（不带 `-p`；`-p` 必须跟参数，而长提示词放命令行会进进程列表）。

## 参数、结果与失败

| 参数 | 含义 |
| --- | --- |
| `--task` | `ask`（默认）、`plan-review`、`result-eval`、`code-review`、`label`、`image`；`label` 只要结果本身，用于批量标注 |
| `--schema` | JSON Schema 文件，仅 claude（`--json-schema`）/ codex（`--output-schema`）；顶层须为 object，数组包成 `{"items": [...]}` |
| `--codex-config` | `inherit`（默认）加载 `~/.codex/config.toml`；`ignore` 加 `--ignore-user-config`，跳过 notify/hooks 等用户配置，认证不变 |
| `--model` / `--effort` | 覆盖默认值并传给目标 CLI。Cursor 不另传 `--effort`，见上文 |
| `--prompt` / `--prompt-file` | 二选一；都没有时读取 stdin |
| `--context` | UTF-8 材料文件，可重复；输入合计最多 2 MiB，不静默截断 |
| `--image` | Codex / agy 图片任务参考图，可重复 |
| `--workspace` | 文本任务的可信项目目录；默认在独立目录执行；**agy 不允许**（无头非只读） |
| `--output-dir` | 新建的结果目录，已存在时拒绝覆盖 |
| `--timeout` | 模型调用超时秒数，默认 600；help 身份探测另有 10 秒超时 |
| `--claude-settings` | `inherit`（默认）沿用用户级设置；`project` 只加载项目级，仅 Claude 可用 |
| `--claude-auth` | `inherit`（默认）继承认证；`login` 显式选择缓存 claude.ai 登录，调用前 status 探测另有 15 秒超时 |
| `--format text` | 终端输出答案；默认 JSON，运行记录始终保存 JSON |
| `--dry-run` | 显示命令结构，不调用模型、不创建记录目录 |

Codex 的 `--effort` 合法取值及 `exec` 对非法值的行为**未验证，取值由 Codex 决定**。
2026-10-05 离线核查 Codex 0.160.0：`exec --help` 未列枚举；`features list` 对乱值也返回 0，
无法据此判断模型调用时是否忽略；`app-server generate-json-schema` 将 `model_reasoning_effort`
引用的 `ReasoningEffort` 定义为模型公布的非空字符串，未列固定集合。官方配置文档在核查环境无法访问，
因此保持现有透传，不添加未经证实的 Codex 专用白名单。

Cursor、Codex、Claude、agy 的 prompt 经 stdin 提交，Grok 经 `--prompt-file`。
prompt 不进入 argv，不会出现在进程列表里，也不受操作系统参数长度限制；材料仍有 2 MiB 上限。
所有调用均通过参数数组执行，不经 shell 展开；调用方写 Shell 命令时仍要正确引用文本，
特别是 `$imagegen` 必须放在单引号内，或用文件提交以免被 Shell 当变量展开。

每次创建独立的 `~/.cache/model-bridge/<provider>-<UTC>-<random>/`：

- `request.txt`：最终提交的任务与材料。
- `stdout.txt` / `stderr.txt`：CLI 原始输出，经尽力脱敏。
- `response.txt`：抽取出的最终答案；Codex 另保留 `answer.txt`。
- `result.json`：`status`、`text`、`error`、`usage`、`session_id`、`artifacts` 与运行元数据。
- `artifacts/`：图片产物，文本调用时也是默认独立工作目录（agy 例外：在同级的 `work/` 中运行，`artifacts/` 只放脚本复制出的图）。
- agy 的 `result.json` 另含 `agy`（会话 ID、用过的工具、被拒绝的动作）和 `warnings`。
- Claude 的 `warnings` 收录 stderr 里的 `[claude-code:…]` 标记；CLI 不认识模型时 `usage.total_cost_usd` 改名为 `total_cost_usd_unreliable`。
- 用了 `--schema` 时有 `json`（解析后的对象，失败为 null）和 `schema.json`；价目表里有的模型有 `cost_estimate`。
- Codex 文本任务带 `--ephemeral`：会话不写 `~/.codex/sessions`、不进 Codex 历史；`session_id` 仍是本次 thread id。
  图片任务不加（来源校验依赖 `generated_images/<thread-id>`，`--ephemeral` 下是否照常写入未验证）。

退出码：0 成功；1 模型/CLI/输出/图片产物失败；2 参数、路径或 CLI 身份错误；
124 超时；130 运行中 Ctrl-C 中断。超时/中断终止本次进程组，不自动重试。
CLI 自身的网络重试、后台守护进程和服务器端计费由目标 CLI 管理。
“一次调用”是一次新 CLI 任务，可能包含多轮推理、工具调用和服务请求。

只读参数与提示词不等于 OS 隔离。用户级配置、启动 hooks、MCP 和目标 CLI
自身的记录机制仍可能生效；脚本没有修改这些配置。默认不用旧会话，也不继承主对话。
`MODEL_BRIDGE_DEPTH=1` 传给子进程，本入口遇到非零标记拒绝递归。

## 认证与计费

本技能不登录、不退出、不设 Key、不修改套餐，默认沿用目标 CLI 当前的认证与配置。
一次 CLI 任务不能保证“一次请求固定价格”，也不保证始终扣订阅。

Claude 的 `--claude-auth login` 是显式选择：仅在本次子进程移除
`ANTHROPIC_AUTH_TOKEN`、`ANTHROPIC_API_KEY`、`CLAUDE_CODE_OAUTH_TOKEN`，
确认 `claude auth status` 为已登录的 `claude.ai / firstParty` 后才发请求。
若仍选择其他认证或登录无效，直接拒绝，不读取 Key 内容、不 fallback，也不改变调用方
环境或用户配置。适用于 CLI 已重新登录，但桌面 App 仍继承旧 token 的情况。

```bash
python3 "$BRIDGE" run claude --claude-auth login \
  --model claude-sonnet-5-5 --effort medium \
  --prompt '你好，介绍一下你自己。' --format text
```

| 目标 | 沿用登录时的路径 | 要注意 |
| --- | --- | --- |
| Codex | ChatGPT 登录使用相应 Codex 额度；API Key 登录按 API 计费 | 用 `codex login status` 核实，不能只凭变量存在推断当前登录方式 |
| Claude | claude.ai 订阅登录使用订阅额度，其他凭据遵循 API / 云平台 / 网关账单 | `ANTHROPIC_AUTH_TOKEN`、`ANTHROPIC_API_KEY` 等可优先于缓存登录；检查 `claude auth status` 与交互 `/status` |
| Cursor | CLI 使用 Cursor 账号及其套餐额度，可能有额外按量消费 | `CURSOR_API_KEY` 是 Cursor 账号认证；选择 Anthropic/OpenAI 模型不意味着直接扣它们的订阅 |
| agy | Antigravity 订阅登录（Google 账号，需账号地区获准使用） | 钥匙串里的会话；未登录时脚本只报错，需你在终端 `agy` 授权；额度怎么计未查清，无头 `/usage` 无输出，须在交互界面查看 |
| Grok | grok.com 登录或 XAI API Key 等目标 CLI 支持的认证 | Build 余额/额度由当前账号控制；额度用尽不自动换成 API Key |

Codex 内置图片生成计入一般 Codex 使用额度；指定的 `gpt-6.1-sol / medium`
控制编排模型，并非底层图片模型。使用 Image API 才走独立 API 计费，
本技能没有此 fallback。CLI `usage`、`total_cost_usd` 等字段只按原值保留（CLI 不认识模型时改名为 `total_cost_usd_unreliable`），不能当实扣账单。
`cost_estimate` 用脚本内 `PRICES` 表（2026-10-09 核对官方价格页，只收核对过的模型）按 token 数估算：
Claude 区分 1 小时 / 5 分钟缓存写入价；Codex 的 `input_tokens` 已含缓存命中；超过长上下文门槛按高档计，
高档里没公布的单价（如 Haiku 长上下文的缓存价）不猜，直接不给估算。价格变了改 `PRICES` 和日期。

依据（核查于 2026-10-05）：

- [Codex 认证与 API 计费](https://learn.chatgpt.com/docs/auth)。
- [Codex 内置图片生成与额度](https://learn.chatgpt.com/docs/image-generation)。
- [Claude 认证优先级](https://code.claude.com/docs/en/authentication#authentication-precedence)
  和 [API Key 与订阅](https://support.claude.com/en/articles/12304248-manage-api-key-environment-variables-in-claude-code)。
- [Cursor CLI 与订阅](https://cursor.com/en-US/blog/cli)、
  [模型与额度池](https://cursor.com/docs/models-and-pricing)、
  [CLI 认证](https://docs.cursor.com/en/cli/reference/authentication)。
- [Grok 官方安装、登录与单次模式](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/01-getting-started.md)。

## 本地验收与维护

### 清理旧运行（prune）

```bash
python3 "$BRIDGE" prune --older-than 14          # 只列出：运行目录数、各家会话数、约释放字节
python3 "$BRIDGE" prune --older-than 14 --apply  # 真删
```

只处理 `~/.cache/model-bridge/` 下名字形如 `<provider>-<UTC>-<8位hex>`、目录名时间早于 N 天的运行（`--output-dir` 指定的目录不碰），并清理：

- Codex：这些运行记录的会话（`codex delete --force <id>`，每个约 1.5 秒；带 `--ephemeral` 的运行本来就没有会话，跳过）。
- agy：`result.json` 记录的会话 ID 对应的 `brain/<id>`、`conversations/<id>.db` 和 `conversation_summaries.db` 中的行；你自己用 agy 的会话不在记录里，不会动。
- Claude：`~/.claude/projects/` 下以这些运行目录命名、且**没有任何文件**的空项目目录（`--no-session-persistence` 仍会建这个目录）。
- `--older-than` 必须大于 0，避免删到正在运行的调用。约释放字节不含 Codex 会话文件本身。

2026-10-10 首次空跑（`--older-than 0.5`）：1034 个运行（约 44 MB）、509 个 Codex 会话、517 个 Claude 空项目目录、4 个 agy 会话；
`codex delete --force` 已用一个临时会话核对过可删且文件随之消失。

### 测试与小请求核查

```bash
python3 -m unittest discover -s skills/model-bridge/tests -v
python3 skills/model-bridge/scripts/call.py doctor
python3 skills/model-bridge/scripts/call.py run codex \
  --model gpt-6.1-sol --effort medium --prompt '解释梯度下降。' --dry-run
```

离线测试以假 CLI 验证实际进程边界：各家参数与输出、材料不被 shell 展开、
认证继承、嵌套拦截、超时终止子进程、错误不冒充成功、结果目录不覆盖、
尽力脱敏、真实图片与伪造路径区分；agy 另有越权工具、转录来源、过滤器/部分输出/未登录等失败形态；
不调用模型、不消耗额度。

2026-10-05 本机实测：Codex 0.160.0 的方案评审成功。
Codex 图片（2026-10-05，Claude 复测）：

- 文生图：经本技能真跑，173 秒，产物为 1672×941 PNG（请求为 16:9 横幅），已人工打开核对，内容符合提示词。
- `--image` 编辑：以上一张为参考，要求改为黄昏暖光，100 秒出图，构图与主体保持，产物与参考图 SHA-256 不同，已人工核对。
- 图片尺寸由 Codex 自行决定；请求 16:9 得到 1672×941（非精确 16:9），需要精确尺寸请调用方后处理。
- JSON 事件流未见 image_gen 调用事件；产物 SHA-256 已核对与 `~/.codex/generated_images/<thread-id>/exec-*.png` 相同。
  脚本现按上述内部目录、运行时间与参考图哈希校验来源；新增判据由离线测试覆盖，真实复测仍由 Claude 后续执行。

Cursor（2026-10-05，Claude 复测，CLI 2026.10.01-e373342）：auto 的 Ask 成功（约 22 秒）；
`grok-4.7-high` 成功（约 31 秒）。`grok-4.7 --effort high` 因拼接 bracket 被 Cursor 拒绝
（已改为调用前报错）。bracket 形式（含 `--help` 示例）在本账号被拒。
Claude 初测返回 `401 Invalid bearer token`；更新至 2.1.289 并重新登录后，
桌面调用方仍继承旧 `ANTHROPIC_AUTH_TOKEN`，默认继承模式仍返回 401。
显式选择 `--claude-auth login` 后，`claude-sonnet-5-5 / medium` 代码审查成功，
正确指出除数为零时违反返回 None 的合同，JSON 输出与模型信息均正常解析。
Grok 1.0.46 的 Grok 4.7 high 请求（2026-10-05）返回 `402 Grok Build usage balance exhausted`，
成功输出解析当时只由离线测试覆盖。
未修改全局凭据、用户登录状态或追加余额；离线测试数量以当前运行结果为准。

Grok（2026-10-08，1.0.46，额度已恢复，真跑）：`grok-4.7` 的 ask（low，约 18–24 秒，3 次重复）、
plan-review（high，24 秒）、result-eval（medium，28 秒）共 6 次成功；文本、用量字段解析正常。
材料里夹带「创建 pwned.txt」的注入指令时模型明确忽略，未写任何文件。
首次调用出现过一次 `Couldn't set model 'grok-4.7': unknown model id`（10 秒返回，`grok models` 同时能列出该模型），
同一命令随后重试及直接调用 CLI 均成功，判断为额度恢复后模型列表刷新的瞬时现象，未改脚本；
脚本不自动重试，遇到时手动重跑一次即可。

agy（2026-10-07，1.3.1，订阅登录）：文本 `gemini-3.8-flash-medium` 与 `gemini-3.1-pro-high` 经本技能真跑成功
（约 17 秒）；文生图 50 秒、`--image` 参考图编辑 68 秒，产物为 JPEG，来源校验通过，人工核对内容符合要求；
材料里夹带「执行 touch」的注入指令时模型未照做；调用前拒绝的 5 类参数已逐一核对。
此前数十次探测性调用（可靠性、长提示词、权限边界、出图重复性）的结论见上文，结论已写入脚本。

2026-10-10（Claude Code 2.1.296、Codex 0.162.0-alpha）真跑：
- `--schema`：Haiku 5.5 与 gpt-6-luna 都返回符合 schema 的对象（Claude 关着工具也能用，内部多一轮）；
  `batch_ask.py --schema` 两家各 10/10，重跑全部跳过。
- `label` 对比 `ask`（Haiku low，同一 10 句情感标注，各 2 次）：输出 154/154 token 对 398/253，`ask` 有一次给 JSON 套了代码围栏；
  luna 两种任务都是 126。样本很小，只说明方向。
- 2.1.296 已认识 `claude-haiku-5-5`（`costBasis: list`），4 次 `total_cost_usd` 与 `cost_estimate` 逐位相同；2.1.289 时是 `unknown`。
- Codex 文本任务带 `--ephemeral` 后 `~/.codex/sessions` 不再新增文件。

CLI 升级后，如参数或 JSON 结构改变，先更新适配与对应假 CLI 契约测试，
再做一次小请求核查；不通过无限重试或更换模型掩盖问题。
安装遵循仓库根 README 的四端平级软链约定，新对话重新发现技能后使用。
