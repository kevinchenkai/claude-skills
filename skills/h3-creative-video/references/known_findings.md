# Known Findings — proven, disproven, unsolved

**Read this before proposing an experiment.** Most of its value is in the *disproven* column:
those are rounds you don't have to spend again.

Evidence tiers: 🟢 paired/two-seed evidence in the recorded runtime profile · 🟡 single sample,
mixed evidence, or a useful heuristic · ⚪ inherited from documentation. A tier is not portability:
record the model, graph, and profile whenever applying a finding elsewhere.

---

## 1. 🟢 Proven

| Finding | Consequence |
| --- | --- |
| **Prompts govern motion; keyframes govern form** | Ask first: *does the thing I want exist in the two frames?* If not, the prompt is the wrong lever |
| **Keyframes are the primary lever for base photorealism** | Realism wording in the video prompt did not improve pores/light/depth across two seeds; the video stage can still introduce temporal artifacts |
| **Framing is controllable only at the endpoints** | Name concrete start/end framing; to control the middle, add a cut |
| **Cuts must carry new information** | Two near-identical shots ⇒ the model invents something to fill the cut |
| **The last frame's *composition* sets the ending pose** | A "finished pose" last frame produces a finished-looking ending |
| **One shot, one primary state transition** | Two competing primary actions in one long shot produced a self-inflicted jump; secondary wind/fabric reactions are compatible |
| **Score instrumentation is directable** | Write instrument + tempo + dynamics; confirm by ear |
| **One generation preserves native audio continuity** | Independently generated clips produced audible seams; visual segmentation therefore requires an explicit post-audio plan |
| **Structured three-field format beats prose** | Adopting the official format improved results |

## 1.1 🟡 Useful but conditional

| Finding | Boundary |
| --- | --- |
| **Avoid an early semantic endpoint in the final action** | Arriving/posing tends to settle early, but endpoint-free words alone do not prevent a hold |
| **The last frame should afford continuation compositionally** | Use an unresolved spatial direction or weight transfer; paired V3 human review still found the subject settling early despite “still turning,” so this is a heuristic, not a guarantee |
| **A shot may perform for only part of its duration, then hold** | A 65–87% range was observed in one profile; do not treat it as a model constant |

## 2. 🔴 Disproven — do not re-run these

| Attempt | Result |
| --- | --- |
| Realism wording in the **video** prompt | Two seeds: pores/light/depth unchanged |
| "Never pull back / never widen", strongest phrasing | Two seeds: frames ~identical to control |
| Swapping camera-move keywords or amplitude adverbs | Two seeds: indistinguishable |
| Rewriting or reinforcing the ending wording to stop the freeze | Multiple paired runs failed; V3.1 increased full-frame activity but human review did not find later subject convergence |
| Adding background motion to stop the freeze | Two seeds failed — the last frame anchors the whole image |
| Single shot instead of two, to fix the ending | **Worse** than two shots |
| `never stops` vs a purely positive clause | **Equivalent** — four clips, two paired seeds, identical freeze onset; effect ~8× below the seed noise floor |
| Exceeding the frame ceiling for a longer piece | **Silent NaN**, all black |
| Displacement magnitude as the sole driver of “performs to the end” | Backwards in the tested pair — a small displacement passed, a large one failed |
| Treating `still turning` as a guaranteed endpoint-free fix | Paired V3 human review found the subject settling before the end; the published 2.12s/1.04s figures were global opening plateaus, not tail-freeze proof |

> **On negation:** the failures attributed to "negation backfiring" were cases where a negation was
> the **only** instruction (`NOT smiling`) or was fighting a strong model prior. A negation
> *supported by a positive clause* is fine — that combination produced the best tail result on record.
> **Don't ban negation; ban unsupported negation.**

## 3. 🔴 Unsolved

| Problem | Tried | Remaining ideas |
| --- | --- | --- |
| **Terminal full-frame freeze (~0.7–1.0 s in validated samples)** | Wording (no effect) · last-frame composition (mixed) | Redesign spatial exit affordance · shorten the final interpolation window · split visual generation with planned post-audio · accept only as a labeled prototype |
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
