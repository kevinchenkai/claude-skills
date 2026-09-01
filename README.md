# claude-skills

个人使用的 Agent Skills 集合，由 [Claude Code](https://claude.com/claude-code)、Codex、Grok CLI、Cursor **四端共用同一份目录**。

每个 skill 都是从实际踩坑里固化出来的：**负面结果和正面结果一起记**，
所以每节都有一张「🔴 上手前先知道的几条」——那部分通常比正面用法更值钱。

## Skills

| Skill | 管什么 | 一句话 |
| --- | --- | --- |
| [`gpu-llm-service-ops`](skills/gpu-llm-service-ops) | 机器和服务 | GPU 服务器上的环境与服务运维：vLLM / ComfyUI / ai-toolkit / OneTrainer 起停、NFS conda 环境、tmux、端口转发、存储选型、多机训练 |
| [`h3-creative-video`](skills/h3-creative-video) | 视频内容 | MiniMax-H3 出片：T2VA / I2VA / FL2VA / L2VA / Ref2VA 五种模式的提示词、ComfyUI 出片与判据验收 |
| [`wps365-cli`](skills/wps365-cli) | 云文档 | WPS 365 / 金山文档：搜索定位、读取导出、新建智能文档、目录治理 |
| [`douyin-hd-downloader`](skills/douyin-hd-downloader) | 抖音原片 | 公开单条作品**优先下上传原片**（实测可达最高转码档 2.4–15 倍），不转码，ffprobe 验证 |

> **怎么分工**：前两个常在同一次对话里接力 —— `gpu-llm-service-ops` 管
> **环境能不能跑起来**，`h3-creative-video` 管**片子好不好**；做视频时机器出问题，
> 就是前者的活。后两个彼此无关，也与前两者无关。

<details>
<summary>每个 skill 的完整能力清单</summary>

- **`gpu-llm-service-ops`** —— GPU 服务器（SSH 访问）上的 conda 环境与推理/训练服务运维：vLLM、ComfyUI、ai-toolkit、kohya_ss、LlamaFactory、OneTrainer；共享 NFS conda 环境管理、tmux 会话、端口转发、存储 I/O 基准、KAS 多机分布式训练。
- **`h3-creative-video`** —— 用 MiniMax-H3 做创意短视频：支持纯文本 T2VA、首帧 I2VA、首尾帧 FL2VA、尾帧 L2VA，以及图像/视频/音频全参考 Ref2VA；覆盖官方三字段或六段式提示词、ComfyUI 出片、判据验收与交付。运行上限与实验结论按模式隔离，不跨模式套用。
- **`wps365-cli`** —— 用官方 [`wps365-cli`](https://github.com/wps365-open/cli) 操作 WPS 365 / 金山文档：搜索定位、读取与导出正文、新建智能文档（AirPage/otl）并灌 Markdown、目录治理（建夹/批量搬家/删除）。含跨盘 drive_id、markdown 抽取丢表格、导出 docx 必填字段等实测坑位。
- **`douyin-hd-downloader`** —— 输入公开抖音完整链接、短链或分享文案，枚举并探测全部视频源，优先下载上传原片（`ratio=default`），原片不可用时回退最高转码档；流式保存不转码，ffprobe 验证真实规格。含水印降级护栏、间歇失败重试与 SSRF 防护。

</details>

## 上手说明

| Skill | 上手说明（本页） | 技术介绍（`docs/`） |
| --- | --- | --- |
| `gpu-llm-service-ops` | [上手 GPU 服务器](#用-gpu-llm-service-ops-上手-gpu-服务器) | [技术介绍](docs/gpu-llm-service-ops-技术介绍.html) |
| `h3-creative-video` | [做 MiniMax-H3 视频](#用-h3-creative-video-做-minimax-h3-视频) | [技术介绍](docs/h3-creative-video-技术介绍.html) |
| `wps365-cli` | [操作金山文档](#用-wps365-cli-操作金山文档) | [技术介绍](docs/wps365-cli-技术介绍.html) |
| `douyin-hd-downloader` | [下载公开抖音原片](#用-douyin-hd-downloader-下载公开抖音原片) | [技术介绍](docs/douyin-hd-downloader-技术介绍.html) |

**两者的分工**：本页讲**怎么用**（第一条 prompt 怎么写、踩过哪些坑）；
`docs/` 下的技术介绍讲**怎么实现的**（调用链、关键函数、实测钉死的不变量），
给要改代码或做评审的人看。是自包含 HTML，克隆后直接用浏览器打开即可。

其余：[安装](#安装) · [各端兼容性](#各端兼容性) · [目录结构](#目录结构) · [说明](#说明)

## 安装

### 这个仓库是怎么被四端共用的

**只有一份实体文件，在这个 git 仓库里；四端各自的 skills 目录放的都是软链。**

```text
                    ~/.claude/skills/<name> ─┐
                    ~/.cursor/skills/<name> ─┤
                    ~/.codex/skills/<name>  ─┼──▶ ~/Work/claude-skills/skills/<name>
                    ~/.grok/skills/<name>   ─┘         （唯一实体 = git 仓库）
```

这么做的原因：

- **改一处，四端立刻生效** —— 不是复制四份再同步，是同一个 inode。
- **`git push` 即备份**，历史和回滚都在 git 里。
- **四条链是平级的**，不要串联（比如让 cursor 指向 `~/.claude/skills/`）——
  平级时任何一端出问题都不牵连其他端。

> 🔴 **给后续维护者（人或 AI）**：要改 skill 内容，**改仓库里的文件**
> （`~/Work/claude-skills/skills/<name>/`），不要去改 `~/.claude/skills/` 之类的路径 ——
> 那些只是软链，看起来能改，实际改的还是仓库里的同一份，但容易让人误以为各端是独立副本。
> **不要把实体文件放进任何一端的目录再从别处链过去**，那会让某一端变成事实上的真源。

### 首次安装

```bash
git clone https://github.com/kevinchenkai/claude-skills.git ~/Work/claude-skills

for S in gpu-llm-service-ops h3-creative-video wps365-cli douyin-hd-downloader; do
  for D in ~/.claude ~/.codex ~/.grok ~/.cursor; do
    mkdir -p "$D/skills" && ln -sfn ~/Work/claude-skills/skills/$S "$D/skills/$S"
  done
done
```

`ln -sfn` 是幂等的：已经建过的链会被原地覆盖，可以反复跑，也可用于新增 skill 后补链。

### 体检：确认四端读的真是同一份

改完之后想确认没链歪，跑这段（**只读，不改任何东西**）：

```bash
REPO=~/Work/claude-skills/skills
for S in gpu-llm-service-ops h3-creative-video wps365-cli douyin-hd-downloader; do
  for D in claude cursor codex grok; do
    L=~/.$D/skills/$S
    T=$(python3 -c "import os,sys;print(os.path.realpath(sys.argv[1]))" "$L" 2>/dev/null)
    [ "$T" = "$(python3 -c "import os;print(os.path.realpath(os.path.expanduser('$REPO/$S')))")" ] \
      && [ -r "$L/SKILL.md" ] && echo "OK   $D/$S" || echo "BAD  $D/$S"
  done
done
```

用 `realpath` 做**完全解析**而不是只看 `readlink` 的第一跳，是为了确认最终真的落在仓库里。

> ⚠️ 但要知道它**查不出什么**：串联的链（cursor → `~/.claude/skills/` → 仓库）
> 完全解析后同样落在仓库，所以这段脚本会报 OK。它能查出的是**链歪或悬空**，不是拓扑。
> 想确认是不是平级直连，得看第一跳：
>
> ```bash
> for D in claude cursor codex grok; do readlink ~/.$D/skills/wps365-cli; done
> ```
>
> 四行都应直接是 `~/Work/claude-skills/skills/...`，出现别的端的路径就是串联了。

最硬的判据是比 inode——四端的 `SKILL.md` inode 相同，才能证明是同一个实体而不只是路径像：

```bash
for D in claude cursor codex grok; do stat -f '%i' ~/.$D/skills/wps365-cli/SKILL.md; done | sort -u | wc -l
```

输出 `1` 就对了（macOS；Linux 用 `stat -c '%i'`）。

顺带一提，各端目录里可能还有**不属于本仓库**的 skill（别的工具装的、或内置的），
它们与这套软链互不影响；但**指向已删目录的悬空链要清掉**，
否则某些端扫描时会报错或把它算成一个坏 skill。

## 用 `gpu-llm-service-ops` 上手 GPU 服务器

管的是**机器和服务**：conda 环境、vLLM/ComfyUI/ai-toolkit/OneTrainer 的起停、
模型下载与软链、tmux、端口转发、存储选型、多机训练。
（**做视频内容**是另一个 skill,见下一节。）

### 第一条 prompt 怎么写

**说清「哪台机器 + 想干什么」就够**,不用自己先给命令。
主机别名（`train-1` / `train-h20` / `vscode`）直接说，它认得：

```text
用 gpu-llm-service-ops，在 train-1 上看看 ComfyUI 现在什么状态。
```

```text
用 gpu-llm-service-ops，在 vscode 上把 <模型名> 下下来，
挂到 ComfyUI 能读到的地方。
```

```text
用 gpu-llm-service-ops，vLLM 起不来，帮我看日志定位。
```

**要它先给方案再动手**,加一句：

```text
先给我方案，确认之后再执行。
```

> 它会**先跑一轮只读探针**（`nvidia-smi`、`conda info --envs`、`df -h`、
> `tmux ls`、端口占用…）再决定动作 —— **不会上来就改东西**。

### 常见任务对应的说法

| 你想干的 | 就这么说 |
| --- | --- |
| 看服务状态 / 起停 | 「看下 ComfyUI 状态」「重启 ai-toolkit」 |
| 装/修 conda 环境 | 「onetrain 环境坏了，修一下」 |
| 装 ComfyUI 自定义节点 | 「装 <节点名>,把依赖和模型都配好」 |
| 下模型 | 「下 <模型>,放共享库并软链过去」 |
| 机器重装后恢复 | 「机器重装了，把 /nfs 和环境恢复起来」 |
| 本地连远端服务 | 「开个隧道，我本地要访问 8188」 |
| 统计用量 | 「统计最近 7 天的训练任务情况」 |
| 存储选型 | 「checkpoint 放 JuiceFS 还是 NFS?」 |
| 多机训练 | 「KAS 上起个多机训练，NCCL 走 IB」 |

### 🔴 上手前先知道的几条

这几条是踩出来的，**不知道会出事**:

| 规则 | 为什么 |
| --- | --- |
| **别往 `/nfs/envs` 里 pip install** | NFS 写入 ~145 MB/s vs JuiceFS ~950 MB/s,且**跨主机共享** —— 装本地再挪 |
| **共用机器上不碰别人的东西** | 别人的服务不重启不 kill、别人的 tmux 不 kill、别人的目录不写入 |
| **不要用宽泛的 `pkill -f`** | 自匹配会连控制脚本一起杀掉 |
| **GPU 绑定看 `/proc/<pid>/environ`** | **不能看 `nvidia-smi` 显存** —— 空闲服务两张卡都显示 ~0 MiB |
| **ComfyUI 的 `/history` 不是任务数** | 它**重启即清空**;`output/` 文件数是**产物数**,一个工作流出多张，会高估 |
| **存储基准冷读热读分开报** | 平均掉就没意义了 |

### 想直接看细节

| 想知道 | 看 |
| --- | --- |
| 主机/环境/bin 脚本/重装恢复 | [`references/nfs_envs_and_juscent_bin.md`](skills/gpu-llm-service-ops/references/nfs_envs_and_juscent_bin.md) |
| 通用运维命令模板 | [`references/gpu_service_runbook.md`](skills/gpu-llm-service-ops/references/gpu_service_runbook.md) |
| ComfyUI 节点/模型/软链 | [`references/comfyui_node_model_ops.md`](skills/gpu-llm-service-ops/references/comfyui_node_model_ops.md) |
| OneTrainer + noVNC | [`references/onetrainer_runbook.md`](skills/gpu-llm-service-ops/references/onetrainer_runbook.md) |
| 存储 I/O 基准与选型 | [`references/storage_io_bench.md`](skills/gpu-llm-service-ops/references/storage_io_bench.md) |
| KAS 多机 / NCCL over IB | [`references/kas_multinode_ib.md`](skills/gpu-llm-service-ops/references/kas_multinode_ib.md) |

---

## 用 `h3-creative-video` 做 MiniMax-H3 视频

### 先按素材角色选择生成格式

“素材是精确首尾帧，还是一般身份/风格/动作/声音参考”决定 conditioning mode；
“只出方案还是端到端执行”是另一件事，不要混在一起。

| 格式 | 你提供的条件 | skill 的行为 |
| --- | --- | --- |
| **T2VA** | 只有文字，没有首尾帧图片 | 直接把原始 brief 规范化为官方三字段 prompt；不生成、不接入任何图片 |
| **I2VA** | 一张明确的首帧图 + 文字 | 以图片锚定 0 秒画面，只连接 `first_frame` |
| **FL2VA** | 明确的首帧图、尾帧图 + 文字 | 规划两张端点图之间的连续路径，同时连接首尾帧 |
| **L2VA** | 一张明确的尾帧图 + 文字 | 从合理的早期状态收束到尾帧，只连接 `last_frame` |
| **Ref2VA** | 用于身份、场景、风格、动作、剪辑、续写、声音或配乐参考的图像/视频/音频 | 冻结素材顺序和 `<Subject N>` / `<Picture N>` / `<Video N>` / `<Audio N>` 标签，使用 Ref2VA 专用权重、节点和六段式 prompt |

如果只给一张图却没说它是精确首/尾帧还是一般参考，skill 应先确认，不能擅自猜成 I2VA。
任何参考视频、参考音频或混合一般参考素材都应路由到 Ref2VA。
写在 prompt 里的“墙上有一张照片”只是场景内容，不算输入图片。

T2VA、I2VA、FL2VA、L2VA 使用三个核心字段，且顺序固定：

```text
integrated_multimodal_description: ...

overall_soundscape: ...

non_diegetic_music: ...
```

T2VA 直接从第一字段开始；I2VA、FL2VA、L2VA 还需要各自严格匹配的图片对齐首行。

Ref2VA 改用六段式结构，不能套三字段开头：

```text
subject_definitions: ...
summary: ...
retention_analysis: ...
detailed_description: ...
overall_soundscape: ...
non_diegetic_music: ...
```

Ref2VA 当前公开规格支持最多 9 张图、3 段视频、3 段独立音频，混合输入文件最多
12 个；视频和音频各自总时长不超过 15 秒。实际提交前还要按当前 ComfyUI 版本复核。

### 通用提交模板

可以直接复制下面这段，再替换尖括号中的内容：

```text
请使用 $h3-creative-video 处理这个任务。

输入素材：<无素材 / 首帧路径 / 首尾帧路径 / 尾帧路径 / 有序参考素材清单>
素材角色：<精确首尾帧；或身份、场景、风格、动作、剪辑、续写、声音、配乐参考>
内容：<人物或主体、地点、动作、镜头、声音、对白>
时长画幅：<例如约 8 秒，16:9，24fps>
风格：<例如真实旅行纪录片；或二维水彩动画>
硬性要求：<必须出现的内容、禁止项、对白原文、可见文字>

请自动判断 T2VA / I2VA / FL2VA / L2VA / Ref2VA；保留原始 prompt，
按所选模式规范化为 MiniMax-H3 官方三字段或六段式格式并运行 lint。
如解释、时长或本机运行上限会实质改变作品，先列出取舍让我确认。

本次执行范围：<只出方案，不连接 GPU / 确认后端到端生成并验收>
```

下面的 base-mode Demo 1–5 使用 8.00 秒，是因为当前记录的 24fps 运行配置中，192 帧
恰好是 8 秒且满足常用帧网格；Ref2VA Demo 6 使用约 5 秒并要求按实际对齐后时长复核。
其他时长必须根据所选模式和当前 runtime profile 重新计算；不能把 FL2VA 的已知上限
直接套给 T2VA、I2VA、L2VA 或 Ref2VA。

### Demo 1：T2VA，只有一段详细 prompt

适合已经写好完整分镜、但没有任何输入图片的任务。原始中文是 source brief，skill
可以规范化成英文，但对白、歌词和画面内文字必须逐字保留。

<details>
<summary>展开：完整 prompt + 规范化后的三字段输出</summary>

```text
请使用 $h3-creative-video，按 T2VA 处理下面的详细 prompt。

没有首帧、尾帧或参考图片；不要生成关键帧，不要插入空白占位图。
目标为 8 秒、16:9、24fps。

原始 prompt：
生成一段阴雨天的江南古寺旅行短片。没有人物。第一镜低角度拍古树和红灯笼，
摄影机缓慢右移；3.2 秒直接切到潮湿的石刻书法墙并缓慢推进；5.6 秒切到旧铜盆，
一滴水落下形成同心圆波纹。冷灰绿色、低饱和、真实旅行纪录片摄影。
环境声只有微风、竹叶和滴水，不要配乐，不要字幕、Logo 或水印。

先输出模式判断、实质性解释、最终三字段 prompt、计划参数和验收矩阵。
本次只出方案，不连接 GPU。
```

规范化后的 prompt 必须直接这样开头，不能出现 Picture 对齐说明：

```text
integrated_multimodal_description: [Shot 1] A photorealistic travel-documentary view of an ancient Jiangnan temple after rain. The camera trucks slowly to the right beneath an old tree and restrained vermilion lanterns. [Shot 2] At 00:03.200, the camera cuts directly to a wet stone calligraphy wall and pushes in slowly. [Shot 3] At 00:05.600, the camera cuts to an old bronze basin as one water drop creates natural concentric ripples.

overall_soundscape: Soft wind moves through bamboo and leaves, followed by a close natural water-drop impact. No speech or human sound.

non_diegetic_music: N/A
```

</details>

### Demo 2：I2VA，提供首帧

适合从一张已经确认的开场画面向前发展。图片路径必须是真实存在的文件。

<details>
<summary>展开：完整 prompt + I2VA 固定开头</summary>

```text
请使用 $h3-creative-video，按 I2VA 端到端生成。

首帧：/absolute/path/temple-first-frame.png
尾帧：无
目标：8 秒、16:9、24fps。

从首帧中的空旷寺庙回廊开始。祈福布条被微风吹动，摄影机缓慢沿回廊向前跟进；
4.5 秒切到院内湿润的竹林。不要人物，不要现代物件。只有风、布条和远处滴水声，
不要配乐。

先验收首帧和运行配置；确认无歧义后执行低步数探针，探针有效再正式生成。
```

I2VA prompt 的固定开头是：

```text
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.

integrated_multimodal_description: [Shot 1] The video begins from the exact referenced empty temple corridor. Hanging prayer cloth strips move gently in a light breeze as the camera tracks slowly forward. [Shot 2] At 00:04.500, the camera cuts directly to wet bamboo in the courtyard, maintaining the same soft overcast light and restrained documentary style. No people or modern objects appear.

overall_soundscape: A soft breeze moves the hanging cloth strips, with distant water drops.

non_diegetic_music: N/A
```

运行时只连接 `first_frame`，不能把同一张图同时冒充尾帧。

</details>

### Demo 3：FL2VA，提供首帧和尾帧

适合起点和落点都必须被图片严格锚定的任务。首尾图需要先检查主体、构图、光线和
身份是否能形成可行的连续路径。

<details>
<summary>展开：完整 prompt + FL2VA 首尾帧对齐写法</summary>

```text
请使用 $h3-creative-video，按 FL2VA 端到端生成。

首帧：/absolute/path/dancer-start.png
尾帧：/absolute/path/dancer-end.png
目标：8 秒、9:16、24fps。

同一名舞者从首帧的侧身起势开始，连续完成一次克制的转身，衣摆和头发持续运动，
最后自然落到尾帧姿态。人物身份、服装、场地和主光方向保持一致。不要切镜，
不要突然变焦。保留真实脚步和衣料声，配乐为稀疏的低音弦乐。

先检查两张端点图是否相容；如不相容先停止，不要强行提交。
```

若全片只有一个镜头，FL2VA prompt 的固定开头是：

```text
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns with the 8.00-second mark of the target video.

integrated_multimodal_description: [Shot 1] The dancer begins in the exact pose and composition of Picture 1, performs one restrained continuous turn, and progressively converges on the exact pose and composition of Picture 2 at the end.

overall_soundscape: Natural footfalls and subtle fabric movement remain synchronized with the turn.

non_diegetic_music: Sparse low strings at a slow tempo, with no percussion and a restrained ending.
```

如果实际有多个镜头，`Picture 2 (from Shot N)` 中的 `N` 必须等于最后一个镜头号。

</details>

### Demo 4：L2VA，只提供尾帧

适合落点画面不可改变、但起点允许模型从文字构造的任务。该模式本地生产 profile
尚未充分标定，未经验证的画幅和帧数应先探针。

<details>
<summary>展开：完整 prompt + L2VA 固定开头</summary>

```text
请使用 $h3-creative-video，按 L2VA 处理。

首帧：无
尾帧：/absolute/path/tea-final-frame.png
目标：8 秒、16:9、24fps。

开场是一只手把白瓷茶杯轻放在潮湿木桌上，热气缓慢上升；摄影机轻微推进，
动作逐渐收束到尾帧中完全一致的茶杯位置、桌面构图和光线。不要对白，
保留杯底接触木桌的轻响和窗外雨声，不要配乐。

只出规范化 prompt、探针计划和验收标准，不连接 GPU。
```

L2VA prompt 的固定开头是：

```text
How the reference pictures align with the target video — <Picture 1> (from [Shot 1]) aligns with the 8.00-second mark of the target video.

integrated_multimodal_description: [Shot 1] A hand gently lowers a white porcelain teacup onto a damp wooden table as steam rises. The camera pushes in slightly, and the cup position, composition, and lighting progressively converge on the exact referenced final frame at 8.00 seconds.

overall_soundscape: A delicate ceramic contact sound is heard over steady rain outside the window.

non_diegetic_music: N/A
```

L2VA 里的 `<Picture 1>` 指唯一输入的尾帧，不代表首帧。

</details>

### Demo 5：已经写成官方三字段格式

如果你不希望 skill 改写 prompt，要明确要求“只校验、不要优化”：

<details>
<summary>展开：只校验不改写的完整示例</summary>

```text
请使用 $h3-creative-video 处理下面的官方 T2VA prompt。

要求：保留 prompt 原文，不做创意改写；只检查模式、字段顺序、镜头编号、时间戳、
对白标签、时长和运行可行性。lint 通过后先给我结果，本次不要连接 GPU。

integrated_multimodal_description: [Shot 1] A locked-off view of rain falling into an empty stone courtyard. [Shot 2] At 00:04.000, the camera cuts to a close view of water running from a dark tiled eave.

overall_soundscape: Continuous natural rainfall, water striking stone, and soft runoff from the roof tiles. No voices.

non_diegetic_music: N/A
```

这类输入通过 lint 后应保持原文不变。只有用户明确说“优化 prompt”，skill 才能进行
创意重写，同时保留 source prompt 和最终 prompt 的哈希。

</details>

### Demo 6：Ref2VA，组合人物、动作和声音参考

适合参考素材不是精确首尾帧，而是分别控制身份、动作、镜头、声音或源视频关系。
Ref2VA 使用 `minimax_h3_ref2va_*` 权重和 `MiniMaxH3ReferenceToVideo`，不能拿 FL2VA
权重或端点节点代替。

<details>
<summary>展开：完整 prompt + 六段式规范化输出 + lint 命令</summary>

```text
请使用 $h3-creative-video，按 Ref2VA 端到端生成。

参考图片 1：/absolute/path/woman.png —— 提供人物身份、红色风衣和短发
参考视频 1：/absolute/path/walk.mp4 —— 只参考步态和侧向跟拍；不要使用其音轨
参考音频 1：/absolute/path/voice.wav —— 只参考女声声线，不复制原句
目标：约 5 秒、16:9、24fps。

同一名女性穿红色风衣沿雨夜街道快步行走，摄影机侧向跟拍。她转头说：
“我们得在午夜前赶到。” 保留雨声和脚步，不要配乐。

先冻结素材哈希、连接顺序和标签表；检查 Ref2VA 专用权重与节点；低步数探针有效后
再正式生成。按身份、步态/镜头、目标对白和声线分别验收。
```

规范化 prompt 使用六段式，例如：

```text
subject_definitions:
<Subject 1> is the short-haired woman whose identity and red trench coat come from <Picture 1> and whose walking motion comes from <Video 1>.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).

summary:
[reference generation + audio reference] The target video follows <Subject 1> walking through a rainy night street, using <Video 1> for gait and lateral tracking and <Audio 1> only for voice timbre.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - her identity, short hair, red trench coat, and referenced walking motion remain recognizable.
<Audio 1>: reference - only the voice timbre guides the new target dialogue; the source signal and words are not copied.

detailed_description:
The target video uses realistic night-street photography with wet reflections and restrained handheld movement.
[Shot 1] <Subject 1> walks briskly through the rain as the camera tracks laterally, following the gait from <Video 1>. She turns toward camera and, using the timbre referenced from <Audio 1>, says, <d>[Chinese] 我们得在午夜前赶到。</d> Her lips close after the sentence while she continues walking.

overall_soundscape:
Steady rain, wet footfalls, and subdued night-street ambience remain synchronized with the shot.

non_diegetic_music:
N/A
```

提交前用实际标签数量运行：

```bash
python scripts/h3_prompt_lint.py prompt.txt --mode ref2va --duration 5 \
  --pictures 1 --videos 1 --audios 1 --json
```

`--audios` 指 ComfyUI 实际发出的 `<Audio N>` 标签数：启用的参考视频音轨会先编号，
然后才是独立音频。若上例启用 `walk.mp4` 的音轨，独立 `voice.wav` 会变成
`<Audio 2>`，prompt 和 lint 参数都必须同步修改。

</details>

### 控制执行范围与分工

只想讨论创意或检查 prompt，在结尾加：

```text
本次只出方案、prompt 和计划参数，不创建项目，不连接 GPU，不执行生成。
```

希望端到端完成，在结尾加：

```text
确认实质性解释后，端到端执行：环境预检 → 冻结工单 → 准备实际存在的条件输入 →
低步数探针 → 正式生成 → 像素/判据/画面/声音验收 → 交付证据。
```

多人协作时明确责任边界，例如：

```text
Codex 负责创意、prompt、GPU 出片和技术验收；最终创意签收由 Claude 完成。
```

出片方与最终验收方最好分开；做不到时应明确披露 self-acceptance。

### 它会怎么处理

1. **先路由 T2VA / I2VA / FL2VA / L2VA / Ref2VA**，再应用对应 prompt、素材和运行规则。
2. **保留原始输入**，把详细 prose 变成需求矩阵和官方三字段或六段式 prompt；实质性解释先过用户 gate。
3. **检查当前模式的 runtime profile**。例如记录中的 FL2VA 上限不能推导出 T2VA 或 Ref2VA 上限。
4. **新模式/画幅/帧数组合先探针并验像素**；`status=success` 不等于视频有效。
5. **图片模式先验收实际提供的端点图**；T2VA 跳过出图，不制造 placeholder。
6. **Ref2VA 先冻结素材顺序、标签、音轨和权重/节点**，再按每个 reference role 分项验收。
7. **按像素 → 数字判据 → 人眼 → 人耳验收**，并区分创意要求的静止结尾与异常冻结。

### 想直接看规则

| 想知道 | 看 |
| --- | --- |
| 纯 prompt T2VA | [`references/t2va_prompt_mode.md`](skills/h3-creative-video/references/t2va_prompt_mode.md) |
| Ref2VA 路由、标签、六段式 prompt 与 ComfyUI 接线 | [`references/ref2va_prompt_mode.md`](skills/h3-creative-video/references/ref2va_prompt_mode.md) |
| 四种 base 格式的提示词 | [`references/prompt_authoring.md`](skills/h3-creative-video/references/prompt_authoring.md) |
| 官方规范 + 项目偏离 | [`references/official_h3_guide.md`](skills/h3-creative-video/references/official_h3_guide.md) |
| 图片模式的出图工单 / 去 AI 味 | [`references/keyframe_imagegen_order.md`](skills/h3-creative-video/references/keyframe_imagegen_order.md) |
| 判据与标定 | [`references/acceptance_criteria.md`](skills/h3-creative-video/references/acceptance_criteria.md) |
| 提交、监控与证据清单 | [`references/h3_runbook.md`](skills/h3-creative-video/references/h3_runbook.md) |
| 🔴 **哪些路已经走死了** | [`references/known_findings.md`](skills/h3-creative-video/references/known_findings.md) |

> **提实验前先看 `known_findings.md`。** 其中结论都带 conditioning-mode 范围；
> FL2VA 里已经证伪的控制手段，不能自动判定为 T2VA 或 Ref2VA 里也无效。

### 作品与复现案例

🎬 **<https://g.ismayday.mobi/h3/>** —— MiniMax-H3 复现画廊，**15 个案例**
（9 个完全成功 / 6 个部分成功 / 0 个失败或全黑）。

| 分区 | 内容 |
| --- | --- |
| **官方基准案例**（3 条）| 官方仓库的参考实现，用来验证环境是否正常 |
| **社区案例复现**（8 条）| 社区真实提示词在开源版上的表现，**逐条标注哪条要求达成、哪条没达成** |
| **结构化长提示词**（4 条）| 显式分镜结构的长提示词，**双 seed 验一致性** |

每条都附**完整提示词**（含字符数与 SHA256）、**生成参数**
（模式 T2VA/I2VA/FL2VA/L2VA/Ref2VA、分辨率、帧数、时长）、
**逐条评估说明**、以及复杂案例的技术分析（色彩测量、切点检测、运动指标）。

> 🔴 **它的用法是"对照",不是"欣赏"**：
> 想写某类片子之前，先看那一类**已经跑出过什么效果、哪条要求没达成** ——
> 比直接开跑省一轮。
>
> **画廊把没做到的地方也列出来了** —— 这和 `known_findings.md`
> 是同一个原则：**负面结果和正面结果一样值钱，它划定边界。**

---

## 用 `wps365-cli` 操作金山文档

管的是**云文档**：找文件、读正文、导出、新建智能文档、目录治理。
前提是本机装好官方 CLI 并已 `auth login` 过一次。

> **上游项目：<https://github.com/wps365-open/cli>** —— 金山官方出品，
> v0.3.3 起覆盖日历、协作、通讯录、邮件、云文档、多维表格、会议、智能文档、智能表格 9 个业务域；
> 本 skill 只用其中的**云文档 + AirPage（智能文档）**。
>
> - 官方手册：<https://365.kdocs.cn/wiki/l/0lcqi8RexYzQKD>
> - 建应用/配权限前置步骤：[`docs/prerequisites.md`](https://github.com/wps365-open/cli/blob/main/docs/prerequisites.md)
> - 安装：`curl -fsSL https://raw.githubusercontent.com/wps365-open/cli/main/install.sh | bash`
> - 全新环境三步走：`config init` → `auth login --device` → `user me`
>
> 🔴 查端点和必填字段**优先查本机 spec**（`wps365-cli spec status` 看路径），
> 它与本机二进制版本严格对应；官方 wiki 讲概念和流程，不保证与本机版本一致。
> 本机已升级到 **v0.3.4**（2026-09-01）。v0.3.2 加了 `--timeout` / `WPS365_TIMEOUT` /
> `config set timeout`（默认 30s）；v0.3.3 起新增 `airpage` / `airsheet` / `drive doclib`
> 精装命令（`airpage block get` 读块不用再手写 base64；但 `block create` 只收**一段纯文本**，
> 灌 Markdown 仍走 `airpage_put.py`）。
> 但**别拿文件体积估耗时**：实测 176MB 的 otl 抽正文只要 0.5 秒（体积几乎全是内嵌图片），
> 目前没遇到过真撞 30s 的操作，不要一看到大文件就加 `--timeout`。

### 想直接看例子

📖 **[`references/demos.md`](skills/wps365-cli/references/demos.md)** —— 13 个案例，每个都给「你就这么说」的原话 + 背后实际跑的命令 + 真实输出：
找文档（跨盘）、读/导出 md、导出 docx（含表格）、本地 md 灌成智能文档、整理目录、以及出错时怎么排查。

### 第一条 prompt 怎么写

**说清「对哪个文档 / 哪个目录 + 想干什么」就够**，不用自己给命令，也不用先查 file_id：

```text
用 wps365-cli，把「<文档名>」导出成 markdown 放到本地。
```

```text
用 wps365-cli，整理一下 <目录名>。
```

```text
用 wps365-cli，把下面这份内容建成智能文档，放到 <目录名> 下面。
```

> 目录治理类的活，它会**先出递归清单和归位方案，等你确认了才动文件** ——
> 不会上来就搬。想跳过确认就明说「不用确认，直接执行」。

### 常见任务对应的说法

| 你想干的 | 就这么说 |
| --- | --- |
| 找文档 | 「找一下叫 <关键词> 的文档在哪」 |
| 读正文 | 「看一下「<文档名>」讲了什么」 |
| 导出 md / docx | 「把「<文档名>」导出成 markdown / docx」 |
| 新建智能文档 | 「把这份内容建成智能文档放到 <目录>」 |
| 目录治理 | 「整理 <目录名>，先给我方案」 |
| 批量搬家 | 「把 <目录> 里的 pptx 都挪到 附件/ 下」 |
| 补授权 | 「scope 不够，补一下读写权限」 |

### 🔴 上手前先知道的几条

这几条都是实测踩出来的，**不知道会得出错误结论**：

| 规则 | 为什么 |
| --- | --- |
| 🔴 **资源名用单数：`drive file`，不是 `drive files`** | v0.2.0 起复数名失效，但**错命令不报错**——退回打印帮助、**exit 0**，只在 stderr 留一句 `unknown flag`；判成功要看有没有拿到 `code:0`，别信退出码 |
| 🔴 **升级 CLI 后换个新 shell 再验证** | 覆盖二进制后在**同一次 shell 调用**里跑新命令，bash 命令哈希仍指向旧二进制，新命令会全部报 `unknown command` —— 我据此得出过「release notes 名不副实」的错误结论，用绝对路径复核才发现命令都在。先 `hash -r` 或用绝对路径 |
| **`airpage block create` 不吃 Markdown** | v0.3.3 的精装写块命令只收**一段纯文本**：带换行直接报 `400445004`，`**加粗**` 会被原样存成字面字符 —— 灌 Markdown 仍要走 `convert`→`create`（`airpage_put.py`）|
| **批量搬/删前先 `--dry-run`** | 官方全局 flag，只打印请求不发送（Authorization 自动打码），确认 URL 和 file_ids 再真跑 |
| 🔴 **`400000004 请求参数不支持` ≠ 接口没开放** | 多半是参数不全。二进制上传曾被误判为「档位没放开」，实际是 `request_upload` 公网必须**同时**给 `hashes`(md5+sha256 两种) 和 `upload_scene:"normal_upload"`，补齐就通 —— 官方 spec 的 `required` 只列了 `size`，公网实际比 spec 更严 |
| **同一个枚举在不同端点可用值不同** | 上传的 `on_name_conflict` 只认 `rename`/`overwrite`，spec 里的 `fail`/`replace` 会被拒；但建文件夹时 `fail` 是好用的 —— 别把某端点的经验套到另一个 |
| **上传没有精装命令，要手写三步** | `request_upload` → PUT 实体 → `commit_upload`，两个 `api post` 都要 `--token-type delegated`；已封装成 `scripts/drive_upload.py` |
| **`drive list` 列不出共享盘** | 只返回你自己名下的盘；团队盘优先用 `drive doclib list` 取 `items[].drive.id`，按具体文档反查时再从 `search` 或短链 `links/meta` 成对取 `drive_id + file_id` |
| **判鉴权用 `user me`，不是 `auth status`** | access token 只有 2 小时，`auth status` 天天显示 `expired`；但 refresh token 一年有效且会自动续期 —— 照 status 判会天天误报要重新登录 |
| **`search` 是全公司跨盘的** | 实测一次 20 条命中横跨 8 个 drive；`file_id` 必须和它自己的 `drive_id` 成对往下传 |
| **报「文件不存在」先怀疑 drive_id** | 盘搞错时报的是 `400008009 文件不存在`，**看着像文件被删了** |
| **markdown 抽取会静默丢表格** | 拿它核对插入结果会误判成失败，然后重复插入插出重复内容 —— 验内容要用 `blocks` 查询或 `export_to_json` |
| 🔴 **`batch-copy` 从共享盘往外复制静默失败** | 返回 `code:0`+`task_id`，但文件根本不出现；从自己盘内复制则立刻成功 —— 共享盘跨盘复制改用 `scripts/airpage_copy.py` |
| **跨盘同步文档不能只复制 blocks 或用 markdown 中转** | markdown 会丢表格和图片；只复制 blocks 又会留下图片空壳。`airpage_copy.py` 会重传附件、重绑 `sourceKey`、验结构与图片像素，失败清理半成品；批注、历史和分享权限不继承 |
| **`code:0` 不等于内容到位** | 批量操作返回的是异步 task_id；要轮询 + 重扫清单比对，别拿返回码当完成 |
| 🔴 **`-copy` 不等于可删** | 实测两种都不能删：一份比原件多 9 个 block、多 477 字（在副本上继续编辑过），另一份压根没有对应原件、它自己就是正本 —— 删之前必须读 blocks 比正文，体积不同也不代表无关 |
| **「>20MB 进附件/」只管 pptx/pdf/mp3** | `.otl` 内嵌图片天然很大（实测 39 个里 6 个超 20MB，全是正文主文档），按体积一刀切会把正文当附件搬走 |
| **`batch-move` 会重写 mtime** | 搬完修改时间全变成当天且**不可恢复** —— 治理前先把清单存下来 |
| **建 otl 的 `name` 要自带 `.otl`** | 接口按最后一个 `.` 切扩展名，`00.月报` 会被当成扩展名报 400 |
| **官方 `export_to_docx` 是可用的，但要轮询** | 早期以为它"常卡 Building" —— 实际是漏传必填 `version`；且**第一次调用必然返回 `Building` + 空 url**，重发一次才 `Completed`，只发一次会误判成失败 |
| **建档 `rename` 重名会静默变 `(1).otl`** | 仍返回 `code:0` —— 失败重试前先确认上次是不是其实建成功了，否则留下多余副本 |

### 它会怎么处理

1. **先定位再动手**：`search` 拿到 `file_id` + `drive_id` 成对使用，不套用默认盘。
2. **目录治理先出方案**：递归清单 → 归位表 → **等确认** → 建夹 + 搬家 → 回传最终树。
3. **删文件前先问**；空文件夹和已确认的治理方案除外。
4. **验收拿正面证据**：轮询异步任务到位、重扫目录比对文件集合、用 `blocks` 而非 markdown 核对正文。
5. **只动指定目录**；别人共享盘里的原件可读可导出，但不改。

---

## 用 `douyin-hd-downloader` 下载公开抖音原片

管的是**单条公开作品**：解析链接 → 枚举所有视频源 → 探测实际可用性 → **优先下上传原片** → ffprobe 验证。
**只做字节流保存，不转码**。

> 🔴 **`highest` ≠ 原画。** `video.bit_rate[]` 里的最高档只是**最高转码档**；
> 上传原片走的是另一条 `ratio=default` 路径，实测可以比最高转码档大**数倍**。
> 这是整个 skill 存在的理由 —— 把这两个概念当成一回事，就会以为自己下到了原画。

### 第一条 prompt 怎么写

**把链接（或整段分享文案）丢过来就行**，不用自己拆 URL、找 aweme_id：

```text
用 douyin-hd-downloader，把这条下下来：<链接或分享文案>
```

```text
用 douyin-hd-downloader，先看看这条有哪些清晰度可选：<链接>
```

短链、完整 URL、带中文的整段「复制打开抖音…」文案都能直接解析。

### 直接用命令

先 `inspect` 看候选，确认无误再下载：

```bash
skills/douyin-hd-downloader/scripts/run.sh inspect '<链接或分享文案>' --debug
```

```bash
skills/douyin-hd-downloader/scripts/run.sh download '<链接>' --quality original
```

下载默认落到 **`~/Downloads/douyin/<aweme_id>/`**（`--output` 可改），每条作品一个目录：

```text
~/Downloads/douyin/<aweme_id>/
├── <aweme_id>.mp4     # 原始字节流，未转码
├── metadata.json      # 作者、标题、选中源、选择理由、sha256、ffprobe 摘要
├── candidates.json    # 所有候选及探测结果（已脱敏，不含 CDN query/签名）
└── ffprobe.json       # 完整 ffprobe 输出
```

想对比原片和最高转码档到底差多少，用 `compare`（两个都下下来并各自 ffprobe）：

```bash
skills/douyin-hd-downloader/scripts/run.sh compare '<链接>' --debug
```

### `--quality` 怎么选

| 值 | 含义 |
| --- | --- |
| `original`（默认）| `ratio=default` 原片探测；**只有探测有效且实际体积大于最高转码档**才用它，否则回退 |
| `highest` | 只在 `video.bit_rate[]` 的转码档里按分辨率 → 码率 → 实际体积排序 |
| `compatible` | 最高质量的 **H.264** 档，给不吃 HEVC 的老设备/剪辑软件 |
| `1080p` / `720p` / `540p` | 锁定目标分辨率档位 |

另有 `--codec h264|h265` 可与上面叠加。

### 实测：原片和最高转码档差多少

三条公开视频的实测对比（2026-08-22，均为**默认 original 模式**）：

| 作品形态 | 原片 | 回退档 | 倍数 | 原片实测规格 |
| --- | ---: | ---: | ---: | --- |
| 12 档 bit_rate | 15.9 MB | 6.6 MB | **2.4×** | 1080p HEVC 60fps / 10.14 Mbps |
| 0 档 bit_rate | 45.6 MB | 3.0 MB | **15×** | 1440×2560 HEVC / 14.28 Mbps |
| 0 档 bit_rate | 35.5 MB | 6.4 MB | **5.5×** | 1080p H.264 60fps / 16.48 Mbps |

注意后两条：**`bit_rate[]` 为空**时唯一的回退是**带水印的 `playwm` 源**——
体积只有原片的 1/15 到 1/5.5。这正是下面那条护栏存在的原因。

### 🔴 上手前先知道的几条

都是实测踩出来的，**不知道会拿到假原片或误判成被风控**：

| 规则 | 为什么 |
| --- | --- |
| 🔴 **`original` 拿不到时会报错中止，不静默降级** | `bit_rate[]` 为空时唯一回退是**带水印**的 `playwm` 源。与其悄悄给你一个 1/15 体积的水印文件还 exit 0，不如报错。**重跑通常就好**；确实要水印结果就显式 `--quality highest` |
| **水印判定看 URL 里的 `/playwm/`，不信 `has_watermark` 字段** | 实测该字段在水印候选上是 `None` —— 只信字段会漏判 |
| 🔴 **单次失败不代表被风控，重跑即可** | SSR 单次成功率约 4/6，页面壳是**常态抖动**。脚本已自动重试；报「3 次尝试均失败」才是真异常 |
| 🔴 **`verifyCenter` 不是风控标记** | 实测它在 **6/6** 页面上都出现，包括全部解析成功的。曾被误当作 WAF 判据，把排查方向带到 cookie 和代理上 —— 真正的挑战标记是 `waf_js` / `wafchallengeid` / `/waf-jschallenge/` |
| **连接超时要配短 connect 上限** | 到部分 CDN 边缘的路由不稳（单次约 50%），**健康连接 ~0.3s、坏连接固定挂满 10.2s**。connect 上限若设成 10s，一个坏边缘就吃掉整个重试预算 —— 已压到 3.5s |
| **`--browser-fallback` 不是默认开** | 只在 SSR 缺 `bit_rate[]` 阶梯时才需要，它要真实 Chrome。别让每条请求都起浏览器 |
| **验稳定性必须连续跑多次** | 这条链路失败是**间歇性**的，跑一次成功证明不了可用性 —— 首版就是这样带着 ~30% 失败率交付的 |
| 🔴 **走 `scripts/run.sh`，别直接 `python3 douyin_hd.py`** | 系统自带 `python3` 常是 3.9 且不带 `httpx`（实测 macOS `/usr/bin/python3` = 3.9.6），直接跑会 `ModuleNotFoundError`。`run.sh` 负责挑可用解释器（>= 3.10 + httpx），要固定就设 `DOUYIN_PYTHON` |
| **只处理公开单条作品** | 不绕登录/私密/付费/地区限制，不做主页批量，不改造成任意 URL 代理 |

### 它会怎么处理

1. **精确域名白名单**解析输入；短链每次跳转都重验，不接受任意 URL。
2. **枚举全部候选**（`bit_rate[]` 各档 + `play_addr*` + `download_addr` + `ratio=default` 原片）。
3. **逐个发 Range 探测**：只认 200/206 且**内容真是视频**——HTML/JSON 风控页即使 HTTP 200 也判失败。
4. **按实际探测体积决策**，不按标签。瞬时失败（超时/5xx/429）重试，403/404 不重试。
5. **流式落盘**：写 `.part` → 校验 Content-Length → 原子改名；中断清理，不留半截文件。
6. **ffprobe 验证**真实分辨率、codec、fps、码率、时长，写进 `metadata.json`。

安全边界：媒体 URL 只能来自 metadata；每跳强制 HTTPS 且解析结果不得落在私网/回环/保留地址；
控制台与 JSON **不输出** CDN query、签名和 Cookie。Cookie 只从环境变量读，不落盘。

### 想直接看细节

| 想知道 | 看 |
| --- | --- |
| 完整参数、故障排查、集成测试 | [`references/usage.md`](skills/douyin-hd-downloader/references/usage.md) |
| 架构、不变量、provider 设计 | [`references/architecture.md`](skills/douyin-hd-downloader/references/architecture.md) |
| 🔴 实测报告（3 条视频 / 两种形态 / 间歇失败与水印护栏）| [`integration-report.md`](skills/douyin-hd-downloader/references/integration-report.md) |

> **报告里最值钱的是负面结果。** 它记录了完整排查过程，
> **含两个被实测证伪的假设**（「CDN IP 挂了」「触发限流」）——
> 后来者不必重走。和 `known_findings.md` 同一个原则：**负面结果划定边界。**

---

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
确认读的是同一份实体而非各自的副本。最近一次实测见
[安装 · 体检](#安装)——四端 `SKILL.md` 的 inode 相同，写穿测试四端立即可见。

各端目录里还可能有**不属于本仓库**的 skill（内置的、或别的工具装的），
它们与这套软链互不影响。但**指向已删目录的悬空链要清掉**：
实测清理过 27 条指向空目录的残留链，它们不报错，只是白白占着 skill 名字。

## 目录结构

```text
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

其中的主机别名（`train-1`、`train-h20`、`vscode` 等）、NFS 路径和端口约定，
以及 `wps365-cli` 里的 `drive_id` / `folder_id` 与目录编号约定，都来自我自己的环境，
使用前请按实际情况替换 —— 这些 ID 是不透明句柄，脱离我的 OAuth 授权没有任何用处。
仓库内不包含任何凭据、密钥、token 或对外可路由的地址。
