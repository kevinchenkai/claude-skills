# Keyframe Work Order — template and photoreal spec

**The keyframes set the ceiling for identity, form, base lighting, and texture.** The video stage
cannot reliably add what is absent, and it may still introduce temporal morphing, synthetic hair,
or motion artifacts. Reject a structurally weak keyframe before proceeding, then accept the video
as a separate stage.

## Contents

1. Required change between frames
2. Continuation affordance
3. Photoreal specification
4. Expression
5. Cross-frame consistency
6. Work-order skeleton
7. Acceptance

---

## 1. What the two frames must differ in

FL2VA needs a **path**. If both frames look nearly the same, the model has ten seconds to fill and
nothing to perform — **so it invents something** (a close-up that was never requested, an expression
that contradicts the brief).

Give it at least one clear change: framing, orientation, position in depth, or state.

> **Distance alone is not the driver.** A small displacement performed fine while a large one
> failed in one paired comparison. Also evaluate semantic endpoint and the final composition's
> ability to continue beyond the frame — see `prompt_authoring.md` §3.

## 2. 🔴 The last frame must afford continuation

Learned the expensive way: a last frame can be **semantically** mid-action yet **compositionally**
a completed pose — leg lifted, arms open, fabric in a perfect symmetric arc. The model treats
reaching that pose as completing the job, then holds.

> **The last frame should look like a shutter caught the middle of a movement — not like a model
> finished a move and held it for the camera.**

Checking local details (heel off the ground, hips rotated) is **not sufficient** — those can all
pass while the overall silhouette still reads as a finished pose. **Judge the whole composition.**

Useful signals of continuation: weight still transferring, **hips and shoulders out of sync**
(torso still catching up), an unresolved direction or exit vector, asymmetric fabric, a crop that
allows travel beyond the frame, and limbs close to the body rather than extended into a pose.

These are affordances, not guarantees. Paired V3 human review found the subject settling early
despite a semantically unfinished turn. The video must pass the terminal full-frame metric and the
separate intended-subject eye check; whole-frame motion alone is insufficient.

## 3. Photoreal spec ("de-AI")

Five recurring symptoms and their fixes:

| Symptom | Fix |
| --- | --- |
| Poreless, even skin | Name the specifics: **pores, uneven tone, small blemishes, shine, fine facial hair** + *not smoothed, not retouched* |
| Flawless lighting | Demand **uneven** light, one side darker, real shadows under chin/nose — **explicitly forbid rim and hair light** |
| Creamy bokeh background | **Moderate** depth of field; the location must stay identifiable |
| Too-perfect flyaway hair | Ask for **messy**: strands out of place, across the cheek, uneven ends |
| Posed, centered framing | Ask for **candid** framing, slightly imperfect, as if following a real moment |

> 🔴 The lighting and framing items are the least intuitive and the most important. **Making a
> person look good is exactly what makes the image look generated.**

**Banned vocabulary** — cut all of these:
`cinematic` · cinema-camera brand names · `shallow depth of field` · `soft diffused light` ·
`rim light` / `hair light` · `radiant` / `glowing` / `luminous` · `stunning` / `beautiful` /
`ethereal` · `perfect` / `flawless` · `masterpiece` · `8k` / `ultra detailed` / `hyperrealistic`

`hyperrealistic` and `8k` push toward **over-sharpened digital** — also an AI tell.

When the goal is a **caught moment**, also ban pose-inducing words: `dynamic pose`, `elegant pose`,
`graceful`, `dramatic`.

## 4. Expression: positive, and verifiable

Negation alone underspecifies. Write what the face is doing — but only in terms a viewer could
check at a glance.

- ✅ Mouth corners level; cheeks flat, no rounding; lips slightly parted with a visible gap;
  eyes about three-quarters open; inner brows very slightly raised; jaw loose
- ❌ Percentages, named muscles, or anything you couldn't adjudicate from the image

**Guard against the cheap workaround:** "mouth corners not raised" can be satisfied by pressed or
pursed lips — which is a different, wrong expression. Require a **visible lip gap** and **no chin
dimpling**.

## 5. Consistency across frames

State shared attributes with **THE SAME** and enumerate them; category words are not enough.

| Check | Why |
| --- | --- |
| **Every accessory, individually** | A strap changed style between frames once; a necklace appeared on one side only |
| **Every garment, including ones not visible in frame 1** | If frame 1 is waist-up, the model invents the lower half in frame 2 — **name it explicitly or continuity breaks at the cut** |
| Same camera position | Background landmarks at the same angle and side |
| Same person | Compare faces side by side at full size |

> When comparing **size across depth**, don't compare pixels — a subject farther away *should*
> be smaller. Compare against a reference in the scene at that depth (floor tiles, lamps).

## 6. Work-order skeleton

```markdown
## Task            2 images, <W>×<H>, output names, destination
## 🔴 Priority     Photoreal — overrides aesthetics; scene-specific traps
## Banned words    (§3)
## Character       Reference images; hair / clothing / accessories / makeup — itemized
## The two frames  Framing · orientation · state, and 🔴 what must differ
## Prompt 1 / 2    Full text, realism blocks included verbatim
## Acceptance      Photoreal checks + structural checks + 🔴 the one re-do trigger
## Delivery        Images + side-by-side + face crop ≥400px + itemized results
```

## 7. Acceptance

**Judge at full resolution — never from a thumbnail.** "Is X present" has been called wrong
repeatedly at thumbnail scale, in both directions.

**Photoreal:** crop the face to ≥400 px and check pores, real shadow, **no rim-light edge**,
messy strands, readable background.
**Overall test:** shrink to phone size — *does this look like a snapshot, or like an app splash
screen?* Splash screen → re-do.

**Structural:** the differences from §1, the unfinished quality from §2, consistency from §5,
plus hands (five separated fingers), person count, and no text/watermark.

> **State the single re-do trigger explicitly in the order**, so the generator knows which failure
> is fatal and which is cosmetic.
