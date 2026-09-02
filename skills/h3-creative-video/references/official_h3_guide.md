# Official H3 Provenance and Project Deviations

Read for source audits or prompt/node updates, not ordinary authoring. Maintain executable prompt
conventions in [prompt_authoring.md](prompt_authoring.md) and [ref2va_prompt_mode.md](ref2va_prompt_mode.md);
maintain local runtime observations in [runtime_profiles.md](runtime_profiles.md). Avoid parallel
copies of templates or frame-ceiling tables here.

## Sources inspected on 2026-08-11

- [Video Prompt Writing Guide](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md), Hugging Face revision `9ac0dd7aabc2c651fcf0ace4c00b2bffd9c8c8a6`.
- [Official H3 skills](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills), revision `fa6891ff7cdaaa03fa4497e89ac64ff169219acf`; `h3-prompt-writing/references/base-en.txt` and `ref-en.txt`, plus the official Ref2VA example.
- [ComfyUI H3 node](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_extras/nodes_minimax_h3.py), revision `c2bcbecd82ec5ae66594340b395c24ef0217b238`.
- [ComfyUI R2V workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_minimax_h3_r2v.json), revision `cca1ea5ea4560108ecc2f44dee951f41ea433062`.
- [Comfy-Org ModelScope mirror](https://modelscope.cn/models/Comfy-Org/MiniMax-H3), inspected manifest and placement/quantization guidance; no immutable revision was recorded.

Links using main/master may change. Use the recorded revisions to reproduce the inspection and
recheck after changing the model/node/workflow. Fetch locally if the GPU host cannot reach sources.
Do not label historical observations as a current inventory without verification.

## Official conventions versus project choices

- Follow official base openings, three-field order, shot/timestamp notation, exact dialogue and
  visible-text preservation, and sound-layer separation. T2VA has no Picture-alignment preamble.
- Official FL2VA favors one continuous shot unless multiple shots are explicitly specified. The
  project uses explicit multi-shot FL2VA for competing primary actions or required reframing;
  this is a scoped deviation, not a restriction on T2VA.
- Ref2VA uses six sections and stable subject/picture/video/audio meanings. The recorded ComfyUI
  node can tokenize free-form exact tags without parsing section names; canonical six-section
  authoring is this skill's production convention for lintable roles and acceptance.
- Local frame grids, area caps, NaN ceilings, and paired creative findings are not official prompt
  rules. Runtime evidence needs a mode/model/graph/launch fingerprint; FL2VA findings do not ban
  prompt controls in T2VA or establish Ref2VA behavior.

When updating a convention, check its official source, maintained reference, and linter together.
A schema validator or successful node execution alone does not establish good output.
