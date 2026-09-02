# Known Findings — proven, disproven, unsolved

**Read this before proposing an experiment.** Most of its value is in the *disproven* column:
those are rounds you don't have to spend again.

Evidence tiers: 🟢 paired/two-seed evidence in the recorded runtime profile · 🟡 single sample,
mixed evidence, or a useful heuristic · ⚪ inherited from documentation. A tier is not portability:
record conditioning mode, model, graph, and profile whenever applying a finding elsewhere.

Unless a row explicitly says T2VA, the paired creative findings below came from FL2VA and must not
be transferred to prompt-only generation.

## Contents

1. Proven FL2VA findings, T2VA evidence, Ref2VA boundary, and conditional FL2VA heuristics
2. Disproven FL2VA paths
3. Unsolved problems
4. Invalidated criteria
5. Method rules
6. Causal comparison
7. First levers by mode

---

## 1. 🟢 Proven in the recorded FL2VA profile

| Finding | Consequence |
| --- | --- |
| **Prompts govern motion; keyframes govern form in FL2VA** | Ask first: *does the thing I want exist in the two endpoint frames?* If not, prompt-only repair is the wrong FL2VA lever |
| **Keyframes are the primary lever for base photorealism** | Realism wording in the video prompt did not improve pores/light/depth across two seeds; the video stage can still introduce temporal artifacts |
| **Framing is controllable only at the endpoints** | Name concrete start/end framing; to control the middle, add a cut |
| **Cuts must carry new information** | Two near-identical shots ⇒ the model invents something to fill the cut |
| **The last frame's *composition* sets the ending pose** | A "finished pose" last frame produces a finished-looking ending |
| **One shot, one primary state transition** | Two competing primary actions in one long shot produced a self-inflicted jump; secondary wind/fabric reactions are compatible |
| **Score instrumentation is directable** | Write instrument + tempo + dynamics; confirm by ear |
| **One generation preserves native audio continuity** | Independently generated clips produced audible seams; visual segmentation therefore requires an explicit post-audio plan |
| **Structured three-field format beats prose** | Adopting the official format improved results |

## 1.1 🟢/🟡 T2VA evidence

| Finding | Evidence and consequence |
| --- | --- |
| **Zero endpoint inputs select T2VA in the recorded base graph** | Valid wiring probe; do not insert placeholders |
| **Official T2VA structure works end to end** | Space Captain reproduction matched the requested shots/actions; numeric records live in [runtime_profiles.md](runtime_profiles.md) |
| **T2VA ceiling remains unknown** | Recorded runs exceeded the historical FL2VA ceiling; keep run lengths in the runtime profile and probe new combinations |
| **Text is the primary T2VA visual condition** | No endpoint images exist; FL2VA conclusions about keyframe-dominated realism/camera paths do not apply without a paired T2VA test |

## 1.2 ⚪ Ref2VA evidence boundary

| Finding | Evidence and consequence |
| --- | --- |
| **Ref2VA is a separate checkpoint/conditioning family** | Recorded official/node revisions; never reuse the FL2VA transformer merely because both accept images |
| **Labels depend on connector order and media type** | Recorded node behavior; freeze the connector-to-label manifest before writing or submitting the prompt |
| **Reference cost grows with media size and length** | Recorded node/workflow guidance; `ref_image_size=max`, longer videos, and more assets require an exact-profile probe |
| **Calibration is profile-specific** | Use identifiable current project evidence or probe; do not import T2VA/FL2VA prompt, ceiling, identity, camera, or freeze conclusions |

## 1.3 🟡 Useful but conditional in FL2VA

| Finding | Boundary |
| --- | --- |
| **Avoid an early semantic endpoint in the final action** | Arriving/posing tends to settle early, but endpoint-free words alone do not prevent a hold |
| **The last frame should afford continuation compositionally** | Use an unresolved spatial direction or weight transfer; paired V3 human review still found the subject settling early despite “still turning,” so this is a heuristic, not a guarantee |
| **A shot may perform for only part of its duration, then hold** | A 65–87% range was observed in one profile; do not treat it as a model constant |

## 2. 🔴 Disproven in FL2VA — do not re-run there

| Attempt | Result |
| --- | --- |
| Realism wording in the **video** prompt | Two seeds: pores/light/depth unchanged |
| "Never pull back / never widen", strongest phrasing | Two seeds: frames ~identical to control |
| Swapping camera-move keywords or amplitude adverbs | Two seeds: indistinguishable |
| Rewriting or reinforcing the ending wording to stop the freeze | Multiple paired runs failed; V3.1 increased full-frame activity but human review did not find later subject convergence |
| Adding background motion to stop the freeze | Two seeds failed — the last frame anchors the whole image |
| Single shot instead of two, to fix the ending | **Worse** than two shots |
| `never stops` vs a purely positive clause | **Equivalent** — four clips, two paired seeds, identical freeze onset; effect ~8× below the seed noise floor |
| Exceeding the recorded FL2VA frame ceiling for a longer piece | **Silent NaN**, all black; not a T2VA ceiling result |
| Displacement magnitude as the sole driver of “performs to the end” | Backwards in the tested pair — a small displacement passed, a large one failed |
| Treating `still turning` as a guaranteed endpoint-free fix | Paired V3 human review found the subject settling before the end; the published 2.12s/1.04s figures were global opening plateaus, not tail-freeze proof |

> **On negation:** the failures attributed to "negation backfiring" were cases where a negation was
> the **only** instruction (`NOT smiling`) or was fighting a strong model prior. A negation
> *supported by a positive clause* is fine — that combination produced the best tail result on record.
> **Don't ban negation; ban unsupported negation.**

None of the realism, camera-keyword, ending-wording, background-motion, or final-frame rows above is
a T2VA negative result. Prompt-only mode needs its own paired controls.

## 3. 🔴 Unsolved, with scope

| Problem | Tried | Remaining ideas |
| --- | --- | --- |
| **FL2VA terminal full-frame freeze (~0.7–1.0 s in validated samples)** | Wording (no effect) · last-frame composition (mixed) | Redesign spatial exit affordance · shorten the final interpolation window · split visual generation with planned post-audio · accept only as a labeled prototype |
| **Subject settles while hair/background still moves** | Whole-frame tail averages cannot isolate the subject; paired V3 human review observed early convergence | Calibrated subject ROI/pose metric, or retain as a human-eye gate |
| **Smile decay compresses to a hold** | Explicit rise→peak→decay wording | Time anchors instead of more facial detail · shorten that shot |
| **Cut-time bias** | Samples landed on both sides of the written time | Calibrate only if several comparable runs in one profile show the same offset |

## 4. Criteria that were themselves wrong

Kept as a warning: **the measurement failed more often than the model did.**

| Criterion | Failure | Fix |
| --- | --- | --- |
| Cut detection by counting over-threshold frames | Reported **19 cuts** for one continuous camera move | Detect **isolated narrow spikes** only |
| Tail activity as a pure ratio | Passed a known-bad clip at **0.50** while absolute motion was 1/11 of good | Add an **absolute floor** |
| "Close-up detector" | Reported zero close-ups in footage full of them | **Deleted**, not tuned |
| Thumbnail judgments of "is X present" | Wrong **four times**, both directions | Judge at full resolution |
| Monitor that only matched success | Silent on crash; silence looks like "running" | Match failure signatures too |
| Local pose checks on the last frame | All passed while the overall silhouette read as a finished pose | Judge the **whole composition** |
| Longest low-motion run anywhere in the clip labeled “tail freeze” | V3's 2.12s/1.04s intervals were the intentionally quiet opening, starting at 0s | Measure consecutive stillness at the exact end, or predeclare a final-shot subject ROI; never infer location from duration alone |

## 5. Method rules earned here

1. **Calibrate a criterion in both directions before using it**; delete it if it can't separate.
2. **Any ÷median metric: can the denominator collapse?** Two criteria here were fooled that way.
3. **Establish the seed noise floor** before believing any effect.
4. **Two seeds must agree in direction**; disagreement is noise, not a win.
5. **A number crossing a line ≠ better** — it may be satisfied by content the model invented.
6. **Failure must not look like success** — configs, probes, monitors, and self-checks alike.
7. **Verify through the real execution path.** A check that runs a different path proves nothing.
8. **Record negative results**; they define the boundary.
9. **Whoever generated it shouldn't be the only one to accept it.**
10. **Counterexamples downgrade rules.** “Still turning” did not keep the subject visibly active
    across paired seeds, so an endpoint-free verb is a heuristic, not a proven tail solution.
11. **A temporal label needs a temporal location.** A global longest-run metric cannot establish a
    tail event without reporting its start/end time.
12. **Mode is part of the evidence.** An FL2VA negative result cannot ban a T2VA prompt control.

## Causal comparison

Assert one intended config difference; keep prompts byte-identical except for the declared variable.
Keep conditioning mode, endpoint/reference wiring, model, graph, host and launch flags fixed unless
one is itself the experimental variable. Use the same seeds for control and treatment; establish
the same-prompt seed noise floor first. Attribute an effect only when both paired seeds agree in
direction and exceed that floor. Disagreement means instability/noise, not a win. A creative bundle
can select a preferred candidate but cannot establish a single-factor cause.

## First levers by mode

| Problem | T2VA | Endpoint modes | Ref2VA |
| --- | --- | --- | --- |
| Missing subject/object/style | Concrete prompt facts, timeline, then seed | Endpoint content if it must exist there | Connector/label mapping, subject role, preservation line |
| Identity drift | Simplify, repeat stable visible attributes at cuts, compare seeds | Endpoint consistency plus video review | Remove conflicting refs, concrete subject definition, then compare `match`/`max` |
| Ending silhouette | Final-shot timeline and candidates | Last-frame composition when supplied | Concrete Picture anchor if intended, otherwise final timeline |
| Motion/expression/cut timing | Prompt | Prompt | Action/video role plus detailed timeline |
| Mid-shot framing | Explicit cut/composition | Endpoints/cut; FL2VA camera wording alone was weak | Picture/Video composition role and exact shot citation |
| Wrong voice/content | Audio prompt and exact words | Same | Recount audio labels; distinguish copy/reference and soundtrack/standalone |
| Subject settles but background moves | Eye check or calibrated subject ROI | Same | Same; reference presence proves no motion |

For measurement failures, use [acceptance_diagnostics.md](acceptance_diagnostics.md). Preserve
negative results and counterexamples with their mode/profile rather than expanding a universal ban.
