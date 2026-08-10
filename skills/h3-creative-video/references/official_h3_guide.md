# Official MiniMax-H3 Guidance — digest, and where we deviate

**Sources**

- Prompt guide: <https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md>
- Official skills: <https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills>
  (`h3-prompt-writing` is the useful one; the rest are stylized end-to-end workflows)

> The GPU host generally cannot reach GitHub/HuggingFace. **Fetch on the local machine and copy over.**

---

## 1. The four task types

| Mode | Input |
| --- | --- |
| T2VA | Text only |
| I2VA | First frame + text — start from the image, develop forward |
| **FL2VA** | **First + last frame + text — describe the path between them** ← what we use |
| L2VA | Last frame + text — infer an opening, land on the image |

## 2. Prompt structure (official, followed verbatim)

Alignment instruction on **line one**, blank line, then three named fields:

```text
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the
0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of
the target video.

integrated_multimodal_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: ...
```

- `N` = index of the **actual final shot**; `S.SS` = effective duration, **two decimals**
- `integrated_multimodal_description` — visuals, action, shots, speakers, dialogue, **diegetic** sound
- `overall_soundscape` — ambient/action/non-verbal human sound (1–4 sentences); `N/A` only if truly silent
- `non_diegetic_music` — score the characters can't hear (1–3 sentences); `N/A` if none

**FL2VA specifically:** describe the **path** between the frames — not two static descriptions.
Recommended shape: *plausible preceding state → explicit action and transition → gradual
convergence → landing on the last frame.*

## 3. Shots and cuts (official)

- First shot: **no timestamp**. Later shots: strictly increasing `At 00:MM.SSS`, within duration.
- Cut verbs: `the camera cuts to`, `the shot cuts to`, `the shot transitions to`, `changes to`, `switches to`.
- **A cut should introduce new information** — subject, space, state, viewpoint, or time.
  *If only distance or a slight angle changes, prefer camera motion over a cut.*

## 4. Camera motion (official vocabulary)

Three dimensions: **motion type + amplitude + speed**, written as natural English inside the shot,
not stacked as trailing labels.

Motion types include `Zoom In/Out`, `Push In / Pull Out`, `Pan`, `Truck`, `Tilt`, `Pedestal`,
`Arc Shot`, `Tracking Shot`, `Static Shot`, `Shake Slightly/Strongly`, `POV`, `Roll`.
Amplitude `with small/large amplitude`; speed `at slow/fast speed` — omit when medium/normal.

> ⚠️ **Our measurements qualify this** — see §6.2.

---

## 5. Where the official guidance held up

| Official point | Our result |
| --- | --- |
| Three-field structured format | ✅ Adopting it improved output vs the freeform prose we used first |
| Alignment line, `(from Shot N)` for the last frame | ✅ Correct and load-bearing |
| Cut timestamps land where written | ✅ Within a few frames |
| Cuts should carry new information | ✅ Matches our finding that two near-identical shots make the model invent one |
| `non_diegetic_music` is directable | ✅ Instrumentation changes are audible |

---

## 6. 🔴 Where we deliberately deviate

### 6.1 Multi-shot, though the guide prefers a single shot

> Official: *"FL2VA generally favors a single shot … Use multiple shots only when they are
> explicitly specified."*

**We cut anyway when the piece contains two distinct actions.** Reasons, measured:

- One long shot holding two actions makes the model **jump on its own** mid-shot.
- **Mid-shot framing cannot be controlled by wording** (§6.2) — adding an endpoint (a cut) is the
  only lever, and it's cheaper than splitting into separate generations.
- Multi-shot keeps **audio continuous**; separate generations always break at the seam.

**Still honor the official constraint that a cut must carry new information** — that is precisely
why two near-identical shots fail.

> 📌 Read `generally` / `favors` as *"there are exceptions — find them"*, not as a prohibition.

### 6.2 Camera-motion vocabulary alone does not steer the camera

The official table is a valid vocabulary, but in our tests **swapping motion types or amplitude
adverbs produced no seed-consistent difference**. What *did* determine the movement was naming
the **concrete start and end framing**.

**Mechanism:** in FL2VA the mid-shot camera path is interpolation between the two supplied frames.
Endpoints are controllable; the middle is not. Wording cannot enter the interpolation.

### 6.3 Realism cannot be requested in the video prompt

Not contradicted by the guide, but not covered by it: **photorealism is decided in the keyframes.**
The model interpolates between two images; two smooth images cannot yield skin texture in between.

---

## 7. Limits the official docs don't state

Empirical, and expensive to rediscover:

| Limit | Note |
| --- | --- |
| **FL2VA frame ceiling ≈ 277** | Higher counts → **silent NaN**: `success`, decodable, all-black. Plain T2VA tolerates more |
| **NaN is silent** | Must check pixels; a clean decode proves nothing |
| **Tail freeze** | Model performs ~65–87 % of the shot, then holds — drives the endpoint rule |
| Frame grid `n % 17 == 5` | Not in the prompt guide; it's an inference-side constraint |
